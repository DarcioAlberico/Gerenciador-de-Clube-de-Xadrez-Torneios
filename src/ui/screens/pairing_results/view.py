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

from src.services.friendly_mode import FRIENDLY_MODE_LABEL
from src.services.pairing.corrections import round_deletion_reason_error

import queue
import tkinter
from tkinter import TclError

from ...support import _unbind_exact

from src.services.snapshot_reconciler import SnapshotReconciler

from .exports import RoundExportActions
from .initial_call import InitialCallSection
from .projector import ProjectorWindow
from .knockout import KnockoutActions
from .qr import QrResultActions
from .swaps import BoardSwapActions
from .correction import ResultCorrectionActions
from .state import (
    RESULT_COLUMN_INDEX,
    RESULT_SHORTCUTS,
    WALKOVER_SHORTCUTS,
    PrimaryRoundAction,
    allowed_results,
    first_pending_index,
    format_pairing_preview,
    individual_result_state,
    needs_round_count_warning,
    primary_round_action,
    recommended_rounds_for_players,
    result_state_tag,
    results_counter_text,
    team_board_result_state,
)

# Rótulo do botão do toast de lançamento (RGS-21): diz o atalho junto, para o
# árbitro aprender o Ctrl+Z sem abrir manual.
UNDO_LABEL = "Desfazer (Ctrl+Z)"

# Onde as teclas são do campo, e não da tela (RGS-21). O foco do CTkEntry e do
# CTkTextbox cai no Entry/Text de dentro deles.
_CAIXAS_DE_TEXTO = (tkinter.Entry, tkinter.Text, tkinter.Spinbox, ttk.Entry)


