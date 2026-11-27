"""RG2-05 — excluir um bye solicitado passa pelo serviço.

A tela apagava direto no banco: um bye já aplicado numa rodada gerada sumia do
cadastro, a mesa continuava "H", o saldo voltava a "nenhum usado" e não ficava
rastro. Com limite de byes no regulamento, o jogador ganhava um bye a mais.
"""
from __future__ import annotations

from src.services.constants import AppError
from src.ui.screens.pairing_arbitration.controller import ArbitrationController
from tests.support.core_service_base import CoreServiceTestCase


class CancelarByeSolicitadoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jogadores = self._create_players(6)
        self.r1 = int(self.service.generate_next_round(self.tournament_id)["id"])

    def _fechar_r1(self) -> None:
        for mesa in self.db.get_pairings_for_round(self.r1):
            if not mesa["is_bye"]:
                self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, self.r1)

    def _bye(self, rodada: int) -> tuple[int, int]:
        jogador = int(self.jogadores[0])
        bye_id = self.service.request_bye(self.tournament_id, jogador, rodada, "H", reason="viagem")
        return bye_id, jogador

    def test_bye_de_rodada_ja_gerada_nao_pode_ser_excluido(self) -> None:
        bye_id, jogador = self._bye(2)
        self._fechar_r1()
        self.service.generate_next_round(self.tournament_id)
        saldo = self.service.bye_balance(self.tournament_id, jogador)

        with self.assertRaises(AppError):
            self.service.cancel_requested_bye(self.tournament_id, bye_id, "engano")

        self.assertEqual(1, len(self.db.list_requested_byes(self.tournament_id)))
        self.assertEqual(saldo, self.service.bye_balance(self.tournament_id, jogador))

    def test_sem_rodada_exige_motivo(self) -> None:
        bye_id, _jogador = self._bye(3)

        with self.assertRaises(AppError):
            self.service.cancel_requested_bye(self.tournament_id, bye_id, "   ")

        self.assertEqual(1, len(self.db.list_requested_byes(self.tournament_id)))

    def test_sem_rodada_exclui_e_audita(self) -> None:
        bye_id, jogador = self._bye(3)

        self.service.cancel_requested_bye(self.tournament_id, bye_id, "voltou da viagem")

        self.assertEqual([], self.db.list_requested_byes(self.tournament_id))
        eventos = self.db.list_audit_events(
            self.tournament_id, action="requested_bye_removed", limit=10
        )
        self.assertEqual(1, len(eventos))
        self.assertEqual(jogador, int(eventos[0]["entity_id"]))
        self.assertIn("voltou da viagem", eventos[0]["reason"])

    def test_bye_de_outro_torneio_nao_e_achado(self) -> None:
        bye_id, _jogador = self._bye(3)
        with self.assertRaises(AppError):
            self.service.cancel_requested_bye(self.tournament_id + 999, bye_id, "x")

    def test_a_tela_so_chama_o_servico(self) -> None:
        bye_id, _jogador = self._bye(2)
        self._fechar_r1()
        self.service.generate_next_round(self.tournament_id)
        controlador = ArbitrationController(self.db, pairing_service=self.service)

        with self.assertRaises(AppError):
            controlador.delete_bye(self.tournament_id, bye_id, False, "engano")

        self.assertEqual(1, len(self.db.list_requested_byes(self.tournament_id)))
