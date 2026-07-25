from __future__ import annotations

from ..support import *
from ..components import Tooltip, danger_button, debounce, menu_button, primary_button, secondary_button


# ---------------------------------------------------------------------------
# Modo Projetor: contraste FIXO, alheio ao tema. Quem ve e a sala, na parede —
# nao faz sentido a projecao seguir a preferencia de cor de quem opera. Por
# isso sao constantes nomeadas, e nao tokens do tema.
# ---------------------------------------------------------------------------
PROJETOR_FUNDO        = "#000000"
PROJETOR_BARRA        = "#111111"
PROJETOR_TEXTO        = "#FFFFFF"
PROJETOR_TEXTO_SUAVE  = "#94A3B8"
PROJETOR_DESTAQUE     = "#FBBF24"
PROJETOR_MESA         = "#F59E0B"
PROJETOR_LINHA_PAR    = "#1E293B"
PROJETOR_LINHA_IMPAR  = "#0F172A"
PROJETOR_BOTAO        = "#334155"
PROJETOR_BOTAO_HOVER  = "#475569"
PROJETOR_TABULEIRO    = "#D97706"


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
            "Gerar proxima rodada",
            self._generate_round,
            tip="Emparceira a proxima rodada a partir dos resultados ja lancados.",
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
            tip="Apaga a rodada selecionada e todos os resultados lancados nela.",
        ).grid(row=0, column=4, sticky="e")

        # Linha 2 - lancamento de resultados (fluxo mais frequente do dia a dia).
        entry = ctk.CTkFrame(toolbar, fg_color="transparent")
        entry.grid(row=1, column=0, padx=SPACE_MD, pady=(0, SPACE_SM), sticky="ew")
        entry.grid_columnconfigure(4, weight=1)
        self.round_option = ctk.CTkOptionMenu(
            entry,
            values=["Sem rodadas"],
            command=lambda _value: self._load_selected_round_pairings(),
            width=190,
        )
        self.round_option.grid(row=0, column=0, padx=(0, SPACE_SM))
        Tooltip(self.round_option, "Escolhe qual rodada visualizar/editar.")
        self.result_option = ctk.CTkOptionMenu(entry, values=RESULTS, width=130)
        self.result_option.grid(row=0, column=1, padx=(0, SPACE_SM))
        Tooltip(self.result_option, "Resultado a aplicar na mesa selecionada ao salvar.")
        primary_button(
            entry,
            "Salvar resultado",
            self._save_selected_result,
            tip="Grava o resultado escolhido na mesa selecionada.",
        ).grid(row=0, column=2, padx=(0, SPACE_MD))
        quick_results = ctk.CTkFrame(entry, fg_color="transparent")
        quick_results.grid(row=0, column=3, sticky="w")
        quick_tips = {
            "1-0": "Lanca vitoria das brancas na mesa selecionada.",
            "1/2-1/2": "Lanca empate na mesa selecionada.",
            "0-1": "Lanca vitoria das pretas na mesa selecionada.",
            "": "Limpa o resultado lancado na mesa selecionada.",
        }
        for label, result in [("1-0", "1-0"), ("1/2", "1/2-1/2"), ("0-1", "0-1"), ("Limpar", "")]:
            quick = ctk.CTkButton(
                quick_results,
                text=label,
                width=64,
                command=lambda value=result: self._quick_save_result(value),
            )
            quick.pack(side="left", padx=(0, SPACE_XS))
            Tooltip(quick, quick_tips[result])

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
        Tooltip(projector, "Abre a rodada atual em tela cheia para projecao na sala.")

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
                "Gerar proxima rodada",
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
            roster_panel = self._make_panel(body)
            roster_panel.grid(row=1, column=0, sticky="nsew")
            roster_panel.grid_columnconfigure(0, weight=1)
            roster_panel.grid_rowconfigure(1, weight=1)
            roster_header = ctk.CTkFrame(roster_panel, fg_color="transparent")
            roster_header.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
            roster_header.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                roster_header,
                text="Chamada inicial antes da primeira rodada",
                font=font_section(),
            ).grid(row=0, column=0, sticky="w")
            self.initial_call_summary_label = ctk.CTkLabel(
                roster_header,
                text="Presentes: 0 | Ausentes: 0 | Total: 0",
                text_color=THEME_TEXT_SUB,
            )
            self.initial_call_summary_label.grid(row=1, column=0, pady=(2, 0), sticky="w")
            self.initial_player_search_entry = ctk.CTkEntry(
                roster_header,
                width=320,
                placeholder_text="Buscar jogador, clube ou categoria",
            )
            self.initial_player_search_entry.grid(row=2, column=0, pady=(8, 0), sticky="w")
            self.initial_player_search_debounced = debounce(
                self.initial_player_search_entry, self._load_initial_players
            )
            self.initial_player_search_entry.bind(
                "<KeyRelease>", self.initial_player_search_debounced
            )
            ctk.CTkButton(
                roster_header,
                text="Exportar lista",
                width=110,
                command=self._export_initial_player_list,
            ).grid(row=0, column=1, padx=(8, 0), sticky="e")
            ctk.CTkButton(
                roster_header,
                text="Imprimir",
                width=85,
                command=self._print_initial_player_list,
            ).grid(row=0, column=2, padx=(8, 0), sticky="e")
            roster_tree_holder = ctk.CTkFrame(roster_panel, fg_color="transparent")
            roster_tree_holder.grid(row=1, column=0, padx=12, pady=(0, 0), sticky="nsew")
            roster_tree_holder.grid_columnconfigure(0, weight=1)
            roster_tree_holder.grid_rowconfigure(0, weight=1)
            self.initial_players_tree = self._make_tree(
                roster_tree_holder,
                ["start", "presence", "name", "rating", "club", "category", "status"],
                {
                    "start": "Inicial",
                    "presence": "Presenca",
                    "name": "Jogador",
                    "rating": "Rating",
                    "club": "Clube",
                    "category": "Categoria",
                    "status": "Status",
                },
                {
                    "start": 70,
                    "presence": 90,
                    "name": 280,
                    "rating": 80,
                    "club": 170,
                    "category": 130,
                    "status": 95,
                },
                visible_rows=14,
            )
            self.initial_players_tree.configure(selectmode="extended")
            self.initial_players_tree.bind(
                "<Double-1>",
                lambda _event: self._toggle_selected_initial_players_presence(),
            )
            self.initial_players_tree.bind(
                "<space>",
                lambda _event: self._toggle_selected_initial_players_presence(),
            )
            roster_actions = ctk.CTkFrame(roster_panel, fg_color="transparent")
            roster_actions.grid(row=2, column=0, padx=12, pady=(8, 12), sticky="ew")
            for column in range(3):
                roster_actions.grid_columnconfigure(column, weight=1)
            ctk.CTkButton(
                roster_actions,
                text="Todos presentes",
                command=self._mark_all_initial_players_present,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")
            ctk.CTkButton(
                roster_actions,
                text="Presente",
                command=lambda: self._set_selected_initial_players_status("active"),
            ).grid(row=0, column=1, padx=6, sticky="ew")
            ctk.CTkButton(
                roster_actions,
                text="Ausente",
                command=lambda: self._set_selected_initial_players_status("absent"),
            ).grid(row=0, column=2, padx=(6, 0), sticky="ew")
            self._load_initial_players()

        if show_initial_call:
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

    def _load_initial_players(self) -> None:
        if not hasattr(self, "initial_players_tree"):
            return
        self.initial_players_tree.delete(*self.initial_players_tree.get_children())
        self.initial_player_row_map = {}
        players = self.db.list_players(self.current_tournament_id, active_only=False)
        present_count = sum(1 for player in players if player.get("player_status") == "active")
        absent_count = len(players) - present_count
        if hasattr(self, "initial_call_summary_label"):
            self.initial_call_summary_label.configure(
                text=f"Presentes: {present_count} | Ausentes: {absent_count} | Total: {len(players)}"
            )
        ordered_players = self.export_service._initial_ranked_players(players)
        query = (
            self.initial_player_search_entry.get().strip().casefold()
            if hasattr(self, "initial_player_search_entry")
            else ""
        )
        for start_number, player in enumerate(ordered_players, start=1):
            searchable = " ".join(
                [
                    player_full_name(player),
                    str(player.get("club") or ""),
                    str(player.get("category") or ""),
                    str(player.get("rating") or ""),
                ]
            ).casefold()
            if query and query not in searchable:
                continue
            status = str(player.get("player_status", "active") or "active")
            item_id = self.initial_players_tree.insert(
                "",
                "end",
                values=(
                    start_number,
                    "Sim" if status == "active" else "Nao",
                    player_full_name(player),
                    player.get("rating", ""),
                    player.get("club", ""),
                    player.get("category", ""),
                    PLAYER_STATUSES.get(status, status),
                ),
            )
            self.initial_player_row_map[item_id] = int(player["id"])

    def _initial_call_locked(self) -> bool:
        if self.db.list_rounds(self.current_tournament_id):
            self._show_warning("A chamada inicial so pode ser alterada antes de gerar a primeira rodada.")
            return True
        return False

    def _selected_initial_player_ids(self) -> list[int]:
        if not hasattr(self, "initial_players_tree"):
            return []
        return [
            self.initial_player_row_map[item_id]
            for item_id in self.initial_players_tree.selection()
            if item_id in self.initial_player_row_map
        ]

    def _set_initial_players_status(self, player_ids: list[int], status: str) -> None:
        try:
            self.require_permission("tournament_write")
            if self._initial_call_locked():
                return
            if not player_ids:
                raise AppError("Selecione um ou mais jogadores na chamada inicial.")
            for player_id in player_ids:
                self.db.set_player_status(player_id, status)
            self._load_initial_players()
        except Exception as exc:
            self._show_error(exc)

    def _set_selected_initial_players_status(self, status: str) -> None:
        self._set_initial_players_status(self._selected_initial_player_ids(), status)

    def _mark_all_initial_players_present(self) -> None:
        if not hasattr(self, "initial_player_row_map"):
            return
        self._set_initial_players_status(list(self.initial_player_row_map.values()), "active")

    def _toggle_selected_initial_players_presence(self) -> str:
        try:
            if self._initial_call_locked():
                return "break"
            player_ids = self._selected_initial_player_ids()
            if not player_ids:
                return "break"
            players = [self.db.get_player(player_id) for player_id in player_ids]
            next_status = "active" if any(
                player and player.get("player_status") != "active"
                for player in players
            ) else "absent"
            self._set_initial_players_status(player_ids, next_status)
            return "break"
        except Exception as exc:
            self._show_error(exc)
            return "break"

    def _initial_player_list_path(self, suffix: str = ".xlsx") -> Path:
        tournament = self.db.get_tournament(self.current_tournament_id) if self.current_tournament_id else None
        safe_name = self._safe_filename(str(tournament.get("name") if tournament else "torneio"), "torneio")
        return self._default_export_dir() / f"{safe_name}_lista_inicial{suffix}"

    def _export_initial_player_list(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            default_path = self._initial_player_list_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar lista inicial",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel", "*.xlsx"),
                    ("CSV", "*.csv"),
                    ("PDF", "*.pdf"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() not in {".csv", ".xlsx", ".pdf"}:
                path = path.with_suffix(".xlsx")
            self._run_background(
                lambda: self.export_service.export_initial_player_list(int(self.current_tournament_id), path),
                lambda _result: self._show_info(f"Lista inicial exportada:\n{path}"),
                "Exportando lista inicial...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _print_initial_player_list(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            path = self._initial_player_list_path(".pdf")
            self._run_background(
                lambda: self.export_service.export_initial_player_list(int(self.current_tournament_id), path),
                lambda _result: self._print_document(path),
                "Preparando impressao...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _current_round_pairings_path(self, suffix: str = ".xlsx") -> Path:
        tournament = self.db.get_tournament(self.current_tournament_id) if self.current_tournament_id else None
        safe_name = self._safe_filename(str(tournament.get("name") if tournament else "torneio"), "torneio")
        round_data = self.db.get_round(self.current_round_id) if self.current_round_id else None
        round_number = int(round_data["number"]) if round_data else 0
        return self._default_export_dir() / f"{safe_name}_rodada_{round_number}{suffix}"

    def _require_current_round(self) -> int:
        if not self.current_round_id:
            raise AppError("Selecione uma rodada.")
        return int(self.current_round_id)

    def _export_current_round_pairings(self) -> None:
        try:
            round_id = self._require_current_round()
            default_path = self._current_round_pairings_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar rodada",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel", "*.xlsx"),
                    ("CSV", "*.csv"),
                    ("PDF", "*.pdf"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() not in {".csv", ".xlsx", ".pdf"}:
                path = path.with_suffix(".xlsx")
            self._run_background(
                lambda: self.export_service.export_pairings(round_id, path),
                lambda _result: self._show_info(f"Rodada exportada:\n{path}"),
                "Exportando rodada...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _print_current_round_pairings(self) -> None:
        try:
            round_id = self._require_current_round()
            path = self._current_round_pairings_path(".pdf")
            self._run_background(
                lambda: self.export_service.export_pairings(round_id, path),
                lambda _result: self._print_document(path),
                "Preparando impressao...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _current_round_scoresheets_path(self) -> Path:
        return self._current_round_pairings_path(".pdf").with_name(
            f"{self._current_round_pairings_path('.pdf').stem}_sumulas.pdf"
        )

    def _current_round_table_cards_path(self) -> Path:
        return self._current_round_pairings_path(".pdf").with_name(
            f"{self._current_round_pairings_path('.pdf').stem}_cartoes.pdf"
        )

    def _export_current_round_scoresheets(self) -> None:
        try:
            round_id = self._require_current_round()
            default_path = self._current_round_scoresheets_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar sumulas de mesa",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() != ".pdf":
                path = path.with_suffix(".pdf")
            self._run_background(
                lambda: self.export_service.export_scoresheets(round_id, path),
                lambda _result: self._show_info(f"Sumulas exportadas:\n{path}"),
                "Exportando sumulas...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _print_current_round_scoresheets(self) -> None:
        try:
            round_id = self._require_current_round()
            path = self._current_round_scoresheets_path()
            self._run_background(
                lambda: self.export_service.export_scoresheets(round_id, path),
                lambda _result: self._print_document(path),
                "Preparando sumulas para impressao...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_table_cards(self) -> None:
        try:
            round_id = self._require_current_round()
            pairings = self.db.get_pairings_for_round(round_id)
            suggested_end = max((int(pairing["board_number"]) for pairing in pairings), default=1)
            value = self._ask_string(
                "Cartoes de mesa",
                f"Informe o intervalo de mesas (ex.: 1-{suggested_end}):",
            )
            if value is None:
                return
            normalized = value.strip().replace(" ", "")
            parts = normalized.split("-", maxsplit=1)
            if len(parts) != 2:
                raise AppError("Informe o intervalo no formato inicio-fim, por exemplo: 1-60.")
            start_board, end_board = (int(part) for part in parts)
            include_qr = self._confirm_action(
                "Cartoes de mesa",
                "Incluir QR de envio de resultado para as mesas da rodada aberta?",
            )
            default_path = self._current_round_table_cards_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar cartoes de mesa",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() != ".pdf":
                path = path.with_suffix(".pdf")
            self._run_background(
                lambda: self.export_service.export_table_cards(
                    path,
                    start_board,
                    end_board,
                    round_id=round_id,
                    include_qr=include_qr,
                ),
                lambda _result: self._show_info(f"Cartoes de mesa exportados:\n{path}"),
                "Exportando cartoes de mesa...",
            )
        except ValueError:
            self._show_error("Informe o intervalo no formato inicio-fim, por exemplo: 1-60.")
        except Exception as exc:
            self._show_error(exc)

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

    @staticmethod
    def _individual_result_state(
        pairing: dict[str, Any],
        submissions_by_pairing: dict[int, dict[str, Any]],
        corrected_pairing_ids: set[int],
    ) -> str:
        pairing_id = int(pairing["id"])
        if pairing_id in corrected_pairing_ids:
            return "corrigido"
        submission = submissions_by_pairing.get(pairing_id)
        if submission:
            status = str(submission.get("status") or "")
            if status == "submitted":
                return "submetido QR"
            if status == "approved":
                return "aprovado QR"
            if status == "rejected":
                return "rejeitado QR"
        if pairing.get("round_status") == "closed":
            return "bloqueado"
        if not pairing.get("result"):
            return "vazio"
        return "registrado"

    @staticmethod
    def _team_board_result_state(board: dict[str, Any], corrected_team_board_ids: set[int], round_status: str = "") -> str:
        board_id = int(board["id"])
        if board_id in corrected_team_board_ids:
            return "corrigido"
        if round_status == "closed":
            return "bloqueado"
        if not board.get("result"):
            return "vazio"
        return "registrado"

    @staticmethod
    def _result_state_tag(state: str) -> str:
        normalized = str(state or "").replace(" ", "_").lower()
        return f"result_state_{normalized}"

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
        result_index = 6 if getattr(self, "pairing_team_mode", False) else 3
        selected_item = children[0]
        for item in children:
            values = self.pairing_tree.item(item, "values")
            result = values[result_index] if len(values) > result_index else ""
            if not result:
                selected_item = item
                break
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
        allowed = set(RESULTS)
        pairing_detail = self._selected_pairing()
        if pairing_detail and pairing_detail.get("row_type") == "individual_pairing" and pairing_detail.get("is_bye"):
            allowed.update({"BYE", "F", "H", "Z"})
        if result in allowed:
            self.result_option.set(result)

    def _bind_pairing_result_shortcuts(self) -> None:
        self._pairing_shortcuts_enabled = True
        shortcut_map = {
            "1": "1-0",
            "<KP_1>": "1-0",
            "0": "0-1",
            "<KP_0>": "0-1",
            "-": "1/2-1/2",
            "<KP_Subtract>": "1/2-1/2",
            "<BackSpace>": "",
            "<Delete>": "",
        }
        for sequence, result in shortcut_map.items():
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

    @staticmethod
    def _recommended_rounds_for_players(players_count: int) -> int:
        if players_count <= 1:
            return 1
        return (players_count - 1).bit_length()

    def _confirm_short_tournament_round_count(self) -> bool:
        if getattr(self, "pairing_team_mode", False):
            return True
        if self.db.list_rounds(self.current_tournament_id):
            return True
        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            return True
        players_count = len(self.db.list_players(self.current_tournament_id, active_only=True))
        recommended_rounds = self._recommended_rounds_for_players(players_count)
        configured_rounds = int(tournament.get("rounds_count") or 0)
        if players_count <= 2 or configured_rounds >= recommended_rounds:
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

    def _format_pairing_preview(self, preview: dict[str, Any]) -> str:
        header = [
            f"Previa da rodada {preview['round_number']}",
            f"Sistema: {preview.get('pairing_system', '')}",
            f"Alertas: {preview.get('alerts_count', 0)}",
            "",
        ]
        if preview.get("competition_type") == "team":
            rows = []
            for match in preview.get("matches", [])[:12]:
                alert_text = f" [{'; '.join(match['alerts'])}]" if match.get("alerts") else ""
                rows.append(
                    f"Match {match['match_number']}: {match['white_team_name']} x {match['black_team_name']}{alert_text}"
                )
            total = len(preview.get("matches", []))
        else:
            rows = []
            for pairing in preview.get("pairings", [])[:12]:
                alert_text = f" [{'; '.join(pairing['alerts'])}]" if pairing.get("alerts") else ""
                rows.append(
                    "Mesa {board}: {white} x {black}{alerts}".format(
                        board=pairing["board_number"],
                        white=pairing["white_name"],
                        black=pairing["black_name"],
                        alerts=alert_text,
                    )
                )
            total = len(preview.get("pairings", []))
        if total > len(rows):
            rows.append(f"... mais {total - len(rows)} item(ns)")
        if not rows:
            rows.append("Nenhuma mesa prevista.")
        rows.append("")
        rows.append("Esta pre-visualizacao nao gravou rodada no banco.")
        return "\n".join(header + rows)

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

            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
                    if not settings.get("allow_dangerous_changes"):
                        raise AppError(
                            "Habilite mudancas perigosas nas configuracoes do torneio para alterar rodada fechada."
                        )
                    confirmed = self._confirm_action(
                        "Confirmar",
                        "Esta rodada ja esta fechada. Alterar o resultado mesmo assim?",
                        danger=True,
                    )
                    if not confirmed:
                        return
            self.pairing_service.update_result(self.current_tournament_id, pairing_id, result)
            self._load_selected_round_pairings()
        except Exception as exc:
            self._show_error(exc)

    def _prompt_bye_edit_warning(self, default_result: str, chosen_result: str) -> str:
        choice = "cancel"
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Aviso: Editar BYE")
        dialog.geometry("450x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")

        msg = (
            "Esta mesa é um BYE (sem oponente).\n"
            "Alterar o resultado para algo diferente do padrão pode causar inconsistências "
            "e impedir o fechamento correto da rodada.\n\n"
            f"Resultado padrão: '{default_result}'\n"
            f"Resultado escolhido: '{chosen_result or 'pendente'}'"
        )
        
        ctk.CTkLabel(
            dialog,
            text=msg,
            justify="left",
            wraplength=410,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        ).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=2, column=0, pady=(0, 20), padx=20, sticky="ew")
        
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)
        
        def set_choice(val):
            nonlocal choice
            choice = val
            dialog.destroy()
            
        btn_restore = ctk.CTkButton(
            actions,
            text="Voltar ao Padrão",
            command=lambda: set_choice("restore"),
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
        )
        btn_restore.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        
        btn_edit = ctk.CTkButton(
            actions,
            text="Realmente Editar",
            command=lambda: set_choice("edit"),
            fg_color=THEME_DANGER,
            hover_color=THEME_DANGER_HOVER,
        )
        btn_edit.grid(row=0, column=1, padx=6, sticky="ew")
        
        btn_cancel = ctk.CTkButton(
            actions,
            text="Cancelar",
            command=lambda: set_choice("cancel"),
            fg_color=THEME_NEUTRAL,
            hover_color=THEME_NEUTRAL_HOVER,
        )
        btn_cancel.grid(row=0, column=2, padx=(6, 0), sticky="ew")
        
        self.wait_window(dialog)
        return choice

    def _show_selected_pairing_qr_link(self) -> None:
        try:
            pairing_id = self._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione uma mesa.")
            if getattr(self, "pairing_team_mode", False):
                raise AppError("QR de resultado por tabuleiro de equipes sera tratado na fase de equipes avancadas.")
            payload = self.qr_result_service.result_url_for_pairing(int(self.current_tournament_id), int(pairing_id))
            self._show_info(
                "Link para envio por QR:\n"
                f"{payload['url']}\n\n"
                "O resultado enviado fica pendente ate aprovacao do arbitro."
            )
        except Exception as exc:
            self._show_error(exc)

    def _start_qr_result_server(self) -> None:
        try:
            if self.local_result_server is None:
                self.local_result_server = LocalResultServer(self.qr_result_service)
            url = self.local_result_server.start()
            self.db.save_app_settings({"local_result_server_url": url})
            self._show_info(f"Servidor QR ativo em:\n{url}\n\nUse este endereco na mesma rede local.")
        except Exception as exc:
            self._show_error(exc)

    def _approve_qr_submission(self, submission_id: int) -> None:
        reviewer, _role = self.db._operator_context()
        self.qr_result_service.approve_submission(submission_id, reviewer=reviewer)
        try:
            self._load_selected_round_pairings()
        except Exception:
            pass
        self._show_toast("Resultado QR aprovado.", kind="success")

    def _reject_qr_submission(self, submission_id: int) -> None:
        reviewer, _role = self.db._operator_context()
        self.qr_result_service.reject_submission(submission_id, reviewer=reviewer)
        self._show_toast("Resultado QR rejeitado.", kind="success")

    def _open_qr_submissions_queue(self) -> None:
        try:
            self.require_permission("tournament_write")
            submissions = self.qr_result_service.pending_submissions(int(self.current_tournament_id))
        except Exception as exc:
            self._show_error(exc)
            return

        window = ctk.CTkToplevel(self)
        window.title("Submissoes QR")
        window.geometry("780x420")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(0, weight=1)

        panel = ctk.CTkFrame(window, fg_color="transparent")
        panel.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            panel,
            ["id", "round", "board", "submitted", "current", "submitter", "time"],
            {
                "id": "ID",
                "round": "Rodada",
                "board": "Mesa",
                "submitted": "Enviado",
                "current": "Atual",
                "submitter": "Enviado por",
                "time": "Horario",
            },
            {
                "id": 60,
                "round": 80,
                "board": 70,
                "submitted": 90,
                "current": 90,
                "submitter": 180,
                "time": 170,
            },
            visible_rows=9,
        )
        for submission in submissions:
            tree.insert(
                "",
                "end",
                values=(
                    submission["id"],
                    submission.get("round_number", ""),
                    submission.get("board_number", ""),
                    submission.get("submitted_result", ""),
                    submission.get("current_result", ""),
                    submission.get("submitter", ""),
                    submission.get("submitted_at", ""),
                ),
            )

        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        def selected_submission_id() -> int:
            selected = tree.selection()
            if not selected:
                raise AppError("Selecione um envio.")
            values = tree.item(selected[0], "values")
            return int(values[0])

        def approve() -> None:
            try:
                self._approve_qr_submission(selected_submission_id())
                window.destroy()
            except Exception as exc:
                self._show_error(exc)

        def reject() -> None:
            try:
                self._reject_qr_submission(selected_submission_id())
                window.destroy()
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(actions, text="Aprovar", command=approve).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(actions, text="Rejeitar", command=reject).grid(row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(actions, text="Fechar", command=window.destroy).grid(row=0, column=2, padx=(6, 0), sticky="ew")

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

    def _swap_selected_colors(self) -> None:
        try:
            self.require_permission("tournament_write")
            if getattr(self, "pairing_team_mode", False):
                team_board_id = self._selected_pairing_id()
                if not team_board_id:
                    raise AppError("Selecione um tabuleiro.")
                if not self.current_round_id:
                    raise AppError("Selecione uma rodada.")
                self.pairing_service.swap_team_board_colors(
                    self.current_tournament_id,
                    self.current_round_id,
                    team_board_id,
                )
                self._load_selected_round_pairings()
                return
            pairing_id = self._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione uma mesa.")
            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    raise AppError("Rodada fechada nao pode ser ajustada.")
            self.db.swap_pairing_colors(pairing_id)
            logger.info("Cores trocadas na mesa %s", pairing_id)
            self._load_selected_round_pairings()
        except Exception as exc:
            self._show_error(exc)

    def _open_player_swap_dialog(self) -> None:
        try:
            self.require_permission("tournament_write")
            if getattr(self, "pairing_team_mode", False):
                self._open_team_player_swap_dialog()
                return
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            pairing = self._selected_pairing()
            if not pairing:
                raise AppError("Selecione uma mesa.")

            players = self.db.list_players(self.current_tournament_id, active_only=True)
            if not players:
                raise AppError("Nao ha jogadores ativos para trocar.")

            player_options = [
                f"{player['id']} - {player_pairing_name(player)} ({player['rating']})"
                for player in players
            ]
            player_map = {option: int(option.split(" ", maxsplit=1)[0]) for option in player_options}
            slot_options = ["Brancas"]
            if not pairing["is_bye"]:
                slot_options.append("Pretas")

            dialog = ctk.CTkToplevel(self)
            dialog.title("Trocar jogador")
            dialog.geometry("430x260")
            dialog.resizable(False, False)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            title = (
                f"Mesa {pairing['board_number']}: "
                f"{pairing['white_display_name']} x "
                f"{pairing['black_display_name']}"
            )
            ctk.CTkLabel(
                dialog,
                text=title,
                font=font_section(),
                wraplength=380,
                justify="left",
            ).grid(row=0, column=0, padx=18, pady=(18, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Lado a trocar").grid(row=1, column=0, padx=18, pady=(4, 4), sticky="w")
            slot_option = ctk.CTkOptionMenu(dialog, values=slot_options, width=180)
            slot_option.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Jogador").grid(row=3, column=0, padx=18, pady=(4, 4), sticky="w")
            player_option = ctk.CTkOptionMenu(dialog, values=player_options, width=360)
            player_option.grid(row=4, column=0, padx=18, pady=(0, 16), sticky="w")

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=5, column=0, padx=18, pady=(2, 18), sticky="e")

            def apply_swap() -> None:
                try:
                    color = "white" if slot_option.get() == "Brancas" else "black"
                    replacement_id = player_map[player_option.get()]
                    self.pairing_service.adjust_pairing_player(
                        self.current_tournament_id,
                        self.current_round_id,
                        pairing["id"],
                        color,
                        replacement_id,
                    )
                    dialog.destroy()
                    self._load_selected_round_pairings()
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(actions, text="Cancelar", fg_color=THEME_NEUTRAL, hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy).pack(
                side="left",
                padx=(0, 8),
            )
            ctk.CTkButton(actions, text="Aplicar", command=apply_swap).pack(side="left")
        except Exception as exc:
            self._show_error(exc)

    def _open_team_player_swap_dialog(self) -> None:
        try:
            self.require_permission("tournament_write")
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            board = self._selected_pairing()
            if not board:
                raise AppError("Selecione um tabuleiro.")

            players = self.db.list_players(self.current_tournament_id, active_only=True)
            if not players:
                raise AppError("Nao ha jogadores ativos para trocar.")

            player_options = []
            player_map: dict[str, int] = {}
            for player in players:
                team_assignment = self.db.get_team_player_by_player(int(player["id"]))
                team_name = team_assignment.get("team_name", "Sem equipe") if team_assignment else "Sem equipe"
                option = f"{player['id']} - {player_pairing_name(player)} ({player['rating']}) - {team_name}"
                player_options.append(option)
                player_map[option] = int(player["id"])

            dialog = ctk.CTkToplevel(self)
            dialog.title("Trocar jogador por equipes")
            dialog.geometry("500x290")
            dialog.resizable(False, False)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            title = (
                f"Match {board.get('team_match_id', '')} - Tab. {board['board_number']}: "
                f"{board.get('white_display_name', '')} x {board.get('black_display_name', '')}"
            )
            ctk.CTkLabel(
                dialog,
                text=title,
                font=font_section(),
                wraplength=450,
                justify="left",
            ).grid(row=0, column=0, padx=18, pady=(18, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Lado a trocar").grid(row=1, column=0, padx=18, pady=(4, 4), sticky="w")
            slot_option = ctk.CTkOptionMenu(dialog, values=["Brancas", "Pretas"], width=180)
            slot_option.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Jogador da mesma equipe").grid(
                row=3,
                column=0,
                padx=18,
                pady=(4, 4),
                sticky="w",
            )
            player_option = ctk.CTkOptionMenu(dialog, values=player_options, width=440)
            player_option.grid(row=4, column=0, padx=18, pady=(0, 16), sticky="w")

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=5, column=0, padx=18, pady=(2, 18), sticky="e")

            def apply_swap() -> None:
                try:
                    color = "white" if slot_option.get() == "Brancas" else "black"
                    replacement_id = player_map[player_option.get()]
                    self.pairing_service.adjust_team_board_player(
                        self.current_tournament_id,
                        self.current_round_id,
                        int(board["id"]),
                        color,
                        replacement_id,
                    )
                    dialog.destroy()
                    self._load_selected_round_pairings()
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(actions, text="Cancelar", fg_color=THEME_NEUTRAL, hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy).pack(
                side="left",
                padx=(0, 8),
            )
            ctk.CTkButton(actions, text="Aplicar", command=apply_swap).pack(side="left")
        except Exception as exc:
            self._show_error(exc)

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

    def _get_projector_data(self) -> list[dict[str, str]]:
        if not self.current_round_id:
            return []
        
        data = []
        if getattr(self, "pairing_team_mode", False):
            matches = self.db.list_team_matches_for_round(self.current_round_id)
            for match in matches:
                if match["is_bye"]:
                    data.append({
                        "board": f"M{match['match_number']}",
                        "white": match["white_team_name"],
                        "black": "BYE"
                    })
                    continue
                for board in self.db.list_team_boards(int(match["id"])):
                    white_name = player_pairing_name({
                        "name": board.get("white_player_name"),
                        "surname": board.get("white_player_surname"),
                        "given_name": board.get("white_player_given_name"),
                    })
                    black_name = player_pairing_name({
                        "name": board.get("black_player_name"),
                        "surname": board.get("black_player_surname"),
                        "given_name": board.get("black_player_given_name"),
                    })
                    data.append({
                        "board": f"M{match['match_number']} T{board['board_number']}",
                        "white": f"{white_name} ({match['white_team_name']})",
                        "black": f"{black_name} ({match['black_team_name']})"
                    })
        else:
            pairings = self.db.get_pairings_for_round(self.current_round_id)
            for pairing in pairings:
                white_name = pairing_player_name(pairing, "white")
                black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
                data.append({
                    "board": str(pairing["board_number"]),
                    "white": white_name,
                    "black": black_name
                })
        return data

    def _open_projector_mode(self) -> None:
        import math
        
        if not self.current_round_id:
            self._show_error(AppError("Selecione uma rodada primeiro."))
            return
            
        pairings_data = self._get_projector_data()
        if not pairings_data:
            self._show_error(AppError("Não há emparceiramentos nesta rodada para exibir."))
            return
            
        dialog = ctk.CTkToplevel(self)
        dialog.title("Modo Projetor - Albericus")
        dialog.configure(fg_color=PROJETOR_FUNDO) # Fundo preto para alto contraste
        dialog.transient(self)
        dialog.grab_set()
        # Abre maximizado por padrão
        dialog.after(10, lambda: dialog.state("zoomed"))
        
        # Estado do projetor
        state = {
            "current_page": 0,
            "font_size": 24,
            "num_cols": 2,
            "rows_per_col": 15,
            "slideshow_active": True,
            "slide_interval_ms": 10000,
            "after_id": None,
            "fullscreen": False
        }
        
        # Frame de Controle Superior (Fundo escuro discreto)
        controls_frame = ctk.CTkFrame(dialog, fg_color=PROJETOR_BARRA, corner_radius=0, height=60)
        controls_frame.pack(fill="x", side="top", padx=0, pady=0)
        
        # Frame de Conteúdo (Totalmente preto)
        content_frame = ctk.CTkFrame(dialog, fg_color=PROJETOR_FUNDO, corner_radius=0)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Funções de Atualização
        def get_capacity():
            return state["num_cols"] * state["rows_per_col"]
            
        def get_total_pages():
            cap = get_capacity()
            return max(1, math.ceil(len(pairings_data) / cap))
            
        def on_columns_change(val):
            state["num_cols"] = int(val.split()[0])
            state["current_page"] = 0
            draw_page()
            reset_slideshow_timer()
            
        def on_rows_change(val):
            state["rows_per_col"] = int(val)
            state["current_page"] = 0
            draw_page()
            reset_slideshow_timer()
            
        def on_interval_change(val):
            state["slide_interval_ms"] = int(val.replace("s", "")) * 1000
            reset_slideshow_timer()
            
        def change_font_size(delta):
            state["font_size"] = max(12, min(48, state["font_size"] + delta))
            draw_page()
            
        def toggle_slideshow():
            state["slideshow_active"] = not state["slideshow_active"]
            if state["slideshow_active"]:
                btn_play.configure(text="⏸ Pausar")
                reset_slideshow_timer()
            else:
                btn_play.configure(text="▶ Iniciar")
                if state["after_id"]:
                    dialog.after_cancel(state["after_id"])
                    state["after_id"] = None
            update_page_label()
            
        def prev_page():
            total_pages = get_total_pages()
            state["current_page"] = (state["current_page"] - 1) % total_pages
            draw_page()
            reset_slideshow_timer()
            
        def next_page():
            total_pages = get_total_pages()
            state["current_page"] = (state["current_page"] + 1) % total_pages
            draw_page()
            reset_slideshow_timer()
            
        def reset_slideshow_timer():
            if state["after_id"]:
                dialog.after_cancel(state["after_id"])
                state["after_id"] = None
            if state["slideshow_active"]:
                state["after_id"] = dialog.after(state["slide_interval_ms"], auto_advance)
                
        def auto_advance():
            total_pages = get_total_pages()
            if total_pages > 1:
                state["current_page"] = (state["current_page"] + 1) % total_pages
                draw_page()
            reset_slideshow_timer()
            
        def update_page_label():
            total_pages = get_total_pages()
            status_text = "Slide" if state["slideshow_active"] else "Pausado"
            lbl_page.configure(text=f"Pág: {state['current_page'] + 1}/{total_pages} ({status_text})")
            
        def toggle_fullscreen(event=None):
            state["fullscreen"] = not state["fullscreen"]
            dialog.attributes("-fullscreen", state["fullscreen"])
            if state["fullscreen"]:
                controls_frame.pack_forget()
                self._show_toast("Pressione ESC ou F11 para sair do modo tela cheia.", kind="info", duration_ms=2500)
            else:
                controls_frame.pack(fill="x", side="top", padx=0, pady=0)
                controls_frame.pack_configure(before=content_frame)
                
        def exit_fullscreen(event=None):
            if state["fullscreen"]:
                state["fullscreen"] = False
                dialog.attributes("-fullscreen", False)
                controls_frame.pack(fill="x", side="top", padx=0, pady=0)
                controls_frame.pack_configure(before=content_frame)
                
        # Configurar Controles
        # Fonte controls
        lbl_font = ctk.CTkLabel(controls_frame, text="Fonte:", text_color=PROJETOR_TEXTO, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl_font.pack(side="left", padx=(15, 5))
        
        btn_font_dec = ctk.CTkButton(controls_frame, text="-", width=30, height=28, font=ctk.CTkFont(size=SIZE_PAGE_SUBTITLE, weight="bold"), command=lambda: change_font_size(-2))
        btn_font_dec.pack(side="left", padx=2)
        
        btn_font_inc = ctk.CTkButton(controls_frame, text="+", width=30, height=28, font=ctk.CTkFont(size=SIZE_PAGE_SUBTITLE, weight="bold"), command=lambda: change_font_size(2))
        btn_font_inc.pack(side="left", padx=2)
        
        # Colunas controls
        lbl_cols = ctk.CTkLabel(controls_frame, text="Colunas:", text_color=PROJETOR_TEXTO, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl_cols.pack(side="left", padx=(15, 5))
        
        cols_menu = ctk.CTkOptionMenu(controls_frame, values=["1 Coluna", "2 Colunas", "3 Colunas", "4 Colunas"], width=110, height=28, command=on_columns_change)
        cols_menu.pack(side="left", padx=2)
        cols_menu.set("2 Colunas")
        
        # Linhas controls
        lbl_rows = ctk.CTkLabel(controls_frame, text="Linhas:", text_color=PROJETOR_TEXTO, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl_rows.pack(side="left", padx=(15, 5))
        
        rows_menu = ctk.CTkOptionMenu(controls_frame, values=["10", "15", "20", "25", "30"], width=80, height=28, command=on_rows_change)
        rows_menu.pack(side="left", padx=2)
        rows_menu.set("15")
        
        # Slideshow controls
        lbl_slide = ctk.CTkLabel(controls_frame, text="Slideshow:", text_color=PROJETOR_TEXTO, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl_slide.pack(side="left", padx=(15, 5))
        
        btn_prev = ctk.CTkButton(controls_frame, text="◀", width=35, height=28, command=prev_page)
        btn_prev.pack(side="left", padx=2)
        
        btn_play = ctk.CTkButton(controls_frame, text="⏸ Pausar", width=80, height=28, command=toggle_slideshow)
        btn_play.pack(side="left", padx=2)
        
        btn_next = ctk.CTkButton(controls_frame, text="▶", width=35, height=28, command=next_page)
        btn_next.pack(side="left", padx=2)
        
        interval_menu = ctk.CTkOptionMenu(controls_frame, values=["5s", "8s", "10s", "12s", "15s", "20s"], width=75, height=28, command=on_interval_change)
        interval_menu.pack(side="left", padx=5)
        interval_menu.set("10s")
        
        # Pagina indicator
        lbl_page = ctk.CTkLabel(controls_frame, text="Pág: 1/1 (Slide)", text_color=PROJETOR_DESTAQUE, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl_page.pack(side="left", padx=(15, 10))
        
        # Tela cheia button
        btn_fs = ctk.CTkButton(controls_frame, text="Tela Cheia [F11]", width=120, height=28, fg_color=PROJETOR_BOTAO, hover_color=PROJETOR_BOTAO_HOVER, command=toggle_fullscreen)
        btn_fs.pack(side="right", padx=15)
        
        # Atalhos
        dialog.bind("<Escape>", exit_fullscreen)
        dialog.bind("<F11>", toggle_fullscreen)
        
        def draw_page():
            for child in content_frame.winfo_children():
                child.destroy()
                
            num_cols = state["num_cols"]
            rows_per_col = state["rows_per_col"]
            cap = num_cols * rows_per_col
            total_pages = get_total_pages()
            
            if state["current_page"] >= total_pages:
                state["current_page"] = 0
            curr_page = state["current_page"]
            
            update_page_label()
            
            start_idx = curr_page * cap
            end_idx = start_idx + cap
            page_pairings = pairings_data[start_idx:end_idx]
            
            header_font = ctk.CTkFont(family="Segoe UI", size=state["font_size"] + 2, weight="bold")
            bold_font   = ctk.CTkFont(family="Segoe UI", size=state["font_size"],     weight="bold")
            board_font  = ctk.CTkFont(family="Segoe UI", size=state["font_size"] + 8, weight="bold")
            
            # Grid columns config
            for c in range(num_cols):
                content_frame.grid_columnconfigure(c, weight=1, uniform="equal")
            content_frame.grid_rowconfigure(0, weight=1)
            
            for c in range(num_cols):
                col_start = c * rows_per_col
                col_pairings = page_pairings[col_start : col_start + rows_per_col]
                if not col_pairings and c > 0:
                    continue
                    
                col_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
                col_frame.grid(row=0, column=c, sticky="nsew", padx=10, pady=0)
                col_frame.grid_columnconfigure(0, weight=1)
                
                # Cabeçalho da coluna
                header_row = ctk.CTkFrame(col_frame, fg_color=PROJETOR_LINHA_PAR, corner_radius=4)
                header_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
                header_row.grid_columnconfigure(0, weight=1)
                header_row.grid_columnconfigure(1, weight=3)
                header_row.grid_columnconfigure(2, weight=3)
                
                ctk.CTkLabel(header_row, text="Mesa", font=header_font, text_color=PROJETOR_MESA).grid(row=0, column=0, padx=8, pady=8)
                ctk.CTkLabel(header_row, text="Brancas", font=header_font, text_color=PROJETOR_TEXTO).grid(row=0, column=1, padx=8, pady=8, sticky="w")
                ctk.CTkLabel(header_row, text="Pretas", font=header_font, text_color=PROJETOR_TEXTO).grid(row=0, column=2, padx=8, pady=8, sticky="w")
                
                # Linhas da tabela
                for r, pairing in enumerate(col_pairings):
                    is_bye = pairing["black"] == "BYE" or pairing["white"] == "BYE"
                    
                    if is_bye:
                        bg_color = PROJETOR_LINHA_PAR if r % 2 == 0 else PROJETOR_LINHA_IMPAR
                        text_color = PROJETOR_TEXTO_SUAVE
                        board_color = PROJETOR_TABULEIRO
                    else:
                        bg_color = PROJETOR_LINHA_PAR if r % 2 == 0 else PROJETOR_LINHA_IMPAR
                        text_color = PROJETOR_TEXTO
                        board_color = PROJETOR_DESTAQUE
                        
                    row_frame = ctk.CTkFrame(col_frame, fg_color=bg_color, corner_radius=4)
                    row_frame.grid(row=r + 1, column=0, sticky="ew", pady=2)
                    row_frame.grid_columnconfigure(0, weight=1)
                    row_frame.grid_columnconfigure(1, weight=3)
                    row_frame.grid_columnconfigure(2, weight=3)
                    
                    # Labels mesa, brancas e pretas (todos em negrito)
                    lbl_board = ctk.CTkLabel(row_frame, text=pairing["board"], font=board_font, text_color=board_color)
                    lbl_board.grid(row=0, column=0, padx=8, pady=6)
                    
                    lbl_white = ctk.CTkLabel(row_frame, text=pairing["white"], font=bold_font, text_color=text_color, anchor="w")
                    lbl_white.grid(row=0, column=1, padx=8, pady=6, sticky="w")
                    
                    lbl_black = ctk.CTkLabel(row_frame, text=pairing["black"], font=bold_font, text_color=text_color, anchor="w")
                    lbl_black.grid(row=0, column=2, padx=8, pady=6, sticky="w")
        
        def on_close():
            if state["after_id"]:
                dialog.after_cancel(state["after_id"])
                state["after_id"] = None
            dialog.destroy()
            
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        draw_page()
        reset_slideshow_timer()
