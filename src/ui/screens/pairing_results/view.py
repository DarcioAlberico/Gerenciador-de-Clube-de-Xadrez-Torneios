"""O mixin da tela de Rodadas — a casca que sobrou (B-6).

Quarta tela-monstro migrada pela **B-6** (1.850 linhas num arquivo só). O que
ficou aqui é o que **é** a tela de Rodadas: a barra da rodada, a tabela de
mesas e o lançamento de resultado. Tudo que era outra coisa saiu para módulo
próprio — ver o [`__init__`](__init__.py) do pacote.

O import externo não mudou (``from .pairing_results import
PairingResultsMixin``), então o `PairingPagesMixin` e a `AlbericusApp` não
souberam da mudança.
"""
from __future__ import annotations

from ...support import *
from ...components import (
    FIELD_HEIGHT,
    Dialog,
    FormStack,
    Tooltip,
    actions_bar,
    choice_dialog,
    danger_button,
    debounce,
    menu_button,
    primary_button,
    reason_dialog,
    secondary_button,
    select_field,
)
from ...components.wrap_row import WrapRow

from src.services.pairing.corrections import (
    DEFAULT_UNLOCK_MINUTES,
    cascade_message,
    cascade_rounds,
    correction_reason_error,
    unlock_reason_error,
)

from .exports import RoundExportActions
from .initial_call import InitialCallSection
from .projector import ProjectorWindow
from .qr import QrResultActions
from .swaps import BoardSwapActions
from .state import (
    RESULT_COLUMN_INDEX,
    RESULT_SHORTCUTS,
    allowed_results,
    first_pending_index,
    format_pairing_preview,
    individual_result_state,
    needs_round_count_warning,
    recommended_rounds_for_players,
    result_state_tag,
    team_board_result_state,
)


