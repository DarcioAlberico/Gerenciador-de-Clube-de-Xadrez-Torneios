"""Tela de Jogadores: monta widgets e faz a ponte com o controlador (B-6).

Terceira camada do molde da F1.5, na segunda tela-monstro da fila. O que sobrou
aqui é só o que precisa de Tk: montar, ler campo, perguntar ao usuário,
redesenhar. Regra de formulário mora em [`state.py`](state.py); conversa com
banco e serviço, em [`controller.py`](controller.py); as importações e as bases
oficiais têm módulos próprios, porque cada uma delas é uma tela dentro da tela.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import FormStack, debounce, secondary_button
from ...i18n import t
from ...support import (
    FIDE_CATEGORIES,
    PLAYER_STATUS_VALUES,
    PLAYER_STATUSES,
    THEME_TEXT_SUB,
)
from .chess_results import ChessResultsActions
from .controller import TournamentPlayersController
from .forms import RegistrationFormActions
from .imports import PlayerImportActions
from .menu import player_actions
from .ratings import OfficialRatingActions
from .state import (
    OFFICIAL_ID_FIELDS,
    PLAYER_FIELDS,
    PLAYER_SECTIONS,
    PlayerForm,
    autofill_updates,
    field_hints,
    field_labels,
    form_from_player,
    normalize_scheveningen_group,
    scheveningen_labels,
    section_titles,
)


def columns() -> dict[str, tuple[str, int]]:
    """Colunas da tabela: código → (título, largura), na ordem de exibição."""
    return {
        "id": (t("players.column.id"), 60),
        "name": (t("players.field.name"), 250),
        "source": (t("players.column.source"), 90),
        "rating": (t("players.field.rating"), 80),
        "fide": (t("players.column.fide"), 90),
        "cbx": (t("players.column.cbx"), 90),
        "lbx": (t("players.column.lbx"), 90),
        "club": (t("players.column.club"), 150),
        "class": (t("players.column.class"), 130),
        "category": (t("players.field.category"), 120),
        "age_category": (t("players.column.age_category"), 90),
        "rating_category": (t("players.column.rating_category"), 95),
        "tags": (t("players.column.tags"), 170),
        "status": (t("players.column.status"), 90),
    }


def _read(widget: Any) -> str:
    """Texto de um campo, seja ele entrada ou seletor."""
    return str(widget.get() or "")


def _write(widget: Any, value: Any) -> None:
    """Escreve num campo respeitando o tipo do widget.

    Valor nulo vira string vazia, e não a palavra "None" — o bug que o piloto
    de Árbitros expôs e que esta tela também tinha.
    """
    texto = str(value or "")
    if isinstance(widget, ctk.CTkOptionMenu):
        widget.set(texto)
    elif hasattr(widget, "delete"):
        widget.delete(0, "end")
        if texto:
            widget.insert(0, texto)


class TournamentPlayersView:
    """Monta a tela de Jogadores sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any) -> None:
        self.host = host
        self.controller = TournamentPlayersController(
            host.db,
            member_service=host.member_service,
            pairing_service=host.pairing_service,
        )
        self.imports = PlayerImportActions(host, self.refresh)
        self.forms = RegistrationFormActions(host)
        self.ratings = OfficialRatingActions(host, self.reload)
        self.chess_results = ChessResultsActions(host, self.reload)
        self.entries: dict[str, Any] = {}
        self.member_map: dict[str, int] = {}
        self.selected_player_id: int | None = None

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    # ---- Montagem --------------------------------------------------------- #

    def build(self) -> None:
        host = self.host
        torneio = host.db.get_tournament(host.current_tournament_id)
        host._clear_content()
        host._page_title(
            t("players.title"),
            t(
                "players.subtitle",
                torneio=torneio["name"] if torneio else "",
                escopo=host._tournament_scope_text(torneio) if torneio else "",
            ),
        )
        host._build_tournament_nav("players")

        body = ctk.CTkFrame(host.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body, torneio)
        self._build_table(body)
        self.refresh()

    def _build_form(self, body: ctk.CTkFrame, tournament: dict[str, Any] | None) -> None:
        """Coluna do cadastro — ``FormStack``, sem a soma de linhas (F5.4).

        A aritmética que sustentava esta coluna (``indice * 2 + 1`` e depois um
        ``linha + 10``) já tinha cobrado o preço uma vez: a versão anterior
        começava os botões em ``+7`` e empilhava três deles **por cima** dos
        seletores do Scheveningen, na mesma célula do grid. Com a pilha, a
        próxima linha é a próxima linha — não há o que somar errado.
        """
        host = self.host
        form = host._make_scrollable_panel(body)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        pilha = FormStack(form)

        rotulos = field_labels()
        titulos = section_titles()
        dicas = field_hints()
        for chave_secao, campos in PLAYER_SECTIONS:
            pilha.section(titulos[chave_secao])
            for chave in campos:
                if chave == "birth_date":
                    campo: Any = pilha.date(rotulos[chave])
                elif chave == "category":
                    campo = pilha.select(rotulos[chave], list(FIDE_CATEGORIES))
                    campo.set("")
                else:
                    campo = pilha.text(rotulos[chave], placeholder=dicas.get(chave, ""))
                self.entries[chave] = campo
                if chave in OFFICIAL_ID_FIELDS:
                    campo.bind(
                        "<FocusOut>", lambda _e, origem=chave: self._autofill_from_official(origem)
                    )

        pilha.section(t("players.section.list"))
        self.search_entry = pilha.text(t("players.search"), placeholder=t("players.search.hint"))
        self.search_entry.bind("<KeyRelease>", debounce(self.search_entry, self.reload))

        self.member_option = pilha.select(
            self.controller.member_source_label(tournament), [t("players.member.none")]
        )
        self.include_out_of_scope = ctk.CTkCheckBox(form, text=t("players.member.include_others"))
        pilha.place(self.include_out_of_scope, "widget", sticky="w")
        self.include_out_of_scope.configure(command=self.reload_members)

        self.status_option = pilha.select(t("players.status"), list(PLAYER_STATUS_VALUES.keys()))
        self.status_option.set(PLAYER_STATUSES["active"])

        # Enter em qualquer campo do cadastro adiciona o jogador (F5.10): e o
        # gesto de quem digita uma lista inteira de inscritos.
        pilha.submit(self._add_player)
        self._build_scheveningen(form, pilha)
        self._build_buttons(form, pilha.row)

    def _build_scheveningen(self, form: Any, pilha: FormStack) -> None:
        """Grupo do sistema Scheveningen — só faz sentido em torneio de dois times."""
        self.scheveningen_labels = scheveningen_labels()
        self.scheveningen_codes = {rotulo: codigo for codigo, rotulo in self.scheveningen_labels.items()}
        self.scheveningen_option = pilha.select(
            t("players.scheveningen"), list(self.scheveningen_labels.values())
        )
        self.scheveningen_option.set(self.scheveningen_labels[""])
        botao = secondary_button(form, t("players.scheveningen.set"), self._set_scheveningen_group)
        pilha.place(botao, "widget")
        self.host._disable_if_unauthorized(botao, "tournament_write")

    def _action_handlers(self) -> dict[str, Any]:
        """Mapa ``chave -> callable`` das 25 acoes. O agrupamento fica em menu.py."""
        return {
            "add_guest": self._add_player,
            "update": self._update_player,
            "clear": self.clear_form,
            "update_status": self._update_status,
            "delete": self._delete_player,
            "register_member": self._register_member,
            "register_all": self._register_all_members,
            "template_players": lambda: self.imports.export_template("players"),
            "template_online": lambda: self.imports.export_template("online"),
            "import_spreadsheet": self.imports.import_spreadsheet,
            "import_online": self.imports.import_online_file,
            "import_online_url": self.imports.import_online_url,
            "import_mapped": self.imports.import_mapped_file,
            "import_mapped_url": self.imports.import_mapped_url,
            "share_form": self.forms.share,
            "configure_form": self.forms.configure,
            "generate_form": self.forms.generate,
            "import_fide": lambda: self.ratings.import_list("FIDE"),
            "import_cbx": lambda: self.ratings.import_list("CBX"),
            "import_lbx": lambda: self.ratings.import_list("LBX"),
            "import_foreign": self.ratings.import_foreign_list,
            "update_lbx": self.ratings.update_lbx_from_internet,
            "compare_official": self.ratings.compare_with_players,
            "import_chess_results": self.chess_results.import_entries,
            "publish_chess_results": self.chess_results.prepare_upload,
        }

    def _build_buttons(self, form: Any, row: int) -> None:
        self.host._grid_form_buttons(
            form,
            player_actions(self._action_handlers()),
            row,
            required_action="tournament_write",
        )

    def _build_table(self, body: ctk.CTkFrame) -> None:
        host = self.host
        painel = host._make_panel(body)
        painel.grid(row=0, column=1, sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(1, weight=1)

        self.summary_label = ctk.CTkLabel(painel, text="", text_color=THEME_TEXT_SUB)
        self.summary_label.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")

        suporte = ctk.CTkFrame(painel, fg_color="transparent")
        suporte.grid(row=1, column=0, sticky="nsew")
        suporte.grid_columnconfigure(0, weight=1)
        suporte.grid_rowconfigure(0, weight=1)
        colunas = columns()
        self.tree = host._make_tree(
            suporte,
            list(colunas),
            {codigo: titulo for codigo, (titulo, _) in colunas.items()},
            {codigo: largura for codigo, (_, largura) in colunas.items()},
        )
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # ---- Ponte com o estado ----------------------------------------------- #

    def current_form(self) -> PlayerForm:
        """Lê a tela e devolve o retrato congelado que o controlador valida."""
        valores = {chave: _read(self.entries[chave]) for chave in PLAYER_FIELDS}
        return PlayerForm(**valores, status=PLAYER_STATUS_VALUES[self.status_option.get()])

    def clear_form(self) -> None:
        self.selected_player_id = None
        for campo in self.entries.values():
            _write(campo, "")
        self.status_option.set(PLAYER_STATUSES["active"])

    def reload(self) -> None:
        """Recarrega a tabela e o resumo com o filtro corrente."""
        linhas, resumo = self.controller.rows(self.tournament_id, self.search_entry.get())
        self.tree.delete(*self.tree.get_children())
        for linha in linhas:
            self.tree.insert("", "end", values=linha.as_values())
        self.summary_label.configure(text=resumo.as_text())

    def reload_members(self) -> None:
        """Recarrega o seletor de sócios ainda não inscritos."""
        self.member_map = self.controller.member_options(
            self.tournament_id, include_out_of_scope=bool(self.include_out_of_scope.get())
        )
        valores = list(self.member_map) or [t("players.member.none")]
        self.member_option.configure(values=valores)
        self.member_option.set(valores[0])

    def refresh(self) -> None:
        """Tabela e sócios juntos — o que muda um quase sempre muda o outro."""
        self.reload()
        self.reload_members()

    def selected_player(self) -> dict[str, Any] | None:
        selecionado = self.tree.selection()
        if not selecionado:
            return None
        return self.controller.get_player(int(self.tree.item(selecionado[0], "values")[0]))

    def _on_select(self, _evento: Any = None) -> None:
        jogador = self.selected_player()
        if not jogador:
            return
        self.selected_player_id = int(jogador["id"])
        formulario = form_from_player(jogador)
        for chave in PLAYER_FIELDS:
            _write(self.entries[chave], getattr(formulario, chave))
        self.status_option.set(PLAYER_STATUSES.get(formulario.status, PLAYER_STATUSES["active"]))
        codigo = normalize_scheveningen_group(jogador.get("scheveningen_group"))
        self.scheveningen_option.set(self.scheveningen_labels[codigo])

    def _autofill_from_official(self, source_key: str) -> None:
        """Preenche o que está vazio a partir da base oficial, ao sair do campo."""
        try:
            oficial = self.controller.official_match(source_key, _read(self.entries[source_key]))
            if not oficial:
                return
            vazios = [chave for chave in PLAYER_FIELDS if not _read(self.entries[chave]).strip()]
            for chave, valor in autofill_updates(oficial, source_key, vazios).items():
                _write(self.entries[chave], valor)
        except Exception as exc:  # noqa: BLE001 — sair de um campo não pode derrubar a tela
            self.host._show_error(exc)

    # ---- Ações ------------------------------------------------------------ #

    def _add_player(self) -> None:
        try:
            formulario = self.current_form()
            erro = formulario.validation_error()
            if erro:
                raise self._app_error(erro)
            # Modo Livre: com rodadas encerradas, pergunta 0,0 ou meio-ponto por
            # rodada ausente. Fora dele devolve (True, None) e o cálculo padrão
            # de late_entry_points segue intacto.
            seguir, pontos_iniciais = self.host.prepare_late_entry(self.tournament_id)
            if not seguir:
                return
            self.controller.create(self.tournament_id, formulario, pontos_iniciais)
            self.clear_form()
            self.refresh()
        except Exception as exc:
            self.host._show_error(exc)

    def _update_player(self) -> None:
        try:
            if not self.selected_player_id:
                raise self._app_error(t("players.error.select_player"))
            self.controller.update(self.selected_player_id, self.current_form())
            self.reload()
        except Exception as exc:
            self.host._show_error(exc)

    def _update_status(self) -> None:
        try:
            jogador = self._require_selection()
            self.controller.set_status(
                int(jogador["id"]), PLAYER_STATUS_VALUES[self.status_option.get()]
            )
            self.reload()
        except Exception as exc:
            self.host._show_error(exc)

    def _set_scheveningen_group(self) -> None:
        try:
            jogador = self._require_selection()
            self.controller.set_scheveningen_group(
                int(jogador["id"]),
                self.scheveningen_codes.get(self.scheveningen_option.get(), ""),
            )
            self.reload()
            self.host._show_toast(t("players.scheveningen.done"), kind="success")
        except Exception as exc:
            self.host._show_error(exc)

    def _delete_player(self) -> None:
        try:
            jogador = self._require_selection()
            if not self.host._confirm_action(
                t("players.delete.title"), t("players.delete.question"), danger=True
            ):
                return
            self.controller.delete_if_unpaired(self.tournament_id, int(jogador["id"]))
            self.clear_form()
            self.refresh()
            self.host._show_toast(t("players.delete.done"), kind="success")
        except Exception as exc:
            self.host._show_error(exc)

    def _register_member(self) -> None:
        try:
            self.controller.register_member(
                self.tournament_id,
                self.member_map.get(self.member_option.get()),
                allow_out_of_scope=bool(self.include_out_of_scope.get()),
            )
            self.refresh()
        except Exception as exc:
            self.host._show_error(exc)

    def _register_all_members(self) -> None:
        try:
            resultado = self.controller.register_all_active_members(
                self.tournament_id,
                include_out_of_scope=bool(self.include_out_of_scope.get()),
            )
            self.refresh()
            self.host._show_info(
                t(
                    "players.member.registered_all",
                    inscritos=resultado["registered"],
                    ja_inscritos=resultado["skipped"],
                )
            )
        except Exception as exc:
            self.host._show_error(exc)

    def _require_selection(self) -> dict[str, Any]:
        jogador = self.selected_player()
        if not jogador:
            raise self._app_error(t("players.error.select_player"))
        return jogador

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)


class TournamentPlayersMixin:
    """Ponto de entrada da tela, no formato que a aplicação já espera."""

    def show_players(self) -> None:
        if not self._require_tournament():
            return
        self._tournament_players_view = TournamentPlayersView(self)
        self._tournament_players_view.build()
