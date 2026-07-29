"""Tela de Torneios: monta widgets e faz a ponte com o controlador (B-6).

Terceira camada do molde da F1.5, agora numa tela de verdade. O que sobrou aqui
é só o que precisa de Tk: montar, ler campo, perguntar ao usuário, redesenhar.
Regra de escopo mora em [`state.py`](state.py); conversa com serviço, em
[`controller.py`](controller.py).

O ganho concreto e verificável: a validação do formulário e a montagem das
linhas passaram a ter teste **sem abrir janela** — antes viviam dentro de
closures de 300 linhas, alcançáveis só clicando.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...support import (
    CLUB_KIND_LABELS,
    COMPETITION_TYPE_VALUES,
    COMPETITION_TYPES,
    THEME_TEXT_SUB,
    TOURNAMENT_SCOPE_VALUES,
    TOURNAMENT_SCOPES,
    filedialog,
)
from ...components import FormStack, danger_button, primary_button, secondary_button
from .controller import TournamentListController
from .state import TournamentForm, TournamentListState, scope_fields

# Colunas da lista: código → (título, largura). Uma estrutura só, em vez de três
# dicionários paralelos que precisavam ser editados juntos.
COLUMNS: dict[str, tuple[str, int]] = {
    "id": ("ID", 60),
    "name": ("Torneio", 230),
    "format": ("Formato", 85),
    "scope": ("Escopo", 95),
    "club": ("Clube/Escola", 150),
    "class": ("Turma", 130),
    "location": ("Local", 140),
    "rounds": ("Rodadas", 75),
    "status": ("Status", 95),
}

# Campos do formulário de criação, agrupados em seções (F5.4/P3-12): chave,
# rótulo e placeholder. O placeholder é parte da anatomia desde a F5.2 — a
# caixa vazia sem dica de formato era a regra em 94 dos 150 campos do app.
FORM_SECTIONS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "Identificação",
        (
            ("name", "Nome do torneio", "Ex.: Aberto de Verão 2026"),
            ("location", "Local", "Ex.: Clube Municipal de Xadrez"),
        ),
    ),
    (
        "Calendário e ritmo",
        (
            ("start_date", "Data inicial", ""),
            ("end_date", "Data final", ""),
            ("rounds_count", "Rodadas", "Ex.: 7"),
            ("time_control", "Ritmo", ""),
            ("bye_points", "Pontos do bye", "Ex.: 0,5"),
        ),
    ),
)


class TournamentListView:
    """Monta a tela de Torneios sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any) -> None:
        self.host = host
        self.state = TournamentListState()
        self.controller = TournamentListController(
            host.db,
            host.tournament_service,
            host.import_service,
            scope_labels=TOURNAMENT_SCOPES,
            competition_labels=COMPETITION_TYPES,
            scope_key=host._tournament_scope_key,
        )

    # ---- Montagem --------------------------------------------------------- #

    def build(self) -> None:
        host = self.host
        host._clear_content()
        host._page_title(
            "Torneios",
            "Crie um torneio e selecione-o para cadastrar jogadores e gerar rodadas.",
        )

        body = ctk.CTkFrame(host.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body)
        self._build_list(body)
        self.reload()

    def _build_form(self, body: ctk.CTkFrame) -> None:
        """Coluna de criação — hoje uma ``FormStack``, sem aritmética de linha.

        A conta de linha (``row=index * 2 + 1`` e um ``linha + 8`` no fim) era
        o que impedia inserir um campo no meio sem renumerar o resto: qualquer
        edição aqui pedia a soma inteira de novo. A pilha avança sozinha.
        """
        host = self.host
        form = host._make_scrollable_panel(body)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        pilha = FormStack(form)

        self.entries: dict[str, Any] = {}
        for titulo, campos in FORM_SECTIONS:
            pilha.section(titulo)
            for key, label, dica in campos:
                if key in ("start_date", "end_date"):
                    entry = pilha.date(label)
                elif key == "time_control":
                    entry = pilha.field(label, host._make_time_control_menu)
                else:
                    entry = pilha.text(label, placeholder=dica)
                self.entries[key] = entry
        self.entries["rounds_count"].insert(0, TournamentForm().rounds_count)
        self.entries["bye_points"].insert(0, TournamentForm().bye_points)

        pilha.section("Abrangência")
        self.scope_option = pilha.select("Escopo", list(TOURNAMENT_SCOPE_VALUES.keys()))
        self.scope_option.set(TOURNAMENT_SCOPES["standalone"])
        self.competition_option = pilha.select("Formato", list(COMPETITION_TYPE_VALUES.keys()))
        self.competition_option.set(COMPETITION_TYPES["individual"])

        self.club_map = self.controller.club_options(CLUB_KIND_LABELS)
        self.club_option = pilha.select("Clube/Escola", list(self.club_map.keys()))
        self.class_map: dict[str, int | None] = {"Sem turma": None}
        self.class_option = pilha.select("Turma", ["Sem turma"])

        self.scope_option.configure(command=lambda _v=None: self._apply_scope())
        self.club_option.configure(command=lambda _v=None: self._reload_classes())
        self._reload_classes()
        self._apply_scope()

        btn_create = primary_button(form, "Criar torneio", self._create)
        pilha.place(btn_create, "section")
        host._disable_if_unauthorized(btn_create, "tournament_write")

        btn_import = secondary_button(form, "Importar TRF (Swiss-Manager)", self._import_trf)
        pilha.place(btn_import, "widget")
        host._disable_if_unauthorized(btn_import, "tournament_write")

    def _build_list(self, body: ctk.CTkFrame) -> None:
        host = self.host
        panel = host._make_panel(body)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        self.tree = host._make_tree(
            panel,
            list(COLUMNS),
            {code: titulo for code, (titulo, _) in COLUMNS.items()},
            {code: largura for code, (_, largura) in COLUMNS.items()},
        )
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<Delete>", lambda _e: self._delete_selected())

        ctk.CTkLabel(
            panel,
            text="Atalhos: duplo clique seleciona; Del exclui o torneio selecionado.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=1, column=0, padx=12, pady=(8, 0), sticky="w")

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=12, sticky="e")
        ctk.CTkButton(actions, text="Selecionar", command=self._open_selected, width=110).pack(
            side="left", padx=(0, 8)
        )
        for texto, comando, largura in (
            ("Duplicar modelo", self._duplicate_selected, 140),
            ("Dividir", self._split_selected, 90),
        ):
            botao = ctk.CTkButton(actions, text=texto, command=comando, width=largura)
            botao.pack(side="left", padx=(0, 8))
            host._disable_if_unauthorized(botao, "tournament_write")
        btn_delete = danger_button(actions, "Excluir", self._delete_selected, width=90)
        btn_delete.pack(side="left")
        host._disable_if_unauthorized(btn_delete, "tournament_write")

    # ---- Ponte com o estado ----------------------------------------------- #

    def current_form(self) -> TournamentForm:
        """Lê a tela e devolve o retrato congelado que o controlador valida."""
        return TournamentForm(
            name=self.entries["name"].get(),
            scope=TOURNAMENT_SCOPE_VALUES[self.scope_option.get()],
            competition_type=COMPETITION_TYPE_VALUES[self.competition_option.get()],
            club_id=self.club_map.get(self.club_option.get()),
            class_id=self.class_map.get(self.class_option.get()),
            location=self.entries["location"].get(),
            rounds_count=self.entries["rounds_count"].get(),
            time_control=self.entries["time_control"].get(),
            start_date=self.entries["start_date"].get(),
            end_date=self.entries["end_date"].get(),
            bye_points=self.entries["bye_points"].get(),
        )

    def _apply_scope(self) -> None:
        campos = scope_fields(TOURNAMENT_SCOPE_VALUES[self.scope_option.get()])
        self.club_option.configure(state=campos.club_widget_state)
        self.class_option.configure(state=campos.class_widget_state)

    def _reload_classes(self, selected_id: int | None = None) -> None:
        self.class_map = self.controller.class_options(self.club_map.get(self.club_option.get()))
        valores = list(self.class_map)
        self.class_option.configure(values=valores)
        escolhido = next(
            (rotulo for rotulo, cid in self.class_map.items() if cid == selected_id), "Sem turma"
        )
        self.class_option.set(escolhido)

    def reload(self) -> None:
        self.state.rows = self.controller.rows()
        self.tree.delete(*self.tree.get_children())
        for linha in self.state.rows:
            self.tree.insert("", "end", values=linha.as_values())

    def selected_id(self) -> int | None:
        selecionado = self.tree.selection()
        if not selecionado:
            return None
        self.state.selected_id = int(self.tree.item(selecionado[0], "values")[0])
        return self.state.selected_id

    # ---- Ações ------------------------------------------------------------ #

    def _create(self) -> None:
        try:
            tournament_id = self.controller.create(self.current_form())
            self.host._set_current_tournament(tournament_id)
            self.host.show_players()
        except Exception as exc:
            self.host._show_error(exc)

    def _import_trf(self) -> None:
        try:
            caminho = filedialog.askopenfilename(
                title="Importar torneio do Swiss-Manager (TRF)",
                filetypes=[("Arquivos TRF", "*.trf"), ("Todos os arquivos", "*.*")],
            )
            if not caminho:
                return
            resultado = self.controller.import_trf(caminho)
            self.host._set_current_tournament(resultado["tournament_id"])
            self.host._show_toast(
                f"Torneio '{resultado['name']}' importado com "
                f"{resultado['players_imported']} jogadores.",
                kind="success",
            )
            self.host.show_players()
        except Exception as exc:
            self.host._show_error(exc)

    def _open_selected(self) -> None:
        tournament_id = self.selected_id()
        if not tournament_id:
            return
        self.host._set_current_tournament(tournament_id)
        self.host.show_players()

    def _duplicate_selected(self) -> None:
        try:
            tournament_id = self._require_selection("duplicar")
            novo_nome = self.host._ask_string("Duplicar torneio", "Nome do novo torneio:")
            if novo_nome is None:
                return
            self.host._set_current_tournament(self.controller.duplicate(tournament_id, novo_nome))
            self.reload()
            self.host._show_info(
                "Torneio duplicado. Ajuste data, local e participantes conforme necessario."
            )
        except Exception as exc:
            self.host._show_error(exc)

    def _delete_selected(self) -> None:
        try:
            tournament_id = self._require_selection("excluir")
            nome = self.controller.display_name(tournament_id)
            if not self.host._confirm_action(
                "Excluir torneio",
                f"Excluir o torneio '{nome}' e todos os jogadores/rodadas vinculados?",
                danger=True,
            ):
                return
            self.controller.delete(tournament_id)
            if self.host.current_tournament_id == tournament_id:
                self.host.current_tournament_id = None
                self.host.current_round_id = None
                self.host.tournament_label.configure(text="Nenhum torneio selecionado")
            self.reload()
            self.host._show_toast("Torneio excluido.", kind="success")
        except Exception as exc:
            self.host._show_error(exc)

    def _split_selected(self) -> None:
        try:
            tournament_id = self._require_selection("dividir")
            resposta = self.host._ask_string("Dividir torneio", "Em quantos grupos (2 ou mais)?")
            if resposta is None:
                return
            grupos = self.controller.split(tournament_id, resposta)
            self.reload()
            self.host._show_info(
                f"Torneio dividido em {len(grupos)} grupos (A, B, ...) por ranking inicial."
            )
        except Exception as exc:
            self.host._show_error(exc)

    def _require_selection(self, acao: str) -> int:
        tournament_id = self.selected_id()
        if not tournament_id:
            from src.services.constants import AppError

            raise AppError(f"Selecione um torneio para {acao}.")
        return tournament_id


class TournamentListMixin:
    """Ponto de entrada da tela, no formato que a aplicação já espera."""

    def show_tournaments(self) -> None:
        self._tournament_list_view = TournamentListView(self)
        self._tournament_list_view.build()