class PairingResultsMixin:
    def _round_export_menu_items(self):
        """Itens do menu 'Exportar' da rodada (exportacao/impressao)."""
        return [
            ("Exportar rodada", self._export_current_round_pairings),
            ("Imprimir rodada", self._print_current_round_pairings),
            None,
            ("Exportar sumulas", self._export_current_round_scoresheets),
            ("Imprimir sumulas", self._print_current_round_scoresheets),
            None,
            ("Exportar cartoes de mesa", self._export_table_cards),
        ]

    def _round_more_menu_items(self):
        """Itens do menu 'Mais' da rodada (pre-visualizacao, ajustes de mesa e QR)."""
        items = [
            ("Pre-visualizar proxima rodada", self._preview_next_round),
            ("Fechar rodada", self._close_current_round),
            None,
            ("Trocar cores da mesa", self._swap_selected_colors),
            ("Trocar jogador da mesa", self._open_player_swap_dialog),
            None,
            ("QR da mesa selecionada", self._show_selected_pairing_qr_link),
            ("Submissoes via QR", self._open_qr_submissions_queue),
            ("Servidor de resultados QR", self._start_qr_result_server),
        ]
        if self._is_free_mode():
            items += [None, ("Re-emparceirar (Modo Livre)", self.free_mode_repair_round)]
        return items

    def _build_round_toolbar(self, toolbar) -> None:
        """Barra de acoes hierarquica da tela de Rodadas (P1-1 / F2.1): primarias
        preenchidas, secundarias recolhidas em 'Exportar'/'Mais' e destrutiva isolada."""
        # Linha 1 - acao principal + menus de secundarias + destrutiva isolada a direita.
        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.grid(row=0, column=0, padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM), sticky="ew")
        actions.grid_columnconfigure(3, weight=1)  # espaco flexivel isola a acao destrutiva
        self._generate_round_button = primary_button(
            actions,
            "Gerar próxima rodada",
            self._generate_round,
            tip="Emparceira a próxima rodada a partir dos resultados ja lançados.",
        )
        self._generate_round_button.grid(row=0, column=0, padx=(0, SPACE_SM))
        menu_button(
            actions,
            "Exportar",
            self._round_export_menu_items(),
            tip="Exportar/imprimir a rodada, as sumulas e os cartoes de mesa.",
        ).grid(row=0, column=1, padx=(0, SPACE_SM))
        menu_button(
            actions,
            "Mais",
            self._round_more_menu_items(),
            tip="Pre-visualizar, fechar rodada, ajustes de mesa e ferramentas de QR.",
        ).grid(row=0, column=2, padx=(0, SPACE_SM))
        danger_button(
            actions,
            "Excluir rodada",
            self._delete_current_round,
            tip="Apaga a rodada selecionada e todos os resultados lançados nela.",
        ).grid(row=0, column=4, sticky="e")

        # Linha 2 - lancamento de resultados (fluxo mais frequente do dia a dia).
        #
        # **Faixa que quebra linha** (continuacao da B-8): esta era a linha que
        # definia o gargalo de largura do app — 1.220px, medidos no botao
        # "Limpar", que e o ultimo da fila. Sao dois seletores, uma primaria e
        # quatro botoes rapidos: em janela estreita nao havia como caber, e o
        # que sobrava para fora era justamente o "Limpar", a acao de desfazer.
        #
        # Aqui a `WrapRow` funciona (e no painel de arbitragem nao funcionava)
        # porque a faixa mede o `content`, que tem largura propria vinda da
        # janela — a barra da rodada ocupa a largura toda, nao uma coluna
        # estreita cuja largura depende da propria faixa.
        entry = WrapRow(toolbar)
        entry.grid(row=1, column=0, padx=SPACE_MD, pady=(0, SPACE_SM), sticky="ew")
        # Piloto da F5.2: seletores com anatomia de CAMPO (select_field) — mesma
        # altura dos botoes da linha; sao dados a escolher, nao acoes.
        self.round_option = entry.add(
            select_field(
                entry.frame,
                values=["Sem rodadas"],
                command=lambda _value: self._load_selected_round_pairings(),
                width=190,
            ),
            width=190,
        )
        Tooltip(self.round_option, "Escolhe qual rodada visualizar/editar.")
        self.result_option = entry.add(
            select_field(entry.frame, values=RESULTS, width=130), width=130
        )
        Tooltip(self.result_option, "Resultado a aplicar na mesa selecionada ao salvar.")
        entry.add(
            primary_button(
                entry.frame,
                "Salvar resultado",
                self._save_selected_result,
                tip="Grava o resultado escolhido na mesa selecionada.",
            ),
            width=160,
        )
        quick_tips = {
            "1-0": "Lanca vitoria das brancas na mesa selecionada.",
            "1/2-1/2": "Lanca empate na mesa selecionada.",
            "0-1": "Lanca vitoria das pretas na mesa selecionada.",
            "": "Limpa o resultado lancado na mesa selecionada.",
        }
        for label, result in [("1-0", "1-0"), ("1/2", "1/2-1/2"), ("0-1", "0-1"), ("Limpar", "")]:
            quick = entry.add(
                ctk.CTkButton(
                    entry.frame,
                    text=label,
                    width=64,
                    height=FIELD_HEIGHT,
                    command=lambda value=result: self._quick_save_result(value),
                ),
                width=64,
            )
            Tooltip(quick, quick_tips[result])
        # Arranja agora e a cada mudanca de largura da janela.
        entry.bind_to(self.content)

        # Linha 3 - modo apresentacao (destaque proprio, cor ambar dedicada).
        projector = ctk.CTkButton(
            toolbar,
            text="  📽  Modo Projetor",
            command=self._open_projector_mode,
            fg_color=THEME_WARNING,
            hover_color=THEME_WARNING_HOVER,
            text_color=THEME_ON_WARNING,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            height=44,
            corner_radius=8,
        )
        projector.grid(row=2, column=0, padx=SPACE_MD, pady=(0, SPACE_MD), sticky="ew")
        Tooltip(projector, "Abre a rodada atual em tela cheia para projeção na sala.")

    def show_pairings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        self.pairing_team_mode = bool(tournament and tournament.get("competition_type") == "team")
        show_initial_call = not self.db.list_rounds(self.current_tournament_id)
        self._clear_content()
        self._page_title(
            "Rodadas e resultados",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("pairings")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(0, weight=1)

        # Zerados a cada montagem: a tela e reconstruida e os botoes antigos morrem —
        # sem isto, _run_background tentaria reabilitar um widget destruido.
        self._generate_round_button = None
        self._preview_round_button = None

        if show_initial_call:
            # Antes da 1a rodada nao ha rodada para editar/exportar: so gerar e pre-visualizar.
            launch = ctk.CTkFrame(toolbar, fg_color="transparent")
            launch.grid(row=0, column=0, padx=SPACE_MD, pady=SPACE_MD, sticky="w")
            self._generate_round_button = primary_button(
                launch,
                "Gerar próxima rodada",
                self._generate_round,
                tip="Emparceira a primeira rodada com os jogadores presentes na chamada inicial.",
            )
            self._generate_round_button.pack(side="left", padx=(0, SPACE_SM))
            self._preview_round_button = secondary_button(
                launch,
                "Pre-visualizar rodada",
                self._preview_next_round,
                tip="Mostra como ficaria o emparceiramento da primeira rodada sem grava-lo.",
            )
            self._preview_round_button.pack(side="left")
        else:
            self._build_round_toolbar(toolbar)

        if show_initial_call:
            # A chamada inicial e OUTRA tela: antes da primeira rodada nao ha
            # rodada para editar nem exportar. Ela tem dono desde a B-6
            # ([`initial_call`](pairing_results/initial_call.py)) — aqui ficou
            # so a decisao de qual das duas telas montar.
            self._initial_call_section = InitialCallSection(self)
            self._initial_call_section.build(body)
            return

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        if self.pairing_team_mode:
            self.pairing_tree = self._make_tree(
                table_panel,
                ["match", "white_team", "match_result", "black_team", "board", "white", "result", "state", "black"],
                {
                    "match": "Match",
                    "white_team": "Equipe A",
                    "match_result": "Placar",
                    "black_team": "Equipe B",
                    "board": "Tab.",
                    "white": "Brancas",
                    "result": "Resultado",
                    "state": "Estado",
                    "black": "Pretas",
                },
                {
                    "match": 70,
                    "white_team": 170,
                    "match_result": 110,
                    "black_team": 170,
                    "board": 60,
                    "white": 230,
                    "result": 105,
                    "state": 120,
                    "black": 230,
                },
            )
        else:
            self.pairing_tree = self._make_tree(
                table_panel,
                ["board", "white", "white_rating", "result", "state", "black", "black_rating"],
                {
                    "board": "Mesa",
                    "white": "Brancas",
                    "white_rating": "Rating",
                    "result": "Resultado",
                    "state": "Estado",
                    "black": "Pretas",
                    "black_rating": "Rating",
                },
                {
                    "board": 70,
                    "white": 260,
                    "white_rating": 90,
                    "result": 110,
                    "state": 120,
                    "black": 260,
                    "black_rating": 90,
                },
            )
        self._configure_result_state_tags(self.pairing_tree)
        self.pairing_tree.bind("<<TreeviewSelect>>", self._on_pairing_select)
        self.pairing_tree.bind("<ButtonRelease-1>", lambda _event: self.pairing_tree.focus_set())
        self.pairing_tree.bind("1", lambda event: self._quick_save_result("1-0"))
        self.pairing_tree.bind("<KP_1>", lambda event: self._quick_save_result("1-0"))
        self.pairing_tree.bind("0", lambda event: self._quick_save_result("0-1"))
        self.pairing_tree.bind("<KP_0>", lambda event: self._quick_save_result("0-1"))
        self.pairing_tree.bind("-", lambda event: self._quick_save_result("1/2-1/2"))
        self.pairing_tree.bind("<KP_Subtract>", lambda event: self._quick_save_result("1/2-1/2"))
        self.pairing_tree.bind("<BackSpace>", lambda event: self._quick_save_result(""))
        self.pairing_tree.bind("<Delete>", lambda event: self._quick_save_result(""))
        self.pairing_tree.bind("<Return>", lambda event: self._save_selected_result())
        self._bind_pairing_result_shortcuts()
        self.pairing_tree.focus_set()
        self._load_round_options()

    # ---- Chamada inicial: ponte para a secao (B-6) ------------------------- #

    def _initial_call(self) -> InitialCallSection:
        """A secao da chamada inicial em exibicao, ou uma nova se nao houver.

        Delegadores finos e nao repasse automatico: o teste de janela chama
        `app._load_initial_players()` e `app.initial_players_tree` — o contrato
        externo da tela nao muda porque o interior foi reorganizado.
        """
        secao = getattr(self, "_initial_call_section", None)
        if secao is None:
            secao = InitialCallSection(self)
            self._initial_call_section = secao
        return secao

    def _load_initial_players(self) -> None:
        self._initial_call().reload()

    def _export_initial_player_list(self) -> None:
        self._initial_call().export_list()

    def _print_initial_player_list(self) -> None:
        self._initial_call().print_list()

    # ---- Exportacoes da rodada: ponte para o modulo (B-6) ------------------ #

    def _round_exports(self) -> RoundExportActions:
        return RoundExportActions(self)

    def _require_current_round(self) -> int:
        return self._round_exports().require_round()

    def _export_current_round_pairings(self) -> None:
        self._round_exports().export_pairings()

    def _print_current_round_pairings(self) -> None:
        self._round_exports().print_pairings()

    def _export_current_round_scoresheets(self) -> None:
        self._round_exports().export_scoresheets()

    def _print_current_round_scoresheets(self) -> None:
        self._round_exports().print_scoresheets()

    def _export_table_cards(self) -> None:
        self._round_exports().export_table_cards()

    def _load_round_options(self) -> None:
        if not hasattr(self, "round_option"):
            return
        rounds = self.db.list_rounds(self.current_tournament_id)
        self.round_option_map = {}
        if not rounds:
            self.current_round_id = None
            self.round_option.configure(values=["Sem rodadas"])
            self.round_option.set("Sem rodadas")
            self.pairing_row_map = {}
            self.pairing_detail_map = {}
            if hasattr(self, "pairing_tree"):
                self.pairing_tree.delete(*self.pairing_tree.get_children())
            return

        values = []
        for round_data in rounds:
            label = f"Rodada {round_data['number']} - {round_data['status']}"
            values.append(label)
            self.round_option_map[label] = round_data["id"]

        self.round_option.configure(values=values)
        first = values[0]
        self.round_option.set(first)
        self.current_round_id = self.round_option_map[first]
        self._load_selected_round_pairings()

    def _load_selected_round_pairings(self) -> None:
        if not hasattr(self, "pairing_tree"):
            return
        selected_label = self.round_option.get()
        self.current_round_id = self.round_option_map.get(selected_label)
        self.pairing_tree.delete(*self.pairing_tree.get_children())
        self.pairing_row_map = {}
        self.pairing_detail_map = {}
        if not self.current_round_id:
            return
        if getattr(self, "pairing_team_mode", False):
            self._load_selected_team_round()
            return
        pairings = self.db.get_pairings_for_round(self.current_round_id)
        submissions_by_pairing, corrected_pairing_ids, _corrected_team_board_ids = self._result_state_context()
        for row_index, pairing in enumerate(pairings):
            white_name = pairing_player_name(pairing, "white")
            black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
            state = self._individual_result_state(pairing, submissions_by_pairing, corrected_pairing_ids)
            result_val = str(pairing["result"] or "")
            zebra = "oddrow" if row_index % 2 == 0 else "evenrow"
            item_id = self.pairing_tree.insert(
                "",
                "end",
                values=(
                    pairing["board_number"],
                    white_name,
                    pairing["white_rating"],
                    result_val,
                    state,
                    black_name,
                    "" if pairing["is_bye"] else pairing["black_rating"],
                ),
                tags=(self._result_state_tag(state), zebra),
            )
            self.pairing_row_map[item_id] = pairing["id"]
            self.pairing_detail_map[item_id] = {
                **pairing,
                "row_type": "individual_pairing",
                "white_display_name": white_name,
                "black_display_name": black_name,
                "result_state": state,
            }
        self._select_first_pending_pairing()

    def _load_selected_team_round(self) -> None:
        if not self.current_round_id:
            return
        matches = self.db.list_team_matches_for_round(self.current_round_id)
        _submissions_by_pairing, _corrected_pairing_ids, corrected_team_board_ids = self._result_state_context()
        for match in matches:
            black_team_name = "BYE" if match["is_bye"] else str(match.get("black_team_name") or "")
            match_result = ""
            if match.get("result"):
                match_result = str(match["result"])
                if match["result"] != "BYE":
                    match_result = (
                        f"{match['white_game_points']}-{match['black_game_points']} "
                        f"({match['white_match_points']}-{match['black_match_points']})"
                    )
            if match["is_bye"]:
                item_id = self.pairing_tree.insert(
                    "",
                    "end",
                    values=(
                        match["match_number"],
                        match["white_team_name"],
                        "BYE",
                        black_team_name,
                        "",
                        "",
                        "BYE",
                        "bloqueado" if match.get("round_status") == "closed" else "registrado",
                        "",
                    ),
                    tags=(self._result_state_tag("bloqueado" if match.get("round_status") == "closed" else "registrado"),),
                )
                self.pairing_detail_map[item_id] = {**match, "row_type": "team_bye"}
                continue

            for board in self.db.list_team_boards(int(match["id"])):
                white_name = player_pairing_name(
                    {
                        "name": board.get("white_player_name"),
                        "surname": board.get("white_player_surname"),
                        "given_name": board.get("white_player_given_name"),
                    }
                )
                black_name = player_pairing_name(
                    {
                        "name": board.get("black_player_name"),
                        "surname": board.get("black_player_surname"),
                        "given_name": board.get("black_player_given_name"),
                    }
                )
                state = self._team_board_result_state(board, corrected_team_board_ids, str(match.get("round_status") or ""))
                item_id = self.pairing_tree.insert(
                    "",
                    "end",
                    values=(
                        match["match_number"],
                        match["white_team_name"],
                        match_result,
                        black_team_name,
                        board["board_number"],
                        white_name,
                        board["result"],
                        state,
                        black_name,
                    ),
                    tags=(self._result_state_tag(state),),
                )
                self.pairing_row_map[item_id] = int(board["id"])
                self.pairing_detail_map[item_id] = {
                    **board,
                    "row_type": "team_board",
                    "team_match_id": int(match["id"]),
                    "white_team_name": match["white_team_name"],
                    "black_team_name": black_team_name,
                    "white_display_name": white_name,
                    "black_display_name": black_name,
                    "result_state": state,
                }
        self._select_first_pending_pairing()

    def _result_state_context(self) -> tuple[dict[int, dict[str, Any]], set[int], set[int]]:
        tournament_id = int(self.current_tournament_id)
        submissions_by_pairing: dict[int, dict[str, Any]] = {}
        for submission in self.db.list_result_submissions(tournament_id=tournament_id, limit=5000):
            pairing_id = int(submission["pairing_id"])
            if pairing_id not in submissions_by_pairing:
                submissions_by_pairing[pairing_id] = submission
        corrected_pairing_ids = {
            int(event["entity_id"])
            for event in self.db.list_audit_events(
                tournament_id,
                action="result_corrected",
                entity_type="pairing",
                limit=5000,
            )
            if event.get("entity_id") is not None
        }
        corrected_team_board_ids = {
            int(event["entity_id"])
            for event in self.db.list_audit_events(
                tournament_id,
                action="team_result_corrected",
                entity_type="team_board",
                limit=5000,
            )
            if event.get("entity_id") is not None
        }
        return submissions_by_pairing, corrected_pairing_ids, corrected_team_board_ids

    # Em que estado esta um resultado e dado puro (B-6): mora em
    # [`state`](pairing_results/state.py), com teste em milissegundos. Aqui
    # ficam so os nomes que a tela ja usava.
    _individual_result_state = staticmethod(individual_result_state)
    _team_board_result_state = staticmethod(team_board_result_state)
    _result_state_tag = staticmethod(result_state_tag)

    @staticmethod
    def _configure_result_state_tags(tree: ttk.Treeview) -> None:
        """Pinta as tags da tabela na aparencia atual.

        As cores vem de RESULT_STATE_COLORS (theme.py) e passam por pick(): o
        ttk aceita uma cor so, e antes isto era um bloco de literais de modo
        escuro — no tema claro a tabela ficava escura no meio da tela clara.
        """
        import platform
        familia = "Segoe UI" if platform.system() == "Windows" else "Helvetica"
        _bold = (familia, 10, "bold")
        _normal = (familia, 10)

        # Linhas alternadas (zebra)
        tree.tag_configure("oddrow", background=pick(THEME_TREE_ODD), font=_normal)
        tree.tag_configure("evenrow", background=pick(THEME_TREE_EVEN), font=_normal)

        # Estados do resultado — negrito, menos o "vazio" e o "anulado"
        for estado, (texto, fundo) in RESULT_STATE_COLORS.items():
            opcoes = {
                "foreground": pick(texto),
                "font": _normal if estado in ("vazio", "anulado") else _bold,
            }
            if fundo is not None:
                opcoes["background"] = pick(fundo)
            tree.tag_configure(f"result_state_{estado}", **opcoes)

        # Resultado lancado
        tree.tag_configure("result_win_white", foreground=pick(THEME_RESULT_WIN), font=_bold)
        tree.tag_configure("result_win_black", foreground=pick(THEME_RESULT_WIN), font=_bold)
        tree.tag_configure("result_draw", foreground=pick(THEME_RESULT_DRAW), font=_bold)
        tree.tag_configure("result_bye", foreground=pick(THEME_RESULT_BYE), font=_normal)

    def _select_first_pending_pairing(self) -> None:
        if not hasattr(self, "pairing_tree"):
            return
        children = list(self.pairing_tree.get_children())
        if not children:
            return
        modo = "team" if getattr(self, "pairing_team_mode", False) else "individual"
        linhas = [self.pairing_tree.item(item, "values") for item in children]
        selected_item = children[first_pending_index(linhas, RESULT_COLUMN_INDEX[modo])]
        self.pairing_tree.selection_set(selected_item)
        self.pairing_tree.focus(selected_item)
        self.pairing_tree.see(selected_item)
        self.pairing_tree.focus_set()

    def _selected_pairing_id(self) -> int | None:
        if not hasattr(self, "pairing_tree"):
            return None
        selected = self.pairing_tree.selection()
        if not selected:
            return None
        return self.pairing_row_map.get(selected[0])

    def _selected_pairing(self) -> dict[str, Any] | None:
        if not hasattr(self, "pairing_tree"):
            return None
        selected = self.pairing_tree.selection()
        if not selected:
            return None
        return self.pairing_detail_map.get(selected[0])

    def _on_pairing_select(self, _event: Any = None) -> None:
        selected = self.pairing_tree.selection()
        if not selected:
            return
        values = self.pairing_tree.item(selected[0], "values")
        result = values[6] if getattr(self, "pairing_team_mode", False) and len(values) > 6 else values[3] if len(values) > 3 else ""
        if result in allowed_results(self._selected_pairing()):
            self.result_option.set(result)

    def _bind_pairing_result_shortcuts(self) -> None:
        self._pairing_shortcuts_enabled = True
        for sequence, result in RESULT_SHORTCUTS.items():
            self.bind(sequence, lambda event, value=result: self._quick_save_result_from_screen(value))
        self.bind("<Return>", self._save_selected_result_from_screen)

    def _pairing_shortcuts_active(self) -> bool:
        if not getattr(self, "_pairing_shortcuts_enabled", False):
            return False
        if not hasattr(self, "pairing_tree") or not self.pairing_tree.winfo_exists():
            return False
        focus = self.focus_get()
        if focus is None:
            return True
        while focus is not None:
            if focus == self.content:
                return True
            focus = getattr(focus, "master", None)
        return False

    def _quick_save_result_from_screen(self, result: str) -> str | None:
        if not self._pairing_shortcuts_active():
            return None
        return self._quick_save_result(result)

    def _save_selected_result_from_screen(self, _event: Any = None) -> str | None:
        if not self._pairing_shortcuts_active():
            return None
        self._save_selected_result()
        return "break"

    _recommended_rounds_for_players = staticmethod(recommended_rounds_for_players)

    def _confirm_short_tournament_round_count(self) -> bool:
        if getattr(self, "pairing_team_mode", False):
            return True
        if self.db.list_rounds(self.current_tournament_id):
            return True
        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            return True
        players_count = len(self.db.list_players(self.current_tournament_id, active_only=True))
        recommended_rounds = recommended_rounds_for_players(players_count)
        configured_rounds = int(tournament.get("rounds_count") or 0)
        if not needs_round_count_warning(
            players_count=players_count,
            configured_rounds=configured_rounds,
            has_rounds=False,  # ja garantido acima
            team_mode=False,
        ):
            return True

        choice = self._confirm_or_cancel(
            "Rodadas abaixo do recomendado",
            "Este torneio tem {players_count} jogadores ativos.\n\n"
            "Para esse número de jogadores, o mínimo recomendado é {recommended_rounds} rodadas. "
            "O torneio está configurado com {configured_rounds} rodadas.\n\n"
            "Sim: continuar mesmo assim\n"
            "Não: abrir Config. Torneio para ajustar\n"
            "Cancelar: voltar sem gerar rodada".format(
                players_count=players_count,
                recommended_rounds=recommended_rounds,
                configured_rounds=configured_rounds,
            ),
        )
        if choice is None:
            return False
        if choice is False:
            self.show_tournament_settings()
            return False
        return True

    def _generate_round(self) -> None:
        # Permissao e confirmacoes ficam na thread da UI (abrem modal); so o
        # emparceiramento em si vai para background — antes ele congelava a
        # janela por segundos em torneios grandes (P1-3 / ESPEC_UI_UX §5.2).
        try:
            self.require_permission("tournament_write")
            if not self._confirm_short_tournament_round_count():
                return
        except Exception as exc:
            self._show_error(exc)
            return
        tournament_id = self.current_tournament_id
        self._run_background(
            lambda: self.pairing_service.generate_next_round(tournament_id),
            on_success=lambda _result: self.show_pairings(),
            busy_message="Gerando emparceiramento...",
            busy_widget=getattr(self, "_generate_round_button", None),
        )

    def _preview_next_round(self) -> None:
        tournament_id = self.current_tournament_id
        self._run_background(
            lambda: self.pairing_service.preview_next_round(tournament_id),
            on_success=lambda preview: self._show_info(self._format_pairing_preview(preview)),
            busy_message="Simulando emparceiramento...",
            busy_widget=getattr(self, "_preview_round_button", None),
        )

    _format_pairing_preview = staticmethod(format_pairing_preview)

    def _save_selected_result(self) -> None:
        try:
            self.require_permission("tournament_write")
            pairing_id = self._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione um tabuleiro." if getattr(self, "pairing_team_mode", False) else "Selecione uma mesa.")
            pairing_detail = self._selected_pairing()
            result = self.result_option.get()
            allowed = set(RESULTS)
            if pairing_detail and pairing_detail.get("row_type") == "individual_pairing" and pairing_detail.get("is_bye"):
                allowed.update({"BYE", "F", "H", "Z"})
            if result not in allowed:
                raise AppError("Resultado invalido.")
                
            if pairing_detail and pairing_detail.get("row_type") == "individual_pairing" and pairing_detail.get("is_bye"):
                # Determine default bye result
                round_data = self.db.get_round(int(pairing_detail["round_id"]))
                round_number = int(round_data["number"]) if round_data else 1
                requested_byes = self.db.list_requested_byes_for_round(
                    int(self.current_tournament_id),
                    round_number
                )
                player_id = int(pairing_detail["white_player_id"])
                req_bye = next((rb for rb in requested_byes if int(rb["player_id"]) == player_id), None)
                default_result = req_bye["bye_type"] if req_bye else "BYE"
                
                if result != default_result:
                    choice = self._prompt_bye_edit_warning(default_result, result)
                    if choice == "cancel":
                        # Restore previous result in OptionMenu
                        self.result_option.set(pairing_detail.get("result") or "")
                        return
                    elif choice == "restore":
                        result = default_result
                        self.result_option.set(result)

            motivo = ""
            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    motivo = self._prompt_closed_round_correction(int(self.current_round_id))
                    if not motivo:
                        return
            self.pairing_service.update_result(
                self.current_tournament_id, pairing_id, result, motivo
            )
            self._load_selected_round_pairings()
            if motivo:
                self._warn_correction_cascade()
        except Exception as exc:
            self._show_error(exc)

    def _warn_correction_cascade(self) -> None:
        """Avisa na hora quando a correção alcança rodadas já pareadas (ARB-01).

        A pendência do painel guarda o mesmo recado, mas o árbitro que acabou de
        corrigir está **aqui** — e a decisão de reparear é agora, não na próxima
        vez que ele abrir a Central. Usa a mesma função pura do serviço, então os
        dois lugares não podem divergir.
        """
        rodada = self.db.get_round(int(self.current_round_id or 0))
        afetadas = cascade_rounds(
            self.db.list_rounds(int(self.current_tournament_id)),
            int((rodada or {}).get("number") or 0),
        )
        if afetadas:
            self._show_warning(cascade_message(int(rodada["number"]), afetadas))

    def _prompt_closed_round_correction(self, round_id: int) -> str:
        """Desbloqueio (se preciso) + motivo da correção. ``""`` = desistiu.

        Duas perguntas, e nessa ordem, porque são duas decisões diferentes:
        *abrir a rodada* (permissão, com prazo) e *o que aconteceu* (o registro
        que sustenta a decisão). Antes havia só um "Alterar mesmo assim?" — e a
        permissão vinha de um interruptor global do torneio que, ligado uma vez,
        deixava todas as rodadas fechadas editáveis.
        """
        estado = self.pairing_service.correction_unlock_state(
            int(self.current_tournament_id), round_id
        )
        if not estado.allowed:
            justificativa = reason_dialog(
                self,
                "Desbloquear rodada fechada",
                "Esta rodada está fechada. Para corrigir um resultado é preciso "
                f"desbloqueá-la: a permissão vale {DEFAULT_UNLOCK_MINUTES} minutos, "
                "fica registrada na auditoria e não afeta as outras rodadas.\n\n"
                "Por que a rodada precisa ser reaberta?",
                validate=unlock_reason_error,
                confirm_text="Desbloquear",
                danger=True,
            )
            if justificativa is None:
                return ""
            aberta = self.pairing_service.unlock_round_for_correction(
                int(self.current_tournament_id), round_id, justificativa
            )
            self._show_warning(
                f"Rodada desbloqueada para correção até {aberta['expires_at']}."
            )
            estado = self.pairing_service.correction_unlock_state(
                int(self.current_tournament_id), round_id
            )

        return reason_dialog(
            self,
            "Corrigir resultado de rodada fechada",
            # A primeira linha diz de onde vem a permissão e até quando ela vale:
            # numa segunda correção da mesma súmula o árbitro já entra aqui, e
            # precisa saber se está usando a janela ou o interruptor global.
            f"{estado.label()}\n\n"
            "A rodada está fechada e o resultado já entrou na classificação "
            "publicada. O motivo abaixo vai para a trilha de auditoria e para a "
            "ata — é o que sustenta a decisão numa apelação.\n\n"
            "O que aconteceu?",
            validate=correction_reason_error,
            confirm_text="Corrigir",
            danger=True,
        ) or ""

    def _prompt_bye_edit_warning(self, default_result: str, chosen_result: str) -> str:
        """Aviso de editar um BYE — o diálogo de cores contraditórias do P3-10.

        Ele tinha as três coisas que a auditoria apontou juntas: **saída segura
        pintada de verde** (a cor que o app usa para confirmar), a destrutiva
        no meio e Cancelar à direita, onde o olho procura a primária. Nada de
        Esc. Agora os três caminhos são declarados por *papel* e o componente
        escolhe posição e cor — a saída segura é a primária, "realmente editar"
        é a de perigo, e Esc cancela.
        """
        return str(
            choice_dialog(
                self,
                "Aviso: editar BYE",
                "Esta mesa é um BYE (sem oponente).\n"
                "Alterar o resultado para algo diferente do padrão pode causar "
                "inconsistências e impedir o fechamento correto da rodada.\n\n"
                f"Resultado padrão: '{default_result}'\n"
                f"Resultado escolhido: '{chosen_result or 'pendente'}'",
                options=[
                    ("Cancelar", "cancel", "secondary"),
                    ("Realmente editar", "edit", "danger"),
                    ("Voltar ao padrão", "restore", "primary"),
                ],
                default="cancel",
            )
        )

    # ---- Resultado por QR: ponte para o modulo (B-6) ----------------------- #

    def _qr_actions(self) -> QrResultActions:
        return QrResultActions(self)

    def _show_selected_pairing_qr_link(self) -> None:
        self._qr_actions().show_link()

    def _start_qr_result_server(self) -> None:
        self._qr_actions().start_server()

    def _approve_qr_submission(self, submission_id: int) -> None:
        self._qr_actions().approve(submission_id)

    def _reject_qr_submission(self, submission_id: int) -> None:
        self._qr_actions().reject(submission_id)

    def _open_qr_submissions_queue(self) -> None:
        self._qr_actions().open_queue()

    def _quick_save_result(self, result: str) -> str:
        try:
            if result not in RESULTS:
                raise AppError("Resultado invalido.")
            if not self._selected_pairing_id():
                return "break"
            self.result_option.set(result)
            selected_before = self.pairing_tree.selection()
            children_before = list(self.pairing_tree.get_children())
            selected_index = children_before.index(selected_before[0]) if selected_before else -1
            self._save_selected_result()
            if selected_index >= 0 and hasattr(self, "pairing_tree"):
                children = list(self.pairing_tree.get_children())
                next_index = selected_index + 1
                if 0 <= next_index < len(children):
                    next_item = children[next_index]
                    self.pairing_tree.selection_set(next_item)
                    self.pairing_tree.focus(next_item)
                    self.pairing_tree.see(next_item)
            return "break"
        except Exception as exc:
            self._show_error(exc)
            return "break"

    # ---- Trocas na mesa: ponte para o modulo (B-6) -------------------------- #

    def _board_swaps(self) -> BoardSwapActions:
        return BoardSwapActions(self)

    def _swap_selected_colors(self) -> None:
        self._board_swaps().swap_colors()

    def _open_player_swap_dialog(self) -> None:
        self._board_swaps().open_player_swap()

    def _open_team_player_swap_dialog(self) -> None:
        self._board_swaps().open_team_player_swap()

    def _close_current_round(self) -> None:
        try:
            self.require_permission("tournament_write")
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            self.pairing_service.close_round(self.current_tournament_id, self.current_round_id)
            self._load_round_options()
            self._show_toast("Rodada fechada.", kind="success")
        except Exception as exc:
            self._show_error(exc)

    def _delete_current_round(self) -> None:
        try:
            self.require_permission("tournament_write")
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            if not self._confirm_action("Confirmar", "Excluir a rodada selecionada?", danger=True):
                return
            self.pairing_service.delete_generated_round(self.current_round_id)
            self._load_round_options()
        except Exception as exc:
            self._show_error(exc)

    def _projector_rows(self) -> list[dict[str, str]]:
        """As mesas da rodada no formato que a projecao mostra.

        Le o banco e devolve dado plano; quem desenha e o
        [`ProjectorWindow`](pairing_results/projector.py). No modo equipes cada
        tabuleiro vira uma linha, com o nome da equipe ao lado do jogador —
        na parede, "Silva" sem a equipe nao diz de quem e o ponto.
        """
        if not self.current_round_id:
            return []
        linhas: list[dict[str, str]] = []
        if getattr(self, "pairing_team_mode", False):
            for match in self.db.list_team_matches_for_round(self.current_round_id):
                if match["is_bye"]:
                    linhas.append(
                        {
                            "board": f"M{match['match_number']}",
                            "white": match["white_team_name"],
                            "black": "BYE",
                        }
                    )
                    continue
                for board in self.db.list_team_boards(int(match["id"])):
                    branco = player_pairing_name(
                        {
                            "name": board.get("white_player_name"),
                            "surname": board.get("white_player_surname"),
                            "given_name": board.get("white_player_given_name"),
                        }
                    )
                    preto = player_pairing_name(
                        {
                            "name": board.get("black_player_name"),
                            "surname": board.get("black_player_surname"),
                            "given_name": board.get("black_player_given_name"),
                        }
                    )
                    linhas.append(
                        {
                            "board": f"M{match['match_number']} T{board['board_number']}",
                            "white": f"{branco} ({match['white_team_name']})",
                            "black": f"{preto} ({match['black_team_name']})",
                        }
                    )
        else:
            for pairing in self.db.get_pairings_for_round(self.current_round_id):
                linhas.append(
                    {
                        "board": str(pairing["board_number"]),
                        "white": pairing_player_name(pairing, "white"),
                        "black": "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black"),
                    }
                )
        return linhas

    def _open_projector_mode(self) -> ProjectorWindow | None:
        """Abre o Modo Projetor. Devolve a janela — o smoke a fecha depois."""
        try:
            if not self.current_round_id:
                raise AppError("Selecione uma rodada primeiro.")
            linhas = self._projector_rows()
            if not linhas:
                raise AppError("Não há emparceiramentos nesta rodada para exibir.")
        except Exception as exc:
            self._show_error(exc)
            return None
        return ProjectorWindow(self, linhas)
