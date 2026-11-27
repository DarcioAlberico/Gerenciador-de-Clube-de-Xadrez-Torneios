"""RGS-06 / RGS-33 — aceite de UI dos formulários com data.

- carregar `2010/05/12` e salvar sem tocar → banco com `2010-05-12`
  (a máscara antiga gravava `0512-10-20`);
- data incompleta → salvar recusado, banco inalterado (antes gravava vazio);
- editar o rating de um jogador com `birth_date="1985"` mantém `"1985"`
  (antes o `get()` devolvia `""` e o nascimento sumia — e com ele a categoria).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import TournamentService
from src.ui.app import AlbericusApp
from src.ui.components.fields import field_has_error
from src.ui.support import MaskedDateEntry
from tests.support.ctk_cleanup import cancel_pending_callbacks, create_tk_window, release_dead_ctk_windows

pytestmark = pytest.mark.gui


class FormulariosComDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.db = Database(base_path / "albericus.db", backup_dir=base_path / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Datas", "rounds_count": "3", "bye_points": "1"}
        )
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tournament_id
        self.errors: list[str] = []
        self.app._show_error = lambda error, *a, **kw: self.errors.append(str(error))
        self.app._show_toast = lambda *a, **kw: None
        self.app._show_info = lambda *a, **kw: None
        self.app.security_service.login("admin", "admin")
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            self.app.destroy()
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    # -- utilitários ---------------------------------------------------------
    def _sql(self, sql: str, *params: object) -> None:
        with self.db.connect() as conexao:
            conexao.execute(sql, params)

    @classmethod
    def _walk(cls, widget: object):
        yield widget
        for child in widget.winfo_children():  # type: ignore[attr-defined]
            yield from cls._walk(child)

    def _date_field(self, rotulo: str) -> MaskedDateEntry:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == rotulo:
                for irmao in widget.master.winfo_children():
                    if isinstance(irmao, MaskedDateEntry):
                        return irmao
        self.fail(f"Campo de data {rotulo!r} nao encontrado")

    def _click(self, texto: str) -> None:
        for widget in reversed(list(self._walk(self.app.content))):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == texto:
                widget.invoke()
                self.app.update()
                return
        self.fail(f"Botao {texto!r} nao encontrado")

    def _type(self, campo: MaskedDateEntry, digitos: str) -> None:
        campo.delete(0, "end")
        campo._entry.focus_force()
        self.app.update()
        for digito in digitos:
            campo._entry.event_generate("<KeyPress>", keysym=digito, when="now")
        self.app.update()

    # -- RGS-06 ----------------------------------------------------------------
    def test_data_legada_conversivel_e_salva_em_iso_sem_tocar(self) -> None:
        self._sql("UPDATE tournaments SET start_date = '2010/05/12' WHERE id = ?", self.tournament_id)
        self.app.show_tournament_settings()
        self.app.update()
        campo = self._date_field("Data inicial")
        self.assertEqual("12/05/2010", campo._entry.get())

        self._click("Salvar")

        self.assertEqual([], self.errors)
        self.assertEqual("2010-05-12", self.db.get_tournament(self.tournament_id)["start_date"])

    def test_data_incompleta_recusa_salvar_e_nao_muda_o_banco(self) -> None:
        self._sql("UPDATE tournaments SET start_date = '2026-11-13' WHERE id = ?", self.tournament_id)
        torneio_antes = self.db.get_tournament(self.tournament_id)
        ajustes_antes = self.db.get_tournament_settings(self.tournament_id)
        self.app.show_tournament_settings()
        self.app.update()
        campo = self._date_field("Data inicial")
        self._type(campo, "120520")
        self.assertEqual("12/05/20", campo._entry.get())

        self._click("Salvar")

        self.assertEqual(1, len(self.errors), self.errors)
        self.assertIn("12/05/20", self.errors[0])
        self.assertTrue(field_has_error(self._date_field("Data inicial")))
        self.assertEqual(torneio_antes, self.db.get_tournament(self.tournament_id))
        self.assertEqual(ajustes_antes, self.db.get_tournament_settings(self.tournament_id))

    def test_data_invalida_gravada_aparece_como_esta(self) -> None:
        self._sql("UPDATE tournaments SET end_date = '2026-02-30' WHERE id = ?", self.tournament_id)
        self.app.show_tournament_settings()
        self.app.update()
        campo = self._date_field("Data final")
        self.assertEqual("2026-02-30", campo._entry.get())
        self.assertTrue(field_has_error(campo))
        self._click("Salvar")
        self.assertEqual(1, len(self.errors))
        self.assertEqual("2026-02-30", self.db.get_tournament(self.tournament_id)["end_date"])

    # -- RGS-33 ----------------------------------------------------------------
    def test_atualizar_rating_mantem_o_ano_de_nascimento(self) -> None:
        jogador = self.db.create_player(self.tournament_id, name="Ana", rating=1500, birth_date="1985")
        categoria_antes = self.db.get_player(jogador)["category"]
        self.app.show_players()
        self.app.update()
        tela = self.app._tournament_players_view
        item = next(
            linha for linha in tela.tree.get_children() if int(tela.tree.item(linha, "values")[0]) == jogador
        )
        tela.tree.selection_set(item)
        tela._on_select()
        self.app.update()
        self.assertEqual("1985", tela.entries["birth_date"]._entry.get())

        tela.entries["rating"].delete(0, "end")
        tela.entries["rating"].insert(0, "1600")
        tela._update_player()
        self.app.update()

        self.assertEqual([], self.errors)
        atualizado = self.db.get_player(jogador)
        self.assertEqual(1600, int(atualizado["rating"]))
        self.assertEqual("1985", atualizado["birth_date"])
        self.assertEqual(categoria_antes, atualizado["category"])


if __name__ == "__main__":
    unittest.main()
