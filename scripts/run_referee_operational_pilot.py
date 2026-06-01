from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import shutil
import socket
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from threading import Barrier
from time import perf_counter
from typing import Any, Callable, Iterator
from unittest import mock
from urllib.parse import parse_qs, urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.database import Database
from src.services.export_service import ExportService
from src.services.pairing_service import PairingService
from src.services.qr_result_service import QRResultService
from src.services.rating_service import OfficialRatingService
from src.services.tournament_service import TournamentService

DEFAULT_MARKDOWN_PATH = ROOT / "docs" / "PILOTO_OPERACIONAL_BASELINE.md"
DEFAULT_JSON_PATH = ROOT / "docs" / "PILOTO_OPERACIONAL_BASELINE.json"


@dataclass
class Measurement:
    operation: str
    elapsed_ms: float
    limit_ms: float
    details: str = ""

    @property
    def status(self) -> str:
        return "OK" if self.elapsed_ms <= self.limit_ms else "REVISAR"


@dataclass
class Scenario:
    players: int
    boards: int
    measurements: list[Measurement]

    @property
    def status(self) -> str:
        return "OK" if all(item.status == "OK" for item in self.measurements) else "REVISAR"


def timed(operation: str, limit_ms: float, action: Callable[[], Any]) -> tuple[Any, Measurement]:
    started_at = perf_counter()
    result = action()
    elapsed_ms = (perf_counter() - started_at) * 1000
    return result, Measurement(operation=operation, elapsed_ms=elapsed_ms, limit_ms=limit_ms)


def seed_players(db: Database, tournament_id: int, players_count: int) -> None:
    for index in range(players_count):
        db.create_player(
            tournament_id,
            name=f"Jogador {index + 1:04d}",
            rating=2400 - index % 1400,
            club=f"Clube {index % 24 + 1:02d}",
            category="ABS",
            fide_id=str(1000000 + index),
            national_rating=2300 - index % 1300,
            international_rating=2200 - index % 1200,
        )


def pdf_pages(path: Path) -> int:
    return len(PdfReader(path).pages)


def restore_in_second_installation(
    source_backup: Path,
    temp_dir: Path,
    tournament_id: int,
    expected_round_id: int,
    expected_boards: int,
) -> str:
    second_root = temp_dir / "second_installation"
    second_backup_dir = second_root / "backups"
    second_db = Database(second_root / "pilot_restored.db", backup_dir=second_backup_dir)
    second_backup_dir.mkdir(parents=True, exist_ok=True)
    transferred_backup = second_backup_dir / source_backup.name
    shutil.copy2(source_backup, transferred_backup)
    second_db.restore_backup(transferred_backup)
    tournament = second_db.get_tournament(tournament_id)
    rounds = second_db.list_rounds(tournament_id)
    pairings = second_db.get_pairings_for_round(expected_round_id)
    if not tournament or len(rounds) != 1 or len(pairings) != expected_boards:
        raise RuntimeError("Backup restaurado nao reproduziu torneio, rodada e mesas esperados.")
    return f"{len(rounds)} rodada; {len(pairings)} mesas validadas"


