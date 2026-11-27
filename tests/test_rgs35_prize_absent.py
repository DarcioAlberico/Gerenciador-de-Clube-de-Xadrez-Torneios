"""RGS-35 — "ausente" não perde prêmio como se fosse desistente.

`prizes.py` tratava `absent`/`ausente` como desistência: com
`prize_exclude_withdrawn` ligado, quem faltou a UMA rodada (status "ausente"
pendente) ficava sem o prêmio que ganhou. E como o banco grava `active = 0`
para todo status que não é `active`, o ausente caía também pela bandeira.

A regra (glossário, seção 7): a exclusão vale só para desistência definitiva e
expulsão, avaliadas no FIM do torneio — o status que o jogador tem quando a
premiação é calculada.
"""

from __future__ import annotations

import unittest

from src.services.prizes import allocate_prizes, is_withdrawn
from tests.support.core_service_base import CoreServiceTestCase

PREMIOS = [
    {"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 500},
    {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 300},
]


def _linha(pid: int, nome: str, pos: int, pontos: float, status: str = "active") -> dict:
    return {
        "player_id": pid,
        "name": nome,
        "position": pos,
        "points": pontos,
        "category": "",
        "player_status": status,
        # O banco grava active=0 para todo status diferente de "active".
        "active": 1 if status == "active" else 0,
    }


class RegraPuraTest(unittest.TestCase):
    def test_ausente_concorre(self) -> None:
        for status in ("absent", "ausente", "inactive"):
            with self.subTest(status=status):
                self.assertFalse(is_withdrawn({"player_status": status, "active": 0}))

    def test_desistencia_definitiva_e_expulsao_excluem(self) -> None:
        for status in ("withdrawn", "desistente", "expelled", "expulso"):
            with self.subTest(status=status):
                self.assertTrue(is_withdrawn({"player_status": status, "active": 0}))

    def test_primeiro_colocado_ausente_recebe_o_premio(self) -> None:
        classificacao = [
            _linha(1, "Duda", 1, 5.0, status="absent"),
            _linha(2, "Ana", 2, 4.0),
            _linha(3, "Fuga", 3, 3.0, status="withdrawn"),
        ]
        resultado = allocate_prizes(classificacao, PREMIOS, "best_only", 0.0, exclude_withdrawn=True)
        por_nome = {item["name"]: item["gross"] for item in resultado["allocations"]}
        self.assertEqual({"Duda": 500.0, "Ana": 300.0}, por_nome)
        self.assertEqual(1, resultado["excluded_withdrawn"])


class AceiteNoServicoTest(CoreServiceTestCase):
    """Aceite da spec: ausente na última rodada e 1º colocado recebe o prêmio
    com `prize_exclude_withdrawn=1`."""

    def test_ausente_na_ultima_rodada_e_primeiro_recebe(self) -> None:
        jogadores = self._create_players(4)
        self.db.save_tournament_settings(self.tournament_id, {"prize_exclude_withdrawn": 1})
        self.prize_service.replace_prizes(self.tournament_id, PREMIOS)

        # Duas rodadas com 4 jogadores: um só termina com 2 pontos (1o isolado).
        for _ in range(2):
            rodada = self.service.generate_next_round(self.tournament_id)
            for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
                if not pairing["is_bye"]:
                    self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(rodada["id"]))

        lider = self.service.standings(self.tournament_id)[0]
        self.assertEqual(2.0, float(lider["points"]))
        self.db.set_player_status(int(lider["player_id"]), "absent")

        alocacao = self.prize_service.allocate(self.tournament_id)
        premiados = {int(item["player_id"]): item["gross"] for item in alocacao["allocations"]}
        self.assertEqual(500.0, premiados.get(int(lider["player_id"])))
        self.assertEqual(0, alocacao["excluded_withdrawn"])
        self.assertIn(int(lider["player_id"]), jogadores)


if __name__ == "__main__":
    unittest.main()
