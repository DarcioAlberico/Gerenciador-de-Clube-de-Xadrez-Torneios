from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.run_referee_operational_pilot import (
    restore_in_second_installation,
    simulate_last_minute_registration,
    simulate_locate_and_submit_table_result,
    simulate_official_rating_correction_before_round_one,
    simulate_simultaneous_qr_submissions,
    verify_offline_local_flow,
)
from src.core.database import Database
from src.services.pairing_service import PairingService
from src.services.tournament_service import TournamentService


class OperationalPilotTest(unittest.TestCase):
    def test_panel_locates_table_outside_inline_cutoff_and_submits_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            details, elapsed_ms = simulate_locate_and_submit_table_result(Path(temp_name), players_count=120)

        self.assertEqual(
            "mesa 60 localizada fora do recorte inline, lancada e removida das pendencias",
            details,
        )
        self.assertGreaterEqual(elapsed_ms, 0)

    def test_official_rating_correction_previews_before_selective_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            measurements = simulate_official_rating_correction_before_round_one(
                Path(temp_name),
                players_count=8,
            )

        self.assertEqual(
            [
                "Importar base oficial FIDE local",
                "Comparar ratings oficiais antes da rodada 1",
                "Confirmar correcoes oficiais selecionadas",
            ],
            [measurement.operation for measurement in measurements],
        )
        self.assertTrue(all(measurement.status == "OK" for measurement in measurements))

    def test_last_minute_registration_preserves_history_and_updates_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            details, elapsed_ms = simulate_last_minute_registration(Path(temp_name), players_count=8)

        self.assertEqual(
            "9 inscritos; 0,5 ponto; historico preservado; jogador presente na previa seguinte",
            details,
        )
        self.assertGreaterEqual(elapsed_ms, 0)

    def test_simultaneous_qr_submissions_are_queued_and_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            details = simulate_simultaneous_qr_submissions(Path(temp_name))

        self.assertEqual("20 envios concorrentes recebidos e aprovados", details)

    def test_offline_local_flow_blocks_network_and_completes_round(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            details = verify_offline_local_flow(Path(temp_name))

        self.assertEqual(
            "painel, 4 resultados, fechamento, classificacao, exportacoes e backup validados",
            details,
        )

    def test_restore_in_second_installation_reproduces_round_and_pairings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            db = Database(temp_dir / "source.db", backup_dir=temp_dir / "source_backups")
            tournament_id = TournamentService(db).create_tournament(
                {"name": "Piloto restore", "rounds_count": "3", "bye_points": "1"}
            )
            for index in range(4):
                db.create_player(tournament_id, name=f"Jogador {index + 1}", rating=1800 - index)
            round_data = PairingService(db).generate_next_round(tournament_id)
            backup_path = db.backup("pilot_test")

            details = restore_in_second_installation(
                backup_path,
                temp_dir,
                tournament_id,
                int(round_data["id"]),
                expected_boards=2,
            )

            self.assertEqual("1 rodada; 2 mesas validadas", details)


if __name__ == "__main__":
    unittest.main()
