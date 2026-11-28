"""RG2-35 — desligar o Modo Livre depois de jogado exige motivo e não apaga o passado.

Antes, ``set_enabled(False)`` não olhava as rodadas: um clique e o torneio
jogado com entrada tardia, rodadas refeitas e atraso flexível passava a valer
rating interno sem pergunta e a sair no TRF sem aviso — a pergunta e o aviso
só consultavam a marca ATUAL.

Agora, com rodada gerada, desligar exige motivo, e o evento
``free_mode_changed`` guarda quantas rodadas já existiam. "Já foi amistoso"
(a marca ligada OU esse evento) mantém a pergunta antes do rating interno e o
aviso no TRF.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services import friendly_mode
from src.services.constants import AppError
from src.services.friendly_mode import FriendlyModeService
from src.services.pairing_service import PairingService
from src.services.rating_service import InternalRatingService


class ModoLivreDesligadoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pasta = tempfile.TemporaryDirectory()
        base = Path(self.pasta.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "b")
        self.modo = FriendlyModeService(self.db)
        self.tid = self.modo.create("Escola", rounds_count=3)["tournament_id"]
        for i in range(4):
            self.db.create_player(self.tid, name=f"Aluno {i + 1}", rating=1000 + 10 * i)
        self.pairing = PairingService(self.db)

    def tearDown(self) -> None:
        self.pasta.cleanup()

    def _fechar_r1(self) -> None:
        rodada = self.pairing.generate_next_round(self.tid)
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            if not mesa.get("is_bye"):
                self.db.update_pairing_result(mesa["id"], "1-0")
        self.pairing.close_round(self.tid, int(rodada["id"]))

    def test_aceite_desligar_com_r1_fechada_e_aplicar_rating_sem_confirmar(self) -> None:
        self._fechar_r1()
        self.modo.set_enabled(self.tid, False, reason="Virou torneio do clube")
        with self.assertRaises(AppError):
            InternalRatingService(self.db).apply_tournament_ratings(self.tid)
        InternalRatingService(self.db).apply_tournament_ratings(self.tid, friendly_confirmed=True)

    def test_com_rodada_gerada_desligar_exige_motivo(self) -> None:
        self.pairing.generate_next_round(self.tid)
        with self.assertRaisesRegex(AppError, "motivo"):
            self.modo.set_enabled(self.tid, False)
        self.assertTrue(friendly_mode.is_friendly(self.db.get_tournament_settings(self.tid)))

    def test_motivo_e_rodadas_ficam_no_evento(self) -> None:
        self._fechar_r1()
        self.modo.set_enabled(self.tid, False, reason="Virou torneio do clube")
        (evento,) = self.db.list_audit_events(self.tid, action="free_mode_changed")
        self.assertEqual("Virou torneio do clube", evento["reason"])
        self.assertIn('"rounds_generated":1', evento["metadata_json"].replace(" ", ""))

    def test_sem_rodada_desliga_sem_motivo_e_nao_conta_como_amistoso(self) -> None:
        self.modo.set_enabled(self.tid, False)
        self.assertFalse(friendly_mode.played_as_friendly(self.db, self.tid))
        self.assertIn("updated", InternalRatingService(self.db).apply_tournament_ratings(self.tid))

    def test_ja_foi_amistoso_mantem_o_aviso_no_trf(self) -> None:
        from src.services.export_service import ExportService

        self._fechar_r1()
        self.modo.set_enabled(self.tid, False, reason="Virou torneio do clube")
        exportador = ExportService(self.db, self.pairing)
        self.assertIn(friendly_mode.RATING_REFUSAL, exportador.validate_chess_results_trf(self.tid))
        with self.assertRaises(AppError):
            exportador.export_chess_results_trf(self.tid, Path(self.pasta.name) / "t.trf", submission=True)


if __name__ == "__main__":
    unittest.main()
