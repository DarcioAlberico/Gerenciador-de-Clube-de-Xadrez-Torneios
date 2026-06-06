from __future__ import annotations

from ..support import *

from .club_members_ui import ClubMembersMixin


class ClubPagesMixin(ClubMembersMixin):
    def show_club(self) -> None:
        self._clear_content()
        self._page_title(
            "Clubes, escolas e turmas",
            "Cadastre unidades, escolas parceiras e turmas vinculadas.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=292)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_club_id: dict[str, int | None] = {"value": None}
        selected_class_id: dict[str, int | None] = {"value": None}

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("name", "Nome"),
            ("city", "Cidade"),
            ("address", "Endereco"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(12, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=270)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(12, 0), sticky="w")
        kind_option = ctk.CTkOptionMenu(form, values=list(CLUB_KIND_VALUES.keys()), width=270)
        kind_option.grid(row=option_row + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
        active_check = ctk.CTkCheckBox(form, text="Ativo")
        active_check.grid(row=option_row + 2, column=0, padx=16, pady=(10, 2), sticky="w")
        active_check.select()

        right_panel = ctk.CTkScrollableFrame(body, fg_color="transparent", corner_radius=0)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1, minsize=118)
        right_panel.grid_rowconfigure(4, weight=1, minsize=118)

        summary_panel = self._make_panel(right_panel)
        summary_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(7):
            summary_panel.grid_columnconfigure(column, weight=1)
        dashboard = self.dashboard_service.overview()
        summary = dashboard["summary"]
        finance_summary = dashboard["finance_summary"]
        upcoming_events = dashboard["upcoming_events"]
        cards = [
            ("Unidades ativas", summary["active_clubs"]),
            ("Turmas ativas", summary["active_classes"]),
            ("Membros ativos", summary["active_members"]),
            ("Membros", summary["total_members"]),
            ("Torneios", summary["total_tournaments"]),
            ("Prox. eventos", len(upcoming_events)),
            ("Backups", dashboard["backups_count"]),
        ]
        for index, (label, value) in enumerate(cards):
            card = self._kpi_card(summary_panel, label, value)
            card.grid(row=0, column=index, padx=6, pady=8, sticky="ew")

        dashboard_panel = self._make_panel(right_panel)
        dashboard_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for column in range(4):
            dashboard_panel.grid_columnconfigure(column, weight=1)

        def add_dashboard_column(column: int, title: str, lines: list[str]) -> None:
            section = ctk.CTkFrame(dashboard_panel, fg_color="transparent")
            section.grid(row=0, column=column, padx=12, pady=8, sticky="nsew")
            self._section_title(section, title, subsection=True).pack(anchor="w")
            if not lines:
                lines = ["Sem registros"]
            for line in lines[:4]:
                ctk.CTkLabel(
                    section,
                    text=line,
                    text_color=THEME_TEXT_SUB,
                    wraplength=230,
                    justify="left",
                ).pack(anchor="w", pady=(2, 0))

        add_dashboard_column(
            0,
            "Proximos eventos",
            [
                f"{event['event_date'] or 'Sem data'} - {event['title']}"
                for event in upcoming_events
            ],
        )
        add_dashboard_column(
            1,
            "Financeiro",
            [
                f"Recebido: {finance_summary['paid_amount']:.2f}",
                f"Pendente: {finance_summary['pending_amount']:.2f}",
                f"Atrasado: {finance_summary['late_amount']:.2f}",
            ],
        )
        add_dashboard_column(
            2,
            "Ranking",
            [
                f"{item['position']}. {item['name']} ({item['rating']})"
                for item in dashboard["ranking_leaders"]
            ],
        )
        add_dashboard_column(
            3,
            "Torneios recentes",
            [
                f"{item['name']} - {item['status']}"
                for item in dashboard["recent_tournaments"]
            ],
        )

        club_holder = self._make_panel(right_panel)
        club_holder.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        club_holder.grid_columnconfigure(0, weight=1)
        club_holder.grid_rowconfigure(0, weight=1)
        club_tree = self._make_tree(
            club_holder,
            ["id", "name", "kind", "active", "members", "classes", "city"],
            {
                "id": "ID",
                "name": "Unidade",
                "kind": "Tipo",
                "active": "Ativo",
                "members": "Membros",
                "classes": "Turmas",
                "city": "Cidade",
            },
            {"id": 55, "name": 240, "kind": 90, "active": 70, "members": 75, "classes": 70, "city": 130},
            visible_rows=3,
        )

        class_section = self._make_panel(right_panel)
        class_section.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        for column in range(3):
            class_section.grid_columnconfigure(column, weight=1)
        class_entries: dict[str, ctk.CTkEntry] = {}
        class_fields = [
            ("name", "Turma", 160, 0, 0),
            ("teacher", "Professor", 150, 0, 1),
            ("weekday", "Dia", 90, 0, 2),
            ("time", "Horario", 90, 2, 0),
            ("location", "Local", 130, 2, 1),
        ]
        for key, label, width, row, column in class_fields:
            ctk.CTkLabel(class_section, text=label).grid(
                row=row,
                column=column,
                padx=(12 if column == 0 else 4, 4),
                pady=(10, 2),
                sticky="w",
            )
            entry = ctk.CTkEntry(class_section, width=width)
            entry.grid(
                row=row + 1,
                column=column,
                padx=(12 if column == 0 else 4, 4),
                pady=(0, 10),
                sticky="ew",
            )
            class_entries[key] = entry
        class_active_check = ctk.CTkCheckBox(class_section, text="Ativa")
        class_active_check.grid(row=3, column=2, padx=8, pady=(0, 10), sticky="w")
        class_active_check.select()
        class_actions = ctk.CTkFrame(class_section, fg_color="transparent")
        class_actions.grid(row=4, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="ew")
        class_actions.grid_columnconfigure(0, weight=1)
        class_actions.grid_columnconfigure(1, weight=1)

        class_holder = self._make_panel(right_panel)
        class_holder.grid(row=4, column=0, sticky="nsew")
        class_holder.grid_columnconfigure(0, weight=1)
        class_holder.grid_rowconfigure(0, weight=1)
        class_tree = self._make_tree(
            class_holder,
            ["id", "name", "teacher", "weekday", "time", "members", "active"],
            {
                "id": "ID",
                "name": "Turma",
                "teacher": "Professor",
                "weekday": "Dia",
                "time": "Horario",
                "members": "Alunos",
                "active": "Ativa",
            },
            {"id": 55, "name": 180, "teacher": 160, "weekday": 90, "time": 90, "members": 70, "active": 70},
            visible_rows=4,
        )

        def clear_club_form() -> None:
            selected_club_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            kind_option.set(CLUB_KIND_LABELS["club"])
            active_check.select()
            clear_class_form()

        def clear_class_form() -> None:
            selected_class_id["value"] = None
            for entry in class_entries.values():
                entry.delete(0, "end")
            class_active_check.select()

        def load_clubs() -> None:
            club_tree.delete(*club_tree.get_children())
            for club in self.db.list_clubs(active_only=False):
                club_tree.insert(
                    "",
                    "end",
                    values=(
                        club["id"],
                        club["name"],
                        CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", "")),
                        "Sim" if club.get("active") else "Nao",
                        club["members_count"],
                        club["active_classes_count"],
                        club["city"],
                    ),
                )

        def load_classes(club_id: int | None = None) -> None:
            class_tree.delete(*class_tree.get_children())
            if not club_id:
                return
            for item in self.db.list_classes(club_id=club_id, active_only=False):
                class_tree.insert(
                    "",
                    "end",
                    values=(
                        item["id"],
                        item["name"],
                        item["teacher"],
                        item["weekday"],
                        item["time"],
                        item["active_members_count"],
                        "Sim" if item["active"] else "Nao",
                    ),
                )

        def selected_club() -> dict[str, Any] | None:
            selected = club_tree.selection()
            if not selected:
                return None
            return self.db.get_club(int(club_tree.item(selected[0], "values")[0]))

        def on_club_select(_event: Any = None) -> None:
            club = selected_club()
            if not club:
                return
            selected_club_id["value"] = int(club["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(club.get(key) or ""))
            kind_option.set(CLUB_KIND_LABELS.get(club.get("kind", "club"), CLUB_KIND_LABELS["club"]))
            active_check.select() if club.get("active") else active_check.deselect()
            clear_class_form()
            load_classes(int(club["id"]))

        def on_class_select(_event: Any = None) -> None:
            selected = class_tree.selection()
            if not selected:
                return
            class_data = self.db.get_class(int(class_tree.item(selected[0], "values")[0]))
            if not class_data:
                return
            selected_class_id["value"] = int(class_data["id"])
            for key, entry in class_entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(class_data.get(key) or ""))
            class_active_check.select() if class_data.get("active") else class_active_check.deselect()

        def save_club() -> None:
            try:
                payload = {key: entry.get() for key, entry in entries.items()}
                payload["kind"] = CLUB_KIND_VALUES[kind_option.get()]
                payload["active"] = active_check.get()
                saved_id = self.club_service.save_profile(payload, selected_club_id["value"])
                selected_club_id["value"] = saved_id
                load_clubs()
                load_classes(saved_id)
                self._show_toast("Unidade salva.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def save_class() -> None:
            try:
                club_id = selected_club_id["value"]
                if not club_id:
                    raise AppError("Selecione uma unidade para cadastrar a turma.")
                payload = {key: entry.get() for key, entry in class_entries.items()}
                payload["club_id"] = club_id
                payload["active"] = class_active_check.get()
                self.club_service.save_class(payload, selected_class_id["value"])
                clear_class_form()
                load_classes(club_id)
                load_clubs()
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(form, text="Nova unidade", command=clear_club_form).grid(
            row=option_row + 3,
            column=0,
            padx=16,
            pady=(16, 4),
            sticky="ew",
        )
        ctk.CTkButton(form, text="Salvar unidade", command=save_club).grid(
            row=option_row + 4,
            column=0,
            padx=16,
            pady=4,
            sticky="ew",
        )
        ctk.CTkButton(form, text="Gerenciar membros", command=self.show_members).grid(
            row=option_row + 5,
            column=0,
            padx=16,
            pady=4,
            sticky="ew",
        )
        ctk.CTkButton(class_actions, text="Nova turma", command=clear_class_form).grid(
            row=0,
            column=0,
            padx=(0, 4),
            sticky="ew",
        )
        ctk.CTkButton(class_actions, text="Salvar turma", command=save_class).grid(
            row=0,
            column=1,
            padx=(4, 0),
            sticky="ew",
        )
        def jump_to_members() -> None:
            if not selected_class_id["value"]:
                self._show_error(AppError("Selecione uma turma primeiro."))
                return
            self.show_members(initial_class_id=selected_class_id["value"])

        ctk.CTkButton(class_actions, text="Lista de alunos", fg_color=THEME_ACCENT, command=jump_to_members).grid(
            row=1,
            column=0,
            columnspan=2,
            padx=0,
            pady=(8, 0),
            sticky="ew",
        )

        club_tree.bind("<<TreeviewSelect>>", on_club_select)
        class_tree.bind("<<TreeviewSelect>>", on_class_select)
        clear_club_form()
        load_clubs()
        first_club = self.db.list_clubs(active_only=False)
        if first_club:
            selected_club_id["value"] = int(first_club[0]["id"])
            load_classes(selected_club_id["value"])

    def show_learning_levels(self) -> None:
        self._clear_content()
        self._page_title(
            "Niveis de aprendizagem",
            "Cadastre os niveis usados para acompanhar a evolucao dos alunos.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_panel(body)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        form.grid_columnconfigure(0, weight=1)

        selected_level_id: dict[str, int | None] = {"value": None}
        name_entry = ctk.CTkEntry(form, width=270)
        order_entry = ctk.CTkEntry(form, width=270)
        description_entry = ctk.CTkEntry(form, width=270)
        active_check = ctk.CTkCheckBox(form, text="Ativo")
        active_check.select()

        ctk.CTkLabel(form, text="Nivel").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        name_entry.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(form, text="Ordem").grid(row=2, column=0, padx=16, pady=(8, 4), sticky="w")
        order_entry.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(form, text="Descricao").grid(row=4, column=0, padx=16, pady=(8, 4), sticky="w")
        description_entry.grid(row=5, column=0, padx=16, pady=(0, 8), sticky="ew")
        active_check.grid(row=6, column=0, padx=16, pady=(8, 12), sticky="w")

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            list_panel,
            ["id", "order", "name", "description", "members", "active"],
            {
                "id": "ID",
                "order": "Ordem",
                "name": "Nivel",
                "description": "Descricao",
                "members": "Alunos",
                "active": "Ativo",
            },
            {
                "id": 55,
                "order": 70,
                "name": 180,
                "description": 420,
                "members": 75,
                "active": 70,
            },
        )
        tree.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        def clear_form() -> None:
            selected_level_id["value"] = None
            name_entry.delete(0, "end")
            order_entry.delete(0, "end")
            description_entry.delete(0, "end")
            active_check.select()

        def load_levels() -> None:
            tree.delete(*tree.get_children())
            for level in self.db.list_learning_levels(active_only=False):
                tree.insert(
                    "",
                    "end",
                    values=(
                        level["id"],
                        level["display_order"],
                        level["name"],
                        level.get("description") or "",
                        level.get("members_count", 0),
                        "Sim" if level.get("active") else "Nao",
                    ),
                )

        def payload() -> dict[str, Any]:
            return {
                "name": name_entry.get(),
                "display_order": order_entry.get(),
                "description": description_entry.get(),
                "active": active_check.get(),
            }

        def selected_level() -> dict[str, Any] | None:
            selected = tree.selection()
            if not selected:
                return None
            level_id = int(tree.item(selected[0], "values")[0])
            return self.db.get_learning_level(level_id)

        def on_select(_event: Any = None) -> None:
            level = selected_level()
            if not level:
                return
            selected_level_id["value"] = int(level["id"])
            name_entry.delete(0, "end")
            name_entry.insert(0, str(level.get("name") or ""))
            order_entry.delete(0, "end")
            order_entry.insert(0, str(level.get("display_order") or 0))
            description_entry.delete(0, "end")
            description_entry.insert(0, str(level.get("description") or ""))
            active_check.select() if level.get("active") else active_check.deselect()

        def save_level() -> None:
            try:
                if selected_level_id["value"]:
                    self.learning_level_service.update_level(selected_level_id["value"], payload())
                else:
                    self.learning_level_service.create_level(payload())
                clear_form()
                load_levels()
            except Exception as exc:
                self._show_error(exc)

        def toggle_level() -> None:
            try:
                level = selected_level()
                if not level:
                    raise AppError("Selecione um nivel.")
                self.learning_level_service.toggle_level_active(int(level["id"]))
                clear_form()
                load_levels()
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Novo nivel", clear_form),
            ("Salvar nivel", save_level),
            ("Ativar/Inativar", toggle_level),
        ]
        self._grid_form_buttons(form, buttons, 7)

        tree.bind("<<TreeviewSelect>>", on_select)
        load_levels()

    def show_guardians(self) -> None:
        self._clear_content()
        self._page_title(
            "Responsaveis",
            "Cadastre contatos responsaveis e vincule-os aos alunos do clube.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("name", "Nome"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("document", "Documento"),
            ("address", "Endereco"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        selected_guardian_id: dict[str, int | None] = {"value": None}
        guardian_member_map: dict[str, int] = {}
        member_option_map: dict[str, int] = {}

        active_check = ctk.CTkCheckBox(form, text="Ativo")
        active_check.grid(row=len(fields) * 2, column=0, padx=16, pady=(10, 2), sticky="w")
        active_check.select()

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=2)
        right_panel.grid_rowconfigure(3, weight=1)
        right_panel.grid_rowconfigure(5, weight=1)

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por nome, telefone, e-mail ou documento")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        active_filter = ctk.CTkOptionMenu(controls, values=["Todos", "Ativos", "Inativos"], width=130)
        active_filter.grid(row=0, column=1)

        guardian_holder = self._make_panel(right_panel)
        guardian_holder.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        guardian_holder.grid_columnconfigure(0, weight=1)
        guardian_holder.grid_rowconfigure(0, weight=1)
        guardian_tree = self._make_tree(
            guardian_holder,
            ["id", "name", "phone", "email", "members", "active"],
            {
                "id": "ID",
                "name": "Responsavel",
                "phone": "Telefone",
                "email": "E-mail",
                "members": "Membros",
                "active": "Ativo",
            },
            {"id": 55, "name": 260, "phone": 130, "email": 220, "members": 80, "active": 70},
        )

        link_panel = self._make_panel(right_panel)
        link_panel.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        link_panel.grid_columnconfigure(0, weight=1)
        link_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(link_panel, text="Membro").grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        member_option = ctk.CTkOptionMenu(link_panel, values=["Sem membros"], width=280)
        member_option.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(link_panel, text="Parentesco").grid(row=0, column=1, padx=8, pady=(10, 2), sticky="w")
        relationship_entry = ctk.CTkEntry(link_panel, width=180)
        relationship_entry.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(link_panel, text="Obs. vinculo").grid(row=0, column=2, padx=8, pady=(10, 2), sticky="w")
        link_notes_entry = ctk.CTkEntry(link_panel, width=170)
        link_notes_entry.grid(row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

        primary_check = ctk.CTkCheckBox(link_panel, text="Principal")
        primary_check.grid(row=1, column=3, padx=8, pady=(0, 10), sticky="w")
        emergency_check = ctk.CTkCheckBox(link_panel, text="Emergencia")
        emergency_check.grid(row=1, column=4, padx=8, pady=(0, 10), sticky="w")

        linked_holder = self._make_panel(right_panel)
        linked_holder.grid(row=3, column=0, sticky="nsew", pady=(0, 12))
        linked_holder.grid_columnconfigure(0, weight=1)
        linked_holder.grid_rowconfigure(0, weight=1)
        linked_tree = self._make_tree(
            linked_holder,
            ["id", "member", "relationship", "primary", "emergency", "phone", "club", "class", "status"],
            {
                "id": "ID",
                "member": "Membro vinculado",
                "relationship": "Parentesco",
                "primary": "Principal",
                "emergency": "Emerg.",
                "phone": "Telefone",
                "club": "Clube/Escola",
                "class": "Turma",
                "status": "Status",
            },
            {
                "id": 55,
                "member": 210,
                "relationship": 110,
                "primary": 75,
                "emergency": 75,
                "phone": 120,
                "club": 150,
                "class": 120,
                "status": 80,
            },
        )

        minors_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        minors_header.grid(row=4, column=0, sticky="ew")
        minors_header.grid_columnconfigure(0, weight=1)
        self._section_title(minors_header, "Alunos menores sem responsavel").grid(
            row=0, column=0, sticky="w"
        )

        minors_holder = self._make_panel(right_panel)
        minors_holder.grid(row=5, column=0, sticky="nsew")
        minors_holder.grid_columnconfigure(0, weight=1)
        minors_holder.grid_rowconfigure(0, weight=1)
        minors_tree = self._make_tree(
            minors_holder,
            ["id", "name", "birth_date", "phone", "club", "class"],
            {
                "id": "ID",
                "name": "Aluno",
                "birth_date": "Nascimento",
                "phone": "Telefone",
                "club": "Clube/Escola",
                "class": "Turma",
            },
            {"id": 55, "name": 220, "birth_date": 105, "phone": 120, "club": 170, "class": 140},
        )

        def guardian_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["active"] = active_check.get()
            return payload

        def clear_form() -> None:
            selected_guardian_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            active_check.select()
            linked_tree.delete(*linked_tree.get_children())
            relationship_entry.delete(0, "end")
            link_notes_entry.delete(0, "end")
            primary_check.deselect()
            emergency_check.deselect()

        def load_member_options() -> None:
            member_option_map.clear()
            values = []
            for member in self.db.list_members(active_only=False):
                club_name = member.get("club_name") or ""
                label = f"{member['id']} - {self._member_display_name(member)} ({club_name})"
                values.append(label)
                member_option_map[label] = int(member["id"])
            if not values:
                values = ["Sem membros"]
            member_option.configure(values=values)
            member_option.set(values[0])

        def load_guardians() -> None:
            guardian_tree.delete(*guardian_tree.get_children())
            query = search_entry.get().strip().casefold()
            filter_value = active_filter.get()
            for guardian in self.db.list_guardians(active_only=False):
                if filter_value == "Ativos" and not guardian.get("active"):
                    continue
                if filter_value == "Inativos" and guardian.get("active"):
                    continue
                searchable = " ".join(
                    [
                        str(guardian.get("name") or ""),
                        str(guardian.get("phone") or ""),
                        str(guardian.get("email") or ""),
                        str(guardian.get("document") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                guardian_tree.insert(
                    "",
                    "end",
                    values=(
                        guardian["id"],
                        guardian["name"],
                        guardian["phone"],
                        guardian["email"],
                        guardian["members_count"],
                        "Sim" if guardian.get("active") else "Nao",
                    ),
                )

        def load_linked_members(guardian_id: int | None = None) -> None:
            linked_tree.delete(*linked_tree.get_children())
            guardian_member_map.clear()
            if not guardian_id:
                return
            for item in self.db.list_guardian_members(guardian_id):
                row_id = linked_tree.insert(
                    "",
                    "end",
                    values=(
                        item["member_id"],
                        item["member_name"],
                        item["relationship"],
                        "Sim" if item.get("primary_contact") else "Nao",
                        "Sim" if item.get("emergency_contact") else "Nao",
                        item.get("member_phone") or "",
                        item.get("club_name") or "",
                        item.get("active_class_name") or "",
                        MEMBER_STATUS_LABELS.get(item["member_status"], item["member_status"]),
                    ),
                )
                guardian_member_map[row_id] = int(item["member_id"])

        def load_missing_minors() -> None:
            minors_tree.delete(*minors_tree.get_children())
            for member in self.guardian_service.minor_members_without_guardians():
                minors_tree.insert(
                    "",
                    "end",
                    values=(
                        member["id"],
                        member["name"],
                        member["birth_date"],
                        member["phone"],
                        member.get("club_name") or "",
                        member.get("active_class_name") or "",
                    ),
                )

        def selected_guardian() -> dict[str, Any] | None:
            selected = guardian_tree.selection()
            if not selected:
                return None
            guardian_id = int(guardian_tree.item(selected[0], "values")[0])
            return self.db.get_guardian(guardian_id)

        def select_guardian_in_tree(guardian_id: int) -> None:
            for item_id in guardian_tree.get_children():
                values = guardian_tree.item(item_id, "values")
                if values and int(values[0]) == guardian_id:
                    guardian_tree.selection_set(item_id)
                    guardian_tree.see(item_id)
                    on_select()
                    return

        def on_select(_event: Any = None) -> None:
            guardian = selected_guardian()
            if not guardian:
                return
            selected_guardian_id["value"] = int(guardian["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(guardian.get(key) or ""))
            active_check.select() if guardian.get("active") else active_check.deselect()
            load_linked_members(int(guardian["id"]))

        def add_guardian() -> None:
            try:
                guardian_id = self.guardian_service.create_guardian(guardian_payload())
                clear_form()
                load_guardians()
                select_guardian_in_tree(guardian_id)
                load_member_options()
            except Exception as exc:
                self._show_error(exc)

        def update_guardian() -> None:
            try:
                guardian_id = selected_guardian_id["value"]
                if not guardian_id:
                    raise AppError("Selecione um responsavel.")
                self.guardian_service.update_guardian(guardian_id, guardian_payload())
                load_guardians()
                select_guardian_in_tree(guardian_id)
            except Exception as exc:
                self._show_error(exc)

        def toggle_guardian() -> None:
            try:
                guardian = selected_guardian()
                if not guardian:
                    raise AppError("Selecione um responsavel.")
                self.guardian_service.toggle_guardian_active(int(guardian["id"]))
                clear_form()
                load_guardians()
            except Exception as exc:
                self._show_error(exc)

        def link_guardian() -> None:
            try:
                guardian_id = selected_guardian_id["value"]
                if not guardian_id:
                    raise AppError("Selecione um responsavel.")
                member_id = member_option_map.get(member_option.get())
                if not member_id:
                    raise AppError("Selecione um membro.")
                self.guardian_service.link_guardian_to_member(
                    {
                        "guardian_id": guardian_id,
                        "member_id": member_id,
                        "relationship": relationship_entry.get(),
                        "primary_contact": primary_check.get(),
                        "emergency_contact": emergency_check.get(),
                        "notes": link_notes_entry.get(),
                    }
                )
                relationship_entry.delete(0, "end")
                link_notes_entry.delete(0, "end")
                primary_check.deselect()
                emergency_check.deselect()
                load_linked_members(guardian_id)
                load_guardians()
                load_missing_minors()
            except Exception as exc:
                self._show_error(exc)

        def unlink_guardian() -> None:
            try:
                guardian_id = selected_guardian_id["value"]
                selected = linked_tree.selection()
                if not guardian_id or not selected:
                    raise AppError("Selecione um vinculo.")
                member_id = guardian_member_map.get(selected[0])
                if not member_id:
                    raise AppError("Selecione um vinculo valido.")
                self.guardian_service.unlink_guardian_from_member(member_id, guardian_id)
                load_linked_members(guardian_id)
                load_guardians()
                load_missing_minors()
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Novo", clear_form),
            ("Adicionar", add_guardian),
            ("Atualizar", update_guardian),
            ("Ativar/Inativar", toggle_guardian),
            ("Vincular membro", link_guardian),
            ("Remover vinculo", unlink_guardian),
        ]
        self._grid_form_buttons(form, buttons, len(fields) * 2 + 1)

        guardian_tree.bind("<<TreeviewSelect>>", on_select)
        search_entry.bind("<KeyRelease>", lambda _event: load_guardians())
        active_filter.configure(command=lambda _value: load_guardians())

        clear_form()
        active_filter.set("Todos")
        load_member_options()
        load_guardians()
        load_missing_minors()


