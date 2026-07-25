from __future__ import annotations

from ..support import *
from ..components import debounce


class ArbitrationPagesMixin:
    def show_arbitration_panel(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        dashboard = self.pairing_service.arbitration_dashboard(
            self.current_tournament_id,
            pending_limit=self._arbitration_inline_tables_limit,
            pending_query=getattr(self, "_arbitration_pending_query", ""),
        )
        metrics = dashboard["metrics"]
        alerts = dashboard["alerts"]
        alerts_detailed = dashboard.get("alerts_detailed", [])
        pending_items = dashboard["pending_items"]

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
        for column in range(6):
            cards.grid_columnconfigure(column, weight=1)

        card_data = [
            ("Rodadas", f"{metrics['closed_rounds']}/{metrics['rounds_count']}", f"{metrics['generated_rounds']} gerada(s)", self.show_pairings),
            ("Pendentes", str(metrics["pending_results"]), "resultados sem fechar", self.show_pairings),
            ("Byes", str(metrics["byes"]), "na rodada atual", self.show_pairings),
            ("Ausentes", str(metrics["absent_players"]), "jogadores", self.show_players),
            ("Correcoes", str(metrics["corrections"]), "auditadas", self.show_audit_logs),
            (
                "Tempo rodada",
                metrics["round_duration_label"],
                f"Inicio {metrics['round_started_label']} | {metrics['round_clock_status'].replace('_', ' ')}",
                self.show_pairings,
            ),
        ]
        for index, (title, value, subtitle, command) in enumerate(card_data):
            card = self._kpi_card(cards, title, value, subtitle=subtitle, command=command)
            card.grid(row=0, column=index, padx=(0 if index == 0 else 8, 0), sticky="ew")

        progress_total = int(metrics.get("total_results") or 0)
        if progress_total:
            resolved_results = int(metrics.get("resolved_results") or 0)
            progress_percent = int(metrics.get("round_progress_percent") or 0)
            progress_bar = ctk.CTkProgressBar(cards)
            progress_bar.set(max(0.0, min(1.0, progress_percent / 100)))
            progress_bar.grid(row=1, column=0, columnspan=5, padx=(0, 8), pady=(12, 0), sticky="ew")
            ctk.CTkLabel(
                cards,
                text=f"Rodada: {resolved_results}/{progress_total} mesas resolvidas ({progress_percent}%)",
                text_color=THEME_TEXT_SUB,
            ).grid(row=1, column=5, padx=(8, 0), pady=(12, 0), sticky="e")

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        alerts_panel = self._make_panel(main)
        alerts_panel.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        alerts_panel.grid_columnconfigure(0, weight=1)
        alerts_panel.grid_columnconfigure(1, weight=0)
        self._section_title(alerts_panel, "Alertas operacionais").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )
        if metrics["blocking_issues"] or metrics["submitted_results"]:
            next_label = "Resolver pendencias bloqueantes"
            next_command = self.show_arbitration_issues
        elif metrics["pending_results"]:
            next_label = f"Lancar {metrics['pending_results']} resultado(s) pendente(s)"
            next_command = self.show_pairings
        elif metrics["ready_to_close"]:
            next_label = f"Fechar rodada {metrics['latest_round_number']}"
            next_command = self._close_current_round_from_panel
        elif metrics["can_preview_next_round"]:
            next_label = "Pre-visualizar proxima rodada"
            next_command = self._preview_next_round
        else:
            next_label = "Abrir chamada inicial"
            next_command = self.show_pairings
        ctk.CTkLabel(alerts_panel, text="Próximo passo recomendado", text_color=THEME_TEXT_SUB).grid(
            row=0, column=1, padx=(8, 14), pady=(14, 2), sticky="e"
        )
        ctk.CTkButton(
            alerts_panel,
            text=next_label,
            command=next_command,
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
        ).grid(row=1, column=1, rowspan=max(1, len(alerts)), padx=(8, 14), pady=(0, 12), sticky="ne")
        alert_commands = {
            "blocking_issues": self.show_arbitration_issues,
            "pending_results": self.show_pairings,
            "ready_to_close": self._close_current_round_from_panel,
            "initial_call": self.show_pairings,
            "absent_players": self.show_players,
            "corrections": self.show_audit_logs,
            "qr_pending": self.show_arbitration_issues,
            "preview_next": self._preview_next_round,
        }
        alert_colors = {
            "danger": THEME_DANGER,
            "warning": THEME_DANGER,
            "success": THEME_SUCCESS,
            "info": THEME_TEXT_MAIN,
        }
        if alerts_detailed:
            for row, alert in enumerate(alerts_detailed, start=1):
                color = alert_colors.get(str(alert.get("severity") or "info"), THEME_TEXT_MAIN)
                command = alert_commands.get(str(alert.get("action") or ""))
                if command is not None:
                    ctk.CTkButton(
                        alerts_panel,
                        text=f"- {alert['text']}   (resolver)",
                        anchor="w",
                        fg_color="transparent",
                        text_color=color,
                        hover_color=THEME_PANEL_BG,
                        command=command,
                    ).grid(row=row, column=0, padx=10, pady=(0, 4), sticky="ew")
                else:
                    ctk.CTkLabel(
                        alerts_panel,
                        text=f"- {alert['text']}",
                        anchor="w",
                        justify="left",
                        text_color=color,
                    ).grid(row=row, column=0, padx=14, pady=(0, 6), sticky="ew")
        else:
            ctk.CTkLabel(alerts_panel, text="Nenhuma pendencia operacional detectada.").grid(
                row=1,
                column=0,
                padx=14,
                pady=(0, 12),
                sticky="w",
            )

        # "Acoes rapidas" em 3 colunas: cabem sem rolagem e aproveitam a largura
        # extra cedida pela coluna esquerda (antes os itens finais, ex.: intervalo
        # de atualizacao, ficavam cortados na coluna estreita de 2 colunas).
        actions_panel = self._make_panel(main)
        actions_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")
        actions_panel.grid_columnconfigure(0, weight=1)
        actions_panel.grid_columnconfigure(1, weight=1)
        actions_panel.grid_columnconfigure(2, weight=1)
        self._section_title(actions_panel, "Acoes rapidas").grid(
            row=0, column=0, columnspan=3, padx=14, pady=(14, 8), sticky="w"
        )
        action_groups = [
            ("Rodada", [
                ("Central de pendencias", self.show_arbitration_issues),
                ("Abrir rodadas", self.show_pairings),
                ("Pre-visualizar proxima", self._preview_next_round),
                ("Checklist de fechamento", self._open_closing_checklist_dialog),
                ("Fechar rodada atual", self._close_current_round_from_panel),
            ]),
            ("Configuração arbitral", [
                ("Ajustes de pontos (TRF25)", self.show_point_adjustments),
                ("Proibicoes (TRF25)", self.show_prohibited_pairings),
                ("Byes solicitados (TRF25)", self.show_requested_byes),
            ]),
            ("Publicacao", [
                ("Validar/exportar", self.show_export),
                ("Publicar HTML", self._export_site_from_panel),
                ("Publicar live", self._publish_live_portal_from_panel),
                ("Pacote da rodada (PDF)", self._export_round_package_from_panel),
                ("Boletim da rodada (PDF)", self._export_round_bulletin_from_panel),
                ("Podio (PDF)", self._export_podium_from_panel),
                ("Ata final (PDF)", self._export_tournament_minutes_from_panel),
            ]),
        ]
        action_row = 1
        columns = 3
        for group_label, actions in action_groups:
            self._section_title(actions_panel, group_label, subsection=True).grid(
                row=action_row, column=0, columnspan=columns, padx=14, pady=(4, 4), sticky="w"
            )
            action_row += 1
            for index, (label, command) in enumerate(actions):
                col = index % columns
                ctk.CTkButton(actions_panel, text=label, command=command).grid(
                    row=action_row + index // columns,
                    column=col,
                    padx=(14 if col == 0 else 4, 14 if col == columns - 1 else 4),
                    pady=(0, 8),
                    sticky="ew",
                )
            action_row += (len(actions) + columns - 1) // columns

        controls = ctk.CTkFrame(actions_panel, fg_color="transparent")
        controls.grid(row=action_row, column=0, columnspan=columns, padx=14, pady=(4, 12), sticky="ew")
        auto_refresh = ctk.CTkCheckBox(
            controls,
            text="Atualizar automaticamente",
            command=self._toggle_arbitration_auto_refresh,
        )
        auto_refresh.grid(row=0, column=0, columnspan=2, sticky="w")
        if self._arbitration_auto_refresh_enabled:
            auto_refresh.select()
        ctk.CTkButton(controls, text="Atualizar agora", width=120, command=self.show_arbitration_panel).grid(
            row=0, column=2, padx=(8, 0), sticky="e"
        )
        ctk.CTkLabel(controls, text="Intervalo (s)", text_color=THEME_TEXT_SUB).grid(
            row=1, column=0, pady=(8, 0), sticky="w"
        )
        refresh_interval = ctk.CTkOptionMenu(
            controls,
            values=["10", "15", "30", "60", "120"],
            width=72,
            command=self._set_arbitration_refresh_interval,
        )
        refresh_interval.grid(row=1, column=1, padx=(6, 0), pady=(8, 0), sticky="w")
        refresh_interval.set(str(self._arbitration_refresh_interval_seconds))
        ctk.CTkLabel(controls, text="Mesas inline", text_color=THEME_TEXT_SUB).grid(
            row=2, column=0, pady=(8, 0), sticky="w"
        )
        inline_limit = ctk.CTkOptionMenu(
            controls,
            values=["10", "20", "30", "40", "50"],
            width=72,
            command=self._set_arbitration_inline_tables_limit,
        )
        inline_limit.grid(row=2, column=1, padx=(6, 0), pady=(8, 0), sticky="w")
        inline_limit.set(str(self._arbitration_inline_tables_limit))

        pending_panel = self._make_panel(main)
        pending_panel.grid(row=1, column=0, padx=(0, 12), pady=(12, 0), sticky="nsew")
        pending_panel.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(pending_panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self._section_title(header, "Mesas aguardando resultado").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=f"Exibindo {len(pending_items)} de {metrics['pending_results']}",
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=1, padx=(8, 0), sticky="e")
        ctk.CTkButton(header, text="Abrir lancamento", width=130, command=self.show_pairings).grid(
            row=0, column=2, padx=(10, 0), sticky="e"
        )
        pending_query_entry = ctk.CTkEntry(
            header,
            width=160,
            placeholder_text="Buscar mesa",
        )
        pending_query_entry.grid(row=1, column=0, pady=(8, 0), sticky="w")
        pending_query_entry.insert(0, getattr(self, "_arbitration_pending_query", ""))
        self.arbitration_pending_query_entry = pending_query_entry

        def apply_pending_query(_event: Any = None) -> None:
            self._arbitration_pending_query = pending_query_entry.get().strip()
            self.show_arbitration_panel()

        def clear_pending_query() -> None:
            self._arbitration_pending_query = ""
            self.show_arbitration_panel()

        pending_query_entry.bind("<Return>", apply_pending_query)
        ctk.CTkButton(header, text="Buscar mesa", width=110, command=apply_pending_query).grid(
            row=1, column=1, padx=(8, 0), pady=(8, 0), sticky="e"
        )
        ctk.CTkButton(header, text="Limpar busca", width=110, command=clear_pending_query).grid(
            row=1, column=2, padx=(10, 0), pady=(8, 0), sticky="e"
        )
        if pending_items:
            pending_tree = self._make_tree(
                pending_panel,
                ["board", "context", "white", "black"],
                {"board": "Mesa", "context": "Contexto", "white": "Brancas", "black": "Pretas"},
                {"board": 70, "context": 100, "white": 320, "black": 320},
                visible_rows=min(6, len(pending_items)),
            )
            pending_tree.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
            self.arbitration_pending_tree = pending_tree
            self.arbitration_pending_row_map = {}
            for item in pending_items:
                item_id = pending_tree.insert(
                    "",
                    "end",
                    values=(item["board"], item["context"], item["white"], item["black"]),
                )
                self.arbitration_pending_row_map[item_id] = int(item["pairing_id"])
            pending_tree.bind("<Double-1>", lambda _event: self.show_pairings())
            pending_tree.bind("1", lambda _event: self._save_arbitration_panel_result("1-0"))
            pending_tree.bind("<KP_1>", lambda _event: self._save_arbitration_panel_result("1-0"))
            pending_tree.bind("0", lambda _event: self._save_arbitration_panel_result("0-1"))
            pending_tree.bind("<KP_0>", lambda _event: self._save_arbitration_panel_result("0-1"))
            pending_tree.bind("-", lambda _event: self._save_arbitration_panel_result("1/2-1/2"))
            pending_tree.bind("<KP_Subtract>", lambda _event: self._save_arbitration_panel_result("1/2-1/2"))
            pending_tree.bind("<BackSpace>", lambda _event: self._save_arbitration_panel_result(""))
            pending_tree.bind("<Delete>", lambda _event: self._save_arbitration_panel_result(""))
            first_pending = pending_tree.get_children()
            if first_pending:
                pending_tree.selection_set(first_pending[0])
                pending_tree.focus(first_pending[0])
                pending_tree.see(first_pending[0])
            inline_actions = ctk.CTkFrame(pending_panel, fg_color="transparent")
            inline_actions.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
            ctk.CTkLabel(inline_actions, text="Lancar resultado:", text_color=THEME_TEXT_SUB).pack(side="left")
            for label, result in [("1-0", "1-0"), ("1/2", "1/2-1/2"), ("0-1", "0-1"), ("Limpar", "")]:
                ctk.CTkButton(
                    inline_actions,
                    text=label,
                    width=64,
                    command=lambda value=result: self._save_arbitration_panel_result(value),
                ).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(
                inline_actions,
                text="Atalhos: 1, -, 0 e Delete",
                text_color=THEME_TEXT_SUB,
            ).pack(side="right")
            pending_tree.focus_set()
        else:
            self.arbitration_pending_row_map = {}
            ctk.CTkLabel(
                pending_panel,
                text="Nenhuma mesa aguardando resultado.",
                text_color=THEME_TEXT_SUB,
            ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

        self._schedule_arbitration_refresh()

    def _save_arbitration_panel_result(self, result: str) -> str:
        try:
            tree = getattr(self, "arbitration_pending_tree", None)
            if tree is None:
                raise AppError("Nao ha mesas pendentes para lancamento.")
            selected = tree.selection()
            if not selected:
                raise AppError("Selecione uma mesa pendente.")
            pairing_id = self.arbitration_pending_row_map.get(selected[0])
            if not pairing_id:
                raise AppError("Mesa pendente nao encontrada.")
            self.pairing_service.update_result(int(self.current_tournament_id), int(pairing_id), result)
            self.show_arbitration_panel()
        except Exception as exc:
            self._show_error(exc)
        return "break"

    def _export_round_package_from_panel(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            rounds = self.db.list_rounds(self.current_tournament_id)
            if not rounds:
                raise AppError("Gere uma rodada antes de montar o pacote.")
            latest = sorted(rounds, key=lambda item: int(item["number"]))[-1]
            directory = filedialog.askdirectory(
                title="Pasta do pacote da rodada",
                initialdir=str(self._default_export_dir()),
            )
            if not directory:
                return

            def show_result(result: dict[str, Any]) -> None:
                message = f"{result['count']} documento(s) gerado(s) em:\n{directory}"
                if result["errors"]:
                    message += "\n\nAvisos:\n" + "\n".join(result["errors"][:6])
                self._show_info(message)

            self._run_background(
                lambda: self.export_service.export_round_package(int(latest["id"]), directory),
                show_result,
                "Gerando pacote da rodada...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_tournament_minutes_from_panel(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            tournament = self.db.get_tournament(self.current_tournament_id)
            initial = self._safe_filename(tournament["name"] if tournament else "torneio", "torneio") + "_ata_final.pdf"
            file_path = filedialog.asksaveasfilename(
                title="Ata final do torneio",
                initialdir=str(self._default_export_dir()),
                initialfile=initial,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("XLSX", "*.xlsx"), ("CSV", "*.csv")],
            )
            if not file_path:
                return
            self._run_background(
                lambda: self.export_service.export_tournament_minutes(int(self.current_tournament_id), file_path),
                lambda _result: self._show_info(f"Ata final gerada:\n{file_path}"),
                "Gerando ata final...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_round_bulletin_from_panel(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            rounds = self.db.list_rounds(self.current_tournament_id)
            if not rounds:
                raise AppError("Gere uma rodada antes de gerar o boletim.")
            latest = sorted(rounds, key=lambda item: int(item["number"]))[-1]
            tournament = self.db.get_tournament(self.current_tournament_id)
            initial = (
                self._safe_filename(tournament["name"] if tournament else "torneio", "torneio")
                + f"_boletim_r{latest['number']}.pdf"
            )
            file_path = filedialog.asksaveasfilename(
                title="Boletim da rodada",
                initialdir=str(self._default_export_dir()),
                initialfile=initial,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("XLSX", "*.xlsx"), ("CSV", "*.csv")],
            )
            if not file_path:
                return
            self._run_background(
                lambda: self.export_service.export_round_bulletin(int(latest["id"]), file_path),
                lambda _result: self._show_info(f"Boletim gerado:\n{file_path}"),
                "Gerando boletim da rodada...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_podium_from_panel(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            tournament = self.db.get_tournament(self.current_tournament_id)
            initial = self._safe_filename(tournament["name"] if tournament else "torneio", "torneio") + "_podio.pdf"
            file_path = filedialog.asksaveasfilename(
                title="Poster do podio",
                initialdir=str(self._default_export_dir()),
                initialfile=initial,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
            )
            if not file_path:
                return
            self._run_background(
                lambda: self.export_service.export_podium(int(self.current_tournament_id), file_path),
                lambda _result: self._show_info(f"Poster do podio gerado:\n{file_path}"),
                "Gerando poster do podio...",
            )
        except Exception as exc:
            self._show_error(exc)

    def _open_closing_checklist_dialog(self) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            items = self.pairing_service.closing_checklist(int(self.current_tournament_id))
        except Exception as exc:
            self._show_error(exc)
            return

        commands = {
            "blocking_issues": self.show_arbitration_issues,
            "pending_results": self.show_pairings,
            "qr_pending": self.show_arbitration_issues,
            "ready_to_close": self._close_current_round_from_panel,
            "initial_call": self.show_pairings,
            "lineups": self.show_teams,
        }
        dialog = ctk.CTkToplevel(self)
        dialog.title("Checklist de fechamento da rodada")
        dialog.geometry("540x360")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dialog, text="Confira antes de fechar a rodada:", anchor="w").grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="ew"
        )
        all_ok = True
        for index, item in enumerate(items, start=1):
            ok = bool(item.get("ok"))
            all_ok = all_ok and ok
            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.grid(row=index, column=0, padx=16, pady=2, sticky="ew")
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row,
                text="OK" if ok else "X",
                width=28,
                text_color=THEME_SUCCESS if ok else THEME_DANGER,
            ).grid(row=0, column=0, padx=(0, 8))
            ctk.CTkLabel(row, text=item.get("label", ""), anchor="w", justify="left").grid(row=0, column=1, sticky="w")
            command = commands.get(str(item.get("action") or ""))
            if not ok and command is not None:
                ctk.CTkButton(
                    row,
                    text="Resolver",
                    width=90,
                    command=lambda c=command, d=dialog: (d.destroy(), c()),
                ).grid(row=0, column=2, padx=(8, 0))

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=len(items) + 1, column=0, padx=16, pady=(12, 16), sticky="e")
        ctk.CTkButton(
            actions,
            text="Fechar dialogo",
            fg_color=THEME_NEUTRAL,
            hover_color=THEME_NEUTRAL_HOVER,
            command=dialog.destroy,
        ).pack(side="left", padx=(0, 8))
        close_round_btn = ctk.CTkButton(
            actions,
            text="Fechar rodada",
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
            command=lambda: (dialog.destroy(), self._close_current_round_from_panel()),
        )
        close_round_btn.pack(side="left")
        if not all_ok:
            close_round_btn.configure(state="disabled")

    def _schedule_arbitration_refresh(self) -> None:
        self._cancel_arbitration_refresh()
        if not self._arbitration_auto_refresh_enabled:
            return
        self._arbitration_refresh_job = self.after(
            self._arbitration_refresh_interval_seconds * 1000,
            self._arbitration_refresh_tick,
        )

    def _cancel_arbitration_refresh(self) -> None:
        if self._arbitration_refresh_job is None:
            return
        try:
            self.after_cancel(self._arbitration_refresh_job)
        except Exception:
            pass
        self._arbitration_refresh_job = None

    def _arbitration_refresh_tick(self) -> None:
        self._arbitration_refresh_job = None
        if getattr(self, "_current_view_method", "") == "show_arbitration_panel":
            self.show_arbitration_panel()

    def _toggle_arbitration_auto_refresh(self) -> None:
        self._arbitration_auto_refresh_enabled = not self._arbitration_auto_refresh_enabled
        self.db.save_app_settings(
            {"arbitration_auto_refresh_enabled": "1" if self._arbitration_auto_refresh_enabled else "0"}
        )
        if self._arbitration_auto_refresh_enabled:
            self._schedule_arbitration_refresh()
        else:
            self._cancel_arbitration_refresh()

    def _set_arbitration_refresh_interval(self, value: str) -> None:
        self._arbitration_refresh_interval_seconds = self._bounded_int_setting(
            {"value": value},
            "value",
            default=15,
            minimum=10,
            maximum=120,
        )
        self.db.save_app_settings(
            {"arbitration_refresh_interval_seconds": str(self._arbitration_refresh_interval_seconds)}
        )
        if self._arbitration_auto_refresh_enabled:
            self._schedule_arbitration_refresh()

    def _set_arbitration_inline_tables_limit(self, value: str) -> None:
        self._arbitration_inline_tables_limit = self._bounded_int_setting(
            {"value": value},
            "value",
            default=20,
            minimum=10,
            maximum=50,
        )
        self.db.save_app_settings(
            {"arbitration_inline_tables_limit": str(self._arbitration_inline_tables_limit)}
        )
        self.show_arbitration_panel()

    def show_arbitration_issues(self) -> None:
        if not self._require_tournament():
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        payload = self.pairing_service.arbitration_issues(int(self.current_tournament_id))
        metrics = payload["metrics"]
        issue_cache: dict[str, dict[str, Any]] = {}
        round_numbers = {
            int(round_data["id"]): int(round_data["number"])
            for round_data in self.db.list_rounds(int(self.current_tournament_id))
        }

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
            ctk.CTkLabel(summary, text=str(value), font=font_kpi_value()).grid(
                row=1, column=column, padx=12, pady=(0, 10), sticky="w"
            )

        panel = self._make_panel(body)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        filters = ctk.CTkFrame(panel, fg_color="transparent")
        filters.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        filters.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(filters, text="Filtro").grid(row=0, column=0, padx=(0, 6), sticky="w")
        filter_by_label = {
            "Todas": "all",
            "Decisao": "decision",
            "QR": "qr",
            "Sync": "sync",
            "Relogio": "clock",
        }
        issue_filter_option = ctk.CTkOptionMenu(filters, values=list(filter_by_label), width=125)
        issue_filter_option.grid(row=0, column=1, padx=(0, 10), sticky="w")
        issue_search_entry = ctk.CTkEntry(
            filters,
            placeholder_text="Buscar mesa, titulo ou detalhe",
        )
        issue_search_entry.grid(row=0, column=2, sticky="ew")
        issue_count_label = ctk.CTkLabel(filters, text="", text_color=THEME_TEXT_SUB)
        issue_count_label.grid(row=0, column=3, padx=(10, 0), sticky="e")
        table_panel = ctk.CTkFrame(panel, fg_color="transparent")
        table_panel.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            table_panel,
            ["severity", "source", "kind", "title", "detail", "round", "created"],
            {
                "severity": "Nível",
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
        self.arbitration_issues_tree = tree
        self.arbitration_issue_filter_option = issue_filter_option
        self.arbitration_issue_search_entry = issue_search_entry
        self.arbitration_issue_count_label = issue_count_label
        tree.tag_configure("decision", foreground=pick(THEME_DANGER))
        tree.tag_configure("attention", foreground=pick(THEME_WARNING_TEXT))

        def load_filtered_issues(_event: Any = None) -> None:
            tree.delete(*tree.get_children())
            issue_cache.clear()
            filtered_issues = self.pairing_service.filter_arbitration_issues(
                payload["issues"],
                filter_by_label.get(issue_filter_option.get(), "all"),
                issue_search_entry.get(),
            )
            issue_count_label.configure(text=f"Exibindo {len(filtered_issues)} de {metrics['total']}")
            for index, issue in enumerate(filtered_issues, start=1):
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
                        round_numbers.get(int(issue.get("round_id") or 0), ""),
                        issue.get("created_at") or "",
                    ),
                    tags=(str(issue.get("severity") or ""),),
                )
            first_issue = tree.get_children()
            if first_issue:
                tree.selection_set(first_issue[0])
                tree.focus(first_issue[0])
                tree.see(first_issue[0])

        issue_filter_option.configure(command=load_filtered_issues)
        # Guardado na instancia: quem precisa do resultado agora (Enter, teste)
        # chama flush() em vez de esperar o intervalo.
        self.arbitration_issue_search_debounced = debounce(
            issue_search_entry, load_filtered_issues
        )
        issue_search_entry.bind("<KeyRelease>", self.arbitration_issue_search_debounced)
        load_filtered_issues()

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
                self._show_toast("Pendencia marcada como ciente.", kind="success")
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

    # Tipos de "abnormal assignment points" (TRF25 §7.3): rótulo amigável -> código.
    _AAT_TYPE_CHOICES = [
        ("Penalidade/Bonus (pontos)", ""),
        ("Vitoria atribuida (W)", "W"),
        ("Empate atribuido (D)", "D"),
        ("Derrota atribuida (L)", "L"),
        ("Bye full-point (F)", "F"),
        ("Bye half-point (H)", "H"),
        ("Bye zero-point (Z)", "Z"),
        ("W.O. a favor (+)", "+"),
        ("W.O. contra (-)", "-"),
    ]

    def show_point_adjustments(self) -> None:
        if not self._require_tournament():
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        is_team = (tournament or {}).get("competition_type") == "team"

        self._clear_content()
        self._page_title(
            "Ajustes de pontos (TRF25)",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Alvos: jogadores (individual) ou equipes (por equipes).
        if is_team:
            entities = sorted(
                self.db.list_teams(self.current_tournament_id, active_only=False),
                key=lambda item: str(item.get("name") or "").casefold(),
            )
        else:
            entities = sorted(
                self.db.list_players(self.current_tournament_id, active_only=False),
                key=lambda item: str(item.get("name") or "").casefold(),
            )
        target_by_label: dict[str, int] = {}
        for item in entities:
            label = f"{item.get('name') or 's/ nome'} (#{item['id']})"
            target_by_label[label] = int(item["id"])
        target_labels = list(target_by_label.keys()) or ["(sem participantes)"]

        rounds = sorted(self.db.list_rounds(self.current_tournament_id), key=lambda r: r["number"])
        round_by_label = {"Todas as rodadas": 0}
        for item in rounds:
            round_by_label[f"Rodada {int(item['number'])}"] = int(item["number"])
        round_labels = list(round_by_label.keys())
        type_by_label = {label: code for label, code in self._AAT_TYPE_CHOICES}

        # Formulario de lancamento.
        form = self._make_panel(body)
        form.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        self._section_title(form, "Novo ajuste").grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w"
        )

        ctk.CTkLabel(form, text="Equipe" if is_team else "Jogador").grid(
            row=1, column=0, padx=16, pady=(4, 0), sticky="w"
        )
        target_option = ctk.CTkOptionMenu(form, values=target_labels, width=260)
        target_option.grid(row=2, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Rodada").grid(row=3, column=0, padx=16, pady=(8, 0), sticky="w")
        round_option = ctk.CTkOptionMenu(form, values=round_labels, width=260)
        round_option.grid(row=4, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Tipo").grid(row=5, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=list(type_by_label.keys()), width=260)
        type_option.grid(row=6, column=0, padx=16, pady=(2, 0), sticky="ew")

        next_row = 7
        match_points_entry = None
        if is_team:
            ctk.CTkLabel(form, text="Match points (+/-)").grid(
                row=next_row, column=0, padx=16, pady=(8, 0), sticky="w"
            )
            match_points_entry = ctk.CTkEntry(form, width=260, placeholder_text="0.0")
            match_points_entry.grid(row=next_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            next_row += 2

        ctk.CTkLabel(form, text="Game points (+/-)").grid(
            row=next_row, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        game_points_entry = ctk.CTkEntry(form, width=260, placeholder_text="0.0")
        game_points_entry.grid(row=next_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Motivo").grid(
            row=next_row + 2, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        reason_entry = ctk.CTkEntry(form, width=260, placeholder_text="Ex.: penalidade disciplinar")
        reason_entry.grid(row=next_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        def parse_points(entry: Any) -> float:
            text = (entry.get() if entry else "").strip().replace(",", ".")
            if not text:
                return 0.0
            try:
                return float(text)
            except ValueError as exc:
                raise AppError("Pontos invalidos: use numero decimal (ex.: -0.5).") from exc

        # Tabela de ajustes existentes.
        panel = self._make_panel(body)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self._section_title(panel, "Ajustes lancados").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )
        tree_holder = ctk.CTkFrame(panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            tree_holder,
            ["round", "target", "type", "mp", "gp", "reason"],
            {
                "round": "Rodada",
                "target": "Alvo",
                "type": "Tipo",
                "mp": "MP",
                "gp": "GP",
                "reason": "Motivo",
            },
            {"round": 80, "target": 200, "type": 60, "mp": 60, "gp": 60, "reason": 240},
            visible_rows=16,
        )

        row_by_iid: dict[str, int] = {}

        def refresh_tree() -> None:
            for child in tree.get_children():
                tree.delete(child)
            row_by_iid.clear()
            for index, adjustment in enumerate(
                self.db.list_point_adjustments(self.current_tournament_id), start=1
            ):
                iid = str(index)
                row_by_iid[iid] = int(adjustment["id"])
                round_number = int(adjustment.get("round_number") or 0)
                target = adjustment.get("team_name") if is_team else adjustment.get("player_name")
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        "Todas" if round_number == 0 else str(round_number),
                        target or "(removido)",
                        adjustment.get("aat_type") or "-",
                        f"{float(adjustment.get('match_points') or 0.0):+.1f}",
                        f"{float(adjustment.get('game_points') or 0.0):+.1f}",
                        adjustment.get("reason") or "",
                    ),
                )

        def add_adjustment() -> None:
            try:
                label = target_option.get()
                if label not in target_by_label:
                    raise AppError("Selecione um participante valido.")
                game_points = parse_points(game_points_entry)
                match_points = parse_points(match_points_entry) if is_team else 0.0
                aat_type = type_by_label.get(type_option.get(), "")
                if not aat_type and match_points == 0.0 and game_points == 0.0:
                    raise AppError("Informe pontos diferentes de zero ou um tipo de atribuicao.")
                target_id = target_by_label[label]
                self.db.add_point_adjustment(
                    self.current_tournament_id,
                    round_number=round_by_label.get(round_option.get(), 0),
                    player_id=None if is_team else target_id,
                    team_id=target_id if is_team else None,
                    aat_type=aat_type,
                    match_points=match_points,
                    game_points=game_points,
                    reason=reason_entry.get().strip(),
                )
                if match_points_entry:
                    match_points_entry.delete(0, "end")
                game_points_entry.delete(0, "end")
                reason_entry.delete(0, "end")
                self._show_toast("Ajuste lancado.", kind="success")
                refresh_tree()
            except Exception as exc:
                self._show_error(exc)

        def delete_selected() -> None:
            try:
                selected = tree.selection()
                if not selected:
                    raise AppError("Selecione um ajuste para remover.")
                if not self._confirm_action(
                    "Remover ajuste", "Confirma a remocao do ajuste selecionado?"
                ):
                    return
                adjustment_id = row_by_iid[selected[0]]
                tournament_id = self.current_tournament_id
                snapshot = next(
                    (
                        row
                        for row in self.db.list_point_adjustments(tournament_id)
                        if int(row["id"]) == int(adjustment_id)
                    ),
                    None,
                )

                def restore_adjustment(record=snapshot) -> None:
                    self.db.add_point_adjustment(
                        tournament_id,
                        round_number=int(record.get("round_number") or 0),
                        player_id=record.get("player_id"),
                        team_id=record.get("team_id"),
                        aat_type=str(record.get("aat_type") or ""),
                        match_points=float(record.get("match_points") or 0.0),
                        game_points=float(record.get("game_points") or 0.0),
                        reason=str(record.get("reason") or ""),
                    )

                self._delete_with_undo(
                    lambda: self.db.delete_point_adjustment(adjustment_id),
                    restore_adjustment if snapshot else None,
                    "Ajuste removido.",
                    refresh_tree,
                )
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(form, text="Adicionar", command=add_adjustment).grid(
            row=next_row + 4, column=0, padx=16, pady=(14, 14), sticky="ew"
        )

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        ctk.CTkButton(footer, text="Atualizar", width=120, command=refresh_tree).pack(side="left")
        ctk.CTkButton(footer, text="Remover selecionado", width=170, command=delete_selected).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(
            footer, text="Voltar ao painel", width=140, command=self.show_arbitration_panel
        ).pack(side="left", padx=(8, 0))

        refresh_tree()

    def show_requested_byes(self) -> None:
        if not self._require_tournament():
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        is_team = (tournament or {}).get("competition_type") == "team"

        self._clear_content()
        self._page_title(
            "Byes solicitados (TRF25)",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Configuração por tipo de competição: equipes ou individual.
        if is_team:
            entity_noun = "Equipe"
            entities = self.db.list_teams(self.current_tournament_id, active_only=False)
            list_fn = self.db.list_requested_team_byes
            add_fn = self.db.add_requested_team_bye
            delete_fn = self.db.delete_requested_team_bye
            name_key = "team_name"
            empty_label = "(sem equipes)"
            hint = (
                "O bye e aplicado quando a rodada for gerada:\n"
                "a equipe fica de fora e pontua por tipo (F=vitoria,\n"
                "H=empate, Z=derrota)."
            )
        else:
            entity_noun = "Jogador"
            entities = self.db.list_players(self.current_tournament_id, active_only=False)
            list_fn = self.db.list_requested_byes
            add_fn = self.db.add_requested_bye
            delete_fn = self.db.delete_requested_bye
            name_key = "player_name"
            empty_label = "(sem jogadores)"
            hint = (
                "O bye e aplicado quando a rodada for gerada:\n"
                "o jogador fica de fora do pareamento e recebe\n"
                "F=1.0, H=0.5 ou Z=0.0 ponto.\n"
                "Valido apenas no sistema Suico."
            )

        entities = sorted(entities, key=lambda item: str(item.get("name") or "").casefold())
        target_by_label: dict[str, int] = {}
        for item in entities:
            label = f"{item.get('name') or 's/ nome'} (#{item['id']})"
            target_by_label[label] = int(item["id"])
        target_labels = list(target_by_label.keys()) or [empty_label]

        configured_rounds = int((tournament or {}).get("rounds_count") or 0)
        round_by_label = {
            f"Rodada {number}": number for number in range(1, configured_rounds + 1)
        }
        round_labels = list(round_by_label.keys()) or ["(sem rodadas)"]
        type_by_label = {label: code for code, label in REQUESTED_BYE_TYPES.items()}

        form = self._make_panel(body)
        form.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        self._section_title(form, "Novo bye solicitado").grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w"
        )

        ctk.CTkLabel(form, text=entity_noun).grid(row=1, column=0, padx=16, pady=(4, 0), sticky="w")
        target_option = ctk.CTkOptionMenu(form, values=target_labels, width=260)
        target_option.grid(row=2, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Rodada").grid(row=3, column=0, padx=16, pady=(8, 0), sticky="w")
        round_option = ctk.CTkOptionMenu(form, values=round_labels, width=260)
        round_option.grid(row=4, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Tipo").grid(row=5, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=list(type_by_label.keys()), width=260)
        type_option.grid(row=6, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Motivo").grid(row=7, column=0, padx=16, pady=(8, 0), sticky="w")
        reason_entry = ctk.CTkEntry(form, width=260, placeholder_text="Ex.: ausencia comunicada")
        reason_entry.grid(row=8, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(
            form,
            text=hint,
            justify="left",
            text_color=("gray40", "gray60"),
        ).grid(row=9, column=0, padx=16, pady=(10, 0), sticky="w")

        panel = self._make_panel(body)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self._section_title(panel, "Byes solicitados").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )
        tree_holder = ctk.CTkFrame(panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            tree_holder,
            ["round", "entity", "type", "reason"],
            {"round": "Rodada", "entity": entity_noun, "type": "Tipo", "reason": "Motivo"},
            {"round": 80, "entity": 220, "type": 60, "reason": 240},
            visible_rows=16,
        )

        row_by_iid: dict[str, int] = {}

        def refresh_tree() -> None:
            for child in tree.get_children():
                tree.delete(child)
            row_by_iid.clear()
            for index, requested in enumerate(
                list_fn(self.current_tournament_id), start=1
            ):
                iid = str(index)
                row_by_iid[iid] = int(requested["id"])
                code = str(requested.get("bye_type") or "").upper()
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        str(int(requested.get("round_number") or 0)),
                        requested.get(name_key) or "(removido)",
                        code or "-",
                        requested.get("reason") or "",
                    ),
                )

        def add_requested_bye() -> None:
            try:
                label = target_option.get()
                if label not in target_by_label:
                    raise AppError(f"Selecione um(a) {entity_noun.lower()} valido(a).")
                if round_option.get() not in round_by_label:
                    raise AppError("Selecione uma rodada valida.")
                bye_type = type_by_label.get(type_option.get(), "")
                if bye_type not in {"F", "H", "Z"}:
                    raise AppError("Selecione um tipo de bye (F, H ou Z).")
                add_fn(
                    self.current_tournament_id,
                    target_by_label[label],
                    round_by_label[round_option.get()],
                    bye_type,
                    reason=reason_entry.get().strip(),
                )
                reason_entry.delete(0, "end")
                self._show_toast("Bye solicitado registrado.", kind="success")
                refresh_tree()
            except Exception as exc:
                self._show_error(exc)

        def delete_selected() -> None:
            try:
                selected = tree.selection()
                if not selected:
                    raise AppError("Selecione um bye para remover.")
                if not self._confirm_action(
                    "Remover bye", "Confirma a remocao do bye solicitado selecionado?"
                ):
                    return
                bye_id = row_by_iid[selected[0]]
                tournament_id = self.current_tournament_id
                entity_key = "team_id" if is_team else "player_id"
                snapshot = next(
                    (
                        row
                        for row in list_fn(tournament_id)
                        if int(row["id"]) == int(bye_id)
                    ),
                    None,
                )

                def restore_bye(record=snapshot) -> None:
                    add_fn(
                        tournament_id,
                        int(record[entity_key]),
                        int(record.get("round_number") or 0),
                        str(record.get("bye_type") or "H"),
                        reason=str(record.get("reason") or ""),
                    )

                self._delete_with_undo(
                    lambda: delete_fn(bye_id),
                    restore_bye if snapshot else None,
                    "Bye removido.",
                    refresh_tree,
                )
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(form, text="Adicionar", command=add_requested_bye).grid(
            row=10, column=0, padx=16, pady=(14, 14), sticky="ew"
        )

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        ctk.CTkButton(footer, text="Atualizar", width=120, command=refresh_tree).pack(side="left")
        ctk.CTkButton(footer, text="Remover selecionado", width=170, command=delete_selected).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(
            footer, text="Voltar ao painel", width=140, command=self.show_arbitration_panel
        ).pack(side="left", padx=(8, 0))

        refresh_tree()

    def show_prohibited_pairings(self) -> None:
        if not self._require_tournament():
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        is_team = (tournament or {}).get("competition_type") == "team"

        self._clear_content()
        self._page_title(
            "Proibicoes de pareamento (TRF25)",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Proibições valem para indivíduos (registro 260 por start-rank) e para
        # equipes (260 por TPN); a tela é a mesma, só muda a entidade/CRUD.
        if is_team:
            entity_noun = "Equipe"
            entities = self.db.list_teams(self.current_tournament_id, active_only=False)
            list_fn = self.db.list_prohibited_team_pairings
            add_fn = self.db.add_prohibited_team_pairing
            delete_fn = self.db.delete_prohibited_team_pairing
            key_a_id, key_b_id = "team_a_id", "team_b_id"
            key_a_name, key_b_name = "team_a_name", "team_b_name"
            empty_label = "(sem equipes)"
        else:
            entity_noun = "Jogador"
            entities = self.db.list_players(self.current_tournament_id, active_only=False)
            list_fn = self.db.list_prohibited_pairings
            add_fn = self.db.add_prohibited_pairing
            delete_fn = self.db.delete_prohibited_pairing
            key_a_id, key_b_id = "player_a_id", "player_b_id"
            key_a_name, key_b_name = "player_a_name", "player_b_name"
            empty_label = "(sem jogadores)"

        entities = sorted(entities, key=lambda item: str(item.get("name") or "").casefold())
        player_by_label: dict[str, int] = {}
        for item in entities:
            label = f"{item.get('name') or 's/ nome'} (#{item['id']})"
            player_by_label[label] = int(item["id"])
        name_by_id = {int(item["id"]): (item.get("name") or "s/ nome") for item in entities}
        player_labels = list(player_by_label.keys()) or [empty_label]

        # Formulario de lancamento.
        form = self._make_panel(body)
        form.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        self._section_title(form, "Nova proibicao").grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w"
        )

        ctk.CTkLabel(form, text=f"{entity_noun} A").grid(row=1, column=0, padx=16, pady=(4, 0), sticky="w")
        player_a_option = ctk.CTkOptionMenu(form, values=player_labels, width=260)
        player_a_option.grid(row=2, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text=f"{entity_noun} B").grid(row=3, column=0, padx=16, pady=(8, 0), sticky="w")
        player_b_option = ctk.CTkOptionMenu(form, values=player_labels, width=260)
        if len(player_labels) > 1:
            player_b_option.set(player_labels[1])
        player_b_option.grid(row=4, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Primeira rodada").grid(
            row=5, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        first_round_entry = ctk.CTkEntry(form, width=260, placeholder_text="1")
        first_round_entry.grid(row=6, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Ultima rodada (0 = todas)").grid(
            row=7, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        last_round_entry = ctk.CTkEntry(form, width=260, placeholder_text="0")
        last_round_entry.grid(row=8, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Motivo").grid(row=9, column=0, padx=16, pady=(8, 0), sticky="w")
        reason_entry = ctk.CTkEntry(form, width=260, placeholder_text="Ex.: mesmo clube/familia")
        reason_entry.grid(row=10, column=0, padx=16, pady=(2, 0), sticky="ew")

        def parse_round(entry: Any, default: int) -> int:
            text = (entry.get() if entry else "").strip()
            if not text:
                return default
            try:
                value = int(text)
            except ValueError as exc:
                raise AppError("Rodada invalida: use um numero inteiro.") from exc
            if value < 0:
                raise AppError("Rodada nao pode ser negativa.")
            return value

        # Tabela de proibicoes existentes.
        panel = self._make_panel(body)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self._section_title(panel, "Proibicoes cadastradas").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )
        tree_holder = ctk.CTkFrame(panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            tree_holder,
            ["players", "window", "reason"],
            {"players": f"{entity_noun}s", "window": "Rodadas", "reason": "Motivo"},
            {"players": 280, "window": 100, "reason": 220},
            visible_rows=16,
        )

        row_by_iid: dict[str, int] = {}

        def refresh_tree() -> None:
            for child in tree.get_children():
                tree.delete(child)
            row_by_iid.clear()
            for index, prohibition in enumerate(
                list_fn(self.current_tournament_id), start=1
            ):
                iid = str(index)
                row_by_iid[iid] = int(prohibition["id"])
                first_round = int(prohibition.get("first_round") or 1)
                last_round = int(prohibition.get("last_round") or 0)
                window = f"{first_round}+" if last_round == 0 else (
                    str(first_round) if first_round == last_round else f"{first_round}-{last_round}"
                )
                a_name = prohibition.get(key_a_name) or name_by_id.get(
                    int(prohibition.get(key_a_id) or 0), "(removido)"
                )
                b_name = prohibition.get(key_b_name) or name_by_id.get(
                    int(prohibition.get(key_b_id) or 0), "(removido)"
                )
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(f"{a_name} x {b_name}", window, prohibition.get("reason") or ""),
                )

        def add_prohibition() -> None:
            try:
                label_a = player_a_option.get()
                label_b = player_b_option.get()
                if label_a not in player_by_label or label_b not in player_by_label:
                    raise AppError(f"Selecione dois itens validos ({entity_noun.lower()}).")
                player_a_id = player_by_label[label_a]
                player_b_id = player_by_label[label_b]
                if player_a_id == player_b_id:
                    raise AppError(f"Escolha duas entidades diferentes ({entity_noun.lower()}).")
                first_round = parse_round(first_round_entry, 1) or 1
                last_round = parse_round(last_round_entry, 0)
                if last_round and last_round < first_round:
                    raise AppError("A ultima rodada nao pode ser menor que a primeira.")
                add_fn(
                    self.current_tournament_id,
                    player_a_id,
                    player_b_id,
                    first_round=first_round,
                    last_round=last_round,
                    reason=reason_entry.get().strip(),
                )
                first_round_entry.delete(0, "end")
                last_round_entry.delete(0, "end")
                reason_entry.delete(0, "end")
                self._show_toast("Proibicao cadastrada.", kind="success")
                refresh_tree()
            except Exception as exc:
                self._show_error(exc)

        def delete_selected() -> None:
            try:
                selected = tree.selection()
                if not selected:
                    raise AppError("Selecione uma proibicao para remover.")
                if not self._confirm_action(
                    "Remover proibicao", "Confirma a remocao da proibicao selecionada?"
                ):
                    return
                prohibition_id = row_by_iid[selected[0]]
                tournament_id = self.current_tournament_id
                snapshot = next(
                    (
                        row
                        for row in list_fn(tournament_id)
                        if int(row["id"]) == int(prohibition_id)
                    ),
                    None,
                )

                def restore_prohibition(record=snapshot) -> None:
                    add_fn(
                        tournament_id,
                        int(record[key_a_id]),
                        int(record[key_b_id]),
                        first_round=int(record.get("first_round") or 1),
                        last_round=int(record.get("last_round") or 0),
                        reason=str(record.get("reason") or ""),
                    )

                self._delete_with_undo(
                    lambda: delete_fn(prohibition_id),
                    restore_prohibition if snapshot else None,
                    "Proibicao removida.",
                    refresh_tree,
                )
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(form, text="Adicionar", command=add_prohibition).grid(
            row=11, column=0, padx=16, pady=(14, 14), sticky="ew"
        )

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        ctk.CTkButton(footer, text="Atualizar", width=120, command=refresh_tree).pack(side="left")
        ctk.CTkButton(footer, text="Remover selecionado", width=170, command=delete_selected).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(
            footer, text="Voltar ao painel", width=140, command=self.show_arbitration_panel
        ).pack(side="left", padx=(8, 0))

        refresh_tree()

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
            self.db.backup_before("publish_site", tournament_id=self.current_tournament_id)
            directory = self._default_export_dir() / f"site_torneio_{self.current_tournament_id}"
            index_path = self.export_service.export_site(self.current_tournament_id, directory)
            self._show_info(f"Site exportado:\n{index_path}")
        except Exception as exc:
            self._show_error(exc)

    def _publish_live_portal_from_panel(self) -> None:
        try:
            self.db.backup_before("publish_live_portal", tournament_id=self.current_tournament_id)
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