class PairingResultsMixin:
    def _round_export_menu_items(self):
        """Itens do menu 'Exportar' da rodada (exportacao/impressao)."""
        return [
            ("Exportar rodada", self._export_current_round_pairings),
            ("Imprimir rodada", self._print_current_round_pairings),
            None,
            ("Exportar súmulas", self._export_current_round_scoresheets),
            ("Imprimir súmulas", self._print_current_round_scoresheets),
            None,
            ("Exportar cartões de mesa", self._export_table_cards),
        ]

    def _round_more_menu_items(self):
        """Itens do menu 'Mais' da rodada (pre-visualizacao, ajustes de mesa e QR)."""
        items = [
            ("Pré-visualizar próxima rodada", self._preview_next_round),
            # "Fechar rodada" saiu daqui (RGS-25): fechava sem confirmar. Agora
            # e o estado do botão primário, com a confirmação das pendências.
            None,
            ("Trocar cores da mesa", self._swap_selected_colors),
            ("Trocar jogador da mesa", self._open_player_swap_dialog),
            None,
            # Mata-mata (PAR-03): a mesa empatada precisa de decisão registrada
            # para a próxima fase existir, e a chave e onde ela aparece depois.
            ("Registrar avanço (mata-mata)", self._open_knockout_advancement_dialog),
            ("Chave do mata-mata", self._show_knockout_bracket),
            None,
            ("QR da mesa selecionada", self._show_selected_pairing_qr_link),
            ("Submissões via QR", self._open_qr_submissions_queue),
            ("Servidor de resultados QR", self._start_qr_result_server),
        ]
        # MA-13: os itens do modo amistoso ficam sempre aqui e conferem a marca
        # no clique. Antes entravam só quando a barra era montada num torneio
        # já amistoso: ligar o modo em Configurações não os trazia.
        items += [
            None,
            (f"Re-emparceirar ({FRIENDLY_MODE_LABEL})", self.free_mode_repair_round),
            (f"Mais uma rodada ({FRIENDLY_MODE_LABEL})", self.free_mode_add_round),
        ]
        return items

    def _build_round_toolbar(self, toolbar) -> None:
        """Barra de ações hierárquica da tela de Rodadas (P1-1 / F2.1): primárias
        preenchidas, secundárias recolhidas em 'Exportar'/'Mais' e destrutiva isolada."""
        # Linha 1 - ação principal + menus de secundárias + destrutiva isolada a direita.
        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.grid(row=0, column=0, padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM), sticky="ew")
        actions.grid_columnconfigure(3, weight=1)  # espaço flexível isola a ação destrutiva
        # RGS-25: o botão primário diz o próximo passo da rodada — "Lançar
        # resultados (32/40)" → "Fechar rodada 3" → "Gerar rodada 4". Rótulo e
        # ação vem de `_refresh_round_progress`, a cada recarga da rodada.
        self._round_primary_button = primary_button(
            actions,
            "Lançar resultados",
            self._run_round_primary_action,
            tip="O próximo passo da rodada: lançar resultados, fechar a rodada (com confirmação) ou gerar a seguinte.",
        )
        self._round_primary_button.grid(row=0, column=0, padx=(0, SPACE_SM))
        # A geração em segundo plano ocupa este mesmo botão enquanto roda.
        self._generate_round_button = self._round_primary_button
        menu_button(
            actions,
            "Exportar",
            self._round_export_menu_items(),
            tip="Exportar/imprimir a rodada, as súmulas e os cartões de mesa.",
        ).grid(row=0, column=1, padx=(0, SPACE_SM))
        menu_button(
            actions,
            "Mais",
            self._round_more_menu_items(),
            tip="Pré-visualizar, ajustes de mesa e ferramentas de QR.",
        ).grid(row=0, column=2, padx=(0, SPACE_SM))
        # RGS-24: entrada tardia numa tela só (o mesmo assistente do Painel).
        secondary_button(
            actions,
            "Entrada tardia…",
            lambda: self.open_late_entry_dialog(refresh=self.show_pairings),
            tip="Inscreve quem chega depois da 1ª rodada: rodada de entrada e pontos das rodadas perdidas.",
        ).grid(row=0, column=3, padx=(0, SPACE_SM), sticky="w")
        danger_button(
            actions,
            "Excluir rodada",
            self._delete_current_round,
            tip="Apaga a rodada selecionada e todos os resultados lançados nela.",
        ).grid(row=0, column=4, sticky="e")

        # Linha 2 - lançamento de resultados (fluxo mais frequente do dia a dia).
        #
        # **Faixa que quebra linha** (continuação da B-8): esta era a linha que
        # definia o gargalo de largura do app — 1.220px, medidos no botão
        # "Limpar", que é o ultimo da fila. São dois seletores, uma primária e
        # quatro botões rápidos: em janela estreita não havia como caber, e o
        # que sobrava para fora era justamente o "Limpar", a ação de desfazer.
        #
        # Aqui a `WrapRow` funciona (e no painel de arbitragem não funcionava)
        # porque a faixa mede o `content`, que tem largura própria vinda da
        # janela — a barra da rodada ocupa a largura toda, não uma coluna
        # estreita cuja largura depende da própria faixa.
        entry = WrapRow(toolbar)
        entry.grid(row=1, column=0, padx=SPACE_MD, pady=(0, SPACE_SM), sticky="ew")
        # Piloto da F5.2: seletores com anatomia de CAMPO (select_field) — mesma
        # altura dos botões da linha; são dados a escolher, não ações.
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
        # Contador da rodada exibida (RGS-21): "32/40 lançadas".
        self._round_progress_label = entry.add(
            ctk.CTkLabel(entry.frame, text="", text_color=THEME_TEXT_SUB, anchor="w"),
            width=120,
        )
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
            "1-0": "Lança vitória das brancas na mesa selecionada.",
            "1/2-1/2": "Lança empate na mesa selecionada.",
            "0-1": "Lança vitória das pretas na mesa selecionada.",
            "": "Limpa o resultado lançado na mesa selecionada.",
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
        # Arranja agora e a cada mudança de largura da janela.
        entry.bind_to(self.content)

        # Linha 3 - modo apresentação (destaque próprio, cor âmbar dedicada).
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

        # Zerados a cada montagem: a tela e reconstruida e os botões antigos morrem —
        # sem isto, _run_background tentaria reabilitar um widget destruído.
        self._generate_round_button = None
        self._preview_round_button = None
        self._round_primary_button = None
        self._round_progress_label = None
        # Desfazer vale para o lançamento feito NESTA tela (RGS-21).
        self._last_result_entry = None

        if show_initial_call:
            # Antes da 1a rodada não há rodada para editar/exportar: só gerar e pré-visualizar.
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
                "Pré-visualizar rodada",
                self._preview_next_round,
                tip="Mostra como ficaria o emparceiramento da primeira rodada sem gravá-lo.",
            )
            self._preview_round_button.pack(side="left")
        else:
            self._build_round_toolbar(toolbar)

        if show_initial_call:
            # A chamada inicial e OUTRA tela: antes da primeira rodada não há
            # rodada para editar nem exportar. Ela tem dono desde a B-6
            # ([`initial_call`](pairing_results/initial_call.py)) — aqui ficou
            # só a decisão de qual das duas telas montar.
            self._initial_call_section = InitialCallSection(self)
            self._initial_call_section.build(body)
            return

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)
        # Aviso PERMANENTE da rodada (RGS-16/RGS-18): motor reserva ou rodada
        # que difere do holandês. Fica embaixo da tabela enquanto a rodada
        # estiver na tela; vazio, não ocupa espaço.
        self._round_notice_label = ctk.CTkLabel(
            body, text="", text_color=THEME_WARNING_TEXT, anchor="w", justify="left", wraplength=900,
        )

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
        # "break" (RG2-02): sem ele o Enter sobe até o atalho da tela, que grava
        # de novo — já na mesa seguinte, para onde o primeiro salvamento andou.
        self.pairing_tree.bind("<Return>", self._save_selected_result_from_tree)
        # W.O. por tecla (RGS-21): as letras do painel, com a mesma confirmação
        # que nomeia mesa e jogadores. Só na tabela — numa caixa de texto a
        # letra e letra.
        for tecla, resultado in WALKOVER_SHORTCUTS.items():
            self.pairing_tree.bind(tecla, lambda event, valor=resultado: self._quick_save_result(valor))
        # "Corrigir resultado…" (RGS-20): a ação mora na mesa. Clique direito,
        # Shift+F10 (a tecla de menu de contexto) e Ctrl+E abrem o MESMO
        # diálogo — sem menu no meio, que custaria uma ação a mais.
        for sequencia in ("<Button-3>", "<Shift-F10>", "<App>", "<Control-e>", "<Control-E>"):
            try:
                self.pairing_tree.bind(sequencia, self._open_result_correction)
            except TclError:  # tecla que esta plataforma não conhece (<App>)
                pass
        self._bind_pairing_result_shortcuts()
        self._bind_screen_undo()
        self.pairing_tree.focus_set()
        self._load_round_options()

    # ---- Chamada inicial: ponte para a seção (B-6) ------------------------- #

    def _initial_call(self) -> InitialCallSection:
        """A seção da chamada inicial em exibição, ou uma nova se não houver.

        Delegadores finos e não repasse automático: o teste de janela chama
        `app._load_initial_players()` e `app.initial_players_tree` — o contrato
        externo da tela não muda porque o interior foi reorganizado.
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

    # ---- Exportações da rodada: ponte para o módulo (B-6) ------------------ #

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
        # Fechar rodada pelo painel chega aqui com a tela de Rodadas já
        # desmontada: o atributo sobra, o widget não.
        if not hasattr(self, "round_option") or not self.round_option.winfo_exists():
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
            label = round_option_label(round_data)
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
        self._refresh_round_progress()
        if not self.current_round_id:
            return
        if getattr(self, "pairing_team_mode", False):
            self._load_selected_team_round()
            return
        self._show_round_notices()
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

    def _show_round_notices(self) -> None:
        """Motor reserva / divergência do holandês da rodada exibida (RGS-16/18)."""
        label = getattr(self, "_round_notice_label", None)
        if label is None or not label.winfo_exists():
            return
        avisos = self.pairing_service.round_pairing_notices(
            int(self.current_tournament_id), int(self.current_round_id)
        )
        if not avisos:
            label.configure(text="")
            label.grid_remove()
            return
        label.configure(text="\n".join(f"⚠ {aviso}" for aviso in avisos))
        label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

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
    # ficam só os nomes que a tela já usava.
    _individual_result_state = staticmethod(individual_result_state)
    _team_board_result_state = staticmethod(team_board_result_state)
    _result_state_tag = staticmethod(result_state_tag)

    @staticmethod
    def _configure_result_state_tags(tree: ttk.Treeview) -> None:
        """Pinta as tags da tabela na aparência atual.

        As cores vem de RESULT_STATE_COLORS (theme.py) e passam por pick(): o
        ttk aceita uma cor só, e antes isto era um bloco de literais de modo
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

        # Resultado lançado
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
        # Numa caixa de texto a tecla é do campo: "1", BackSpace, Enter e
        # Ctrl+Z não podem lançar, apagar nem desfazer o resultado da mesa.
        if isinstance(focus, _CAIXAS_DE_TEXTO):
            return False
        while focus is not None:
            if focus == self.content:
                return True
            focus = getattr(focus, "master", None)
        return False

    def _quick_save_result_from_screen(self, result: str) -> str | None:
        if not self._pairing_shortcuts_active():
            return None
        return self._quick_save_result(result)

    def _save_selected_result_from_tree(self, _event: Any = None) -> str:
        self._save_selected_result()
        return "break"

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
            has_rounds=False,  # já garantido acima
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
        # Permissão e confirmações ficam na thread da UI (abrem modal); só o
        # emparceiramento em si vai para background — antes ele congelava a
        # janela por segundos em torneios grandes (P1-3 / ESPEC_UI_UX §5.2).
        try:
            self.require_permission("tournament_write")
            if not self._confirm_short_tournament_round_count():
                return
            # MA-09: no limite de rodadas do modo amistoso, oferece mais uma.
            if not self.free_mode_offer_extra_round(self.current_tournament_id):
                return
        except Exception as exc:
            self._show_error(exc)
            return
        self._start_round_generation(self.current_tournament_id, reserve_engine=False)

    def _start_round_generation(
        self, tournament_id: int, *, reserve_engine: bool, forfeit_empty_teams: bool = False
    ) -> None:
        self._run_background(
            lambda: self.pairing_service.generate_next_round(
                tournament_id,
                reserve_engine=reserve_engine,
                forfeit_empty_teams=forfeit_empty_teams,
            ),
            on_success=lambda _result: self.show_pairings(),
            busy_message="Gerando emparceiramento...",
            busy_widget=getattr(self, "_generate_round_button", None),
            on_error=None if (reserve_engine or forfeit_empty_teams) else (
                lambda error: self._offer_round_way_out(tournament_id, error)
            ),
        )

    def _offer_round_way_out(self, tournament_id: int, error: Exception) -> bool:
        """A geração recusou com saída que é decisão do árbitro: pergunta qual.

        Recusa do Gacrux → motor reserva; equipe sem ninguém presente
        (EQ-02.4) → W.O. do confronto inteiro. Outro erro segue o caminho
        normal (``False``).
        """
        from src.services.pairing.team_swiss import TeamWithoutPlayersError
        from src.ui.components.dialogs import confirm_dialog

        if not isinstance(error, TeamWithoutPlayersError):
            return self._offer_reserve_engine(tournament_id, error)
        if confirm_dialog(
            self,
            "Equipe sem jogadores presentes",
            f"{error}\n\nConfirmar: a rodada sai com o W.O. do confronto inteiro. "
            "Cancelar: volte e registre o bye Z da equipe.",
            confirm_text="Confirmar o W.O.",
            cancel_text="Cancelar",
        ):
            self._start_round_generation(
                tournament_id, reserve_engine=False, forfeit_empty_teams=True
            )
        return True

    def _offer_reserve_engine(self, tournament_id: int, error: Exception) -> bool:
        """Recusa do Gacrux (RGS-03/19): pergunta se a rodada sai pelo motor reserva.

        Pontuação que o TRF não diz ou saída do motor que não confere: as duas
        são ``GacruxRefusal``. Devolve ``False`` para qualquer outro erro, que
        segue o caminho normal.
        """
        from src.services.pairing.gacrux_engine import GacruxRefusal
        from src.ui.components.dialogs import confirm_dialog

        if not isinstance(error, GacruxRefusal):
            return False
        if confirm_dialog(
            self,
            "Motor FIDE recusou a rodada",
            f"{error}\n\nA escolha fica registrada na auditoria do torneio.",
            confirm_text="Parear com o motor reserva",
            cancel_text="Cancelar",
        ):
            self._start_round_generation(tournament_id, reserve_engine=True)
        return True

    def _preview_next_round(self) -> None:
        tournament_id = self.current_tournament_id
        self._run_background(
            lambda: self.pairing_service.preview_next_round(tournament_id),
            on_success=lambda preview: self._show_info(self._format_pairing_preview(preview)),
            busy_message="Simulando emparceiramento...",
            busy_widget=getattr(self, "_preview_round_button", None),
        )

    _format_pairing_preview = staticmethod(format_pairing_preview)

    def _save_selected_result(self) -> bool:
        """Grava o resultado do campo na mesa selecionada. Devolve se seguiu.

        ``False`` quando nada foi feito (cancelou um aviso, recusa de regra): o
        lançamento por tecla só avança para a mesa seguinte quando esta foi
        resolvida — cancelar um W.O. e ver o cursor pular confunde.
        """
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
                raise AppError("Resultado inválido.")
                
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
                        return False
                    elif choice == "restore":
                        result = default_result
                        self.result_option.set(result)

            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    # RGS-20: rodada fechada vai para o diálogo único, já com o
                    # resultado escolhido — falta so o motivo + Enter. Eram dois
                    # diálogos e dois motivos (desbloquear, depois corrigir).
                    self._result_corrections().open(
                        int(pairing_id),
                        detail=pairing_detail,
                        preselect=result,
                        on_done=self._reload_current_round,
                    )
                    return True
            if not self._confirm_walkover_entry(result, pairing_detail):
                self.result_option.set((pairing_detail or {}).get("result") or "")
                return False
            anterior = self._current_entry_result(int(pairing_id))
            self.pairing_service.update_result(
                self.current_tournament_id, pairing_id, result, ""
            )
            self._load_selected_round_pairings()
            self._offer_result_undo(int(pairing_id), pairing_detail, applied=result, previous=anterior)
            return True
        except Exception as exc:
            self._show_error(exc)
            return False

    # ---- Desfazer, contador e W.O. por tecla (RGS-21) ---------------------- #

    def _confirm_walkover_entry(self, result: str, detail: dict[str, Any] | None) -> bool:
        """W.O. e decisao, nao transcricao: a confirmacao do painel (ARB-02)."""
        from ..pairing_arbitration.pending import CONFIRMED_RESULTS, confirm_walkover

        if result not in CONFIRMED_RESULTS:
            return True
        detail = detail or {}
        return confirm_walkover(
            self,
            result,
            mesa=detail.get("board_number", "?"),
            brancas=detail.get("white_display_name", "?"),
            pretas=detail.get("black_display_name", "?"),
        )

    def _current_entry_result(self, entry_id: int) -> str:
        """Resultado gravado agora na mesa (ou tabuleiro de equipes)."""
        if getattr(self, "pairing_team_mode", False):
            linha = self.db.get_team_board(entry_id)
        else:
            linha = self.db.get_pairing(entry_id)
        return str((linha or {}).get("result") or "")

    @staticmethod
    def _entry_label(detail: dict[str, Any] | None) -> str:
        detail = detail or {}
        if detail.get("row_type") == "team_board":
            return f"Tabuleiro {detail.get('board_number', '?')}"
        return f"Mesa {detail.get('board_number', '?')}"

    def _offer_result_undo(
        self, entry_id: int, detail: dict[str, Any] | None, *, applied: str, previous: str
    ) -> None:
        """Toast "Mesa 7 → 1-0 · Desfazer (Ctrl+Z)" depois de um lançamento.

        O botão do toast desfaz ESTE lançamento; o Ctrl+Z, o ultimo. Sem
        mudança (mesmo resultado de novo) não há o que desfazer.
        """
        if applied == previous:
            return
        rotulo = self._entry_label(detail)
        entrada = {
            "entry_id": entry_id,
            "applied": applied,
            "previous": previous,
            "label": rotulo,
            "done": False,
        }
        self._last_result_entry = entrada
        self._show_toast(
            f"{rotulo} → {applied or 'pendente'}",
            kind="success",
            action=(UNDO_LABEL, lambda: self._undo_result_entry(entrada)),
        )

    def _bind_screen_undo(self) -> None:
        """Ctrl+Z na tela de Rodadas inteira (RGS-21), e só enquanto ela existir.

        A janela e a única etiqueta de evento comum a todo widget da tela, e e
        nela que a tecla e ligada; a ligação sai junto com a tabela. Sem
        ``bind_all`` e sem Ctrl+Z sobrando na tela seguinte.
        """
        for sequencia in ("<Control-z>", "<Control-Z>"):
            funcid = self.bind(sequencia, self._undo_last_result_from_screen, add="+")
            self.pairing_tree.bind(
                "<Destroy>",
                lambda _event, seq=sequencia, ligacao=funcid: _unbind_exact(self, seq, ligacao),
                add="+",
            )

    def _undo_last_result_from_screen(self, event: Any = None) -> str | None:
        """Numa caixa de texto o Ctrl+Z e o desfazer do proprio campo."""
        if not self._pairing_shortcuts_active():
            return None
        return self._undo_last_result(event)

    def _undo_last_result(self, _event: Any = None) -> str:
        """Desfaz o ultimo lancamento desta tela (Ctrl+Z ou botao do toast)."""
        entrada = getattr(self, "_last_result_entry", None)
        if entrada is not None:
            self._undo_result_entry(entrada)
        return "break"

    def _undo_result_entry(self, entrada: dict[str, Any]) -> None:
        if entrada.get("done"):
            self._show_toast(f"{entrada['label']}: lançamento já desfeito.", kind="info")
            return
        try:
            self.require_permission("tournament_write")
            self.pairing_service.undo_result(
                self.current_tournament_id,
                int(entrada["entry_id"]),
                applied=str(entrada["applied"]),
                previous=str(entrada["previous"]),
            )
        except Exception as exc:
            self._show_error(exc)
            return
        finally:
            # Recusado ou feito, este lançamento não se desfaz de novo.
            entrada["done"] = True
            if getattr(self, "_last_result_entry", None) is entrada:
                self._last_result_entry = None
        self._reload_selecting(int(entrada["entry_id"]))
        self._show_toast(
            f"Desfeito: {entrada['label']} → {entrada['previous'] or 'pendente'}", kind="info"
        )

    def _reload_selecting(self, entry_id: int) -> None:
        """Recarrega a rodada e poe o cursor na mesa indicada."""
        if not hasattr(self, "pairing_tree") or not self.pairing_tree.winfo_exists():
            return
        self._load_selected_round_pairings()
        for item, pairing_id in getattr(self, "pairing_row_map", {}).items():
            if pairing_id == entry_id:
                self.pairing_tree.selection_set(item)
                self.pairing_tree.focus(item)
                self.pairing_tree.see(item)
                break

    # ---- Botão primário e contador da rodada (RGS-21 / RGS-25) ------------ #

    def _latest_round(self) -> dict[str, Any] | None:
        rodadas = self.db.list_rounds(self.current_tournament_id)
        if not rodadas:
            return None
        return max(rodadas, key=lambda item: int(item["number"]))

    def _round_primary_state(self) -> tuple[PrimaryRoundAction, dict[str, Any]] | None:
        """O proximo passo do torneio, sempre a partir da ULTIMA rodada."""
        ultima = self._latest_round()
        if ultima is None:
            return None
        progresso = self.pairing_service.round_progress(
            int(self.current_tournament_id), int(ultima["id"])
        )
        torneio = self.db.get_tournament(self.current_tournament_id) or {}
        acao = primary_round_action(
            round_number=int(ultima["number"]),
            round_status=str(ultima.get("status") or ""),
            resolved=int(progresso["resolved_results"]),
            total=int(progresso["total_results"]),
            pending=int(progresso["pending_results"]),
            rounds_count=int(torneio.get("rounds_count") or 0),
        )
        return acao, ultima

    def _refresh_round_progress(self) -> None:
        """Contador da rodada exibida e rotulo do botao primario."""
        contador = getattr(self, "_round_progress_label", None)
        if contador is not None and contador.winfo_exists():
            texto = ""
            if self.current_round_id:
                progresso = self.pairing_service.round_progress(
                    int(self.current_tournament_id), int(self.current_round_id)
                )
                texto = results_counter_text(
                    int(progresso["resolved_results"]), int(progresso["total_results"])
                )
            contador.configure(text=texto)
        botao = getattr(self, "_round_primary_button", None)
        if botao is None or not botao.winfo_exists():
            return
        estado = self._round_primary_state()
        if estado is not None:
            botao.configure(text=estado[0].label)

    def _run_round_primary_action(self) -> None:
        """Clique no botão primário: o estado e relido na hora do clique.

        Toda transição que muda o rótulo por baixo do cursor e segura: "Fechar"
        sempre passa pela confirmação.
        """
        try:
            estado = self._round_primary_state()
        except Exception as exc:
            self._show_error(exc)
            return
        if estado is None:
            return
        acao, ultima = estado
        if acao.kind == "launch":
            self._focus_round_pending(int(ultima["id"]))
        elif acao.kind == "close":
            self._confirm_and_close_round(ultima)
        elif acao.kind == "generate":
            self._generate_round()
        else:
            self.show_standings()

    def _focus_round_pending(self, round_id: int) -> None:
        """Leva a rodada indicada para a tela e o cursor para a 1a mesa pendente."""
        if self.current_round_id != round_id:
            rotulo = next(
                (r for r, rid in getattr(self, "round_option_map", {}).items() if rid == round_id),
                None,
            )
            if rotulo is not None:
                self.round_option.set(rotulo)
                self._load_selected_round_pairings()
        self._select_first_pending_pairing()

    def _confirm_and_close_round(self, rodada: dict[str, Any]) -> None:
        """Fechar rodada com a lista de pendencias na frente (RGS-25)."""
        if self._confirm_round_closing(rodada):
            self._close_current_round()

    def _round_closing_effect(self, numero: int) -> str:
        """O que fechar a rodada faz — dito na confirmacao e no checklist do painel."""
        torneio = self.db.get_tournament(self.current_tournament_id) or {}
        if numero < int(torneio.get("rounds_count") or 0):
            efeito = f"libera o emparceiramento da rodada {numero + 1}"
        else:
            efeito = "grava a classificação final"
        return (
            "Fechar trava os resultados (depois, só Corrigir resultado…, "
            f"com motivo) e {efeito}."
        )

    def _confirm_round_closing(self, rodada: dict[str, Any], *, confirmed: bool = False) -> bool:
        """A confirmação de fechar rodada — a única, da tela de Rodadas e do painel.

        Item reprovado no checklist (QR aguardando, pendência bloqueante) não
        vira confirmação inútil — o serviço recusaria: vai para a faixa de
        regra, com o "Resolver". Tudo certo: confirmação com a lista; Esc ou
        "Voltar" não fecham. Confirmada, a rodada vira a ``current_round_id``.
        ``confirmed``: o usuário já confirmou olhando a mesma lista (o
        "Checklist" do painel) — confere de novo, mas não pergunta duas vezes.
        """
        from ...components.dialogs import confirm_dialog

        try:
            self.require_permission("tournament_write")
            numero = int(rodada["number"])
            itens = [
                item
                for item in self.pairing_service.closing_checklist(int(self.current_tournament_id))
                if item.get("action") != "ready_to_close"
            ]
            falhas = [item for item in itens if not item.get("ok")]
            if falhas:
                resolver = None
                destino = getattr(self, "_arbitration_action", None)
                comando = destino(str(falhas[0].get("action") or "")) if destino else None
                if comando is not None:
                    resolver = ("Resolver", comando)
                self._show_rule_error(
                    "\n".join(f"✗ {item['label']}" for item in falhas),
                    title=f"A rodada {numero} ainda não pode ser fechada",
                    suggestion="Resolva os itens marcados e tente fechar de novo.",
                    action=resolver,
                )
                return False
            lista = "\n".join(f"✓ {item['label']}" for item in itens)
            if not confirmed and not confirm_dialog(
                self,
                f"Fechar rodada {numero}",
                f"{lista}\n\n{self._round_closing_effect(numero)}",
                confirm_text=f"Fechar rodada {numero}",
                cancel_text="Voltar",
            ):
                return False
            self.current_round_id = int(rodada["id"])
        except Exception as exc:
            self._show_error(exc)
            return False
        return True

    # ---- "Corrigir resultado…" na mesa (RGS-20) ---------------------------- #

    def _result_corrections(self) -> ResultCorrectionActions:
        return ResultCorrectionActions(self)

    def _open_result_correction(self, event: Any = None) -> str:
        """Clique direito / Shift+F10 / Ctrl+E numa mesa: abre o dialogo unico."""
        tree = getattr(self, "pairing_tree", None)
        if tree is None:
            return "break"
        if event is not None and getattr(event, "num", None) == 3:
            # Clique direito numa linha não selecionada corrige ESSA linha.
            linha = tree.identify_row(event.y)
            if linha:
                tree.selection_set(linha)
                tree.focus(linha)
        target_id = self._selected_pairing_id()
        if not target_id:
            self._show_error(
                AppError(
                    "Selecione um tabuleiro." if getattr(self, "pairing_team_mode", False) else "Selecione uma mesa.",
                    suggestion="Clique com o botão direito na mesa, ou selecione-a e tecle Ctrl+E.",
                )
            )
            return "break"
        self._result_corrections().open(
            int(target_id),
            detail=self._selected_pairing(),
            on_done=self._reload_current_round,
        )
        return "break"

    def _reload_current_round(self) -> None:
        """Recarrega a rodada exibida, mantendo a mesa que estava selecionada."""
        if not hasattr(self, "pairing_tree") or not self.pairing_tree.winfo_exists():
            return
        anterior = self._selected_pairing_id()
        self._load_selected_round_pairings()
        for item, pairing_id in getattr(self, "pairing_row_map", {}).items():
            if pairing_id == anterior:
                self.pairing_tree.selection_set(item)
                self.pairing_tree.focus(item)
                self.pairing_tree.see(item)
                break

    # ---- Reconciliação dos retratos em segundo plano (RGS-10) ------------- #

    _RECONCILE_POLL_MS = 400

    def _start_snapshot_reconciler(self) -> None:
        """Liga o trabalhador dos retratos e termina o que ficou pendente.

        A correção só marca os retratos; quem regrava e o trabalhador, numa
        thread, e ele só fala com a tela pelo `after()`. Chamado na abertura
        (depois do login): uma reconciliação interrompida — falha, app fechado —
        e terminada aqui, sem o árbitro pedir.

        O aviso entra numa fila que a PRÓPRIA thread da tela esvazia por um
        `after()` periódico: chamar `after()` de outra thread só funciona com o
        `mainloop` já rodando (senão o Tk levanta "main thread is not in main
        loop" e o aviso se perde).
        """
        avisos: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        reconciler = SnapshotReconciler(
            self.pairing_service,
            notify=avisos.put,
            on_done=self._on_snapshots_reconciled,
            on_error=self._on_snapshot_reconcile_error,
        )
        self.snapshot_reconciler = reconciler
        self.pairing_service.on_snapshots_pending = reconciler.start

        def drenar() -> None:
            while True:
                try:
                    aviso = avisos.get_nowait()
                except queue.Empty:
                    break
                try:
                    aviso()
                except Exception:
                    logger.exception("Falha ao mostrar o aviso da reconciliacao")
            try:
                self.after(self._RECONCILE_POLL_MS, drenar)
            except Exception:  # janela destruída: o laço acaba aqui
                pass

        drenar()
        reconciler.start()

    def _on_snapshots_reconciled(self, total: int) -> None:
        if hasattr(self, "status_label"):
            plural = "s" if total != 1 else ""
            self.status_label.configure(
                text=f"{total} retrato{plural} de classificação reconciliado{plural}."
            )

    def _on_snapshot_reconcile_error(self, error: Exception) -> None:
        # O erro já foi para o log com o traceback; a pendência fica no banco.
        if hasattr(self, "status_label"):
            self.status_label.configure(
                text=(
                    "Falha ao reconciliar os retratos de classificação; a pendência "
                    f"será retomada na próxima abertura. ({error})"
                )
            )

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

    # ---- Resultado por QR: ponte para o módulo (B-6) ----------------------- #

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
                raise AppError("Resultado inválido.")
            if not self._selected_pairing_id():
                return "break"
            self.result_option.set(result)
            selected_before = self.pairing_tree.selection()
            children_before = list(self.pairing_tree.get_children())
            selected_index = children_before.index(selected_before[0]) if selected_before else -1
            if not self._save_selected_result():
                return "break"
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

    # ---- Trocas na mesa: ponte para o módulo (B-6) -------------------------- #

    def _board_swaps(self) -> BoardSwapActions:
        return BoardSwapActions(self)

    def _swap_selected_colors(self) -> None:
        self._board_swaps().swap_colors()

    def _open_player_swap_dialog(self) -> None:
        self._board_swaps().open_player_swap()

    def _open_team_player_swap_dialog(self) -> None:
        self._board_swaps().open_team_player_swap()

    # ---- Mata-mata: avanço registrado e chave (PAR-03) ---------------------- #

    def _knockout_actions(self) -> KnockoutActions:
        return KnockoutActions(self)

    def _open_knockout_advancement_dialog(self) -> None:
        self._knockout_actions().open_advancement()

    def _show_knockout_bracket(self) -> None:
        self._knockout_actions().show_bracket()

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
            if self._confirm_and_delete_round(int(self.current_round_id)):
                self._load_round_options()
        except Exception as exc:
            self._show_error(exc)

    def _confirm_and_delete_round(self, round_id: int) -> bool:
        """Exclui rodada gerada perguntando o que ela custa (RGS-34).

        Sem resultado lançado, a confirmação de sempre. Com resultado, o
        diálogo diz quantos somem e pede o motivo — que vai para a auditoria
        junto com os resultados apagados. Devolve se excluiu.
        """
        previa = self.pairing_service.round_deletion_preview(int(round_id))
        numero = previa["number"]
        if not previa["results"]:
            if not self._confirm_action("Confirmar", f"Excluir a rodada {numero}?", danger=True):
                return False
            self.pairing_service.delete_generated_round(int(round_id))
            return True
        total = int(previa["results"])
        motivo = reason_dialog(
            self,
            f"Excluir rodada {numero}",
            f"{previa['message']}. Eles ficam guardados na auditoria, junto com o "
            "motivo, mas saem da rodada e da classificação.\n\n"
            "Por que a rodada precisa ser excluída?",
            validate=lambda texto: round_deletion_reason_error(texto, total),
            confirm_text="Excluir rodada",
            danger=True,
        )
        if motivo is None:
            return False
        self.pairing_service.delete_generated_round(int(round_id), reason=motivo)
        self._show_toast(f"Rodada {numero} excluída ({previa['message']}).", kind="success")
        return True

    def _projector_rows(self) -> list[dict[str, str]]:
        """As mesas da rodada no formato que a projeção mostra.

        Lê o banco e devolve dado plano; quem desenha e o
        [`ProjectorWindow`](pairing_results/projector.py). No modo equipes cada
        tabuleiro vira uma linha, com o nome da equipe ao lado do jogador —
        na parede, "Silva" sem a equipe não diz de quem e o ponto.
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
