from __future__ import annotations

from ..support import *


class TournamentPagesMixin:
    def show_tournaments(self) -> None:
        self._clear_content()
        self._page_title(
            "Torneios",
            "Crie um torneio e selecione-o para cadastrar jogadores e gerar rodadas.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=272)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("name", "Nome do torneio"),
            ("location", "Local"),
            ("start_date", "Data inicial"),
            ("end_date", "Data final"),
            ("rounds_count", "Rodadas"),
            ("time_control", "Ritmo"),
            ("bye_points", "Pontos do bye"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(12, 0), sticky="w")
            if key in ("start_date", "end_date"):
                entry = self._make_date_entry(form, width=28)
            elif key == "time_control":
                entry = self._make_time_control_menu(form, width=230)
            else:
                entry = ctk.CTkEntry(form, width=230)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            entries[key] = entry
        entries["rounds_count"].insert(0, "5")
        entries["bye_points"].insert(0, "1.0")

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Escopo").grid(row=option_row, column=0, padx=16, pady=(12, 0), sticky="w")
        scope_option = ctk.CTkOptionMenu(form, values=list(TOURNAMENT_SCOPE_VALUES.keys()), width=230)
        scope_option.grid(row=option_row + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
        scope_option.set(TOURNAMENT_SCOPES["standalone"])

        ctk.CTkLabel(form, text="Formato").grid(row=option_row + 2, column=0, padx=16, pady=(12, 0), sticky="w")
        competition_option = ctk.CTkOptionMenu(form, values=list(COMPETITION_TYPE_VALUES.keys()), width=230)
        competition_option.grid(row=option_row + 3, column=0, padx=16, pady=(4, 2), sticky="ew")
        competition_option.set(COMPETITION_TYPES["individual"])

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(12, 0), sticky="w")
        club_map: dict[str, int] = {}
        club_values = []
        for club in self.db.list_clubs(active_only=True):
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            label = f"{club['id']} - {club['name'] or 'Clube padrao'} ({kind})"
            club_values.append(label)
            club_map[label] = int(club["id"])
        if not club_values:
            club_values = ["1 - Clube padrao (Clube)"]
            club_map[club_values[0]] = 1
        tournament_club_option = ctk.CTkOptionMenu(form, values=club_values, width=230)
        tournament_club_option.grid(row=option_row + 5, column=0, padx=16, pady=(4, 2), sticky="ew")

        ctk.CTkLabel(form, text="Turma").grid(row=option_row + 6, column=0, padx=16, pady=(12, 0), sticky="w")
        class_map: dict[str, int | None] = {"Sem turma": None}
        class_option = ctk.CTkOptionMenu(form, values=["Sem turma"], width=230)
        class_option.grid(row=option_row + 7, column=0, padx=16, pady=(4, 2), sticky="ew")

        def load_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            class_map.clear()
            class_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    class_map[label] = int(class_data["id"])
            class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in class_map.items() if class_id == selected_id),
                "Sem turma",
            )
            class_option.set(chosen)

        def refresh_scope_state(_value: str | None = None) -> None:
            scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
            club_state = "normal" if scope in {"club", "class"} else "disabled"
            class_state = "normal" if scope == "class" else "disabled"
            tournament_club_option.configure(state=club_state)
            class_option.configure(state=class_state)

        def on_club_change(_value: str) -> None:
            load_class_options(club_map.get(tournament_club_option.get()), None)

        scope_option.configure(command=refresh_scope_state)
        tournament_club_option.configure(command=on_club_change)
        load_class_options(club_map.get(tournament_club_option.get()), None)
        refresh_scope_state()

        def create_tournament() -> None:
            try:
                name = entries["name"].get().strip()
                if not name:
                    raise AppError("Informe o nome do torneio.")
                scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
                club_id = None
                class_id = None
                if scope in {"club", "class"}:
                    club_id = club_map.get(tournament_club_option.get())
                    if not club_id:
                        raise AppError("Selecione o clube/escola do torneio.")
                if scope == "class":
                    class_id = class_map.get(class_option.get())
                    if not class_id:
                        raise AppError("Selecione a turma do torneio.")
                tournament_id = self.tournament_service.create_tournament(
                    {
                        "name": name,
                        "scope": scope,
                        "competition_type": COMPETITION_TYPE_VALUES[competition_option.get()],
                        "club_id": club_id,
                        "class_id": class_id,
                        "location": entries["location"].get(),
                        "rounds_count": entries["rounds_count"].get(),
                        "time_control": entries["time_control"].get(),
                        "start_date": entries["start_date"].get(),
                        "end_date": entries["end_date"].get(),
                        "bye_points": entries["bye_points"].get(),
                    }
                )
                self._set_current_tournament(tournament_id)
                logger.info("Torneio criado: %s", tournament_id)
                self.show_players()
            except Exception as exc:
                self._show_error(exc)

        btn_create = ctk.CTkButton(form, text="Criar torneio", command=create_tournament)
        btn_create.grid(row=option_row + 8, column=0, padx=16, pady=18, sticky="ew")
        self._disable_if_unauthorized(btn_create, "tournament_write")

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        columns = ["id", "name", "format", "scope", "club", "class", "location", "rounds", "status"]
        tree = self._make_tree(
            list_panel,
            columns,
            {
                "id": "ID",
                "name": "Torneio",
                "format": "Formato",
                "scope": "Escopo",
                "club": "Clube/Escola",
                "class": "Turma",
                "location": "Local",
                "rounds": "Rodadas",
                "status": "Status",
            },
            {
                "id": 60,
                "name": 230,
                "format": 85,
                "scope": 95,
                "club": 150,
                "class": 130,
                "location": 140,
                "rounds": 75,
                "status": 95,
            },
        )

        def load_tournaments() -> None:
            tree.delete(*tree.get_children())
            for tournament in self.db.list_tournaments():
                tree.insert(
                    "",
                    "end",
                    values=(
                        tournament["id"],
                        tournament["name"],
                        COMPETITION_TYPES.get(tournament.get("competition_type", "individual"), "Individual"),
                        TOURNAMENT_SCOPES[self._tournament_scope_key(tournament)],
                        tournament.get("club_name") or "",
                        tournament.get("class_name") or "",
                        tournament["location"],
                        tournament["rounds_count"],
                        tournament["status"],
                    ),
                )

        def open_selected() -> None:
            tournament_id = selected_tournament_id()
            if not tournament_id:
                return
            self._set_current_tournament(tournament_id)
            logger.info("Torneio selecionado: %s", tournament_id)
            self.show_players()

        def selected_tournament_id() -> int | None:
            selected = tree.selection()
            if not selected:
                return None
            values = tree.item(selected[0], "values")
            return int(values[0])

        def duplicate_selected() -> None:
            try:
                tournament_id = selected_tournament_id()
                if not tournament_id:
                    raise AppError("Selecione um torneio para duplicar.")
                tournament = self.db.get_tournament(tournament_id)
                if not tournament:
                    raise AppError("Torneio selecionado nao encontrado.")
                suggested_name = f"{tournament['name']} - copia"
                new_name = self._ask_string("Duplicar torneio", "Nome do novo torneio:")
                if new_name is None:
                    return
                new_tournament_id = self.tournament_service.duplicate_tournament(
                    tournament_id,
                    new_name.strip() or suggested_name,
                )
                self._set_current_tournament(new_tournament_id)
                load_tournaments()
                self._show_info("Torneio duplicado. Ajuste data, local e participantes conforme necessario.")
            except Exception as exc:
                self._show_error(exc)

        def delete_selected() -> None:
            try:
                tournament_id = selected_tournament_id()
                if not tournament_id:
                    raise AppError("Selecione um torneio para excluir.")
                tournament = self.db.get_tournament(tournament_id)
                name = tournament["name"] if tournament else str(tournament_id)
                confirmed = messagebox.askyesno(
                    "Excluir torneio",
                    f"Excluir o torneio '{name}' e todos os jogadores/rodadas vinculados?",
                )
                if not confirmed:
                    return
                self.tournament_service.delete_tournament(tournament_id)
                if self.current_tournament_id == tournament_id:
                    self.current_tournament_id = None
                    self.current_round_id = None
                    self.tournament_label.configure(text="Nenhum torneio selecionado")
                load_tournaments()
                self._show_info("Torneio excluido.")
            except Exception as exc:
                self._show_error(exc)

        tree.bind("<Double-1>", lambda _event: open_selected())
        ctk.CTkLabel(
            list_panel,
            text="Atalhos: duplo clique seleciona; Del exclui o torneio selecionado.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=1, column=0, padx=12, pady=(8, 0), sticky="w")
        actions = ctk.CTkFrame(list_panel, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=12, sticky="e")
        ctk.CTkButton(actions, text="Selecionar", command=open_selected, width=110).pack(
            side="left",
            padx=(0, 8),
        )
        btn_duplicate = ctk.CTkButton(actions, text="Duplicar modelo", command=duplicate_selected, width=140)
        btn_duplicate.pack(side="left", padx=(0, 8))
        self._disable_if_unauthorized(btn_duplicate, "tournament_write")
        btn_delete = ctk.CTkButton(
            actions,
            text="Excluir",
            command=delete_selected,
            fg_color=THEME_DANGER,
            width=90,
        )
        btn_delete.pack(side="left")
        self._disable_if_unauthorized(btn_delete, "tournament_write")
        tree.bind("<Delete>", lambda _event: delete_selected())
        load_tournaments()

    def show_tournament_dashboard(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            self._show_error(AppError("Selecione um torneio valido."))
            return

        rounds = self.db.list_rounds(self.current_tournament_id)
        players = self.db.list_players(self.current_tournament_id, active_only=False)
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
        competition_type = str(tournament.get("competition_type") or "individual")
        is_team_tournament = competition_type == "team"

        self._clear_content()
        self._page_title(
            "Central do Torneio",
            f"{tournament['name']} - {self._tournament_scope_text(tournament)}",
        )
        self._build_tournament_nav("central")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        summary_panel = self._make_panel(body)
        summary_panel.grid(row=0, column=0, sticky="new")
        summary_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            summary_panel,
            text="Resumo",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        summary_rows = [
            ("Formato", COMPETITION_TYPES.get(competition_type, "Individual")),
            ("Status", str(tournament.get("status") or "")),
            ("Local", str(tournament.get("location") or "Nao informado")),
            ("Periodo", self._tournament_period_text(tournament)),
            ("Rodadas", f"{len(rounds)} geradas de {tournament['rounds_count']}"),
            ("Jogadores", str(len(players))),
            ("Perfil", TOURNAMENT_PROFILES.get(str(settings.get("tournament_profile") or "free"), "Livre")),
        ]
        if is_team_tournament:
            summary_rows.append(("Equipes", str(len(self.db.list_teams(self.current_tournament_id)))))

        for index, (label, value) in enumerate(summary_rows, start=1):
            row = ctk.CTkFrame(summary_panel, fg_color="transparent")
            row.grid(row=index, column=0, padx=16, pady=(2, 8), sticky="ew")
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label, text_color=THEME_TEXT_SUB, width=84, anchor="w").grid(
                row=0,
                column=0,
                sticky="w",
            )
            ctk.CTkLabel(row, text=value, text_color=THEME_TEXT_MAIN, anchor="w", wraplength=260).grid(
                row=0,
                column=1,
                sticky="ew",
            )

        ctk.CTkButton(
            summary_panel,
            text="Voltar para lista de torneios",
            command=self.show_tournaments,
            fg_color="transparent",
            border_width=1,
            text_color=THEME_TEXT_MAIN,
        ).grid(row=len(summary_rows) + 1, column=0, padx=16, pady=(10, 16), sticky="ew")

    @staticmethod
    def _tournament_period_text(tournament: dict[str, Any]) -> str:
        start_date = str(tournament.get("start_date") or "").strip()
        end_date = str(tournament.get("end_date") or "").strip()
        if start_date and end_date:
            return f"{start_date} a {end_date}"
        if start_date:
            return start_date
        if end_date:
            return end_date
        return "Nao informado"

    def show_tournament_settings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            self._show_error(AppError("Selecione um torneio valido."))
            return
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}

        self._clear_content()
        self._page_title(
            "Configuracao do torneio",
            f"Torneio: {tournament['name']} - {self._tournament_scope_text(tournament)}",
        )
        self._build_tournament_nav("settings")

        body = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        basic_panel = self._make_panel(body)
        basic_panel.grid(row=0, column=0, padx=(0, 8), pady=(0, 12), sticky="nsew")
        settings_panel = self._make_panel(body)
        settings_panel.grid(row=0, column=1, padx=(8, 0), pady=(0, 12), sticky="nsew")
        schedule_panel = self._make_panel(body)
        schedule_panel.grid(row=1, column=0, columnspan=2, pady=(0, 12), sticky="ew")
        schedule_panel.grid_columnconfigure(1, weight=1)
        schedule_panel.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            basic_panel,
            text="Dados gerais",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(
            settings_panel,
            text="Dados oficiais e regras",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

        tournament_entries: dict[str, ctk.CTkEntry] = {}
        tournament_fields = [
            ("name", "Nome do torneio"),
            ("location", "Local"),
            ("start_date", "Data inicial"),
            ("end_date", "Data final"),
            ("rounds_count", "Rodadas"),
            ("time_control", "Ritmo"),
            ("bye_points", "Pontos do bye"),
        ]
        for index, (key, label) in enumerate(tournament_fields, start=1):
            ctk.CTkLabel(basic_panel, text=label).grid(
                row=index * 2 - 1,
                column=0,
                padx=16,
                pady=(8, 0),
                sticky="w",
            )
            if key in ("start_date", "end_date"):
                entry = self._make_date_entry(basic_panel, width=40)
            elif key == "time_control":
                entry = self._make_time_control_menu(basic_panel, width=330)
            else:
                entry = ctk.CTkEntry(basic_panel, width=330)
            entry.grid(row=index * 2, column=0, padx=16, pady=(2, 0), sticky="ew")
            entry.insert(0, str(tournament.get(key) or ""))
            tournament_entries[key] = entry

        scope_row = len(tournament_fields) * 2 + 1
        ctk.CTkLabel(basic_panel, text="Escopo").grid(
            row=scope_row,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        scope_option = ctk.CTkOptionMenu(basic_panel, values=list(TOURNAMENT_SCOPE_VALUES.keys()), width=330)
        scope_option.grid(row=scope_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
        scope_option.set(TOURNAMENT_SCOPES[self._tournament_scope_key(tournament)])

        competition_by_label = {label: value for value, label in COMPETITION_TYPES.items()}
        ctk.CTkLabel(basic_panel, text="Formato").grid(
            row=scope_row + 2,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        competition_option = ctk.CTkOptionMenu(
            basic_panel,
            values=list(competition_by_label.keys()),
            width=330,
        )
        competition_option.grid(row=scope_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")
        competition_option.set(
            COMPETITION_TYPES.get(tournament.get("competition_type", "individual"), COMPETITION_TYPES["individual"])
        )

        tournament_club_map: dict[str, int] = {}
        tournament_club_values = []
        for club in self.db.list_clubs(active_only=True):
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            label = f"{club['id']} - {club['name'] or 'Clube padrao'} ({kind})"
            tournament_club_values.append(label)
            tournament_club_map[label] = int(club["id"])
        if not tournament_club_values:
            tournament_club_values = ["1 - Clube padrao (Clube)"]
            tournament_club_map[tournament_club_values[0]] = 1
        ctk.CTkLabel(basic_panel, text="Clube/Escola").grid(
            row=scope_row + 4,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        tournament_club_option = ctk.CTkOptionMenu(basic_panel, values=tournament_club_values, width=330)
        tournament_club_option.grid(row=scope_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")
        selected_tournament_club = next(
            (
                label
                for label, club_id in tournament_club_map.items()
                if club_id == int(tournament.get("club_id") or 1)
            ),
            tournament_club_values[0],
        )
        tournament_club_option.set(selected_tournament_club)

        ctk.CTkLabel(basic_panel, text="Turma").grid(
            row=scope_row + 6,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        tournament_class_map: dict[str, int | None] = {"Sem turma": None}
        tournament_class_option = ctk.CTkOptionMenu(basic_panel, values=["Sem turma"], width=330)
        tournament_class_option.grid(row=scope_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        def load_tournament_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            tournament_class_map.clear()
            tournament_class_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    tournament_class_map[label] = int(class_data["id"])
            tournament_class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in tournament_class_map.items() if class_id == selected_id),
                "Sem turma",
            )
            tournament_class_option.set(chosen)

        def refresh_tournament_scope_state(_value: str | None = None) -> None:
            scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
            club_state = "normal" if scope in {"club", "class"} else "disabled"
            class_state = "normal" if scope == "class" else "disabled"
            tournament_club_option.configure(state=club_state)
            tournament_class_option.configure(state=class_state)

        def on_tournament_club_change(_value: str) -> None:
            load_tournament_class_options(tournament_club_map.get(tournament_club_option.get()), None)

        scope_option.configure(command=refresh_tournament_scope_state)
        tournament_club_option.configure(command=on_tournament_club_change)
        load_tournament_class_options(
            tournament_club_map.get(tournament_club_option.get()),
            tournament.get("class_id"),
        )
        refresh_tournament_scope_state()

        setting_entries: dict[str, ctk.CTkEntry] = {}
        setting_fields = [
            ("fide_event_id", "FIDE Event-ID"),
            ("organizer", "Organizador"),
            ("website", "Pagina web"),
            ("contact_email", "E-mail"),
            ("director", "Diretor do torneio"),
            ("chief_arbiter", "Arbitro principal"),
            ("arbiters", "Arbitros auxiliares"),
            ("federation", "Federacao"),
            ("state", "Estado"),
            ("categories", "Categorias"),
            ("cutoff_date", "Data de corte"),
            ("comments", "Comentarios"),
            ("prizes", "Premiacao"),
            ("late_entry_points", "Pontos por adesao tardia"),
            ("team_boards_count", "Tabuleiros por equipe"),
            ("team_match_win_points", "Pontos por vitoria da equipe"),
            ("team_match_draw_points", "Pontos por empate da equipe"),
            ("team_match_loss_points", "Pontos por derrota da equipe"),
        ]
        for index, (key, label) in enumerate(setting_fields, start=1):
            ctk.CTkLabel(settings_panel, text=label).grid(
                row=index * 2 - 1,
                column=0,
                padx=16,
                pady=(8, 0),
                sticky="w",
            )
            entry = ctk.CTkEntry(settings_panel, width=350)
            entry.grid(row=index * 2, column=0, padx=16, pady=(2, 0), sticky="ew")
            value = settings.get(key)
            entry.insert(0, "" if value is None else str(value))
            setting_entries[key] = entry

        initial_order_by_label = {label: value for value, label in INITIAL_ORDER_OPTIONS.items()}
        profile_by_label = {label: value for value, label in TOURNAMENT_PROFILES.items()}
        type_by_label = {label: value for value, label in TOURNAMENT_TYPES.items()}
        pairing_by_label = {label: value for value, label in PAIRING_METHODS.items()}
        team_pairing_by_label = {label: value for value, label in TEAM_PAIRING_METHODS.items()}
        team_criterion_by_label = {label: value for value, label in TEAM_STANDING_CRITERIA.items()}
        option_start_row = len(setting_fields) * 2 + 1
        ctk.CTkLabel(settings_panel, text="Ordem inicial").grid(
            row=option_start_row,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        initial_order_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(initial_order_by_label.keys()),
            width=350,
        )
        initial_order_option.grid(row=option_start_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
        initial_order_option.set(
            INITIAL_ORDER_OPTIONS.get(settings.get("initial_order", "rating"), INITIAL_ORDER_OPTIONS["rating"])
        )

        ctk.CTkLabel(settings_panel, text="Perfil do torneio").grid(
            row=option_start_row + 2,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        tournament_profile_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(profile_by_label.keys()),
            width=350,
        )
        tournament_profile_option.grid(row=option_start_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")
        tournament_profile_option.set(
            TOURNAMENT_PROFILES.get(settings.get("tournament_profile", "free"), TOURNAMENT_PROFILES["free"])
        )

        ctk.CTkLabel(settings_panel, text="Tipo de torneio").grid(
            row=option_start_row + 4,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        tournament_type_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(type_by_label.keys()),
            width=350,
        )
        tournament_type_option.grid(row=option_start_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")
        tournament_type_option.set(
            TOURNAMENT_TYPES.get(settings.get("tournament_type", "real"), TOURNAMENT_TYPES["real"])
        )

        ctk.CTkLabel(settings_panel, text="Sistema de emparceiramento").grid(
            row=option_start_row + 6,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        pairing_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(pairing_by_label.keys()),
            width=350,
        )
        pairing_option.grid(row=option_start_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")
        pairing_option.set(
            PAIRING_METHODS.get(settings.get("pairing_method", "swiss"), PAIRING_METHODS["swiss"])
        )

        ctk.CTkLabel(settings_panel, text="Metodo por equipes").grid(
            row=option_start_row + 8,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        team_pairing_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(team_pairing_by_label.keys()),
            width=350,
        )
        team_pairing_option.grid(row=option_start_row + 9, column=0, padx=16, pady=(2, 0), sticky="ew")
        team_pairing_option.set(
            TEAM_PAIRING_METHODS.get(settings.get("team_pairing_method", "swiss"), TEAM_PAIRING_METHODS["swiss"])
        )

        ctk.CTkLabel(settings_panel, text="Criterio principal por equipes").grid(
            row=option_start_row + 10,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        team_primary_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(team_criterion_by_label.keys()),
            width=350,
        )
        team_primary_option.grid(row=option_start_row + 11, column=0, padx=16, pady=(2, 0), sticky="ew")
        team_primary_option.set(
            TEAM_STANDING_CRITERIA.get(
                settings.get("team_standing_primary", "match_points"),
                TEAM_STANDING_CRITERIA["match_points"],
            )
        )

        ctk.CTkLabel(settings_panel, text="Criterio secundario por equipes").grid(
            row=option_start_row + 12,
            column=0,
            padx=16,
            pady=(12, 0),
            sticky="w",
        )
        team_secondary_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(team_criterion_by_label.keys()),
            width=350,
        )
        team_secondary_option.grid(row=option_start_row + 13, column=0, padx=16, pady=(2, 0), sticky="ew")
        team_secondary_option.set(
            TEAM_STANDING_CRITERIA.get(
                settings.get("team_standing_secondary", "game_points"),
                TEAM_STANDING_CRITERIA["game_points"],
            )
        )

        team_fixed_board_order_check = ctk.CTkCheckBox(settings_panel, text="Manter ordem fixa dos tabuleiros")
        team_fixed_board_order_check.grid(
            row=option_start_row + 14,
            column=0,
            padx=16,
            pady=(10, 0),
            sticky="w",
        )
        if settings.get("team_fixed_board_order", 1):
            team_fixed_board_order_check.select()

        flag_labels = {
            "allow_public_registration": "Permitir inscricao publica",
            "allow_player_result_edit": "Jogador pode alterar resultado",
            "allow_dangerous_changes": "Permitir mudancas perigosas",
            "disable_bye": "Desativar bye/tchau",
            "accelerated_system": "Sistema acelerado",
            "hide_standings": "Ocultar classificacao",
            "calculate_performance": "Calcular desempenho do jogador",
            "hide_color_names": "Ocultar nomes de cores",
            "show_opponents_in_standings": "Mostrar adversarios na classificacao",
            "archived": "Arquivado",
        }
        flag_checks: dict[str, ctk.CTkCheckBox] = {}
        for offset, key in enumerate(sorted(TOURNAMENT_FLAG_FIELDS)):
            checkbox = ctk.CTkCheckBox(settings_panel, text=flag_labels.get(key, key))
            checkbox.grid(
                row=option_start_row + 15 + offset,
                column=0,
                padx=16,
                pady=(8 if offset == 0 else 4, 0),
                sticky="w",
            )
            if settings.get(key):
                checkbox.select()
            flag_checks[key] = checkbox

        ctk.CTkLabel(
            schedule_panel,
            text="Datas e horarios das rodadas",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(16, 8), sticky="w")

        existing_schedule = self.db.list_round_schedule(self.current_tournament_id)
        first_schedule_date = next((str(item.get("date") or "") for item in existing_schedule if item.get("date")), "")
        first_schedule_time = next((str(item.get("time") or "") for item in existing_schedule if item.get("time")), "")
        generator_frame = ctk.CTkFrame(schedule_panel, fg_color="transparent")
        generator_frame.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 8), sticky="ew")
        for column in range(5):
            generator_frame.grid_columnconfigure(column, weight=1)

        auto_fields = [
            ("start_date", "Data inicial", str(tournament.get("start_date") or first_schedule_date or Database.now()[:10]), 130),
            ("first_time", "Hora inicial", first_schedule_time or "08:00", 95),
            ("rounds_per_day", "Rodadas/dia", str(tournament.get("rounds_count") or len(existing_schedule) or 1), 100),
            ("duration", "Duracao min", "45", 95),
            ("break", "Intervalo min", "15", 95),
        ]
        auto_entries: dict[str, ctk.CTkEntry] = {}
        for column, (key, label, value, width) in enumerate(auto_fields):
            ctk.CTkLabel(generator_frame, text=label).grid(
                row=0,
                column=column,
                padx=(0 if column == 0 else 8, 0),
                pady=(0, 2),
                sticky="w",
            )
            if key == "start_date":
                entry = self._make_date_entry(generator_frame, width=15)
            else:
                entry = ctk.CTkEntry(generator_frame, width=width)
            entry.grid(
                row=1,
                column=column,
                padx=(0 if column == 0 else 8, 0),
                pady=(0, 6),
                sticky="ew",
            )
            entry.insert(0, value)
            auto_entries[key] = entry

        all_same_day_check = ctk.CTkCheckBox(generator_frame, text="Todas no mesmo dia")
        all_same_day_check.grid(row=2, column=0, columnspan=2, pady=(2, 0), sticky="w")
        all_same_day_check.select()

        def refresh_auto_rounds_state() -> None:
            auto_entries["rounds_per_day"].configure(state="disabled" if all_same_day_check.get() else "normal")

        all_same_day_check.configure(command=refresh_auto_rounds_state)
        refresh_auto_rounds_state()

        ctk.CTkLabel(schedule_panel, text="Rodada").grid(row=3, column=0, padx=16, sticky="w")
        ctk.CTkLabel(schedule_panel, text="Data").grid(row=3, column=1, padx=8, sticky="w")
        ctk.CTkLabel(schedule_panel, text="Hora").grid(row=3, column=2, padx=8, sticky="w")

        schedule_entries: dict[int, tuple[ctk.CTkEntry, ctk.CTkEntry]] = {}
        for row_index, item in enumerate(existing_schedule, start=4):
            round_number = int(item["round_number"])
            ctk.CTkLabel(schedule_panel, text=str(round_number)).grid(
                row=row_index,
                column=0,
                padx=16,
                pady=(4, 0),
                sticky="w",
            )
            date_entry = self._make_date_entry(schedule_panel, width=20)
            date_entry.grid(row=row_index, column=1, padx=8, pady=(4, 0), sticky="ew")
            date_entry.insert(0, str(item.get("date") or ""))
            time_entry = ctk.CTkEntry(schedule_panel, width=140)
            time_entry.grid(row=row_index, column=2, padx=(8, 16), pady=(4, 0), sticky="ew")
            time_entry.insert(0, str(item.get("time") or ""))
            schedule_entries[round_number] = (date_entry, time_entry)

        def apply_auto_schedule() -> None:
            try:
                rounds_count = int(tournament_entries["rounds_count"].get() or tournament.get("rounds_count") or 1)
                rounds_per_day = rounds_count if all_same_day_check.get() else auto_entries["rounds_per_day"].get()
                generated_schedule = self.tournament_service.generate_round_schedule(
                    rounds_count=rounds_count,
                    start_date=auto_entries["start_date"].get(),
                    first_time=auto_entries["first_time"].get(),
                    round_duration_minutes=auto_entries["duration"].get(),
                    break_minutes=auto_entries["break"].get(),
                    rounds_per_day=rounds_per_day,
                )
                for item in generated_schedule:
                    entries = schedule_entries.get(int(item["round_number"]))
                    if not entries:
                        continue
                    entries[0].delete(0, "end")
                    entries[0].insert(0, str(item["date"]))
                    entries[1].delete(0, "end")
                    entries[1].insert(0, str(item["time"]))
            except Exception as exc:
                self._show_error(exc)

        btn_auto = ctk.CTkButton(generator_frame, text="Preencher agenda", command=apply_auto_schedule)
        btn_auto.grid(row=2, column=4, padx=(8, 0), pady=(2, 0), sticky="e")
        self._disable_if_unauthorized(btn_auto, "tournament_write")

        def profile_payloads() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
            tournament_payload = {
                key: entry.get()
                for key, entry in tournament_entries.items()
            }
            settings_payload = {
                key: entry.get()
                for key, entry in setting_entries.items()
            }
            scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
            tournament_payload["scope"] = scope
            tournament_payload["competition_type"] = competition_by_label[competition_option.get()]
            tournament_payload["club_id"] = None
            tournament_payload["class_id"] = None
            if scope in {"club", "class"}:
                tournament_payload["club_id"] = tournament_club_map.get(tournament_club_option.get())
                if not tournament_payload["club_id"]:
                    raise AppError("Selecione o clube/escola do torneio.")
            if scope == "class":
                tournament_payload["class_id"] = tournament_class_map.get(tournament_class_option.get())
                if not tournament_payload["class_id"]:
                    raise AppError("Selecione a turma do torneio.")
            settings_payload["initial_order"] = initial_order_by_label[initial_order_option.get()]
            settings_payload["tournament_profile"] = profile_by_label[tournament_profile_option.get()]
            settings_payload["tournament_type"] = type_by_label[tournament_type_option.get()]
            settings_payload["pairing_method"] = pairing_by_label[pairing_option.get()]
            settings_payload["team_pairing_method"] = team_pairing_by_label[team_pairing_option.get()]
            settings_payload["team_standing_primary"] = team_criterion_by_label[team_primary_option.get()]
            settings_payload["team_standing_secondary"] = team_criterion_by_label[team_secondary_option.get()]
            settings_payload["team_fixed_board_order"] = team_fixed_board_order_check.get()
            for key, checkbox in flag_checks.items():
                settings_payload[key] = checkbox.get()
            schedule_payload = [
                {
                    "round_number": round_number,
                    "date": entries[0].get(),
                    "time": entries[1].get(),
                }
                for round_number, entries in schedule_entries.items()
            ]
            return tournament_payload, settings_payload, schedule_payload

        def save_settings(show_message: bool = True) -> None:
            try:
                tournament_payload, settings_payload, schedule_payload = profile_payloads()
                self.tournament_service.save_profile(
                    self.current_tournament_id,
                    tournament_payload,
                    settings_payload,
                    schedule_payload,
                )
                self._set_current_tournament(self.current_tournament_id)
                if show_message:
                    self._show_info("Configuracoes do torneio salvas.")
                self.show_tournament_settings()
            except Exception as exc:
                self._show_error(exc)

        def save_as_new_tournament() -> None:
            try:
                tournament_payload, settings_payload, schedule_payload = profile_payloads()
                new_name = self._ask_string(
                    "Salvar como novo torneio",
                    "Nome do novo torneio (em branco usa o nome do formulario):",
                )
                if new_name is None:
                    return
                if new_name.strip():
                    tournament_payload["name"] = new_name.strip()
                new_tournament_id = self.tournament_service.create_tournament_from_profile(
                    tournament_payload,
                    settings_payload,
                    schedule_payload,
                )
                self._set_current_tournament(new_tournament_id)
                self._show_info("Novo torneio criado com estas configuracoes. Inclua ou importe os participantes.")
                self.show_tournament_settings()
            except Exception as exc:
                self._show_error(exc)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=2, sticky="e")
        btn_save_config = ctk.CTkButton(actions, text="Salvar configuracoes", command=save_settings)
        btn_save_config.pack(side="right", padx=(8, 0), pady=(0, 12))
        self._disable_if_unauthorized(btn_save_config, "tournament_write")
        btn_save_as = ctk.CTkButton(actions, text="Salvar como novo", command=save_as_new_tournament)
        btn_save_as.pack(side="right", padx=(8, 0), pady=(0, 12))
        self._disable_if_unauthorized(btn_save_as, "tournament_write")
        btn_refs = ctk.CTkButton(actions, text="Equipe de Arbitragem", command=self.show_tournament_referees_dialog)
        btn_refs.pack(side="right", padx=(8, 0), pady=(0, 12))
        self._disable_if_unauthorized(btn_refs, "tournament_write")

    def show_players(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        self._clear_content()
        self._page_title(
            "Jogadores",
            f"Torneio: {tournament['name'] if tournament else ''} - {self._tournament_scope_text(tournament) if tournament else ''}",
        )
        self._build_tournament_nav("players")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=280)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, Any] = {}
        player_fields = [
            ("name", "Nome"),
            ("surname", "Sobrenome"),
            ("given_name", "Nome proprio"),
            ("title", "Titulo"),
            ("sex", "Sexo"),
            ("rating", "Rating principal"),
            ("national_rating", "Rating nacional"),
            ("international_rating", "Rating internacional"),
            ("fide_id", "FIDE ID"),
            ("cbx_id", "CBX ID"),
            ("club", "Clube/Cidade"),
            ("category", "Categoria"),
            ("birth_date", "Nascimento"),
        ]
        for index, (key, label) in enumerate(player_fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(12, 0), sticky="w")
            if key == "birth_date":
                entry = self._make_date_entry(form, width=28)
            elif key == "category":
                from ..support import FIDE_CATEGORIES
                entry = ctk.CTkOptionMenu(form, values=FIDE_CATEGORIES, width=240)
                entry.set("")
            else:
                entry = ctk.CTkEntry(form, width=240)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            entries[key] = entry
            
            if key in ["fide_id", "cbx_id"]:
                def autofill_from_official(event, current_key=key):
                    val = entries[current_key].get().strip()
                    if not val:
                        return
                    
                    params = {"fide_id": val} if current_key == "fide_id" else {"cbx_id": val}
                    player = self.db.find_latest_official_player(**params)
                    if not player:
                        return
                        
                    def update_if_empty(field_name, value):
                        if field_name in entries and not entries[field_name].get().strip() and value:
                            entries[field_name].delete(0, "end")
                            entries[field_name].insert(0, str(value))
                            
                    update_if_empty("name", player.get("name"))
                    update_if_empty("surname", player.get("surname"))
                    update_if_empty("given_name", player.get("given_name"))
                    update_if_empty("title", player.get("title"))
                    update_if_empty("sex", player.get("sex"))
                    update_if_empty("birth_date", player.get("birth_date"))
                    update_if_empty("international_rating", player.get("international_rating"))
                    update_if_empty("national_rating", player.get("national_rating"))
                    rating_to_use = player.get("standard_rating") or player.get("international_rating") or player.get("national_rating")
                    if rating_to_use:
                        update_if_empty("rating", rating_to_use)
                    
                    if current_key == "fide_id":
                        update_if_empty("cbx_id", player.get("cbx_id"))
                    else:
                        update_if_empty("fide_id", player.get("fide_id"))
                        
                entry.bind("<FocusOut>", autofill_from_official)
        control_row = len(player_fields) * 2
        ctk.CTkLabel(form, text="Buscar na lista").grid(row=control_row, column=0, padx=16, pady=(16, 0), sticky="w")
        search_entry = ctk.CTkEntry(form, width=240, placeholder_text="Nome, clube, turma, categoria ou rating")
        search_entry.grid(row=control_row + 1, column=0, padx=16, pady=(4, 8), sticky="ew")

        member_source_label = "Membro cadastrado"
        if tournament and tournament.get("class_id"):
            member_source_label = "Membro da turma"
        elif tournament and tournament.get("club_id"):
            member_source_label = "Membro do clube/escola"
        ctk.CTkLabel(form, text=member_source_label).grid(
            row=control_row + 2,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        member_option_map: dict[str, int] = {}
        member_option = ctk.CTkOptionMenu(form, values=["Sem membros disponiveis"], width=240)
        member_option.grid(row=control_row + 3, column=0, padx=16, pady=(4, 4), sticky="ew")
        include_out_of_scope_check = ctk.CTkCheckBox(form, text="Incluir outros clubes/turmas")
        include_out_of_scope_check.grid(row=control_row + 4, column=0, padx=16, pady=(8, 4), sticky="w")

        ctk.CTkLabel(form, text="Status no torneio").grid(
            row=control_row + 5,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        player_status_option = ctk.CTkOptionMenu(form, values=list(PLAYER_STATUS_VALUES.keys()), width=240)
        player_status_option.grid(row=control_row + 6, column=0, padx=16, pady=(4, 4), sticky="ew")
        player_status_option.set(PLAYER_STATUSES["active"])

        selected_player_id: dict[str, int | None] = {"value": None}

        table_panel = self._make_panel(body)
        table_panel.grid(row=0, column=1, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)
        players_summary_label = ctk.CTkLabel(
            table_panel,
            text="Total: 0 | Visiveis: 0 | Presentes: 0 | Ausentes: 0 | Membros: 0 | Convidados: 0",
            text_color=THEME_TEXT_SUB,
        )
        players_summary_label.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        players_tree_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        players_tree_holder.grid(row=1, column=0, sticky="nsew")
        players_tree_holder.grid_columnconfigure(0, weight=1)
        players_tree_holder.grid_rowconfigure(0, weight=1)

        columns = [
            "id",
            "name",
            "source",
            "rating",
            "fide",
            "cbx",
            "club",
            "class",
            "category",
            "age_category",
            "rating_category",
            "tags",
            "status",
        ]
        tree = self._make_tree(
            players_tree_holder,
            columns,
            {
                "id": "ID",
                "name": "Nome",
                "source": "Origem",
                "rating": "Rating",
                "fide": "FIDE",
                "cbx": "CBX",
                "club": "Clube",
                "class": "Turma",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "status": "Status",
            },
            {
                "id": 60,
                "name": 250,
                "source": 90,
                "rating": 80,
                "fide": 90,
                "cbx": 90,
                "club": 150,
                "class": 130,
                "category": 120,
                "age_category": 90,
                "rating_category": 95,
                "tags": 170,
                "status": 90,
            },
        )

        def clear_form() -> None:
            selected_player_id["value"] = None
            for entry in entries.values():
                if isinstance(entry, ctk.CTkOptionMenu):
                    entry.set("")
                elif hasattr(entry, "delete"):
                    entry.delete(0, "end")
            player_status_option.set(PLAYER_STATUSES["active"])

        def load_players() -> None:
            tree.delete(*tree.get_children())
            query = search_entry.get().strip().casefold()
            players = self.db.list_players(self.current_tournament_id, active_only=False)
            visible_count = 0
            present_count = sum(1 for player in players if player.get("player_status") == "active")
            member_count = sum(1 for player in players if player.get("member_id"))
            absent_count = len(players) - present_count
            for player in players:
                display_name = player_full_name(player)
                searchable = " ".join(
                    [
                        display_name,
                        str(player["name"] or ""),
                        str(player.get("surname") or ""),
                        str(player.get("given_name") or ""),
                        str(player["club"] or ""),
                        str(player.get("active_class_name") or ""),
                        str(player["category"] or ""),
                        str(player.get("age_category") or ""),
                        str(player.get("rating_category") or ""),
                        str(player.get("prize_tags") or ""),
                        str(player["rating"] or ""),
                        str(player.get("fide_id") or ""),
                        str(player.get("cbx_id") or ""),
                        str(player.get("national_rating") or ""),
                        str(player.get("international_rating") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                visible_count += 1
                tree.insert(
                    "",
                    "end",
                    values=(
                        player["id"],
                        display_name,
                        "Membro" if player.get("member_id") else "Convidado",
                        player["rating"],
                        player.get("fide_id", ""),
                        player.get("cbx_id", ""),
                        player["club"],
                        player.get("active_class_name", ""),
                        player["category"],
                        player.get("age_category", ""),
                        player.get("rating_category", ""),
                        player.get("prize_tags", ""),
                        PLAYER_STATUSES.get(player.get("player_status", "active"), player.get("player_status", "")),
                    ),
                )
            players_summary_label.configure(
                text=(
                    f"Total: {len(players)} | Visiveis: {visible_count} | "
                    f"Presentes: {present_count} | Ausentes: {absent_count} | "
                    f"Membros: {member_count} | Convidados: {len(players) - member_count}"
                )
            )

        def load_member_options() -> None:
            member_option_map.clear()
            values = []
            include_out_of_scope = bool(include_out_of_scope_check.get())
            for member in self.db.list_members_for_tournament(
                self.current_tournament_id,
                active_only=True,
                include_out_of_scope=include_out_of_scope,
            ):
                if member["registered_player_id"]:
                    continue
                club_name = str(member.get("club_name") or "Sem clube").strip()
                class_name = str(member.get("active_class_name") or "").strip()
                scope_parts = [club_name]
                if class_name:
                    scope_parts.append(class_name)
                scope_text = " / ".join(scope_parts)
                label = f"{member['id']} - {self._member_display_name(member)} ({member['rating']}) - {scope_text}"
                values.append(label)
                member_option_map[label] = int(member["id"])
            if not values:
                values = ["Sem membros disponiveis"]
            member_option.configure(values=values)
            member_option.set(values[0])

        def selected_player() -> dict[str, Any] | None:
            selected = tree.selection()
            if not selected:
                return None
            player_id = int(tree.item(selected[0], "values")[0])
            return self.db.get_player(player_id)

        def on_select(_event: Any = None) -> None:
            player = selected_player()
            if not player:
                return
            selected_player_id["value"] = player["id"]
            player_status_option.set(
                PLAYER_STATUSES.get(player.get("player_status", "active"), PLAYER_STATUSES["active"])
            )
            clear_values = {
                key: player.get(key, "")
                for key, _label in player_fields
            }
            for key, value in clear_values.items():
                if isinstance(entries[key], ctk.CTkOptionMenu):
                    entries[key].set(str(value or ""))
                elif hasattr(entries[key], "delete"):
                    entries[key].delete(0, "end")
                    entries[key].insert(0, str(value or ""))

        def add_player() -> None:
            try:
                name = entries["name"].get().strip()
                if not name:
                    raise AppError("Informe o nome do jogador.")
                rating = int(entries["rating"].get() or "0")
                national_rating = int(entries["national_rating"].get() or "0")
                international_rating = int(entries["international_rating"].get() or "0")
                self.db.create_player(
                    self.current_tournament_id,
                    name=name,
                    rating=rating,
                    club=entries["club"].get(),
                    category=entries["category"].get(),
                    federation_id="",
                    fide_id=entries["fide_id"].get(),
                    birth_date=entries["birth_date"].get(),
                    surname=entries["surname"].get(),
                    given_name=entries["given_name"].get(),
                    title=entries["title"].get(),
                    sex=entries["sex"].get(),
                    cbx_id=entries["cbx_id"].get(),
                    national_rating=national_rating,
                    international_rating=international_rating,
                    player_status=PLAYER_STATUS_VALUES[player_status_option.get()],
                )
                logger.info("Jogador criado no torneio %s: %s", self.current_tournament_id, name)
                clear_form()
                load_players()
                load_member_options()
            except Exception as exc:
                self._show_error(exc)

        def register_member() -> None:
            try:
                member_id = member_option_map.get(member_option.get())
                if not member_id:
                    raise AppError("Nao ha membro disponivel para inscrever.")
                self.member_service.register_member_in_tournament(
                    self.current_tournament_id,
                    member_id,
                    allow_out_of_scope=bool(include_out_of_scope_check.get()),
                )
                load_players()
                load_member_options()
            except Exception as exc:
                self._show_error(exc)

        def register_all_active_members() -> None:
            try:
                result = self.member_service.register_active_members_in_tournament(
                    self.current_tournament_id,
                    include_out_of_scope=bool(include_out_of_scope_check.get()),
                )
                load_players()
                load_member_options()
                self._show_info(
                    f"{result['registered']} membros ativos inscritos. "
                    f"{result['skipped']} ja estavam inscritos."
                )
            except Exception as exc:
                self._show_error(exc)

        def update_player() -> None:
            try:
                player_id = selected_player_id["value"]
                if not player_id:
                    raise AppError("Selecione um jogador.")
                current = self.db.get_player(player_id)
                if not current:
                    raise AppError("Jogador nao encontrado.")
                self.db.update_player(
                    player_id,
                    name=entries["name"].get(),
                    club=entries["club"].get(),
                    rating=int(entries["rating"].get() or "0"),
                    category=entries["category"].get(),
                    active=int(current["active"]),
                    federation_id=current.get("federation_id", ""),
                    fide_id=entries["fide_id"].get(),
                    birth_date=entries["birth_date"].get(),
                    surname=entries["surname"].get(),
                    given_name=entries["given_name"].get(),
                    title=entries["title"].get(),
                    sex=entries["sex"].get(),
                    cbx_id=entries["cbx_id"].get(),
                    national_rating=int(entries["national_rating"].get() or "0"),
                    international_rating=int(entries["international_rating"].get() or "0"),
                    player_status=PLAYER_STATUS_VALUES[player_status_option.get()],
                )
                logger.info("Jogador atualizado: %s", player_id)
                load_players()
            except Exception as exc:
                self._show_error(exc)

        def update_player_status() -> None:
            try:
                player = selected_player()
                if not player:
                    raise AppError("Selecione um jogador.")
                status = PLAYER_STATUS_VALUES[player_status_option.get()]
                self.db.set_player_status(player["id"], status)
                logger.info("Status do jogador %s alterado para %s", player["id"], status)
                load_players()
            except Exception as exc:
                self._show_error(exc)

        def delete_player() -> None:
            try:
                player = selected_player()
                if not player:
                    raise AppError("Selecione um jogador.")
                confirmed = messagebox.askyesno(
                    "Excluir jogador",
                    "Excluir este jogador do torneio?\n\n"
                    "A exclusao so e permitida se ele ainda nao apareceu em nenhuma rodada.",
                )
                if not confirmed:
                    return
                self.pairing_service.delete_player_if_unpaired(
                    self.current_tournament_id,
                    int(player["id"]),
                )
                clear_form()
                load_players()
                load_member_options()
                self._show_info("Jogador excluido do torneio.")
            except Exception as exc:
                self._show_error(exc)

        def import_players() -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title="Importar jogadores",
                    filetypes=[
                        ("Planilhas e CSV", "*.csv;*.xls;*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Excel", "*.xls;*.xlsx"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                tournament_id = int(self.current_tournament_id)

                def show_import_result(result: dict[str, Any]) -> None:
                    load_players()
                    load_member_options()
                    message = f"{result['imported']} jogadores importados."
                    if result["errors"]:
                        message += "\n\nErros:\n" + "\n".join(result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    lambda: self.import_service.import_players(tournament_id, file_path),
                    show_import_result,
                    "Importando jogadores...",
                )
            except Exception as exc:
                self._show_error(exc)

        def show_online_registration_preview(result: dict[str, Any], file_path: str) -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Inscricoes online")
            dialog.geometry("980x560")
            dialog.minsize(860, 460)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_rowconfigure(1, weight=1)

            summary = (
                f"Total: {result['total']} | Prontas: {result['ready']} | "
                f"Duplicadas: {result['duplicate']} | Erros: {result['error']}"
            )
            ctk.CTkLabel(
                dialog,
                text=summary,
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=THEME_TEXT_MAIN,
            ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

            table_panel = ctk.CTkFrame(dialog, fg_color="transparent")
            table_panel.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")
            table_panel.grid_columnconfigure(0, weight=1)
            table_panel.grid_rowconfigure(0, weight=1)
            preview_tree = self._make_tree(
                table_panel,
                ["line", "status", "name", "birth", "rating", "club", "category", "message"],
                {
                    "line": "Linha",
                    "status": "Status",
                    "name": "Nome",
                    "birth": "Nascimento",
                    "rating": "Rating",
                    "club": "Clube/Cidade",
                    "category": "Categoria",
                    "message": "Mensagem",
                },
                {
                    "line": 60,
                    "status": 90,
                    "name": 210,
                    "birth": 100,
                    "rating": 80,
                    "club": 150,
                    "category": 110,
                    "message": 260,
                },
                visible_rows=13,
            )
            for row in result["rows"]:
                preview_tree.insert(
                    "",
                    "end",
                    values=(
                        row["line"],
                        row["status_label"],
                        row["name"],
                        row["birth_date"],
                        row["rating"],
                        row["club"],
                        row["category"],
                        row["message"],
                    ),
                )

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="e")

            def run_import() -> None:
                dialog.destroy()
                tournament_id = int(self.current_tournament_id)

                def show_result(import_result: dict[str, Any]) -> None:
                    load_players()
                    load_member_options()
                    message = (
                        f"{import_result['imported']} inscricoes online importadas.\n"
                        f"{import_result['skipped']} linhas ignoradas."
                    )
                    if import_result["errors"]:
                        message += "\n\nErros:\n" + "\n".join(import_result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    lambda: self.import_service.import_online_registrations(tournament_id, file_path),
                    show_result,
                    "Importando inscricoes online...",
                )

            ctk.CTkButton(actions, text="Cancelar", fg_color="#64748B", command=dialog.destroy).pack(
                side="left",
                padx=(0, 8),
            )
            import_button = ctk.CTkButton(actions, text="Importar prontas", command=run_import)
            import_button.pack(side="left")
            if result["ready"] <= 0:
                import_button.configure(state="disabled")

        def import_online_registrations() -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title="Importar inscricoes online",
                    filetypes=[
                        ("Planilhas e CSV", "*.csv;*.xls;*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Excel", "*.xls;*.xlsx"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                tournament_id = int(self.current_tournament_id)
                self._run_background(
                    lambda: self.import_service.preview_online_registrations(tournament_id, file_path),
                    lambda result: show_online_registration_preview(result, file_path),
                    "Lendo inscricoes online...",
                )
            except Exception as exc:
                self._show_error(exc)

        def import_online_registrations_url() -> None:
            try:
                source_url = self._ask_string(
                    "Importar inscricoes online",
                    "Cole o link CSV publicado do Google Sheets/Forms:",
                )
                if not source_url:
                    return
                tournament_id = int(self.current_tournament_id)
                source_url = source_url.strip()
                self._run_background(
                    lambda: self.import_service.preview_online_registrations(tournament_id, source_url),
                    lambda result: show_online_registration_preview(result, source_url),
                    "Lendo inscricoes online...",
                )
            except Exception as exc:
                self._show_error(exc)

        def export_import_template(template_type: str) -> None:
            try:
                default_name = (
                    "modelo_inscricoes_online.xlsx"
                    if template_type == "online"
                    else "modelo_jogadores.xlsx"
                )
                file_path = filedialog.asksaveasfilename(
                    title="Salvar modelo de importacao",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_name,
                    defaultextension=".xlsx",
                    filetypes=[
                        ("Excel", "*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() not in {".csv", ".xlsx"}:
                    path = path.with_suffix(".xlsx")
                exporter = (
                    self.export_service.export_online_registration_template
                    if template_type == "online"
                    else self.export_service.export_player_import_template
                )
                self._run_background(
                    lambda: exporter(path),
                    lambda _result: self._show_info(f"Modelo salvo:\n{path}"),
                    "Gerando modelo...",
                )
            except Exception as exc:
                self._show_error(exc)

        def import_official_ratings(source: str) -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title=f"Importar lista {source}",
                    filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
                )
                if not file_path:
                    return
                def show_import_result(result: dict[str, Any]) -> None:
                    message = f"{result['imported']} jogadores importados para a base {source}."
                    if result["errors"]:
                        message += "\n\nErros:\n" + "\n".join(result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    lambda: self.official_rating_service.import_official_csv(file_path, source),
                    show_import_result,
                    f"Importando lista {source}...",
                )
            except Exception as exc:
                self._show_error(exc)

        def update_official_ratings() -> None:
            try:
                tournament_id = int(self.current_tournament_id)

                def show_update_result(result: dict[str, Any]) -> None:
                    load_players()
                    message = f"{result['updated']} jogadores atualizados pela base oficial."
                    if result["unmatched"]:
                        message += "\n\nSem correspondencia:\n" + "\n".join(result["unmatched"][:12])
                    self._show_info(message)

                self._run_background(
                    lambda: self.official_rating_service.update_tournament_players(tournament_id),
                    show_update_result,
                    "Atualizando ratings oficiais...",
                )
            except Exception as exc:
                self._show_error(exc)

        tree.bind("<<TreeviewSelect>>", on_select)
        search_entry.bind("<KeyRelease>", lambda _event: load_players())
        include_out_of_scope_check.configure(command=load_member_options)

        button_specs = [
            ("Adicionar convidado", add_player),
            ("Atualizar", update_player),
            ("Atualizar status", update_player_status),
            ("Excluir jogador", delete_player),
            ("Limpar", clear_form),
            ("Inscrever membro", register_member),
            ("Inscrever todos ativos", register_all_active_members),
            ("Modelo jogadores", lambda: export_import_template("players")),
            ("Importar CSV/Excel", import_players),
            ("Modelo inscricoes", lambda: export_import_template("online")),
            ("Importar inscricoes online", import_online_registrations),
            ("Importar link Forms/Sheets", import_online_registrations_url),
            ("Importar FIDE", lambda: import_official_ratings("FIDE")),
            ("Importar CBX", lambda: import_official_ratings("CBX")),
            ("Atualizar ratings oficiais", update_official_ratings),
        ]
        self._grid_form_buttons(form, button_specs, control_row + 7, required_action="tournament_write")

        load_players()
        load_member_options()

    def show_teams(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            self._show_error(AppError("Selecione um torneio valido."))
            return

        self._clear_content()
        self._page_title(
            "Equipes",
            f"Torneio: {tournament['name']} - {COMPETITION_TYPES.get(tournament.get('competition_type', 'individual'), 'Individual')}",
        )
        self._build_tournament_nav("teams")

        if tournament.get("competition_type") != "team":
            body = ctk.CTkFrame(self.content, fg_color="transparent")
            body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
            panel = self._make_panel(body)
            panel.grid(row=0, column=0, sticky="nw")
            ctk.CTkLabel(
                panel,
                text="Este torneio esta no formato Individual.",
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
            ctk.CTkLabel(
                panel,
                text="Altere o formato para Equipes na configuracao do torneio para cadastrar equipes.",
                text_color=THEME_TEXT_SUB,
                wraplength=420,
                justify="left",
            ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
            ctk.CTkButton(
                panel,
                text="Abrir configuracao do torneio",
                command=self.show_tournament_settings,
            ).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")
            return

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=292)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        team_entries: dict[str, ctk.CTkEntry] = {}
        team_fields = [
            ("name", "Nome da equipe"),
            ("club", "Clube/Cidade"),
            ("captain", "Capitao"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(team_fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(12, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=252)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            team_entries[key] = entry

        active_check = ctk.CTkCheckBox(form, text="Equipe ativa")
        active_check.grid(row=len(team_fields) * 2, column=0, padx=16, pady=(12, 4), sticky="w")
        active_check.select()

        assignment_row = len(team_fields) * 2 + 1
        ctk.CTkLabel(
            form,
            text="Jogador da equipe",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=assignment_row, column=0, padx=16, pady=(18, 4), sticky="w")

        ctk.CTkLabel(form, text="Jogador inscrito").grid(
            row=assignment_row + 1,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        player_option_map: dict[str, int] = {}
        player_option = ctk.CTkOptionMenu(form, values=["Sem jogadores disponiveis"], width=252)
        player_option.grid(row=assignment_row + 2, column=0, padx=16, pady=(4, 2), sticky="ew")

        ctk.CTkLabel(form, text="Funcao").grid(
            row=assignment_row + 3,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        role_option = ctk.CTkOptionMenu(form, values=list(TEAM_PLAYER_ROLE_VALUES.keys()), width=252)
        role_option.grid(row=assignment_row + 4, column=0, padx=16, pady=(4, 2), sticky="ew")
        role_option.set(TEAM_PLAYER_ROLES["starter"])

        ctk.CTkLabel(form, text="Tabuleiro").grid(
            row=assignment_row + 5,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        board_entry = ctk.CTkEntry(form, width=252)
        board_entry.grid(row=assignment_row + 6, column=0, padx=16, pady=(4, 2), sticky="ew")

        selected_team_id: dict[str, int | None] = {"value": None}
        selected_team_player_id: dict[str, int | None] = {"value": None}

        table_area = ctk.CTkFrame(body, fg_color="transparent")
        table_area.grid(row=0, column=1, sticky="nsew")
        table_area.grid_columnconfigure(0, weight=1)
        table_area.grid_rowconfigure(0, weight=1)
        table_area.grid_rowconfigure(1, weight=1)

        teams_panel = self._make_panel(table_area)
        teams_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        teams_panel.grid_columnconfigure(0, weight=1)
        teams_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            teams_panel,
            text="Equipes cadastradas",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        team_tree = self._make_tree(
            teams_panel,
            ["id", "name", "club", "captain", "starters", "players", "status"],
            {
                "id": "ID",
                "name": "Equipe",
                "club": "Clube/Cidade",
                "captain": "Capitao",
                "starters": "Titulares",
                "players": "Jogadores",
                "status": "Status",
            },
            {
                "id": 60,
                "name": 220,
                "club": 160,
                "captain": 150,
                "starters": 80,
                "players": 85,
                "status": 85,
            },
            visible_rows=7,
        )
        self.team_tree = team_tree

        roster_panel = self._make_panel(table_area)
        roster_panel.grid(row=1, column=0, sticky="nsew")
        roster_panel.grid_columnconfigure(0, weight=1)
        roster_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            roster_panel,
            text="Escalacao da equipe",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        roster_tree = self._make_tree(
            roster_panel,
            ["id", "board", "role", "player", "rating", "club", "status"],
            {
                "id": "ID",
                "board": "Tab.",
                "role": "Funcao",
                "player": "Jogador",
                "rating": "Rating",
                "club": "Clube",
                "status": "Status",
            },
            {
                "id": 60,
                "board": 60,
                "role": 90,
                "player": 240,
                "rating": 80,
                "club": 150,
                "status": 90,
            },
            visible_rows=8,
        )
        self.team_player_tree = roster_tree

        def team_payload() -> dict[str, Any]:
            return {
                "name": team_entries["name"].get(),
                "club": team_entries["club"].get(),
                "captain": team_entries["captain"].get(),
                "notes": team_entries["notes"].get(),
                "active": active_check.get(),
            }

        def all_assigned_player_ids(current_player_id: int | None = None) -> set[int]:
            assigned: set[int] = set()
            for team in self.db.list_teams(self.current_tournament_id, active_only=False):
                for item in self.db.list_team_players(int(team["id"]), active_only=False):
                    player_id = int(item["player_id"])
                    if current_player_id and player_id == current_player_id:
                        continue
                    assigned.add(player_id)
            return assigned

        def load_player_options(current_player_id: int | None = None) -> None:
            player_option_map.clear()
            assigned = all_assigned_player_ids(current_player_id)
            values = []
            for player in self.db.list_players(self.current_tournament_id, active_only=False):
                player_id = int(player["id"])
                if player_id in assigned:
                    continue
                if player.get("player_status") != "active" and player_id != current_player_id:
                    continue
                label = (
                    f"{player_id} - {player_full_name(player)} "
                    f"({player.get('rating') or 0}) - {player.get('club') or 'Sem clube'}"
                )
                values.append(label)
                player_option_map[label] = player_id
            if not values:
                values = ["Sem jogadores disponiveis"]
            player_option.configure(values=values)
            player_option.set(values[0])

        def clear_team_form() -> None:
            selected_team_id["value"] = None
            for entry in team_entries.values():
                entry.delete(0, "end")
            active_check.select()
            team_tree.selection_remove(*team_tree.selection())
            clear_assignment()
            load_team_players()

        def clear_assignment() -> None:
            selected_team_player_id["value"] = None
            board_entry.delete(0, "end")
            role_option.set(TEAM_PLAYER_ROLES["starter"])
            roster_tree.selection_remove(*roster_tree.selection())
            load_player_options()

        def load_teams() -> None:
            team_tree.delete(*team_tree.get_children())
            for team in self.db.list_teams(self.current_tournament_id, active_only=False):
                team_tree.insert(
                    "",
                    "end",
                    values=(
                        team["id"],
                        team["name"],
                        team.get("club", ""),
                        team.get("captain", ""),
                        team.get("starters_count", 0),
                        team.get("players_count", 0),
                        "Ativa" if team.get("active") else "Inativa",
                    ),
                )

        def load_team_players() -> None:
            roster_tree.delete(*roster_tree.get_children())
            team_id = selected_team_id["value"]
            if not team_id:
                load_player_options()
                return
            for item in self.db.list_team_players(team_id, active_only=False):
                roster_tree.insert(
                    "",
                    "end",
                    values=(
                        item["id"],
                        item.get("board_number") or "",
                        TEAM_PLAYER_ROLES.get(item.get("role", "starter"), item.get("role", "")),
                        player_full_name(
                            {
                                "name": item.get("player_name"),
                                "surname": item.get("player_surname"),
                                "given_name": item.get("player_given_name"),
                            }
                        ),
                        item.get("player_rating", 0),
                        item.get("player_club", ""),
                        PLAYER_STATUSES.get(item.get("player_status", "active"), item.get("player_status", "")),
                    ),
                )
            load_player_options()

        def selected_team() -> dict[str, Any] | None:
            selected = team_tree.selection()
            if not selected:
                return None
            return self.db.get_team(int(team_tree.item(selected[0], "values")[0]))

        def selected_assignment() -> dict[str, Any] | None:
            selected = roster_tree.selection()
            if not selected:
                return None
            return self.db.get_team_player(int(roster_tree.item(selected[0], "values")[0]))

        def on_team_select(_event: Any = None) -> None:
            team = selected_team()
            if not team:
                return
            selected_team_id["value"] = int(team["id"])
            for key in ("name", "club", "captain", "notes"):
                team_entries[key].delete(0, "end")
                team_entries[key].insert(0, str(team.get(key) or ""))
            if team.get("active"):
                active_check.select()
            else:
                active_check.deselect()
            selected_team_player_id["value"] = None
            board_entry.delete(0, "end")
            role_option.set(TEAM_PLAYER_ROLES["starter"])
            load_team_players()

        def on_roster_select(_event: Any = None) -> None:
            assignment = selected_assignment()
            if not assignment:
                return
            selected_team_player_id["value"] = int(assignment["id"])
            role_option.set(TEAM_PLAYER_ROLES.get(assignment.get("role", "starter"), TEAM_PLAYER_ROLES["starter"]))
            board_entry.delete(0, "end")
            if assignment.get("board_number"):
                board_entry.insert(0, str(assignment["board_number"]))
            load_player_options(int(assignment["player_id"]))
            current_label = next(
                (
                    label
                    for label, player_id in player_option_map.items()
                    if player_id == int(assignment["player_id"])
                ),
                None,
            )
            if current_label:
                player_option.set(current_label)

        def create_team() -> None:
            try:
                team_id = self.team_service.create_team(self.current_tournament_id, team_payload())
                selected_team_id["value"] = team_id
                load_teams()
                load_team_players()
                self._show_info("Equipe criada.")
            except Exception as exc:
                self._show_error(exc)

        def update_team() -> None:
            try:
                team_id = selected_team_id["value"]
                if not team_id:
                    raise AppError("Selecione uma equipe.")
                self.team_service.update_team(team_id, team_payload())
                load_teams()
                self._show_info("Equipe atualizada.")
            except Exception as exc:
                self._show_error(exc)

        def delete_team() -> None:
            try:
                team_id = selected_team_id["value"]
                if not team_id:
                    raise AppError("Selecione uma equipe.")
                if not messagebox.askyesno(
                    "Excluir equipe",
                    "Excluir esta equipe e sua escalacao? Equipes usadas em rodadas devem ser inativadas.",
                ):
                    return
                self.team_service.delete_team(team_id)
                clear_team_form()
                load_teams()
                self._show_info("Equipe excluida.")
            except Exception as exc:
                self._show_error(exc)

        def add_player_to_team() -> None:
            try:
                team_id = selected_team_id["value"]
                if not team_id:
                    raise AppError("Selecione uma equipe.")
                player_id = player_option_map.get(player_option.get())
                if not player_id:
                    raise AppError("Nao ha jogador disponivel para adicionar.")
                self.team_service.add_player(
                    team_id,
                    player_id,
                    board_entry.get(),
                    TEAM_PLAYER_ROLE_VALUES[role_option.get()],
                )
                clear_assignment()
                load_teams()
                load_team_players()
            except Exception as exc:
                self._show_error(exc)

        def update_assignment() -> None:
            try:
                team_player_id = selected_team_player_id["value"]
                if not team_player_id:
                    raise AppError("Selecione um jogador da equipe.")
                self.team_service.update_player_assignment(
                    team_player_id,
                    board_entry.get(),
                    TEAM_PLAYER_ROLE_VALUES[role_option.get()],
                )
                clear_assignment()
                load_teams()
                load_team_players()
            except Exception as exc:
                self._show_error(exc)

        def remove_assignment() -> None:
            try:
                team_player_id = selected_team_player_id["value"]
                if not team_player_id:
                    raise AppError("Selecione um jogador da equipe.")
                self.team_service.remove_player(team_player_id)
                clear_assignment()
                load_teams()
                load_team_players()
            except Exception as exc:
                self._show_error(exc)

        team_tree.bind("<<TreeviewSelect>>", on_team_select)
        roster_tree.bind("<<TreeviewSelect>>", on_roster_select)

        button_specs = [
            ("Criar equipe", create_team),
            ("Atualizar equipe", update_team),
            ("Excluir equipe", delete_team),
            ("Limpar equipe", clear_team_form),
            ("Adicionar jogador", add_player_to_team),
            ("Atualizar escalacao", update_assignment),
            ("Remover jogador", remove_assignment),
        ]
        self._grid_form_buttons(form, button_specs, assignment_row + 7, required_action="tournament_write")

        load_teams()
        load_player_options()

    def show_tournament_referees_dialog(self) -> None:
        if not self._require_tournament():
            return
            
        dialog = ctk.CTkToplevel(self)
        dialog.title("Equipe de Arbitragem")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        form_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        form_frame.pack(fill="x", pady=(0, 10))
        
        all_referees = self.referee_service.list_referees(active_only=True)
        ref_map = {f"{r['name']} ({r['category']})": r["id"] for r in all_referees}
        
        ctk.CTkLabel(form_frame, text="Adicionar árbitro:").pack(side="left", padx=(0, 10))
        
        ref_option = ctk.CTkOptionMenu(form_frame, values=list(ref_map.keys()) if ref_map else ["Nenhum árbitro ativo"])
        ref_option.pack(side="left", padx=(0, 10))
        
        role_option = ctk.CTkOptionMenu(form_frame, values=["Árbitro Principal", "Árbitro Auxiliar", "Diretor"])
        role_option.pack(side="left", padx=(0, 10))
        
        list_frame = ctk.CTkFrame(main_frame)
        list_frame.pack(fill="both", expand=True)
        
        tree = self._make_tree(
            list_frame,
            ["id", "name", "role", "category"],
            {"id": "ID", "name": "Nome", "role": "Papel", "category": "Cat."},
            {"id": 40, "name": 200, "role": 150, "category": 60}
        )
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        def load_tournament_refs():
            tree.delete(*tree.get_children())
            refs = self.referee_service.list_tournament_referees(self.current_tournament_id)
            for r in refs:
                tree.insert("", "end", values=(r["referee_id"], r["name"], r["role"], r["category"]))
                
        def add_referee():
            if not ref_map:
                return
            ref_id = ref_map.get(ref_option.get())
            if not ref_id:
                return
            self.referee_service.assign_tournament_referee(self.current_tournament_id, ref_id, role_option.get())
            load_tournament_refs()
            
        def remove_referee():
            selected = tree.selection()
            if not selected:
                return
            ref_id = int(tree.item(selected[0], "values")[0])
            self.referee_service.remove_tournament_referee(self.current_tournament_id, ref_id)
            load_tournament_refs()
            
        ctk.CTkButton(form_frame, text="Adicionar", command=add_referee).pack(side="left")
        
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btn_frame, text="Remover Selecionado", command=remove_referee, fg_color="#ef4444", hover_color="#dc2626").pack(side="right")
        
        load_tournament_refs()

    def _make_time_control_menu(self, parent: ctk.CTkFrame, width: int = 230) -> ctk.CTkOptionMenu:
        preset_options = [
            "10 min",
            "15 min + 10 s",
            "3 min + 2 s",
            "90 min + 30 s",
            "Personalizado..."
        ]
        
        var = ctk.StringVar(value="10 min")
        menu = ctk.CTkOptionMenu(parent, values=preset_options, variable=var, width=width)
        
        def on_change(choice: str) -> None:
            if choice == "Personalizado...":
                custom_val = self._open_time_control_builder()
                if custom_val:
                    current_values = list(menu.cget("values"))
                    if custom_val not in current_values:
                        current_values.insert(0, custom_val)
                        menu.configure(values=current_values)
                    var.set(custom_val)
                else:
                    var.set("10 min")
                    
        menu.configure(command=on_change)
        
        def insert_hack(index: int, text: str) -> None:
            if text:
                current_values = list(menu.cget("values"))
                if text not in current_values and text != "Personalizado...":
                    current_values.insert(0, text)
                    menu.configure(values=current_values)
                var.set(text)
        
        menu.insert = insert_hack  # type: ignore
        return menu

    def _open_time_control_builder(self) -> str | None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Construtor de Ritmo")
        dialog.geometry("450x440")
        dialog.transient(self)
        dialog.grab_set()

        result: list[str | None] = [None]

        ctk.CTkLabel(dialog, text="Tempo inicial (minutos):").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        base_time = ctk.CTkEntry(dialog, width=100)
        base_time.grid(row=0, column=1, padx=16, pady=(16, 4), sticky="w")

        ctk.CTkLabel(dialog, text="Incremento por lance (s):").grid(row=1, column=0, padx=16, pady=4, sticky="w")
        inc_time = ctk.CTkEntry(dialog, width=100)
        inc_time.grid(row=1, column=1, padx=16, pady=4, sticky="w")

        adv_var = ctk.IntVar(value=0)
        
        def toggle_adv() -> None:
            state = "normal" if adv_var.get() else "disabled"
            moves_period_1.configure(state=state)
            time_period_2.configure(state=state)
            
        adv_check = ctk.CTkCheckBox(dialog, text="Múltiplos Períodos (Xadrez Clássico)", variable=adv_var, command=toggle_adv)
        adv_check.grid(row=2, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")

        ctk.CTkLabel(dialog, text="Lances do 1º período:").grid(row=3, column=0, padx=16, pady=4, sticky="w")
        moves_period_1 = ctk.CTkEntry(dialog, width=100, state="disabled")
        moves_period_1.grid(row=3, column=1, padx=16, pady=4, sticky="w")

        ctk.CTkLabel(dialog, text="Tempo 2º período (minutos):").grid(row=4, column=0, padx=16, pady=4, sticky="w")
        time_period_2 = ctk.CTkEntry(dialog, width=100, state="disabled")
        time_period_2.grid(row=4, column=1, padx=16, pady=4, sticky="w")
        
        help_text = (
            "Exemplos comuns gerados:\n"
            "• 3 min + 2 s (Blitz)\n"
            "• 10 min (Rápido s/ inc)\n"
            "• 15 min + 10 s (Rápido)\n"
            "• 90 min + 30 s (Clássico)\n"
            "• 90 min / 40 lances + 30 min + 30 s"
        )
        help_label = ctk.CTkLabel(dialog, text=help_text, justify="left", text_color="gray", font=ctk.CTkFont(size=12))
        help_label.grid(row=5, column=0, columnspan=2, padx=16, pady=(15, 0), sticky="w")

        def save() -> None:
            try:
                base = base_time.get().strip() or "0"
                inc = inc_time.get().strip() or "0"
                if adv_var.get():
                    m1 = moves_period_1.get().strip() or "0"
                    t2 = time_period_2.get().strip() or "0"
                    out = f"{base} min / {m1} lances + {t2} min"
                    if inc != "0":
                        out += f" + {inc} s"
                else:
                    out = f"{base} min"
                    if inc != "0":
                        out += f" + {inc} s"
                result[0] = out
                dialog.destroy()
            except Exception:
                pass

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ctk.CTkButton(btn_frame, text="Cancelar", command=dialog.destroy, width=100, fg_color="gray").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Confirmar", command=save, width=100).pack(side="left", padx=10)

        dialog.wait_window()
        return result[0]
