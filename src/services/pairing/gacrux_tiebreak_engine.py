from __future__ import annotations
import hashlib
import os
import tempfile
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.resources import PROJECT_ROOT
from src.services.constants import AppError
from src.services.pairing import gacrux_runner
from src.services.export_service import ExportService
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.federation_exporters.trf25 import TRF25Exporter
from src.services.pairing.gacrux_tiebreak_map import (
    TiebreakPlan,
    build_team_tiebreak_plan,
    build_tiebreak_plan,
    parse_competitors,
)

logger = logging.getLogger(__name__)

# Mesmo teto do motor de pareamento: evita pendurar a aplicação se o subprocesso
# do Gacrux travar (ver GacruxEngine em gacrux_engine.py).
GACRUX_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class TiebreakJob:
    """Uma chamada ao ``tiebreakchecker``: tudo o que o motor recebe, e o mapa de volta.

    ``trf`` são os bytes exatos do arquivo entregue ao motor; ``args`` a linha
    de comando sem os caminhos; ``cid_to_id`` traduz o número do TRF para
    ``player_id``/``team_id``.
    """

    trf: bytes
    args: tuple[str, ...]
    plan: TiebreakPlan
    cid_to_id: tuple[tuple[int, int], ...]

    @property
    def fingerprint(self) -> str:
        """Hash de TODA entrada do cálculo — a chave do cache (RGS-36).

        A chave antiga era montada à mão e esquecia ``bye_points``, pontos
        iniciais e ajustes: mudar um deles servia a classificação antiga. Pelo
        hash do próprio TRF, qualquer dado que mude o arquivo muda a chave.
        """
        digest = hashlib.sha256(self.trf)
        digest.update(repr((self.args, self.plan, self.cid_to_id)).encode("utf-8"))
        return digest.hexdigest()


