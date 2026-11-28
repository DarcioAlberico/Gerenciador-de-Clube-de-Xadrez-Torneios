"""RG2-09 — excluir jogador de torneio por equipes não apaga quem já jogou.

A guarda "já jogou" olhava só a tabela ``pairings`` (individual). No por
equipes o jogo mora em ``team_boards``, com ``ON DELETE SET NULL``: excluir o
jogador deixava o tabuleiro jogado sem ninguém, com o resultado lá.
"""
from __future__ import annotations

import unittest

from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase


class ExcluirJogadorDeEquipeTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tid, _equipes = self._create_team_tournament(teams_count=4, boards_count=2)
        self.rodada = self.service.generate_next_round(self.tid)
        confronto = next(c for c in self.db.list_team_matches_for_round(self.rodada["id"]) if not c["is_bye"])
        self.tabuleiro = self.db.list_team_boards(int(confronto["id"]))[0]
        self.service.update_result(self.tid, int(self.tabuleiro["id"]), "1-0")

    def _tabuleiro_agora(self) -> dict:
        return next(t for t in self.db.list_team_boards(int(self.tabuleiro["team_match_id"])) if t["id"] == self.tabuleiro["id"])

    def test_quem_jogou_num_tabuleiro_nao_pode_ser_excluido(self) -> None:
        for cor in ("white_player_id", "black_player_id"):
            with self.subTest(cor=cor):
                jogador = int(self.tabuleiro[cor])
                with self.assertRaisesRegex(AppError, "Retirar do torneio"):
                    self.service.delete_player_if_unpaired(self.tid, jogador)
                self.assertEqual(jogador, self._tabuleiro_agora()[cor])
                self.assertEqual("1-0", self._tabuleiro_agora()["result"])

    def test_quem_nunca_entrou_em_tabuleiro_continua_excluivel(self) -> None:
        reserva = self.db.create_player(self.tid, name="Reserva sem jogo", rating=1500)
        self.service.delete_player_if_unpaired(self.tid, reserva)
        self.assertIsNone(self.db.get_player(reserva))


if __name__ == "__main__":
    unittest.main()
