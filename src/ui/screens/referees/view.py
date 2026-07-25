"""Tela de Árbitros — só montagem de widgets e ligação com o controlador.

Piloto da F1.5: a view não decide nada. Ela lê o formulário dos widgets, entrega
ao :class:`RefereesController` e escreve de volta o que ele devolver. Toda a
regra vive em ``controller.py``/``state.py``, que são testáveis sem janela.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .controller import RefereesController
from .state import CAMPOS_TEXTO, CATEGORIA_PADRAO, CATEGORIAS, RefereeForm

COLUNAS = ["id", "name", "category", "fide_id", "cbx_id", "active"]
TITULOS = {
    "id": "ID",
    "name": "Nome",
    "category": "Cat.",
    "fide_id": "FIDE",
    "cbx_id": "CBX",
    "active": "Ativo",
}
LARGURAS = {"id": 50, "name": 200, "category": 60, "fide_id": 80, "cbx_id": 80, "active": 60}


class RefereePagesMixin:
    def show_referees(self) -> None:
        self._clear_content()
        self._page_title("Árbitros", "Gerenciamento da equipe de arbitragem.")

        controller = RefereesController(self.referee_service, self.db)
        # Estado da tela num dataclass, nao num dicionario de uma chave ao
        # lado dos widgets (P0-3) — e por isso que da para testar sem janela.
        form_atual = RefereeForm()

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form_panel = self._make_scrollable_panel(body, width=292)
        form_panel.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        for indice, (chave, rotulo) in enumerate(CAMPOS_TEXTO):
            ctk.CTkLabel(form_panel, text=rotulo).grid(
                row=indice * 2, column=0, padx=16, pady=(12, 0), sticky="w"
            )
            entrada = ctk.CTkEntry(form_panel, width=270)
            entrada.grid(row=indice * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            entries[chave] = entrada

        linha_opcoes = len(CAMPOS_TEXTO) * 2
        ctk.CTkLabel(form_panel, text="Categoria").grid(
            row=linha_opcoes, column=0, padx=16, pady=(12, 0), sticky="w"
        )
        category_option = ctk.CTkOptionMenu(form_panel, values=list(CATEGORIAS), width=270)
        category_option.grid(row=linha_opcoes + 1, column=0, padx=16, pady=(4, 2), sticky="ew")

        active_check = ctk.CTkCheckBox(form_panel, text="Ativo")
        active_check.grid(row=linha_opcoes + 2, column=0, padx=16, pady=(10, 2), sticky="w")
        active_check.select()

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(list_panel, COLUNAS, TITULOS, LARGURAS)
        tree.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        # -- ponte widgets <-> estado -------------------------------------

        def ler_form() -> RefereeForm:
            """Widgets -> dataclass. Unico lugar que le a tela."""
            valores = {chave: entrada.get() for chave, entrada in entries.items()}
            return form_atual.with_values(
                category=category_option.get(),
                active=bool(active_check.get()),
                **valores,
            )

        def escrever_form(form: RefereeForm) -> None:
            """Dataclass -> widgets. Unico lugar que escreve na tela."""
            nonlocal form_atual
            form_atual = form
            for chave, entrada in entries.items():
                entrada.delete(0, "end")
                entrada.insert(0, getattr(form, chave))
            category_option.set(form.category or CATEGORIA_PADRAO)
            active_check.select() if form.active else active_check.deselect()

        def carregar_lista() -> None:
            tree.delete(*tree.get_children())
            for linha in controller.rows():
                tree.insert("", "end", values=linha.as_values())

        def ao_selecionar(_event: Any = None) -> None:
            selecionado = tree.selection()
            if not selecionado:
                return
            referee_id = int(tree.item(selecionado[0], "values")[0])
            form = controller.load(referee_id)
            if form is not None:
                escrever_form(form)

        def novo() -> None:
            escrever_form(RefereeForm())

        def salvar() -> None:
            try:
                controller.save(ler_form())
                novo()
                carregar_lista()
                self._show_toast("Árbitro salvo com sucesso.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        self._grid_form_buttons(
            form_panel,
            [("Novo árbitro", novo), ("Salvar árbitro", salvar)],
            linha_opcoes + 3,
        )
        tree.bind("<<TreeviewSelect>>", ao_selecionar)
        carregar_lista()
