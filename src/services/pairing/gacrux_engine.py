from __future__ import annotations
import os
import sys
import tempfile
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Sequence

from src.services.constants import AppError, player_pairing_name
from src.services.export_service import ExportService
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.pairing.gacrux_trf import acceleration_records, reconcile_scores

logger = logging.getLogger(__name__)

# Teto de tempo do subprocesso do Gacrux: evita pendurar a aplicacao se o motor
# travar (essencial agora que o Gacrux pode ser o motor padrao de pareamento).
GACRUX_TIMEOUT_SECONDS = 120


class GacruxEngine:
    def __init__(self, db) -> None:
        self.db = db
        # Avisos da última rodada pareada (PAR-02): o que o arquivo TRF não
        # conseguiu contar ao motor. Quem chama repassa ao árbitro.
        self.warnings: list[str] = []

    def pair_round(
        self,
        tournament_id: int,
        to_pair: list[dict[str, Any]],
        round_number: int,
        *,
        accelerated_player_ids: Sequence[int] = (),
        acceleration_bonus: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Executes Swiss pairing for the specified round using the FIDE-approved Gacrux engine.
        Re-uses the existing TRF16Exporter to serialize the tournament state, runs Gacrux,
        and parses back the results.

        `accelerated_player_ids` recebe o bônus fictício de `acceleration_bonus`
        nesta rodada (PAR-02): o motor não tem parâmetro de aceleração, ela viaja
        como registro 250 no TRF. Ver `gacrux_trf.acceleration_records`.
        """
        self.warnings = []
        # Instantiate a temporary ExportService and TRF16Exporter
        from src.services.pairing_service import PairingService
        pairing_service = PairingService(self.db)
        export_service = ExportService(self.db, pairing_service)
        exporter = TRF16Exporter(export_service)

        # Get all players for rank mapping
        all_players = sorted(
            self.db.list_players(tournament_id, active_only=False),
            key=lambda player: (
                -export_service._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
        )
        
        # Map FIDE TRF 1-based rank back to the player ID
        rank_to_player_id = {index: int(p["id"]) for index, p in enumerate(all_players, start=1)}

        # Determine which players are NOT to be paired in this round (inactive or requested byes)
        to_pair_ids = {int(p["id"]) for p in to_pair}
        unpaired_ranks = []
        for index, player in enumerate(all_players, start=1):
            if int(player["id"]) not in to_pair_ids:
                unpaired_ranks.append(str(index))

        # Use a temporary directory for file exchange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.trf"
            output_path = Path(tmpdir) / "output.json"

            # Export the current tournament state to TRF
            exporter.export(tournament_id, input_path)

            accelerated = {int(player_id) for player_id in accelerated_player_ids}
            self._adjust_trf_for_pairing(
                input_path,
                round_number,
                [rank for rank, player_id in rank_to_player_id.items() if player_id in accelerated],
                acceleration_bonus,
            )

            if logger.isEnabledFor(logging.DEBUG):
                with open(input_path, "r", encoding="utf-8") as f:
                    logger.debug("TRF gerado para o Gacrux:\n%s", "".join(f.readlines()[:25]))

            # Determine paths for execution
            current_dir = Path(__file__).resolve().parent
            script_path = current_dir / "gacrux" / "pairingchecker.py"
            if not script_path.exists():
                raise AppError(f"Motor Gacrux nao encontrado em: {script_path}")
            project_root = current_dir.parent.parent.parent

            # Construct Gacrux command using script path invocation
            cmd = [
                sys.executable,
                str(script_path),
                "-i", str(input_path),
                "-o", str(output_path),
                "-b", "utf-8",
                "-p",
                "-n", str(round_number),
                "-m", "dutch",
                "-F", "JSON",
                "-v"
            ]
            if unpaired_ranks:
                cmd.extend(["-u"] + unpaired_ranks)

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
                logger.debug("Gacrux STDOUT: %s", result.stdout)
                logger.debug("Gacrux STDERR: %s", result.stderr)
            except subprocess.TimeoutExpired as exc:
                raise AppError(
                    f"O motor Gacrux excedeu {GACRUX_TIMEOUT_SECONDS}s ao parear a rodada "
                    f"{round_number} e foi interrompido. Tente novamente ou use o motor proprio "
                    "nas configuracoes do torneio."
                ) from exc
            except Exception as e:
                raise AppError(f"Falha ao executar o motor Gacrux: {e}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
                raise AppError(f"Erro no emparceiramento Gacrux: {error_msg}")

            if not output_path.exists():
                raise AppError("O motor Gacrux nao gerou o arquivo de saida esperado.")

            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.debug("Gacrux data: %s", data)
            except Exception as e:
                raise AppError(f"Falha ao ler o resultado do emparceiramento: {e}")

            # Check status returned by Gacrux
            status = data.get("status", {})
            if status.get("code") != 0:
                errors = status.get("error", [])
                err_text = "; ".join(errors) if errors else "Erro interno do Gacrux"
                raise AppError(f"Gacrux: {err_text}")

            pairing_res = data.get("pairingResult", {})
            pairs = pairing_res.get("pairs", [])
            
            # Map Gacrux pairs back to Albericus database structure
            board_number = 1
            normal_pairings = []
            bye_pairings = []

            for w_rank, b_rank in pairs:
                if w_rank == 0 and b_rank == 0:
                    continue  # Safety guard

                if w_rank == 0 or b_rank == 0:
                    bye_rank = w_rank if w_rank != 0 else b_rank
                    bye_player_id = rank_to_player_id.get(bye_rank)
                    if not bye_player_id:
                        continue
                    bye_pairings.append({
                        "board_number": 9999,
                        "white_player_id": bye_player_id,
                        "black_player_id": None,
                        "result": "BYE",
                        "is_bye": 1,
                    })
                else:
                    white_id = rank_to_player_id.get(w_rank)
                    black_id = rank_to_player_id.get(b_rank)
                    if not white_id or not black_id:
                        continue
                    normal_pairings.append({
                        "board_number": board_number,
                        "white_player_id": white_id,
                        "black_player_id": black_id,
                        "result": "",
                        "is_bye": 0,
                    })
                    board_number += 1

            final_pairings = normal_pairings + bye_pairings
            for idx, p in enumerate(final_pairings, start=1):
                p["board_number"] = idx

            logger.debug("Rank -> player id: %s", rank_to_player_id)
            logger.debug("Pareamentos mapeados: %s", final_pairings)
            return final_pairings

    def _adjust_trf_for_pairing(
        self,
        input_path: Path,
        round_number: int,
        accelerated_ranks: list[int],
        bonus: float,
    ) -> None:
        """Reescreve o TRF exportado com o que só o PAREAMENTO precisa (PAR-02).

        O arquivo oficial de envio continua sendo o do exportador, intocado: o que
        entra aqui — registro 250 de aceleração e células coerentes com os pontos
        da classificação — existe para o motor pontuar como a classificação
        pontua, e não teria por que ir para a federação.
        """
        with open(input_path, "r", encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines()

        lines, warnings = reconcile_scores(lines)
        lines.extend(acceleration_records(bonus, round_number, accelerated_ranks))
        self.warnings = warnings
        for aviso in warnings:
            logger.warning("Rodada %s (Gacrux): %s", round_number, aviso)

        with open(input_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(f"{line}\r\n" for line in lines))
