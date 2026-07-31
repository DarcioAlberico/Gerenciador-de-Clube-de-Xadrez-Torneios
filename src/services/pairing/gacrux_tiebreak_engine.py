from __future__ import annotations
import os
import sys
import tempfile
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from src.services.constants import AppError, player_pairing_name
from src.services.export_service import ExportService
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.federation_exporters.trf25 import TRF25Exporter
from src.services.pairing.gacrux_tiebreak_map import (
    build_team_tiebreak_plan,
    build_tiebreak_plan,
    parse_competitors,
)

logger = logging.getLogger(__name__)

# Mesmo teto do motor de pareamento: evita pendurar a aplicacao se o subprocesso
# do Gacrux travar (ver GacruxEngine em gacrux_engine.py).
GACRUX_TIMEOUT_SECONDS = 120


class GacruxTiebreakEngine:
    """Calcula os desempates (classificacao) com o motor FIDE oficial Gacrux.

    Espelha o fluxo do ``GacruxEngine`` de pareamento: exporta o estado do
    torneio para TRF, roda ``tiebreakchecker.py`` e traduz ``tiebreakResult`` de
    volta para ``player_id`` (individual) ou ``team_id`` (equipes). Lida apenas
    com I/O; o mapeamento de criterios e o parse vivem em ``gacrux_tiebreak_map``.
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
        """Devolve ``{player_id: {"rank": int, "scores": {codigo: float}}}``.

        ``codes`` e a sequencia de criterios do Albericus (sem ``points``);
        ``current_round`` e o numero de rodadas a considerar (por padrao, o
        total de rodadas fechadas). Retorna ``{}`` quando nao ha rodadas
        fechadas. Levanta ``AppError`` em qualquer falha do motor.
        """
        rounds = self._closed_rounds(tournament_id, current_round)
        if rounds <= 0:
            return {}

        export_service = self._export_service()
        plan = build_tiebreak_plan(codes)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        swiss = str(settings.get("pairing_method") or "swiss") != "round_robin"

        # Ranking 1-based pela MESMA ordenacao do exporter (==> cid do TRF).
        all_players = sorted(
            self.db.list_players(tournament_id, active_only=False),
            key=lambda player: (
                -export_service._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
        )
        rank_to_player_id = {index: int(p["id"]) for index, p in enumerate(all_players, start=1)}

        data = self._run_tiebreakchecker(
            TRF16Exporter(export_service), tournament_id, plan.specifiers, rounds, swiss=swiss
        )
        by_cid = parse_competitors(data.get("tiebreakResult", {}).get("competitors", []), plan)

        out: dict[int, dict[str, Any]] = {}
        for cid, payload in by_cid.items():
            player_id = rank_to_player_id.get(cid)
            if player_id is not None:
                out[player_id] = payload
        logger.debug("Desempates Gacrux por player_id: %s", out)
        return out

    # ------------------------------------------------------------------ #
    # Equipes
    # ------------------------------------------------------------------ #
    def compute_teams(
        self,
        tournament_id: int,
        codes: list[Any],
        current_round: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Devolve ``{team_id: {"rank": int, "scores": {codigo: float}}}``.

        Usa o TRF-25 (que carrega o tipo de torneio por equipes e o sistema de
        pontos), nao o TRF-16. ``codes`` e a sequencia de criterios de equipe do
        Albericus (match_points, game_points, buchholz, wins).
        """
        rounds = self._closed_rounds(tournament_id, current_round)
        if rounds <= 0:
            return {}

        export_service = self._export_service()
        exporter = TRF25Exporter(export_service)
        plan = build_team_tiebreak_plan(codes)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        swiss = str(settings.get("team_pairing_method") or "swiss") != "round_robin"

        # cid (Team Pairing Number do TRF-25) -> team_id, reusando a MESMA
        # ordenacao do exporter (_prepare_teams ordena por forca/nome).
        players = sorted(
            self.db.list_players(tournament_id, active_only=False),
            key=lambda player: (
                -export_service._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
        )
        start_rank_by_player = {int(p["id"]): index for index, p in enumerate(players, start=1)}
        teams = self.db.list_teams(tournament_id, active_only=False)
        prepared = exporter._prepare_teams(tournament_id, teams, players, start_rank_by_player)
        cid_to_team_id = {index: int(item["team_id"]) for index, item in enumerate(prepared, start=1)}

        data = self._run_tiebreakchecker(
            exporter, tournament_id, plan.specifiers, rounds, swiss=swiss
        )
        by_cid = parse_competitors(data.get("tiebreakResult", {}).get("competitors", []), plan)

        out: dict[int, dict[str, Any]] = {}
        for cid, payload in by_cid.items():
            team_id = cid_to_team_id.get(cid)
            if team_id is not None:
                out[team_id] = payload
        logger.debug("Desempates Gacrux por team_id: %s", out)
        return out

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _export_service(self) -> ExportService:
        from src.services.pairing_service import PairingService
        return ExportService(self.db, PairingService(self.db))

    def _closed_rounds(self, tournament_id: int, current_round: int | None) -> int:
        if current_round is not None:
            return int(current_round)
        return sum(
            1
            for round_data in self.db.list_rounds(tournament_id)
            if round_data.get("status") == "closed"
        )

    def _run_tiebreakchecker(
        self,
        exporter: TRF16Exporter,
        tournament_id: int,
        specifiers: tuple[str, ...],
        current_round: int,
        swiss: bool = True,
    ) -> dict[str, Any]:
        """Exporta o TRF com ``exporter`` e roda o ``tiebreakchecker.py``.

        Devolve o JSON parseado do Gacrux. ``swiss`` escolhe as regras: ``-s``
        (Suico) ou ``-p`` (pre-determinado/round-robin) — necessario porque os
        tiebreaks da FIDE diferem entre os dois sistemas. ``-t`` vai por ULTIMO:
        como tem ``nargs='*'``, engoliria flags seguintes.
        """
        current_dir = Path(__file__).resolve().parent
        script_path = current_dir / "gacrux" / "tiebreakchecker.py"
        if not script_path.exists():
            raise AppError(f"Motor Gacrux (desempate) nao encontrado em: {script_path}")
        project_root = current_dir.parent.parent.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.trf"
            output_path = Path(tmpdir) / "output.json"

            exporter.export(tournament_id, input_path)

            cmd = [
                sys.executable,
                str(script_path),
                "-i", str(input_path),
                "-o", str(output_path),
                "-b", "utf-8",
                # Suico (-s) ou round-robin/pre-determinado (-p). Nossos tipos de
                # torneio dizem "Suico" (nao "SWISS"), entao a regra e sempre
                # explicita; sem isso o motor inferiria pelo numero de jogadores.
                "-s" if swiss else "-p",
                "-n", str(current_round),
                "-F", "JSON",
                "-t", *specifiers,
            ]

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
                raise AppError(f"Erro no calculo de desempates do Gacrux: {error_msg}")

            if not output_path.exists():
                raise AppError("O motor Gacrux (desempate) nao gerou o arquivo de saida esperado.")

            try:
                with open(output_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception as exc:
                raise AppError(f"Falha ao ler o resultado dos desempates do Gacrux: {exc}")

        # code 0 = OK; 1 = OK porem divergente no modo -c (nao usamos -c aqui).
        status = data.get("status", {})
        if status.get("code", 0) not in (0, 1):
            errors = status.get("error", [])
            err_text = "; ".join(errors) if errors else "Erro interno do Gacrux"
            raise AppError(f"Gacrux (desempate): {err_text}")
        return data
