"""RG2-17 — duplicar torneio copia tudo, menos o que é da edição.

A cópia era uma lista de colunas escrita à mão, que não acompanhou ORG-01..04:
perdia as categorias, o rateio Hort, a data de referência das categorias e a
tolerância de atraso; copiava "arquivado" (o torneio novo nascia escondido da
lista) e o ``fide_event_id`` (a nova edição iria à FIDE com o ID da antiga).

Agora a cópia é por **lista de exclusão**: toda coluna das tabelas é copiada,
menos as da edição. Este teste compara todas as colunas — uma coluna nova em
``tournaments`` ou ``tournament_settings`` entra na cópia sem ninguém lembrar.

(Antes era ``test_dup_check_tmp.py``, que só fazia ``print``.)
"""
from __future__ import annotations

import sqlite3
import unittest

from src.core.database_tournament_core import (
    DUPLICATE_RESET_SETTINGS_COLUMNS,
    DUPLICATE_RESET_TOURNAMENT_COLUMNS,
)
from tests.support.core_service_base import CoreServiceTestCase

AJUSTES = {
    "prize_tie_split": "hort",
    "prize_exclude_withdrawn": 1,
    "late_tolerance_minutes": 30,
    "rating_speed": "rapid",
    "rating_regulation": "fide",
    "category_reference_date": "2026-01-01",
    "prize_policy": "cumulative",
    "prize_tax_percent": 12.5,
    "fide_event_id": "999001",
    "chess_results_url": "https://chess-results.example/tnr1",
    "cutoff_date": "2025-11-01",
    "initial_color": "white",
    "archived": 1,
}
CATEGORIAS = [
    {"name": "Sub-07", "kind": "age", "max_value": 7, "position": 0},
    {"name": "Sub-09", "kind": "age", "max_value": 9, "position": 1},
    {"name": "Feminino", "kind": "sex", "sex": "F", "position": 2},
]


class DuplicarTorneioTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.origem = self.tournament_id
        self.db.save_tournament_settings(self.origem, AJUSTES)
        self.db.replace_tournament_categories(self.origem, CATEGORIAS)
        self.db.replace_tournament_prizes(
            self.origem,
            [{"kind": "category", "label": "Sub-07", "category": "Sub-07", "rank_from": 1, "rank_to": 1, "amount": 50.0}],
        )
        self.copia = self.tournament_service.duplicate_tournament(self.origem, "Copia 2027")

    def _linha(self, tabela: str, coluna_id: str, valor: int) -> dict:
        conexao = sqlite3.connect(self.db.db_path)
        try:
            conexao.row_factory = sqlite3.Row
            linha = conexao.execute(f"SELECT * FROM {tabela} WHERE {coluna_id} = ?", (valor,)).fetchone()
        finally:
            conexao.close()
        return dict(linha)

    def _diferencas(self, tabela: str, coluna_id: str, excluidas: frozenset[str]) -> dict:
        origem = self._linha(tabela, coluna_id, self.origem)
        copia = self._linha(tabela, coluna_id, self.copia)
        return {
            coluna: (origem[coluna], copia[coluna])
            for coluna in origem
            if coluna not in excluidas and coluna != coluna_id and origem[coluna] != copia[coluna]
        }

    def test_toda_coluna_de_tournaments_e_copiada_menos_as_da_edicao(self) -> None:
        self.assertEqual({}, self._diferencas("tournaments", "id", DUPLICATE_RESET_TOURNAMENT_COLUMNS | {"name"}))

    def test_toda_coluna_de_ajustes_e_copiada_menos_as_da_edicao(self) -> None:
        self.assertEqual(
            {}, self._diferencas("tournament_settings", "tournament_id", DUPLICATE_RESET_SETTINGS_COLUMNS)
        )

    def test_os_ajustes_de_organizacao_vem_junto(self) -> None:
        copia = self.db.get_tournament_settings(self.copia)
        for chave in ("prize_tie_split", "prize_exclude_withdrawn", "category_reference_date", "late_tolerance_minutes"):
            with self.subTest(chave=chave):
                self.assertEqual(AJUSTES[chave], copia[chave])

    def test_categorias_vem_junto_na_ordem(self) -> None:
        self.assertEqual(
            ["Sub-07", "Sub-09", "Feminino"], [c["name"] for c in self.db.list_tournament_categories(self.copia)]
        )
        self.assertEqual(
            [("category", "Sub-07")], [(p["kind"], p["category"]) for p in self.db.list_tournament_prizes(self.copia)]
        )

    def test_o_que_e_da_edicao_recomeca(self) -> None:
        copia = self.db.get_tournament_settings(self.copia)
        self.assertEqual(0, copia["archived"])
        for chave in ("fide_event_id", "chess_results_url", "cutoff_date"):
            with self.subTest(chave=chave):
                self.assertFalse(copia[chave])
        torneio = self.db.get_tournament(self.copia)
        self.assertEqual("draft", torneio["status"])
        self.assertEqual("Copia 2027", torneio["name"])
        self.assertIsNone(torneio["parent_tournament_id"])

    def test_a_copia_aparece_na_lista_mesmo_vindo_de_arquivado(self) -> None:
        self.assertIn(self.copia, [t["id"] for t in self.db.list_tournaments()])
        self.assertNotIn(self.origem, [t["id"] for t in self.db.list_tournaments()])

    def test_lista_de_exclusao_e_a_da_espec(self) -> None:
        self.assertEqual(
            frozenset({"id", "created_at", "start_date", "end_date", "status", "parent_tournament_id"}),
            DUPLICATE_RESET_TOURNAMENT_COLUMNS,
        )
        self.assertEqual(
            frozenset({"tournament_id", "updated_at", "archived", "fide_event_id", "chess_results_url",
                       "cutoff_date", "initial_color"}),
            DUPLICATE_RESET_SETTINGS_COLUMNS,
        )


if __name__ == "__main__":
    unittest.main()
