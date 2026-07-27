"""Casca comum dos três cadastros TRF25 — formulário à esquerda, tabela à direita.

Ajustes de pontos, byes solicitados e proibições de pareamento são a **mesma
tela** três vezes: um formulário estreito, uma tabela larga, um rodapé com
Atualizar / Remover / Voltar, e exclusão com Desfazer. No arquivo de 1.527
linhas isso estava escrito três vezes, o que significa que uma correção feita
numa delas podia não chegar às outras — e não chegava: só um dos três rodapés
tinha o botão destrutivo destacado.

Aqui a casca é uma só. O que cada cadastro tem de próprio (campos, colunas,
CRUD, textos) mora numa subclasse de [`RegistryPage`](page.py), e é lá que a
diferença entre individual e equipes fica visível.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import WrapRow, danger_button, primary_button, secondary_button
from ...i18n import t
from ...support import THEME_TEXT_SUB
from .page import Field, RegistryPage

FIELD_WIDTH = 260


class RegistryView:
    """Monta um cadastro TRF25 sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any, page: RegistryPage) -> None:
        self.host = host
        self.page = page
        self.widgets: dict[str, Any] = {}
        self.tree: Any = None
        self.row_by_iid: dict[str, int] = {}

    # ---- Montagem --------------------------------------------------------- #

    def build(self) -> None:
        host = self.host
        host._clear_content()
        host._page_title(self.page.title(), self.page.subtitle())
        host._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(host.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body)
        self._build_table(body)
        self.refresh()

    def _build_form(self, body: ctk.CTkFrame) -> None:
        host = self.host
        form = host._make_panel(body)
        form.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        host._section_title(form, self.page.form_title()).grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w"
        )

        linha = 1
        for campo in self.page.fields():
            ctk.CTkLabel(form, text=campo.label).grid(
                row=linha, column=0, padx=16, pady=(8, 0), sticky="w"
            )
            widget = self._build_field(form, campo)
            widget.grid(row=linha + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            self.widgets[campo.key] = widget
            linha += 2

        dica = self.page.hint()
        if dica:
            ctk.CTkLabel(form, text=dica, justify="left", text_color=THEME_TEXT_SUB).grid(
                row=linha, column=0, padx=16, pady=(10, 0), sticky="w"
            )
            linha += 1

        primary_button(form, t("arbitration.common.add"), self._add).grid(
            row=linha, column=0, padx=16, pady=(14, 14), sticky="ew"
        )

    def _build_field(self, form: ctk.CTkFrame, campo: Field) -> Any:
        if campo.kind == Field.OPTION:
            seletor = ctk.CTkOptionMenu(form, values=list(campo.values), width=FIELD_WIDTH)
            if campo.initial:
                seletor.set(campo.initial)
            return seletor
        return ctk.CTkEntry(form, width=FIELD_WIDTH, placeholder_text=campo.placeholder)

    def _build_table(self, body: ctk.CTkFrame) -> None:
        host = self.host
        panel = host._make_panel(body)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        host._section_title(panel, self.page.table_title()).grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )

        holder = ctk.CTkFrame(panel, fg_color="transparent")
        holder.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        colunas = self.page.columns()
        self.tree = host._make_tree(
            holder,
            list(colunas),
            {chave: titulo for chave, (titulo, _largura) in colunas.items()},
            {chave: largura for chave, (_titulo, largura) in colunas.items()},
            visible_rows=16,
        )

        # Rodapé que quebra linha (B-8): três botões numa linha rígida somam
        # ~430px e eram parte do que segurava o limiar da sidebar.
        rodape = WrapRow(panel)
        rodape.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        rodape.add(
            secondary_button(rodape.frame, t("arbitration.common.refresh"), self.refresh, width=120),
            120,
        )
        rodape.add(
            danger_button(
                rodape.frame,
                t("arbitration.common.remove_selected"),
                self._delete_selected,
                width=170,
            ),
            170,
        )
        rodape.add(
            secondary_button(
                rodape.frame,
                t("arbitration.common.back_to_panel"),
                host.show_arbitration_panel,
                width=140,
            ),
            140,
        )
        rodape.bind_to(host.content)

    # ---- Ponte ------------------------------------------------------------ #

    def refresh(self) -> None:
        tree = self.tree
        if tree is None:
            return
        for filho in tree.get_children():
            tree.delete(filho)
        self.row_by_iid.clear()
        for indice, (record_id, valores) in enumerate(self.page.rows(), start=1):
            iid = str(indice)
            self.row_by_iid[iid] = int(record_id)
            tree.insert("", "end", iid=iid, values=valores)

    def _values(self) -> dict[str, str]:
        return {chave: str(widget.get() or "") for chave, widget in self.widgets.items()}

    def _add(self) -> None:
        try:
            self.page.add(self._values())
        except Exception as exc:
            self.host._show_error(exc)
            return
        for chave in self.page.clear_on_add():
            widget = self.widgets.get(chave)
            if widget is not None and hasattr(widget, "delete"):
                widget.delete(0, "end")
        self.host._show_toast(self.page.added_message(), kind="success")
        self.refresh()

    def _delete_selected(self) -> None:
        try:
            selecionado = self.tree.selection() if self.tree is not None else ()
            if not selecionado:
                raise self._app_error(self.page.select_error())
            record_id = self.row_by_iid[selecionado[0]]
            titulo, mensagem = self.page.confirm_texts()
            if not self.host._confirm_action(titulo, mensagem, danger=True):
                return
            # Retrato tirado ANTES da exclusão: é o que o Desfazer recria (F2.4).
            # Estes são registros-folha (ninguém depende deles), então o id novo
            # diferir do original não muda nada para quem olha a tela.
            retrato = self.page.snapshot(record_id)
            self.host._delete_with_undo(
                lambda: self.page.delete(record_id),
                (lambda: self.page.restore(retrato)) if retrato else None,
                self.page.removed_message(),
                self.refresh,
            )
        except Exception as exc:
            self.host._show_error(exc)

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
