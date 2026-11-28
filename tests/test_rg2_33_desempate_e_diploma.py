"""RG2-33 — "desempate decide" e o diploma por categoria lendo a premiação.

Antes, o rateio entre empatados só conhecia "dividir por igual" e Hort: o
edital que diz "o desempate decide" (500 para o 1º, 300 para o 2º, mesmo com
os dois em 5 pontos) não tinha como ser configurado. E o diploma de categoria
(``category_award``) refazia a conta sozinho: só olhava a categoria principal,
ignorava "excluir desistentes" e a trava de um prêmio por jogador — o diploma
"1º Feminino" podia sair para quem não recebeu o prêmio Feminino.

Agora o diploma lê a MESMA alocação da premiação (RG2-16). Torneio sem prêmio
de categoria no edital continua com o diploma pela classificação da categoria.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src.services.pairing_service import PairingService
from src.services.prizes import PRIZE_TIE_SPLITS, allocate_prizes
from tests.support.core_service_base import CoreServiceTestCase


def _linha(player_id: int, posicao: int, pontos: float, categorias: str, **extra) -> dict:
    return {
        "player_id": player_id,
        "name": f"J{player_id}",
        "position": posicao,
        "points": pontos,
        "category": categorias.split(";")[0].strip(),
        "categories": categorias,
        "player_status": "active",
        "active": 1,
        **extra,
    }


class DesempateDecideTest(unittest.TestCase):
    PREMIOS = [
        {"kind": "overall", "label": "1º", "rank_from": 1, "rank_to": 1, "amount": 500},
        {"kind": "overall", "label": "2º", "rank_from": 2, "rank_to": 2, "amount": 300},
    ]

    def test_aceite_empate_em_5_pontos_com_500_e_300(self) -> None:
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 5, "Adulto")]
        resultado = allocate_prizes(classificacao, self.PREMIOS, policy="best_only", tie_split="tiebreak")
        self.assertEqual({1: 500.0, 2: 300.0}, {a["player_id"]: a["gross"] for a in resultado["allocations"]})

    def test_a_opcao_aparece_para_o_arbitro(self) -> None:
        self.assertIn("tiebreak", PRIZE_TIE_SPLITS)

    def test_empatado_sem_premio_da_posicao_nao_fica_travado(self) -> None:
        """O 3º empatado não recebe nada do geral e continua disputando a categoria."""
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 5, "Adulto"), _linha(3, 3, 5, "Sub-12")]
        premios = [*self.PREMIOS, {"kind": "category", "label": "Sub-12", "category": "Sub-12", "rank_from": 1, "rank_to": 1, "amount": 100}]
        resultado = allocate_prizes(classificacao, premios, policy="best_only", tie_split="tiebreak")
        self.assertEqual({1: 500.0, 2: 300.0, 3: 100.0}, {a["player_id"]: a["gross"] for a in resultado["allocations"]})


class DiplomaLeAPremiacaoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ana = self.db.create_player(self.tournament_id, name="Ana", sex="F", category="Sub-12")
        self.bia = self.db.create_player(self.tournament_id, name="Bia", sex="F", category="Sub-14")
        self.caio = self.db.create_player(self.tournament_id, name="Caio", sex="M", category="Sub-12")
        self.dani = self.db.create_player(self.tournament_id, name="Dani", sex="F", category="Sub-14")

    def _classificacao(self, **por_jogador: dict) -> list[dict]:
        linhas = []
        for posicao, (pid, pontos) in enumerate(
            [(self.ana, 4), (self.bia, 3), (self.caio, 2), (self.dani, 1)], start=1
        ):
            jogador = self.db.get_player(pid)
            linhas.append(
                {
                    "player_id": pid,
                    "name": jogador["name"],
                    "position": posicao,
                    "points": pontos,
                    "category": jogador["category"],
                    "categories": f"{jogador['category']}; Feminino" if jogador["sex"] == "F" else jogador["category"],
                    "player_status": "active",
                    "active": 1,
                    **por_jogador.get(jogador["name"], {}),
                }
            )
        return linhas

    def _diplomas(self, classificacao: list[dict]) -> list[tuple[str, str, int]]:
        with mock.patch.object(PairingService, "standings", return_value=classificacao):
            recebem = self.certificate_service.tournament_recipients(
                self.tournament_id, certificate_type="category_award"
            )
        return [(r["name"], r["category"], r["category_position"]) for r in recebem]

    def test_1o_feminino_sai_para_quem_recebeu_o_premio_feminino(self) -> None:
        """Ana leva o geral; o prêmio Feminino desce para Bia, e o diploma também."""
        self.prize_service.replace_prizes(
            self.tournament_id,
            [
                {"kind": "overall", "label": "1º geral", "rank_from": 1, "rank_to": 1, "amount": 200},
                {"kind": "category", "label": "1º Feminino", "category": "Feminino", "rank_from": 1, "rank_to": 1, "amount": 100},
            ],
        )
        self.assertEqual([("Bia", "Feminino", 1)], self._diplomas(self._classificacao()))

    def test_desistente_excluido_nao_recebe_diploma(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"prize_exclude_withdrawn": 1})
        self.prize_service.replace_prizes(
            self.tournament_id,
            [{"kind": "category", "label": "1º Feminino", "category": "Feminino", "rank_from": 1, "rank_to": 1, "amount": 100}],
        )
        classificacao = self._classificacao(Ana={"player_status": "withdrawn", "active": 0})
        self.assertEqual([("Bia", "Feminino", 1)], self._diplomas(classificacao))

    def test_sem_premio_de_categoria_vale_a_classificacao_da_categoria(self) -> None:
        """Torneio sem prêmio de categoria: o diploma segue como antes (top 1 de cada categoria)."""
        with mock.patch.object(PairingService, "standings", return_value=self._classificacao()):
            recebem = self.certificate_service.tournament_recipients(
                self.tournament_id, certificate_type="category_award", top_n=1
            )
        self.assertEqual({("Ana", "Sub-12"), ("Bia", "Sub-14")}, {(r["name"], r["category"]) for r in recebem})


if __name__ == "__main__":
    unittest.main()
