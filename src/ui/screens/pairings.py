from __future__ import annotations

from ..support import *


class PairingPagesMixin:
    def show_arbitration_panel(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        dashboard = self.pairing_service.arbitration_dashboard(self.current_tournament_id)
        metrics = dashboard["metrics"]
        alerts = dashboard["alerts"]

        self._clear_content()
        self._page_title(
            "Painel do arbitro",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        cards = ctk.CTkFrame(body, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(5):
            cards.grid_columnconfigure(column, weight=1)

        card_data = [
            ("Rodadas", f"{metrics['closed_rounds']}/{metrics['rounds_count']}", f"{metrics['generated_rounds']} gerada(s)"),
            ("Pendentes", str(metrics["pending_results"]), "resultados sem fechar"),
            ("Byes", str(metrics["byes"]), "na rodada atual"),
            ("Ausentes", str(metrics["absent_players"]), "jogadores"),
            ("Correcoes", str(metrics["corrections"]), "auditadas"),
        ]
        for index, (title, value, subtitle) in enumerate(card_data):
            card = self._make_panel(cards)
            card.grid(row=0, column=index, padx=(0 if index == 0 else 8, 0), sticky="ew")
            ctk.CTkLabel(card, text=title, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=14, pady=(12, 0))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=14)
            ctk.CTkLabel(card, text=subtitle, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=14, pady=(0, 12))

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        alerts_panel = self._make_panel(main)
        alerts_panel.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        alerts_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            alerts_panel,
            text="Alertas operacionais",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")
        if alerts:
            for row, alert in enumerate(alerts, start=1):
                ctk.CTkLabel(alerts_panel, text=f"- {alert}", anchor="w", justify="left").grid(
                    row=row,
                    column=0,
                    padx=14,
                    pady=(0, 6),
                    sticky="ew",
                )
        else:
            ctk.CTkLabel(alerts_panel, text="Nenhuma pendencia operacional detectada.").grid(
                row=1,
                column=0,
                padx=14,
                pady=(0, 12),
                sticky="w",
            )

        actions_panel = self._make_panel(main)
        actions_panel.grid(row=0, column=1, sticky="nsew")
        actions_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            actions_panel,
            text="Acoes rapidas",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        actions = [
            ("Central de pendencias", self.show_arbitration_issues),
            ("Abrir rodadas", self.show_pairings),
            ("Pre-visualizar proxima", self._preview_next_round),
            ("Fechar rodada atual", self._close_current_round_from_panel),
            ("Validar/exportar", self.show_export),
            ("Publicar HTML", self._export_site_from_panel),
            ("Publicar live", self._publish_live_portal_from_panel),
        ]
        for row, (label, command) in enumerate(actions, start=1):
            ctk.CTkButton(actions_panel, text=label, command=command).grid(
                row=row,
                column=0,
                padx=14,
                pady=(0, 8),
                sticky="ew",
            )

    def show_arbitration_issues(self) -> None:
        if not self._require_tournament():
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        payload = self.pairing_service.arbitration_issues(int(self.current_tournament_id))
        metrics = payload["metrics"]
        issue_cache: dict[str, dict[str, Any]] = {}

        self._clear_content()
        self._page_title(
            "Central de pendencias",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        summary = self._make_panel(body)
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(5):
            summary.grid_columnconfigure(column, weight=1)
        cards = [
            ("Total", metrics["total"]),
            ("QR", metrics["qr_pending"]),
            ("Sync", metrics["sync_conflicts"]),
            ("Relogio", metrics["clock_alerts"]),
            ("Decisao", metrics["decision_required"]),
        ]
        for column, (label, value) in enumerate(cards):
            ctk.CTkLabel(summary, text=label, text_color=THEME_TEXT_SUB).grid(
                row=0, column=column, padx=12, pady=(10, 0), sticky="w"
            )
            ctk.CTkLabel(summary, text=str(value), font=ctk.CTkFont(size=20, weight="bold")).grid(
                row=1, column=column, padx=12, pady=(0, 10), sticky="w"
            )

        panel = self._make_panel(body)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            panel,
            ["severity", "source", "kind", "title", "detail", "round", "created"],
            {
                "severity": "Nivel",
                "source": "Origem",
                "kind": "Tipo",
                "title": "Pendencia",
                "detail": "Detalhe",
                "round": "Rodada",
                "created": "Data",
            },
            {"severity": 95, "source": 80, "kind": 150, "title": 220, "detail": 360, "round": 80, "created": 150},
            visible_rows=18,
        )
        for index, issue in enumerate(payload["issues"], start=1):
            item_id = str(index)
            issue_cache[item_id] = issue
            tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    issue.get("severity") or "",
                    issue.get("source") or "",
                    issue.get("kind") or "",
                    issue.get("title") or "",
                    issue.get("detail") or "",
                    issue.get("round_id") or "",
                    issue.get("created_at") or "",
                ),
            )

        def show_issue_detail(_event: Any = None) -> None:
            selected = tree.selection()
            if not selected:
                self._show_error(AppError("Selecione uma pendencia."))
                return
            issue = issue_cache.get(str(selected[0]), {})
            self._show_json_detail("Pendencia de arbitragem", issue)

        tree.bind("<Double-1>", show_issue_detail)

        def selected_qr_submission_id() -> int:
            selected = tree.selection()
            if not selected:
                raise AppError("Selecione uma pendencia QR.")
            issue = issue_cache.get(str(selected[0]), {})
            if issue.get("source") != "qr" or issue.get("kind") != "result_submission":
                raise AppError("Selecione uma pendencia QR.")
            return int(issue["entity_id"])

        def selected_issue() -> dict[str, Any]:
            selected = tree.selection()
            if not selected:
                raise AppError("Selecione uma pendencia.")
            return issue_cache.get(str(selected[0]), {})

        def approve_selected_qr() -> None:
            try:
                self._approve_qr_submission(selected_qr_submission_id())
                self.show_arbitration_issues()
            except Exception as exc:
                self._show_error(exc)

        def reject_selected_qr() -> None:
            try:
                self._reject_qr_submission(selected_qr_submission_id())
                self.show_arbitration_issues()
            except Exception as exc:
                self._show_error(exc)

        def acknowledge_selected_issue() -> None:
            try:
                issue = selected_issue()
                if issue.get("source") == "qr":
                    raise AppError("Use Aprovar QR ou Rejeitar QR para pendencia QR.")
                self.pairing_service.acknowledge_arbitration_issue(
                    int(self.current_tournament_id),
                    str(issue.get("issue_key") or ""),
                )
                self._show_info("Pendencia marcada como ciente.")
                self.show_arbitration_issues()
            except Exception as exc:
                self._show_error(exc)

        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(footer, text="Atualizar", width=120, command=self.show_arbitration_issues).pack(side="left")
        ctk.CTkButton(footer, text="Detalhes", width=120, command=show_issue_detail).pack(side="left", padx=(8, 0))
        ctk.CTkButton(footer, text="Aprovar QR", width=120, command=approve_selected_qr).pack(side="left", padx=(8, 0))
        ctk.CTkButton(footer, text="Rejeitar QR", width=120, command=reject_selected_qr).pack(side="left", padx=(8, 0))
        ctk.CTkButton(footer, text="Marcar ciencia", width=140, command=acknowledge_selected_issue).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(footer, text="Abrir fila QR", width=140, command=self._open_qr_submissions_queue).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(footer, text="Integrações", width=140, command=self.show_integrations).pack(side="left", padx=(8, 0))
        ctk.CTkButton(footer, text="Voltar ao painel", width=140, command=self.show_arbitration_panel).pack(
            side="left", padx=(8, 0)
        )

    def _close_current_round_from_panel(self) -> None:
        latest = self.db.get_latest_round(self.current_tournament_id)
        if not latest:
            self._show_error(AppError("Nenhuma rodada gerada para fechar."))
            return
        self.current_round_id = int(latest["id"])
        self._close_current_round()
        self.show_arbitration_panel()

    def _export_site_from_panel(self) -> None:
        try:
            directory = self._default_export_dir() / f"site_torneio_{self.current_tournament_id}"
            index_path = self.export_service.export_site(self.current_tournament_id, directory)
            self._show_info(f"Site exportado:\n{index_path}")
        except Exception as exc:
            self._show_error(exc)

    def _publish_live_portal_from_panel(self) -> None:
        try:
            if self.local_result_server is None:
                self.local_result_server = LocalResultServer(self.qr_result_service)
            settings = self.db.get_app_settings()
            mode = str(settings.get("live_portal_mode") or "publico")
            url = self.local_result_server.publish_tournament(
                int(self.current_tournament_id),
                self.export_service,
                mode=mode,
            )
            self.db.save_app_settings({"local_result_server_url": self.local_result_server.url})
            self._show_info(
                "Portal live publicado:\n"
                f"{url}\n\n"
                "O JSON publico esta em:\n"
                f"{self.local_result_server.url}/api/tournaments/{self.current_tournament_id}/public?mode={mode}"
            )
        except Exception as exc:
            self._show_error(exc)

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
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(toolbar, text="Gerar proxima rodada", command=self._generate_round).grid(
            row=0,
            column=0,
            padx=12,
            pady=12,
        )
        ctk.CTkButton(toolbar, text="Pre-visualizar rodada", command=self._preview_next_round).grid(
            row=0,
            column=1,
            padx=(0, 8),
            pady=12,
        )

        if not show_initial_call:
            self.round_option = ctk.CTkOptionMenu(
                toolbar,
                values=["Sem rodadas"],
                command=lambda _value: self._load_selected_round_pairings(),
                width=190,
            )
            self.round_option.grid(row=0, column=2, padx=8, pady=12, sticky="w")

            self.result_option = ctk.CTkOptionMenu(toolbar, values=RESULTS, width=130)
            self.result_option.grid(row=0, column=3, padx=8, pady=12)
            ctk.CTkButton(toolbar, text="Salvar resultado", command=self._save_selected_result).grid(
                row=0,
                column=4,
                padx=8,
                pady=12,
            )
            quick_results = ctk.CTkFrame(toolbar, fg_color="transparent")
            quick_results.grid(row=0, column=5, padx=(4, 12), pady=12, sticky="e")
            for label, result in [("1-0", "1-0"), ("1/2", "1/2-1/2"), ("0-1", "0-1"), ("Limpar", "")]:
                ctk.CTkButton(
                    quick_results,
                    text=label,
                    width=64,
                    command=lambda value=result: self._quick_save_result(value),
                ).pack(side="left", padx=(0, 6))
            round_actions = ctk.CTkFrame(toolbar, fg_color="transparent")
            round_actions.grid(row=1, column=0, columnspan=6, padx=12, pady=(0, 12), sticky="ew")
            for column in range(6):
                round_actions.grid_columnconfigure(column, weight=1)
            ctk.CTkButton(round_actions, text="Trocar cores", command=self._swap_selected_colors).grid(
                row=0,
                column=0,
                padx=(0, 4),
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Trocar jogador", command=self._open_player_swap_dialog).grid(
                row=0,
                column=1,
                padx=4,
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Fechar rodada", command=self._close_current_round).grid(
                row=0,
                column=2,
                padx=4,
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Excluir gerada", command=self._delete_current_round).grid(
                row=0,
                column=3,
                padx=4,
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Exportar rodada", command=self._export_current_round_pairings).grid(
                row=0,
                column=4,
                padx=4,
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Imprimir rodada", command=self._print_current_round_pairings).grid(
                row=0,
                column=5,
                padx=(4, 0),
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="QR mesa", command=self._show_selected_pairing_qr_link).grid(
                row=1,
                column=0,
                padx=(0, 4),
                pady=(8, 0),
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Submissoes QR", command=self._open_qr_submissions_queue).grid(
                row=1,
                column=1,
                padx=4,
                pady=(8, 0),
                sticky="ew",
            )
            ctk.CTkButton(round_actions, text="Servidor QR", command=self._start_qr_result_server).grid(
                row=1,
                column=2,
                padx=4,
                pady=(8, 0),
                sticky="ew",
            )

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
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=0, column=0, sticky="w")
            self.initial_call_summary_label = ctk.CTkLabel(
                roster_header,
                text="Presentes: 0 | Ausentes: 0 | Total: 0",
                text_color=THEME_TEXT_SUB,
            )
            self.initial_call_summary_label.grid(row=1, column=0, pady=(2, 0), sticky="w")
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
                visible_rows=5,
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
        ordered_players = sorted(
            players,
            key=lambda player: (
                0 if player.get("player_status") == "active" else 1,
                -int(player.get("rating") or 0),
                player_pairing_name(player).casefold(),
            ),
        )
        for start_number, player in enumerate(ordered_players, start=1):
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
        for pairing in pairings:
            white_name = pairing_player_name(pairing, "white")
            black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
            state = self._individual_result_state(pairing, submissions_by_pairing, corrected_pairing_ids)
            item_id = self.pairing_tree.insert(
                "",
                "end",
                values=(
                    pairing["board_number"],
                    white_name,
                    pairing["white_rating"],
                    pairing["result"],
                    state,
                    black_name,
                    "" if pairing["is_bye"] else pairing["black_rating"],
                ),
                tags=(self._result_state_tag(state),),
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
        tree.tag_configure("result_state_vazio", foreground="#64748B")
        tree.tag_configure("result_state_registrado", foreground="#166534")
        tree.tag_configure("result_state_submetido_qr", foreground="#B45309")
        tree.tag_configure("result_state_aprovado_qr", foreground="#166534")
        tree.tag_configure("result_state_rejeitado_qr", foreground="#991B1B")
        tree.tag_configure("result_state_corrigido", foreground="#7C3AED")
        tree.tag_configure("result_state_bloqueado", foreground="#334155")

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
        if result in RESULTS:
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

        choice = messagebox.askyesnocancel(
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
        try:
            self.require_permission("tournament_write")
            if not self._confirm_short_tournament_round_count():
                return
            self.pairing_service.generate_next_round(self.current_tournament_id)
            self.show_pairings()
        except Exception as exc:
            self._show_error(exc)

    def _preview_next_round(self) -> None:
        try:
            preview = self.pairing_service.preview_next_round(self.current_tournament_id)
            self._show_info(self._format_pairing_preview(preview))
        except Exception as exc:
            self._show_error(exc)

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
            result = self.result_option.get()
            if result not in RESULTS:
                raise AppError("Resultado invalido.")
            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
                    if not settings.get("allow_dangerous_changes"):
                        raise AppError(
                            "Habilite mudancas perigosas nas configuracoes do torneio para alterar rodada fechada."
                        )
                    confirmed = messagebox.askyesno(
                        "Confirmar",
                        "Esta rodada ja esta fechada. Alterar o resultado mesmo assim?",
                    )
                    if not confirmed:
                        return
            self.pairing_service.update_result(self.current_tournament_id, pairing_id, result)
            self._load_selected_round_pairings()
        except Exception as exc:
            self._show_error(exc)

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
        self._show_info("Resultado QR aprovado.")

    def _reject_qr_submission(self, submission_id: int) -> None:
        reviewer, _role = self.db._operator_context()
        self.qr_result_service.reject_submission(submission_id, reviewer=reviewer)
        self._show_info("Resultado QR rejeitado.")

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
                font=ctk.CTkFont(size=15, weight="bold"),
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

            ctk.CTkButton(actions, text="Cancelar", fg_color="#64748B", command=dialog.destroy).pack(
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
                font=ctk.CTkFont(size=15, weight="bold"),
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

            ctk.CTkButton(actions, text="Cancelar", fg_color="#64748B", command=dialog.destroy).pack(
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
            self._show_info("Rodada fechada.")
        except Exception as exc:
            self._show_error(exc)

    def _delete_current_round(self) -> None:
        try:
            self.require_permission("tournament_write")
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            if not messagebox.askyesno("Confirmar", "Excluir a rodada gerada selecionada?"):
                return
            self.pairing_service.delete_generated_round(self.current_round_id)
            self._load_round_options()
        except Exception as exc:
            self._show_error(exc)

    def show_standings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
        self._clear_content()
        self._page_title(
            "Classificacao",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("standings")

        if settings.get("hide_standings"):
            body = ctk.CTkFrame(self.content, fg_color="transparent")
            body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
            panel = self._make_panel(body)
            panel.pack(anchor="nw", fill="x")
            ctk.CTkLabel(
                panel,
                text="A classificacao esta oculta nas configuracoes do torneio.",
                text_color=THEME_TEXT_SUB,
            ).pack(anchor="w", padx=16, pady=16)
            return

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        if tournament and tournament.get("competition_type") == "team":
            ctk.CTkButton(toolbar, text="Recalcular", command=self.show_standings).pack(
                side="left",
                padx=12,
                pady=12,
            )

            table_panel = self._make_panel(body)
            table_panel.grid(row=1, column=0, sticky="nsew")
            table_panel.grid_columnconfigure(0, weight=1)
            table_panel.grid_rowconfigure(0, weight=1)

            tree = self._make_tree(
                table_panel,
                [
                    "pos",
                    "team",
                    "club",
                    "captain",
                    "match_points",
                    "game_points",
                    "wins",
                    "draws",
                    "losses",
                    "byes",
                    "buchholz",
                    "status",
                ],
                {
                    "pos": "Pos",
                    "team": "Equipe",
                    "club": "Clube/Cidade",
                    "captain": "Capitao",
                    "match_points": "MP",
                    "game_points": "GP",
                    "wins": "V",
                    "draws": "E",
                    "losses": "D",
                    "byes": "Byes",
                    "buchholz": "Buchholz",
                    "status": "Status",
                },
                {
                    "pos": 60,
                    "team": 240,
                    "club": 170,
                    "captain": 150,
                    "match_points": 70,
                    "game_points": 70,
                    "wins": 55,
                    "draws": 55,
                    "losses": 55,
                    "byes": 65,
                    "buchholz": 90,
                    "status": 90,
                },
            )
            self.standings_tree = tree

            for item in self.pairing_service.team_standings(self.current_tournament_id):
                tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item.get("club", ""),
                        item.get("captain", ""),
                        item["match_points"],
                        item["game_points"],
                        item["wins"],
                        item["draws"],
                        item["losses"],
                        item["byes"],
                        item["buchholz"],
                        "Ativa" if item.get("active") else "Inativa",
                    ),
                )
            return

        def apply_internal_rating() -> None:
            try:
                result = self.internal_rating_service.apply_tournament_ratings(
                    int(self.current_tournament_id)
                )
                self._show_info(
                    "Ratings internos atualizados: {updated}\n"
                    "Ja aplicados anteriormente: {duplicates}\n"
                    "Sem performance suficiente: {skipped}\n"
                    "Convidados externos ignorados: {external}".format(**result)
                )
                self.show_standings()
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(toolbar, text="Recalcular", command=self.show_standings).pack(
            side="left",
            padx=12,
            pady=12,
        )
        ctk.CTkButton(
            toolbar,
            text="Atualizar rating interno",
            command=apply_internal_rating,
        ).pack(side="left", padx=(0, 12), pady=12)
        categories = sorted(
            {
                str(player["category"]).strip()
                for player in self.db.list_players(self.current_tournament_id, active_only=False)
                if str(player["category"]).strip()
            }
        )
        ctk.CTkLabel(toolbar, text="Categoria").pack(side="left", padx=(10, 6), pady=12)
        category_option = ctk.CTkOptionMenu(toolbar, values=["Todas"] + categories, width=170)
        category_option.pack(side="left", padx=(0, 12), pady=12)

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            table_panel,
            [
                "pos",
                "name",
                "category",
                "age_category",
                "rating_category",
                "tags",
                "points",
                "buchholz",
                "median",
                "sb",
                "wins",
                "performance",
                "rating",
                "club",
            ],
            {
                "pos": "Pos",
                "name": "Nome",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "points": "Pts",
                "buchholz": "Buchholz",
                "median": "Buchholz M",
                "sb": "SB",
                "wins": "Vitorias",
                "performance": "Perf.",
                "rating": "Rating",
                "club": "Clube",
            },
            {
                "pos": 60,
                "name": 220,
                "category": 105,
                "age_category": 85,
                "rating_category": 90,
                "tags": 150,
                "points": 70,
                "buchholz": 90,
                "median": 100,
                "sb": 80,
                "wins": 80,
                "performance": 80,
                "rating": 80,
                "club": 180,
            },
        )
        self.standings_tree = tree
        row_player_ids: dict[str, int] = {}

        def show_tiebreak_detail(criterion: str = "") -> None:
            selected = tree.selection()
            if not selected:
                self._show_info("Selecione um jogador na classificacao.")
                return
            player_id = row_player_ids.get(selected[0])
            if not player_id:
                return
            standings = self.pairing_service.tiebreak_report(
                int(self.current_tournament_id),
                player_id=player_id,
            )
            if not standings:
                self._show_info("Nao ha componentes de desempate para este jogador.")
                return
            components = standings[0].get("tiebreak_components") or {}
            keys = [criterion] if criterion else [
                "buchholz",
                "buchholz_median",
                "sonneborn_berger",
                "direct_encounter",
                "wins",
                "performance",
            ]
            lines = [f"{standings[0]['name']} - {standings[0]['points']} ponto(s)"]
            for key in keys:
                component = components.get(key) or {}
                if not component:
                    continue
                lines.append("")
                lines.append(f"{component.get('label', key)}: {component.get('value', '')}")
                lines.append(str(component.get("formula", "")))
                for opponent in component.get("opponents", [])[:8]:
                    value = opponent.get("contribution", opponent.get("points", ""))
                    lines.append(f"- {opponent.get('opponent_name', '')}: {value}")
                if "used_scores" in component:
                    lines.append(f"- Usados: {component.get('used_scores', [])}")
                    if component.get("cut_low") is not None:
                        lines.append(f"- Corte menor: {component.get('cut_low')}")
                    if component.get("cut_high") is not None:
                        lines.append(f"- Corte maior: {component.get('cut_high')}")
                for game in component.get("games", [])[:8]:
                    lines.append(f"- {game.get('opponent_name', '')}: {game.get('earned', '')}")
            self._show_info("\n".join(lines))

        ctk.CTkButton(
            toolbar,
            text="Explicar desempate",
            command=lambda: show_tiebreak_detail(),
        ).pack(side="left", padx=(0, 12), pady=12)

        for column, criterion in {
            "buchholz": "buchholz",
            "median": "buchholz_median",
            "sb": "sonneborn_berger",
            "wins": "wins",
            "performance": "performance",
        }.items():
            tree.heading(
                column,
                text=tree.heading(column)["text"],
                command=lambda selected_criterion=criterion: show_tiebreak_detail(selected_criterion),
            )

        def load_standings() -> None:
            tree.delete(*tree.get_children())
            row_player_ids.clear()
            category = category_option.get()
            for item in self.pairing_service.standings(self.current_tournament_id):
                if category != "Todas" and item["category"] != category:
                    continue
                row_id = tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item.get("category", ""),
                        item.get("age_category", ""),
                        item.get("rating_category", ""),
                        item.get("prize_tags", ""),
                        item["points"],
                        item["buchholz"],
                        item["buchholz_median"],
                        item["sonneborn_berger"],
                        item["wins"],
                        item["performance"],
                        item["rating"],
                        item["club"],
                    ),
                )
                row_player_ids[row_id] = int(item["player_id"])

        category_option.configure(command=lambda _value: load_standings())
        load_standings()


