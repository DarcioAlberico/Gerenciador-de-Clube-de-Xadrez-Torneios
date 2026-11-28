"""RG2-18 — categoria "até X" pode aceitar quem está abaixo, se o edital disser.

Antes, cada jogador ficava com UMA categoria por dimensão — a mais estreita: o
menino de 2017 com 1300 era só "Sub-10; Sub-1400", e os prêmios Sub-12 e
Sub-1800 iam para o 2º, mesmo quando o edital deixava o Sub-10 disputá-los. O
docstring prometia "se o edital deixar", mas não havia onde dizer.

**D2** (decidida pelo dono em 2026-11-28): cada categoria ganha "aceita quem
está abaixo" — na idade, quem é mais novo; no rating, quem tem rating menor —,
**desligado** por padrão. Desligado, nada muda. Ligado, a categoria entra nas
categorias premiáveis do jogador junto com a mais estreita; a trava "um prêmio
por jogador" do RG2-16 continua valendo.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from tkinter import TclError

import pytest

from src.core.categories import competition_category_payload
from src.core.database import Database
from src.services.categories import default_categories
from src.services.categories.definition import CategoryDefinition
from src.services.prizes import allocate_prizes
from tests.support.core_service_base import CoreServiceTestCase
from tests.support.ctk_cleanup import cancel_pending_callbacks, create_tk_window, release_dead_ctk_windows


def _edital(ligadas: tuple[str, ...] = ()) -> list[dict]:
    return [
        {
            "name": item.name,
            "kind": item.kind,
            "min_value": item.min_value,
            "max_value": item.max_value,
            "sex": item.sex,
            "tag": item.tag,
            "awards": item.awards,
            "accepts_below": item.name in ligadas,
        }
        for item in default_categories()
    ]


class DesligadaEIgualAHojeTest(unittest.TestCase):
    """Caracterização: com a opção desligada, as categorias são as de antes."""

    JOGADORES = [
        {"birth_date": "2017", "rating": 1300, "sex": "M"},
        {"birth_date": "2014", "rating": 1750, "sex": "F"},
        {"birth_date": "1970", "rating": 2300, "sex": "M"},
        {"birth_date": "", "rating": 0, "sex": ""},
    ]

    def test_padrao_e_edital_com_a_opcao_desligada_dao_o_mesmo(self) -> None:
        desligado = [CategoryDefinition(**{**vars(item), "accepts_below": False}) for item in default_categories()]
        for jogador in self.JOGADORES:
            with self.subTest(jogador=jogador):
                self.assertEqual(
                    competition_category_payload(**jogador, year=2026),
                    competition_category_payload(**jogador, year=2026, definitions=desligado),
                )

    def test_o_menino_de_2017_continua_so_sub10_e_sub1400(self) -> None:
        payload = competition_category_payload(birth_date="2017", rating=1300, year=2026, sex="M")
        self.assertEqual("Sub-10; Sub-1400", payload["categories"])


class LigadaTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        with self.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET start_date = '2026-03-01' WHERE id = ?", (self.tournament_id,))
        self.menino = self.db.create_player(self.tournament_id, name="Menino", birth_date="2017", rating=1300)
        self.segundo = self.db.create_player(self.tournament_id, name="Segundo", birth_date="2014", rating=1700)

    def _categorias(self, player_id: int) -> str:
        return str(self.db.get_player(player_id)["categories"])

    def test_ligada_no_sub12_e_no_sub1800_o_menino_disputa_as_duas(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, _edital(("Sub-12", "Sub-1800")))
        self.assertEqual("Sub-10; Sub-12; Sub-1400; Sub-1800", self._categorias(self.menino))
        self.assertEqual("Sub-10", self.db.get_player(self.menino)["category"], "a principal segue a mais estreita")

    def test_desligada_nada_muda(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, _edital())
        self.assertEqual("Sub-10; Sub-1400", self._categorias(self.menino))

    def test_premio_respeita_a_trava_do_rg2_16(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, _edital(("Sub-12", "Sub-1800")))
        classificacao = [
            {"player_id": self.menino, "position": 1, "points": 5, **self._linha(self.menino)},
            {"player_id": self.segundo, "position": 2, "points": 4, **self._linha(self.segundo)},
        ]
        premios = [
            {"kind": "category", "label": "Sub-12", "category": "Sub-12", "rank_from": 1, "rank_to": 1, "amount": 100},
            {"kind": "category", "label": "Sub-1800", "category": "Sub-1800", "rank_from": 1, "rank_to": 1, "amount": 100},
        ]
        acumula = allocate_prizes(classificacao, premios, policy="cumulative")
        self.assertEqual({self.menino: 200.0}, {a["player_id"]: a["gross"] for a in acumula["allocations"]})
        um_so = allocate_prizes(classificacao, premios, policy="best_only")
        self.assertEqual(
            {self.menino: 100.0, self.segundo: 100.0}, {a["player_id"]: a["gross"] for a in um_so["allocations"]}
        )

    def test_faixa_com_minimo_aceita_o_mais_novo_so_ligada(self) -> None:
        """Sub-12 de 11 a 12 anos: o de 9 só entra com a opção ligada."""
        edital = [{"name": "Sub-12", "kind": "age", "min_value": 11, "max_value": 12}]
        self.tournament_service.replace_categories(self.tournament_id, edital)
        self.assertNotIn("Sub-12", self._categorias(self.menino))
        self.tournament_service.replace_categories(
            self.tournament_id, [{**edital[0], "accepts_below": True}], confirmed=True
        )
        self.assertIn("Sub-12", self._categorias(self.menino))
        self.assertNotEqual("Sub-12", self.db.get_player(self.menino)["category"], "a faixa ampliada não vira a principal")

    def test_a_opcao_volta_do_banco(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, _edital(("Sub-12",)))
        ligadas = {row["name"] for row in self.db.list_tournament_categories(self.tournament_id) if row["accepts_below"]}
        self.assertEqual({"Sub-12"}, ligadas)

    def _linha(self, player_id: int) -> dict:
        jogador = self.db.get_player(player_id)
        return {"name": jogador["name"], "category": jogador["category"], "categories": jogador["categories"]}


class MigracaoTest(unittest.TestCase):
    def test_banco_antigo_ganha_a_coluna_desligada(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "albericus.db"
            db = Database(caminho, backup_dir=Path(pasta) / "b")
            torneio = db.create_tournament("T", rounds_count=3)
            db.replace_tournament_categories(torneio, [{"name": "Sub-12", "kind": "age", "max_value": 12}])
            with closing(sqlite3.connect(caminho)) as conexao:
                conexao.execute("ALTER TABLE tournament_categories DROP COLUMN accepts_below")
                conexao.execute("PRAGMA user_version = 61")
                conexao.commit()
            db = Database(caminho, backup_dir=Path(pasta) / "b")
            (linha,) = db.list_tournament_categories(torneio)
            self.assertEqual(0, linha["accepts_below"])



@pytest.mark.gui
class EditorDeCategoriasTest(unittest.TestCase):
    def setUp(self) -> None:
        import customtkinter as ctk

        try:
            self.janela = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            self.skipTest(f"Tk indisponivel: {exc}")

    def tearDown(self) -> None:
        cancel_pending_callbacks(self.janela)
        try:
            self.janela.destroy()
        except TclError:  # pragma: no cover - janela já fechada pelo Tk
            pass
        release_dead_ctk_windows()

    def test_o_interruptor_vai_e_volta(self) -> None:
        from src.ui.screens.tournament_widgets import CategoryEditor

        editor = CategoryEditor(
            self.janela,
            [
                {"name": "Sub-12", "kind": "age", "max_value": 12, "accepts_below": 1},
                {"name": "Sub-10", "kind": "age", "max_value": 10},
            ],
        )
        self.assertEqual([True, False], [row["accepts_below"] for row in editor.get_rows()])
        editor._widgets[1]["accepts_below"].select()
        self.assertEqual([True, True], [row["accepts_below"] for row in editor.get_rows()])


if __name__ == "__main__":
    unittest.main()