@contextmanager
def blocked_network() -> Iterator[None]:
    def deny_network(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("Rede bloqueada pelo piloto offline.")

    with (
        mock.patch("socket.create_connection", side_effect=deny_network),
        mock.patch.object(socket.socket, "connect", deny_network),
        mock.patch("urllib.request.urlopen", side_effect=deny_network),
        mock.patch("src.services.export_service.urlopen", side_effect=deny_network),
        mock.patch("src.services.sync_service.urlopen", side_effect=deny_network),
    ):
        yield


def verify_offline_local_flow(temp_dir: Path) -> str:
    offline_root = temp_dir / "offline_installation"
    db = Database(offline_root / "offline.db", backup_dir=offline_root / "backups")
    tournament_id = TournamentService(db).create_tournament(
        {
            "name": "Piloto continuidade offline",
            "location": "Instalacao isolada",
            "rounds_count": "3",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    pairing_service = PairingService(db)
    export_service = ExportService(db, pairing_service)
    seed_players(db, tournament_id, 8)
    round_data = pairing_service.generate_next_round(tournament_id)
    round_id = int(round_data["id"])
    db.backup("before_offline")

    with blocked_network():
        dashboard = pairing_service.arbitration_dashboard(tournament_id, pending_limit=50)
        initial_list_path = offline_root / "lista_chamada.pdf"
        scoresheets_path = offline_root / "sumulas.pdf"
        crosstable_path = offline_root / "tabela_cruzada.html"
        export_service.export_initial_player_list(tournament_id, initial_list_path)
        export_service.export_scoresheets(round_id, scoresheets_path)
        pairings = [
            pairing
            for pairing in db.get_pairings_for_round(round_id)
            if not pairing.get("is_bye")
        ]
        for pairing in pairings:
            pairing_service.update_result(tournament_id, int(pairing["id"]), "1-0")
        pairing_service.close_round(tournament_id, round_id)
        standings = pairing_service.standings(tournament_id)
        export_service.export_crosstable(tournament_id, crosstable_path)
        final_backup = db.backup("offline_final")

    if dashboard["metrics"]["pending_results"] != 4:
        raise RuntimeError("Painel offline nao exibiu as quatro mesas pendentes esperadas.")
    if len(standings) != 8:
        raise RuntimeError("Classificacao offline nao preservou os oito jogadores esperados.")
    if not all(
        path.exists()
        for path in (initial_list_path, scoresheets_path, crosstable_path, final_backup)
    ):
        raise RuntimeError("Fluxo offline nao gerou todas as exportacoes e backup esperados.")
    return "painel, 4 resultados, fechamento, classificacao, exportacoes e backup validados"


def simulate_simultaneous_qr_submissions(temp_dir: Path, submissions_count: int = 20) -> str:
    qr_root = temp_dir / "qr_installation"
    db = Database(qr_root / "qr.db", backup_dir=qr_root / "backups")
    tournament_id = TournamentService(db).create_tournament(
        {
            "name": "Piloto envios QR simultaneos",
            "location": "Rede local simulada",
            "rounds_count": "3",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    pairing_service = PairingService(db)
    qr_service = QRResultService(db, pairing_service)
    seed_players(db, tournament_id, submissions_count * 2)
    round_data = pairing_service.generate_next_round(tournament_id)
    round_id = int(round_data["id"])
    pairings = db.get_pairings_for_round(round_id)[:submissions_count]
    urls = qr_service.result_urls_for_pairings(
        tournament_id,
        [{**pairing, "tournament_id": tournament_id} for pairing in pairings],
    )
    tokens = [
        parse_qs(urlparse(urls[int(pairing["id"])]).query)["token"][0]
        for pairing in pairings
    ]
    start_barrier = Barrier(submissions_count)

    def submit(index_and_token: tuple[int, str]) -> dict[str, Any]:
        index, token = index_and_token
        start_barrier.wait()
        return qr_service.submit_result(token, "1-0", submitter=f"Mesa {index + 1}")

    with ThreadPoolExecutor(max_workers=submissions_count) as executor:
        submissions = list(executor.map(submit, enumerate(tokens)))

    pending = qr_service.pending_submissions(tournament_id)
    issues = pairing_service.arbitration_issues(tournament_id)
    if len(pending) != submissions_count or issues["metrics"]["qr_pending"] != submissions_count:
        raise RuntimeError("Fila QR nao exibiu todas as submissoes simultaneas esperadas.")

    for submission in submissions:
        qr_service.approve_submission(int(submission["id"]), reviewer="Arbitro piloto")

    approved = db.list_result_submissions(tournament_id=tournament_id, status="approved")
    pairings_after_review = db.get_pairings_for_round(round_id)
    approved_results = sum(1 for pairing in pairings_after_review if pairing.get("result") == "1-0")
    if len(approved) != submissions_count or approved_results != submissions_count:
        raise RuntimeError("Aprovacao QR nao aplicou todos os resultados esperados.")
    if qr_service.pending_submissions(tournament_id):
        raise RuntimeError("Fila QR permaneceu com submissoes pendentes depois da aprovacao.")
    return f"{submissions_count} envios concorrentes recebidos e aprovados"


def simulate_last_minute_registration(temp_dir: Path, players_count: int) -> tuple[str, float]:
    late_root = temp_dir / f"late_registration_{players_count}"
    db = Database(late_root / "late.db", backup_dir=late_root / "backups")
    tournament_id = TournamentService(db).create_tournament(
        {
            "name": f"Piloto inscricao tardia {players_count}",
            "location": "Secretaria simulada",
            "rounds_count": "3",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    settings = db.get_tournament_settings(tournament_id) or {}
    settings["late_entry_points"] = 0.5
    db.save_tournament_settings(tournament_id, settings)
    pairing_service = PairingService(db)
    seed_players(db, tournament_id, players_count)
    first_round = pairing_service.generate_next_round(tournament_id)
    round_id = int(first_round["id"])
    historical_pairings = db.get_pairings_for_round(round_id)
    for pairing in historical_pairings:
        if not pairing.get("is_bye"):
            pairing_service.update_result(tournament_id, int(pairing["id"]), "1-0")
    pairing_service.close_round(tournament_id, round_id)

    started_at = perf_counter()
    late_player_id = db.create_player(
        tournament_id,
        name="Inscrito de ultima hora",
        rating=1500,
        club="Clube visitante",
        category="ABS",
    )
    refreshed_players = db.list_players(tournament_id, active_only=False)
    standings = pairing_service.standings(tournament_id)
    preview = pairing_service.preview_next_round(tournament_id)
    elapsed_ms = (perf_counter() - started_at) * 1000

    late_player = db.get_player(late_player_id) or {}
    late_standing = next(
        (item for item in standings if int(item["player_id"]) == late_player_id),
        None,
    )
    scheduled_player_ids = {
        int(player_id)
        for pairing in preview["pairings"]
        for player_id in (pairing.get("white_player_id"), pairing.get("black_player_id"))
        if player_id
    }
    historical_player_ids = {
        int(player_id)
        for pairing in db.get_pairings_for_round(round_id)
        for player_id in (pairing.get("white_player_id"), pairing.get("black_player_id"))
        if player_id
    }
    if len(refreshed_players) != players_count + 1:
        raise RuntimeError("Inscricao tardia nao apareceu na lista atualizada.")
    if float(late_player.get("starting_points") or 0) != 0.5:
        raise RuntimeError("Inscricao tardia nao recebeu a pontuacao configurada.")
    if not late_standing or float(late_standing.get("points") or 0) != 0.5:
        raise RuntimeError("Classificacao nao incorporou a pontuacao da inscricao tardia.")
    if late_player_id not in scheduled_player_ids or late_player_id in historical_player_ids:
        raise RuntimeError("Inscricao tardia nao entrou somente na proxima rodada.")
    return (
        f"{players_count + 1} inscritos; 0,5 ponto; historico preservado; jogador presente na previa seguinte",
        elapsed_ms,
    )


def simulate_official_rating_correction_before_round_one(
    temp_dir: Path,
    players_count: int,
) -> list[Measurement]:
    rating_root = temp_dir / f"official_rating_{players_count}"
    db = Database(rating_root / "rating.db", backup_dir=rating_root / "backups")
    tournament_id = TournamentService(db).create_tournament(
        {
            "name": f"Piloto conferencia oficial {players_count}",
            "location": "Secretaria simulada",
            "rounds_count": "3",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    seed_players(db, tournament_id, players_count)
    rating_service = OfficialRatingService(db)
    changed_count = min(700, players_count)
    unmatched_count = players_count - changed_count
    official_csv = rating_root / "fide_oficial.csv"
    official_csv.write_text(
        "name,fide,title,fide_rating,federation\n"
        + "".join(
            f"Jogador Oficial {index + 1:04d},{1000000 + index},FM,{2500 - index % 900},BRA\n"
            for index in range(changed_count)
        ),
        encoding="utf-8",
    )
    first_player_before = db.get_player(1) or {}
    measurements: list[Measurement] = []

    import_result, measurement = timed(
        "Importar base oficial FIDE local",
        5_000,
        lambda: rating_service.import_official_csv(official_csv, "FIDE", "2026-06"),
    )
    measurement.details = f"{import_result['imported']} registros oficiais importados"
    measurements.append(measurement)

    preview, measurement = timed(
        "Comparar ratings oficiais antes da rodada 1",
        2_000,
        lambda: rating_service.preview_tournament_player_updates(tournament_id),
    )
    measurement.details = (
        f"{preview['changed']} alteracoes; {preview['unmatched_count']} sem correspondencia; sem persistir"
    )
    measurements.append(measurement)

    first_player_after_preview = db.get_player(1) or {}
    changed_player_ids = [
        int(row["player_id"])
        for row in preview["rows"]
        if row["status"] == "changed"
    ]
    apply_result, measurement = timed(
        "Confirmar correcoes oficiais selecionadas",
        10_000,
        lambda: rating_service.apply_tournament_player_updates(tournament_id, changed_player_ids),
    )
    measurement.details = f"{apply_result['updated']} alteracoes aplicadas seletivamente"
    measurements.append(measurement)

    first_player_after_apply = db.get_player(1) or {}
    if import_result["imported"] != changed_count:
        raise RuntimeError("Importacao oficial nao carregou todos os registros esperados.")
    if preview["total"] != players_count or preview["changed"] != changed_count:
        raise RuntimeError("Comparacao oficial nao encontrou todas as divergencias esperadas.")
    if preview["unmatched_count"] != unmatched_count:
        raise RuntimeError("Comparacao oficial nao separou os inscritos sem correspondencia.")
    if first_player_after_preview != first_player_before:
        raise RuntimeError("Comparacao oficial persistiu dados antes da confirmacao.")
    if apply_result["updated"] != changed_count:
        raise RuntimeError("Confirmacao oficial nao aplicou todas as divergencias selecionadas.")
    if first_player_after_apply.get("name") == first_player_before.get("name"):
        raise RuntimeError("Confirmacao oficial nao atualizou o inscrito selecionado.")
    if db.list_rounds(tournament_id):
        raise RuntimeError("Conferencia oficial gerou rodada antes da aprovacao do arbitro.")
    return measurements


def simulate_locate_and_submit_table_result(temp_dir: Path, players_count: int) -> tuple[str, float]:
    panel_root = temp_dir / f"panel_table_search_{players_count}"
    db = Database(panel_root / "panel.db", backup_dir=panel_root / "backups")
    tournament_id = TournamentService(db).create_tournament(
        {
            "name": f"Piloto busca de mesa {players_count}",
            "location": "Painel arbitral simulado",
            "rounds_count": "3",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    pairing_service = PairingService(db)
    seed_players(db, tournament_id, players_count)
    pairing_service.generate_next_round(tournament_id)
    target_board = max(1, players_count // 2)
    started_at = perf_counter()
    dashboard = pairing_service.arbitration_dashboard(
        tournament_id,
        pending_limit=50,
        pending_query=str(target_board),
    )
    if len(dashboard["pending_items"]) != 1:
        raise RuntimeError("Busca no painel nao localizou exatamente a mesa esperada.")
    target = dashboard["pending_items"][0]
    if int(target["board"]) != target_board:
        raise RuntimeError("Busca no painel retornou outra mesa.")
    pairing_service.update_result(tournament_id, int(target["pairing_id"]), "1-0")
    refreshed = pairing_service.arbitration_dashboard(
        tournament_id,
        pending_limit=50,
        pending_query=str(target_board),
    )
    if refreshed["pending_items"]:
        raise RuntimeError("Mesa continuou pendente depois do lancamento inline.")
    expected_pending = players_count // 2 - 1
    if int(refreshed["metrics"]["pending_results"]) != expected_pending:
        raise RuntimeError("Painel nao atualizou a quantidade de mesas pendentes.")
    elapsed_ms = (perf_counter() - started_at) * 1000
    return (
        f"mesa {target_board} localizada fora do recorte inline, lancada e removida das pendencias",
        elapsed_ms,
    )


def run_scenario(players_count: int) -> Scenario:
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db = Database(temp_dir / "pilot.db", backup_dir=temp_dir / "backups")
        tournament_id = TournamentService(db).create_tournament(
            {
                "name": f"Piloto operacional {players_count}",
                "location": "Simulacao local",
                "rounds_count": "10",
                "time_control": "15+10",
                "bye_points": "1",
            }
        )
        pairing_service = PairingService(db)
        export_service = ExportService(db, pairing_service)
        measurements: list[Measurement] = []

        _, measurement = timed(
            "Cadastrar inscritos",
            10_000,
            lambda: seed_players(db, tournament_id, players_count),
        )
        measurements.append(measurement)

        preview, measurement = timed(
            "Pre-visualizar primeira rodada",
            1_000,
            lambda: pairing_service.preview_next_round(tournament_id),
        )
        measurement.details = f"{len(preview['pairings'])} emparceiramentos planejados"
        measurements.append(measurement)

        round_data, measurement = timed(
            "Gerar primeira rodada",
            2_000,
            lambda: pairing_service.generate_next_round(tournament_id),
        )
        round_id = int(round_data["id"])
        measurements.append(measurement)

        dashboard, measurement = timed(
            "Carregar painel do arbitro",
            500,
            lambda: pairing_service.arbitration_dashboard(tournament_id, pending_limit=50),
        )
        measurement.details = (
            f"{dashboard['metrics']['pending_results']} pendentes; "
            f"{len(dashboard['pending_items'])} exibidos inline"
        )
        measurements.append(measurement)

        initial_list_path = temp_dir / "lista_chamada.pdf"
        _, measurement = timed(
            "Exportar lista de chamada PDF",
            5_000,
            lambda: export_service.export_initial_player_list(tournament_id, initial_list_path),
        )
        measurement.details = f"{pdf_pages(initial_list_path)} paginas"
        measurements.append(measurement)

        scoresheets_path = temp_dir / "sumulas.pdf"
        _, measurement = timed(
            "Exportar sumulas PDF",
            5_000,
            lambda: export_service.export_scoresheets(round_id, scoresheets_path),
        )
        measurement.details = f"{pdf_pages(scoresheets_path)} paginas"
        measurements.append(measurement)

        wall_path = temp_dir / "mural.pdf"
        _, measurement = timed(
            "Exportar mural PDF com QR",
            30_000,
            lambda: export_service.export_pairings(round_id, wall_path),
        )
        measurement.details = f"{pdf_pages(wall_path)} paginas"
        measurements.append(measurement)

        pairings = [
            pairing
            for pairing in db.get_pairings_for_round(round_id)
            if not pairing.get("is_bye")
        ]
        launch_durations = []
        for pairing in pairings[:20]:
            started_at = perf_counter()
            pairing_service.update_result(tournament_id, int(pairing["id"]), "1-0")
            pairing_service.arbitration_dashboard(tournament_id, pending_limit=50)
            launch_durations.append((perf_counter() - started_at) * 1000)
        launch_average_ms = mean(launch_durations) if launch_durations else 0.0
        measurements.append(
            Measurement(
                operation="Lancar resultado e recarregar painel",
                elapsed_ms=launch_average_ms,
                limit_ms=250,
                details=f"media de {len(launch_durations)} lancamentos",
            )
        )

        for pairing in pairings[20:]:
            pairing_service.update_result(tournament_id, int(pairing["id"]), "1-0")

        _, measurement = timed(
            "Fechar primeira rodada",
            5_000,
            lambda: pairing_service.close_round(tournament_id, round_id),
        )
        measurements.append(measurement)

        crosstable, measurement = timed(
            "Calcular tabela cruzada",
            2_000,
            lambda: pairing_service.crosstable(tournament_id),
        )
        measurement.details = f"{len(crosstable['rows'])} linhas"
        measurements.append(measurement)

        crosstable_path = temp_dir / "tabela_cruzada.html"
        _, measurement = timed(
            "Exportar tabela cruzada HTML",
            2_000,
            lambda: export_service.export_crosstable(tournament_id, crosstable_path),
        )
        measurement.details = f"{crosstable_path.stat().st_size} bytes"
        measurements.append(measurement)

        backup_path, measurement = timed(
            "Criar backup final",
            5_000,
            lambda: db.backup("pilot_transfer"),
        )
        measurement.details = f"{backup_path.stat().st_size} bytes"
        measurements.append(measurement)

        restore_details, measurement = timed(
            "Restaurar backup em segunda instalacao",
            5_000,
            lambda: restore_in_second_installation(
                backup_path,
                temp_dir,
                tournament_id,
                round_id,
                len(pairings) + (1 if players_count % 2 else 0),
            ),
        )
        measurement.details = restore_details
        measurements.append(measurement)

        offline_details, measurement = timed(
            "Validar continuidade offline",
            5_000,
            lambda: verify_offline_local_flow(temp_dir),
        )
        measurement.details = offline_details
        measurements.append(measurement)

        qr_details, measurement = timed(
            "Simular envios QR simultaneos e aprovar",
            5_000,
            lambda: simulate_simultaneous_qr_submissions(temp_dir),
        )
        measurement.details = qr_details
        measurements.append(measurement)

        late_details, late_elapsed_ms = simulate_last_minute_registration(temp_dir, players_count)
        measurements.append(
            Measurement(
                operation="Cadastrar inscricao de ultima hora e atualizar previa",
                elapsed_ms=late_elapsed_ms,
                limit_ms=2_000,
                details=late_details,
            )
        )

        measurements.extend(
            simulate_official_rating_correction_before_round_one(temp_dir, players_count)
        )

        panel_details, panel_elapsed_ms = simulate_locate_and_submit_table_result(temp_dir, players_count)
        measurements.append(
            Measurement(
                operation="Localizar mesa e lancar resultado pelo painel",
                elapsed_ms=panel_elapsed_ms,
                limit_ms=1_000,
                details=panel_details,
            )
        )

        return Scenario(
            players=players_count,
            boards=len(pairings),
            measurements=measurements,
        )


def markdown_report(scenarios: list[Scenario], generated_at: str) -> str:
    lines = [
        "# Piloto Operacional Simulado",
        "",
        f"Gerado em: {generated_at}",
        "",
        "Este relatorio executa o fluxo critico do arbitro em banco temporario.",
        "Ele detecta regressoes locais de desempenho, mas nao substitui o teste",
        "presencial com operadores, impressora e rede do evento.",
        "",
        "## Resultado Automatizado",
        "",
    ]
    for scenario in scenarios:
        lines.extend(
            [
                f"### Cenario com {scenario.players} jogadores",
                "",
                f"Status geral: **{scenario.status}**",
                "",
                f"Mesas validas na primeira rodada: {scenario.boards}",
                "",
                "| Operacao | Tempo | Limite | Status | Detalhes |",
                "|---|---:|---:|---|---|",
            ]
        )
        for item in scenario.measurements:
            lines.append(
                f"| {item.operation} | {item.elapsed_ms:.4f} ms | "
                f"{item.limit_ms:.0f} ms | {item.status} | {item.details} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Validacao Presencial Pendente",
            "",
            "Execute ao menos um ensaio com arbitro e auxiliar usando o",
            "[manual operacional](Manual_Operacional_Arbitragem.pdf).",
            "",
            "- [x] Cronometrar inscricao de ultima hora (automatizado).",
            "- [ ] Repetir inscricao de ultima hora com operador no computador do evento.",
            "- [x] Cronometrar correcao de rating oficial antes da rodada 1 (automatizado).",
            "- [ ] Repetir correcao de rating oficial com operador antes do evento.",
            "- [ ] Confirmar legibilidade do mural impresso a distancia.",
            "- [ ] Testar impressao de sumulas e cartoes na impressora do evento.",
            "- [x] Medir tempo para localizar e lancar resultado de uma mesa (automatizado).",
            "- [ ] Repetir localizacao e lancamento de mesa com arbitro no evento.",
            "- [x] Simular envio QR simultaneo e aprovacao pelo arbitro (automatizado).",
            "- [ ] Repetir envio QR simultaneo com celulares na rede local do evento.",
            "- [x] Desligar a rede e confirmar continuidade local (automatizado).",
            "- [ ] Repetir teste offline em computador fisico do evento.",
            "- [x] Restaurar um backup em segunda instalacao temporaria (automatizado).",
            "- [ ] Repetir restauracao em segundo computador fisico do evento.",
            "- [ ] Registrar incidentes, cliques desnecessarios e trocas de tela.",
            "",
            "## Criterio para Proxima Iteracao",
            "",
            "Priorizar somente gargalos observados no piloto presencial ou operacoes",
            "automatizadas marcadas como `REVISAR`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(scenarios: list[Scenario], markdown_path: Path, json_path: Path) -> None:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown_report(scenarios, generated_at), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "scenarios": [
                    {
                        **asdict(scenario),
                        "status": scenario.status,
                        "measurements": [
                            {**asdict(item), "status": item.status}
                            for item in scenario.measurements
                        ],
                    }
                    for scenario in scenarios
                ],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa o piloto operacional simulado do painel do arbitro.")
    parser.add_argument("--players", nargs="+", type=int, default=[121, 801])
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--strict", action="store_true", help="Retorna erro quando alguma medicao exceder o limite.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = [run_scenario(players_count) for players_count in args.players]
    write_reports(scenarios, args.markdown, args.json)
    for scenario in scenarios:
        print(f"{scenario.players} jogadores: {scenario.status}")
    print(args.markdown.resolve())
    if args.strict and any(scenario.status != "OK" for scenario in scenarios):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
