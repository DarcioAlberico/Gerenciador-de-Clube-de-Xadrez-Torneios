"""RG2-22 — sem pareamento legal possível, o árbitro recebe a regra, não um traceback.

Antes: com 2 jogadores na R2 (ou 3 na R4) o Gacrux saía com código ≠ 0 e o
``AppError`` levava o stderr inteiro — ``Traceback … RuntimeError: Gacrux: 2
nó(s) sem par``. Pedir o motor reserva dava o mesmo traceback. Não existe
pareamento que respeite os critérios absolutos (C.04.1: ninguém joga duas vezes
contra o mesmo adversário, ninguém recebe um segundo bye): o motor reserva não é
saída, e a tela passa a oferecer o que é — encerrar o torneio aqui ou rever as
ausências.
"""
from __future__ import annotations

import unittest
from unittest import mock

import pytest

from src.services.constants import AppError
from src.services.pairing.gacrux_engine import GacruxNoLegalPairing, GacruxRefusal
from tests.support.core_service_base import CoreServiceTestCase


@pytest.mark.gacrux  # o Gacrux de verdade é quem descobre que não há pareamento
class DoisJogadoresNaR2Test(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(
            self.tournament_id,
            {"pairing_method": "swiss", "pairing_system": "gacrux_swiss", "initial_color": "W"},
        )
        self._create_players(2)
        rodada = self.service.generate_next_round(self.tournament_id)
        (mesa,) = self.db.get_pairings_for_round(int(rodada["id"]))
        self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))

    def test_a_recusa_cita_a_regra_e_nao_o_traceback(self) -> None:
        with self.assertRaises(GacruxRefusal) as recusa:
            self.service.generate_next_round(self.tournament_id)
        self.assertIsInstance(recusa.exception, GacruxNoLegalPairing)
        texto = str(recusa.exception)
        self.assertNotIn("Traceback", texto)
        self.assertNotIn("RuntimeError", texto)
        self.assertIn("C.04.1", texto)
        self.assertNotIn("É possível parear esta rodada com o", texto)
        self.assertFalse(recusa.exception.offers_reserve)
        self.assertEqual(1, len(self.db.list_rounds(self.tournament_id)))

    def test_o_motor_reserva_nao_e_saida(self) -> None:
        with self.assertRaises(GacruxNoLegalPairing):
            self.service.generate_next_round(self.tournament_id, reserve_engine=True)
        self.assertEqual(1, len(self.db.list_rounds(self.tournament_id)))

    def test_encerrar_aqui_fecha_o_torneio_na_ultima_rodada_jogada(self) -> None:
        self.service.end_tournament_early(self.tournament_id, "não há pareamento legal para a R2")
        torneio = self.db.get_tournament(self.tournament_id)
        self.assertEqual(1, int(torneio["rounds_count"]))
        self.assertEqual("finished", torneio["status"])
        (evento,) = self.db.list_audit_events(self.tournament_id, action="tournament_ended_early")
        self.assertIn("R2", evento["reason"])


class MarcaDoMotorTest(unittest.TestCase):
    def test_o_motor_vendorizado_usa_a_marca_que_o_albericus_procura(self) -> None:
        from pathlib import Path

        from src.services.pairing import gacrux_engine

        fonte = Path(gacrux_engine.__file__).with_name("gacrux") / "pairing.py"
        self.assertIn(gacrux_engine.NO_LEGAL_PAIRING_TAG, fonte.read_text(encoding="utf-8"))


class EncerrarAquiRecusaTest(CoreServiceTestCase):
    def test_com_rodada_aberta_recusa(self) -> None:
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)
        with self.assertRaisesRegex(AppError, "aberta"):
            self.service.end_tournament_early(self.tournament_id, "motivo")
        self.assertEqual(5, int(self.db.get_tournament(self.tournament_id)["rounds_count"]))

    def test_sem_rodada_jogada_recusa(self) -> None:
        with self.assertRaisesRegex(AppError, "rodada"):
            self.service.end_tournament_early(self.tournament_id, "motivo")

    def test_sem_motivo_recusa(self) -> None:
        with self.assertRaisesRegex(AppError, "motivo"):
            self.service.end_tournament_early(self.tournament_id, "  ")


class OfertaNaTelaTest(unittest.TestCase):
    def _tela(self):
        from src.ui.screens.pairing_results.view import PairingResultsMixin

        chamadas: list[tuple] = []

        class Tela(PairingResultsMixin):
            pairing_service = mock.Mock()

            def _start_round_generation(self, tournament_id, *, reserve_engine):
                chamadas.append(("gerar", tournament_id, reserve_engine))

            def show_pairings(self):
                chamadas.append(("recarregar",))

            def _show_error(self, exc):
                chamadas.append(("erro", str(exc)))

        return Tela(), chamadas

    def test_encerrar_aqui_em_vez_do_motor_reserva(self) -> None:
        tela, chamadas = self._tela()
        recusa = GacruxNoLegalPairing(2, ["2 jogadores sem adversário possível"])
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as dialogo:
            self.assertTrue(tela._offer_reserve_engine(7, recusa))
        self.assertEqual("Encerrar o torneio aqui", dialogo.call_args.kwargs["confirm_text"])
        self.assertEqual("Rever ausências", dialogo.call_args.kwargs["cancel_text"])
        tela.pairing_service.end_tournament_early.assert_called_once()
        self.assertEqual(7, tela.pairing_service.end_tournament_early.call_args.args[0])
        self.assertNotIn(("gerar", 7, True), chamadas)
        self.assertIn(("recarregar",), chamadas)

    def test_rever_ausencias_nao_grava_nada(self) -> None:
        tela, chamadas = self._tela()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False):
            self.assertTrue(tela._offer_reserve_engine(7, GacruxNoLegalPairing(2, ["x"])))
        tela.pairing_service.end_tournament_early.assert_not_called()
        self.assertEqual([], chamadas)


if __name__ == "__main__":
    unittest.main()
