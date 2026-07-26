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

from ...components import debounce
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
from .ratings import OfficialRatingActions
from .state import (
    OFFICIAL_ID_FIELDS,
    PLAYER_FIELDS,
    PlayerForm,
    autofill_updates,
    field_labels,
    form_from_player,
    normalize_scheveningen_group,
    scheveningen_labels,
)

FIELD_WIDTH = 240


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
        host = self.host
        form = host._make_scrollable_panel(body, width=280)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        rotulos = field_labels()
        for indice, chave in enumerate(PLAYER_FIELDS):
            self._label(form, rotulos[chave], indice * 2)
            if chave == "birth_date":
                campo: Any = host._make_date_entry(form, width=28)
            elif chave == "category":
                campo = ctk.CTkOptionMenu(form, values=FIDE_CATEGORIES, width=FIELD_WIDTH)
                campo.set("")
            else:
                campo = ctk.CTkEntry(form, width=FIELD_WIDTH)
            campo.grid(row=indice * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            self.entries[chave] = campo
            if chave in OFFICIAL_ID_FIELDS:
                campo.bind(
                    "<FocusOut>", lambda _e, origem=chave: self._autofill_from_official(origem)
                )

        linha = len(PLAYER_FIELDS) * 2
        self._label(form, t("players.search"), linha, pady=(16, 0))
        self.search_entry = ctk.CTkEntry(
            form, width=FIELD_WIDTH, placeholder_text=t("players.search.hint")
        )
        self.search_entry.grid(row=linha + 1, column=0, padx=16, pady=(4, 8), sticky="ew")
        self.search_entry.bind("<KeyRelease>", debounce(self.search_entry, self.reload))

        self._label(form, self.controller.member_source_label(tournament), linha + 2, pady=(8, 0))
        self.member_option = ctk.CTkOptionMenu(
            form, values=[t("players.member.none")], width=FIELD_WIDTH
        )
        self.member_option.grid(row=linha + 3, column=0, padx=16, pady=(4, 4), sticky="ew")
        self.include_out_of_scope = ctk.CTkCheckBox(form, text=t("players.member.include_others"))
        self.include_out_of_scope.grid(row=linha + 4, column=0, padx=16, pady=(8, 4), sticky="w")
        self.include_out_of_scope.configure(command=self.reload_members)

        self._label(form, t("players.status"), linha + 5, pady=(8, 0))
        self.status_option = ctk.CTkOptionMenu(
            form, values=list(PLAYER_STATUS_VALUES.keys()), width=FIELD_WIDTH
        )
        self.status_option.grid(row=linha + 6, column=0, padx=16, pady=(4, 4), sticky="ew")
        self.status_option.set(PLAYER_STATUSES["active"])

        self._build_scheveningen(form, linha + 7)
        # +10 e não +7: os três widgets do Scheveningen ocupam 7, 8 e 9. A tela
        # antiga começava os botões em +7 e empilhava três deles **por cima**
        # dos seletores, na mesma célula do grid.
        self._build_buttons(form, linha + 10)

    def _build_scheveningen(self, form: Any, row: int) -> None:
        """Grupo do sistema Scheveningen — só faz sentido em torneio de dois times."""
        self._label(form, t("players.scheveningen"), row, pady=(8, 0))
        self.scheveningen_labels = scheveningen_labels()
        self.scheveningen_codes = {rotulo: codigo for codigo, rotulo in self.scheveningen_labels.items()}
        self.scheveningen_option = ctk.CTkOptionMenu(
            form, values=list(self.scheveningen_labels.values()), width=FIELD_WIDTH
        )
        self.scheveningen_option.grid(row=row + 1, column=0, padx=16, pady=(4, 4), sticky="ew")
        self.scheveningen_option.set(self.scheveningen_labels[""])
        botao = ctk.CTkButton(
            form, text=t("players.scheveningen.set"), command=self._set_scheveningen_group
        )
        botao.grid(row=row + 2, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.host._disable_if_unauthorized(botao, "tournament_write")

    def _build_buttons(self, form: Any, row: int) -> None:
        especificacoes: list[tuple[str, Any]] = [
            (t("players.action.add_guest"), self._add_player),
            (t("players.action.update"), self._update_player),
            (t("players.action.update_status"), self._update_status),
            (t("players.action.delete"), self._delete_player),
            (t("players.action.clear"), self.clear_form),
            (t("players.action.register_member"), self._register_member),
            (t("players.action.register_all"), self._register_all_members),
            (t("players.action.template_players"), lambda: self.imports.export_template("players")),
            (t("players.action.import_spreadsheet"), self.imports.import_spreadsheet),
            (t("players.action.template_online"), lambda: self.imports.export_template("online")),
            (t("players.action.share_form"), self.forms.share),
            (t("players.action.configure_form"), self.forms.configure),
            (t("players.action.generate_form"), self.forms.generate),
            (t("players.action.import_online"), self.imports.import_online_file),
            (t("players.action.import_online_url"), self.imports.import_online_url),
            (t("players.action.import_mapped"), self.imports.import_mapped_file),
            (t("players.action.import_mapped_url"), self.imports.import_mapped_url),
            (t("players.action.import_fide"), lambda: self.ratings.import_list("FIDE")),
            (t("players.action.import_cbx"), lambda: self.ratings.import_list("CBX")),
            (t("players.action.import_lbx"), lambda: self.ratings.import_list("LBX")),
            (t("players.action.import_foreign"), self.ratings.import_foreign_list),
            (t("players.action.update_lbx"), self.ratings.update_lbx_from_internet),
            (t("players.action.compare_official"), self.ratings.compare_with_players),
            (t("players.action.import_chess_results"), self.chess_results.import_entries),
            (t("players.action.publish_chess_results"), self.chess_results.prepare_upload),
        ]
        self.host._grid_form_buttons(
            form, especificacoes, row, required_action="tournament_write"
        )

    def _label(self, form: Any, text: str, row: int, pady: tuple[int, int] = (12, 0)) -> None:
        ctk.CTkLabel(form, text=text).grid(row=row, column=0, padx=16, pady=pady, sticky="w")

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