class GacruxTiebreakEngine:
    """Calcula os desempates (classificação) com o motor FIDE oficial Gacrux.

    Espelha o fluxo do ``GacruxEngine`` de pareamento: exporta o estado do
    torneio para TRF, roda ``tiebreakchecker.py`` e traduz ``tiebreakResult`` de
    volta para ``player_id`` (individual) ou ``team_id`` (equipes). Lida apenas
    com I/O; o mapeamento de critérios e o parse vivem em ``gacrux_tiebreak_map``.
    """

    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Individual
    # ------------------------------------------------------------------ #
    def compute(
        self,
        tournament_id: int,
        codes: list[Any],
        current_round: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Devolve ``{player_id: {"rank": int, "scores": {código: float}}}``.

        ``codes`` e a sequência de critérios do Albericus (sem ``points``);
        ``current_round`` e o número de rodadas a considerar (por padrão, o
        total de rodadas fechadas). Retorna ``{}`` quando não há rodadas
        fechadas. Levanta ``AppError`` em qualquer falha do motor.
        """
        job = self.prepare(tournament_id, codes, current_round)
        return self.run(job) if job is not None else {}

    def prepare(
        self,
        tournament_id: int,
        codes: list[Any],
        current_round: int | None = None,
    ) -> TiebreakJob | None:
        """Gera o TRF e a linha de comando, sem rodar o motor (None: nada fechado)."""
        rounds = self._closed_rounds(tournament_id, current_round)
        if rounds <= 0:
            return None

        export_service = self._export_service()
        plan = build_tiebreak_plan(codes)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        swiss = str(settings.get("pairing_method") or "swiss") != "round_robin"

        # Ranking 1-based pela MESMA lista do exporter (==> cid do TRF): a ordem
        # inicial do torneio (`seeding_key`, RGS-13), só com quem existia no
        # recorte (RGS-10: o entrante tardio não entra no desempate de antes).
        exporter = TRF16Exporter(export_service)
        all_players = exporter.players(tournament_id, up_to_round=rounds)
        cid_to_id = tuple((index, int(p["id"])) for index, p in enumerate(all_players, start=1))
        # Só as rodadas do cálculo (`-n`): resultado digitado na rodada em
        # aberto não muda o desempate, e portanto não muda a chave.
        trf = exporter.render(tournament_id, up_to_round=rounds)
        trf = self._with_score_records(tournament_id, trf, all_players, rounds)
        return self._job(trf.encode("utf-8"), plan, rounds, swiss, cid_to_id)

    def _with_score_records(
        self,
        tournament_id: int,
        trf: str,
        players: list[dict[str, Any]],
        rounds: int,
    ) -> str:
        """O TRF do desempate com o placar que a classificação conta (RGS-03).

        Sem o 162 o Gacrux DEDUZ o sistema de pontos das células e quebrava com
        PAB de 0 ou 0,5, ajuste do árbitro ou entrante tardio ("Erro
        desconhecido"), derrubando a classificação para o motor próprio. Aqui
        entra a mesma reconciliação do pareamento: 162 (``P = bye_points``), um
        299 por ajuste de rodada do recorte e as rodadas de ausência do
        entrante tardio como ``H``/``F``.

        O PTS do Gacrux continua sendo a soma das rodadas: o 299 só entra na
        pontuação de PAREAMENTO (ACC, patch local em ``gacrux/tiebreak.py``) e o
        Albericus soma o ajuste por cima (TBK-01) — Buchholz e SB medem pontos
        de tabuleiro, não a penalidade.

        Efeito no Buchholz (C.07 §16): o Gacrux avalia a rodada sem jogo pelo
        resultado da célula até a última rodada jogada do jogador (16.3; depois
        dela, como empate). As ausências do entrante tardio estão ANTES das
        rodadas jogadas, então ``Z`` -> ``H``/``F`` muda a pontuação ajustada dele
        — e o Buchholz dos adversários — pelos pontos de entrada, que são parte
        da pontuação oficial dele. Sem o preenchimento o motor mediria esses
        adversários por uma pontuação menor do que a publicada. ``H`` continua
        sendo rodada não jogada voluntária (VUR, cortada primeiro no Cut-1),
        como ``Z``; ``F`` (só quando o deficit exige ponto inteiro) não é VUR.

        O que o arquivo não consegue representar vira ``AppError``: o chamador
        registra e usa o motor próprio, como em qualquer falha do motor.
        """
        from src.services.pairing.gacrux_trf import pairing_score, rebased_score_lines

        rank_by_player = {int(p["id"]): rank for rank, p in enumerate(players, start=1)}
        tournament = self.db.get_tournament(tournament_id) or {}
        score = pairing_score(
            float(tournament.get("bye_points", 1.0) or 0.0),
            self.db.list_point_adjustments(tournament_id),
            rank_by_player,
            int(rounds) + 1,
        )
        starting = {
            rank_by_player[int(p["id"])]: float(p.get("starting_points") or 0.0)
            for p in players
        }
        lines, problems = rebased_score_lines(trf.splitlines(), score, starting)
        if problems:
            for item in problems:
                logger.warning("Desempate Gacrux recusado: %s", item)
            raise AppError(
                "O arquivo TRF não consegue dizer ao motor FIDE (Gacrux) a pontuação "
                "da classificação:\n" + "\n".join(f"- {item}" for item in problems)
            )
        return "".join(f"{line}\r\n" for line in lines)

    # ------------------------------------------------------------------ #
    # Equipes
    # ------------------------------------------------------------------ #
    def compute_teams(
        self,
        tournament_id: int,
        codes: list[Any],
        current_round: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Devolve ``{team_id: {"rank": int, "scores": {código: float}}}``.

        Usa o TRF-25 (que carrega o tipo de torneio por equipes e o sistema de
        pontos), não o TRF-16. ``codes`` e a sequência de critérios de equipe do
        Albericus (match_points, game_points, buchholz, wins).
        """
        job = self.prepare_teams(tournament_id, codes, current_round)
        return self.run(job) if job is not None else {}

    def prepare_teams(
        self,
        tournament_id: int,
        codes: list[Any],
        current_round: int | None = None,
    ) -> TiebreakJob | None:
        """Como :meth:`prepare`, para equipes (TRF-25)."""
        rounds = self._closed_rounds(tournament_id, current_round)
        if rounds <= 0:
            return None

        export_service = self._export_service()
        exporter = TRF25Exporter(export_service)
        plan = build_team_tiebreak_plan(codes)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        swiss = str(settings.get("team_pairing_method") or "swiss") != "round_robin"

        # cid (Team Pairing Number do TRF-25) -> team_id, reusando a MESMA
        # ordenação do exporter (_prepare_teams ordena pelo TPN, EQ-01). Os
        # jogadores são os DO ARQUIVO (`players(up_to_round)`, como em
        # `prepare`): no retrato da R1 a reserva inscrita depois não entra, e
        # o número de cada jogador e o mesmo que o exportador escreve. As
        # equipes não são cortadas: o TPN e gravado e a tardia fica no fim, sem
        # mexer no número das outras (o retrato as descarta em `_team_standings`).
        players = exporter.players(tournament_id, up_to_round=rounds)
        start_rank_by_player = {int(p["id"]): index for index, p in enumerate(players, start=1)}
        teams = self.db.list_teams(tournament_id, active_only=False)
        prepared = exporter._prepare_teams(tournament_id, teams, players, start_rank_by_player)
        cid_to_id = tuple(
            (index, int(item["team_id"])) for index, item in enumerate(prepared, start=1)
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            trf_path = Path(tmpdir) / "input.trf"
            exporter.export(tournament_id, trf_path, up_to_round=rounds)
            trf = trf_path.read_text(encoding="utf-8")
        # E5: a mesma reconciliação do individual. A linha 001 do TRF25 traz os
        # pontos de HOJE e as células só até `rounds`; no retrato da rodada N o
        # Gacrux conferia uma contra a outra e parava ("Erro desconhecido"). Os
        # 299 de EQUIPE saem junto (o exportador não os recorta por rodada) sem
        # perda: o Gacrux só os acumula, não os usa no desempate de equipes
        # (`trf2json.parse_trf_abnormal`), e quem aplica o ajuste e o Albericus.
        trf = self._with_score_records(tournament_id, trf, players, rounds)
        return self._job(trf.encode("utf-8"), plan, rounds, swiss, cid_to_id)

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #
    def run(self, job: TiebreakJob) -> dict[int, dict[str, Any]]:
        """Roda o motor sobre ``job`` e devolve os desempates por id."""
        data = self._run_tiebreakchecker(job)
        by_cid = parse_competitors(data.get("tiebreakResult", {}).get("competitors", []), job.plan)

        id_by_cid = dict(job.cid_to_id)
        out: dict[int, dict[str, Any]] = {}
        for cid, payload in by_cid.items():
            entity_id = id_by_cid.get(cid)
            if entity_id is not None:
                out[entity_id] = payload
        logger.debug("Desempates Gacrux por id: %s", out)
        return out

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _export_service(self) -> ExportService:
        from src.services.pairing_service import PairingService
        return ExportService(self.db, PairingService(self.db))

    @staticmethod
    def _job(
        trf: bytes,
        plan: TiebreakPlan,
        current_round: int,
        swiss: bool,
        cid_to_id: tuple[tuple[int, int], ...],
    ) -> TiebreakJob:
        """Monta a chamada ao motor sobre o TRF já gerado.

        ``swiss`` escolhe as regras: ``-s`` (Suíço) ou ``-p`` (pré-determinado/
        round-robin) — necessário porque os tiebreaks da FIDE diferem entre os
        dois sistemas. Nossos tipos de torneio dizem "Suico" (não "SWISS"),
        então a regra e sempre explicita; sem isso o motor inferiria pelo número
        de jogadores. ``-t`` vai por ULTIMO: como tem ``nargs='*'``, engoliria
        flags seguintes.
        """
        args = (
            "-s" if swiss else "-p",
            "-n", str(current_round),
            "-F", "JSON",
            "-t", *plan.specifiers,
        )
        return TiebreakJob(trf=trf, args=args, plan=plan, cid_to_id=cid_to_id)

    def _closed_rounds(self, tournament_id: int, current_round: int | None) -> int:
        if current_round is not None:
            return int(current_round)
        return sum(
            1
            for round_data in self.db.list_rounds(tournament_id)
            if round_data.get("status") == "closed"
        )

    def _run_tiebreakchecker(self, job: TiebreakJob) -> dict[str, Any]:
        """Roda o ``tiebreakchecker.py`` sobre o TRF de ``job``; devolve o JSON parseado."""
        # RGS-01: o comando mora em gacrux_runner (script ou `--gacrux`).
        script_path = gacrux_runner.script_path("tiebreak")
        if not script_path.exists():
            raise AppError(f"Motor Gacrux (desempate) não encontrado em: {script_path}")
        project_root = PROJECT_ROOT

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.trf"
            output_path = Path(tmpdir) / "output.json"
            input_path.write_bytes(job.trf)

            cmd = gacrux_runner.gacrux_command("tiebreak", [
                "-i", str(input_path),
                "-o", str(output_path),
                "-b", "utf-8",
                *job.args,
            ])

            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(project_root),
                    env=env,
                    timeout=GACRUX_TIMEOUT_SECONDS,
                )
                logger.debug("Gacrux tiebreak STDOUT: %s", result.stdout)
                logger.debug("Gacrux tiebreak STDERR: %s", result.stderr)
            except subprocess.TimeoutExpired as exc:
                raise AppError(
                    f"O motor Gacrux excedeu {GACRUX_TIMEOUT_SECONDS}s ao calcular os "
                    "desempates e foi interrompido."
                ) from exc
            except Exception as exc:  # pragma: no cover - falhas de SO/execucao
                raise AppError(f"Falha ao executar o motor Gacrux (desempate): {exc}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
                raise AppError(f"Erro no cálculo de desempates do Gacrux: {error_msg}")

            if not output_path.exists():
                raise AppError("O motor Gacrux (desempate) não gerou o arquivo de saída esperado.")

            try:
                with open(output_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception as exc:
                raise AppError(f"Falha ao ler o resultado dos desempates do Gacrux: {exc}")

        # code 0 = OK; 1 = OK porem divergente no modo -c (não usamos -c aqui).
        status = data.get("status", {})
        if status.get("code", 0) not in (0, 1):
            errors = status.get("error", [])
            err_text = "; ".join(errors) if errors else "Erro interno do Gacrux"
            raise AppError(f"Gacrux (desempate): {err_text}")
        return data
