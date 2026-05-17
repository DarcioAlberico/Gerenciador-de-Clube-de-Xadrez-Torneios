from __future__ import annotations

from .ui_support import *


class ClubPagesMixin:
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
            card = ctk.CTkFrame(summary_panel, fg_color="#F8FAFC", corner_radius=8)
            card.grid(row=0, column=index, padx=6, pady=8, sticky="ew")
            ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=18, weight="bold")).pack(
                anchor="w",
                padx=10,
                pady=(8, 0),
            )
            ctk.CTkLabel(card, text=label, text_color="#64748B").pack(anchor="w", padx=10, pady=(0, 8))

        dashboard_panel = self._make_panel(right_panel)
        dashboard_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for column in range(4):
            dashboard_panel.grid_columnconfigure(column, weight=1)

        def add_dashboard_column(column: int, title: str, lines: list[str]) -> None:
            section = ctk.CTkFrame(dashboard_panel, fg_color="transparent")
            section.grid(row=0, column=column, padx=12, pady=8, sticky="nsew")
            ctk.CTkLabel(
                section,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#0F172A",
            ).pack(anchor="w")
            if not lines:
                lines = ["Sem registros"]
            for line in lines[:4]:
                ctk.CTkLabel(
                    section,
                    text=line,
                    text_color="#475569",
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
                self._show_info("Unidade salva.")
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

    def show_members(self) -> None:
        self._clear_content()
        self._page_title(
            "Membros",
            "Cadastre socios, alunos, visitantes e convidados do clube.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=292)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("name", "Nome"),
            ("surname", "Sobrenome"),
            ("rating", "Rating"),
            ("category", "Categoria"),
            ("city", "Cidade"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("document", "Documento"),
            ("birth_date", "Nascimento"),
            ("guardian_name", "Responsavel"),
            ("guardian_phone", "Telefone resp."),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=250)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        member_type_option = ctk.CTkOptionMenu(form, values=list(MEMBER_TYPE_VALUES.keys()), width=250)
        member_type_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Status").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        status_option = ctk.CTkOptionMenu(form, values=list(MEMBER_STATUS_VALUES.keys()), width=250)
        status_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        club_option = ctk.CTkOptionMenu(form, values=[""], width=250)
        club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Turma").grid(row=option_row + 6, column=0, padx=16, pady=(8, 0), sticky="w")
        class_option = ctk.CTkOptionMenu(form, values=["Sem turma"], width=250)
        class_option.grid(row=option_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Nivel de aprendizagem").grid(
            row=option_row + 8,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        learning_level_option = ctk.CTkOptionMenu(form, values=["Sem nivel"], width=250)
        learning_level_option.grid(row=option_row + 9, column=0, padx=16, pady=(2, 0), sticky="ew")

        selected_member_id: dict[str, int | None] = {"value": None}
        club_option_map: dict[str, int] = {}
        class_option_map: dict[str, int | None] = {"Sem turma": None}
        class_filter_map: dict[str, int] = {}
        learning_level_option_map: dict[str, int | None] = {"Sem nivel": None}
        learning_level_filter_map: dict[str, int] = {}

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(1, weight=2)
        list_panel.grid_rowconfigure(3, weight=1)

        controls = ctk.CTkFrame(list_panel, fg_color="transparent")
        controls.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por nome, telefone, e-mail ou categoria")
        search_entry.grid(row=0, column=0, columnspan=2, pady=(0, 8), sticky="ew")

        type_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos os tipos"] + list(MEMBER_TYPE_VALUES.keys()),
            width=150,
        )
        type_filter.grid(row=1, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")

        status_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos os status"] + list(MEMBER_STATUS_VALUES.keys()),
            width=150,
        )
        status_filter.grid(row=1, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")

        category_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todas as categorias"],
            width=170,
        )
        category_filter.grid(row=2, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")

        club_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos clubes"],
            width=180,
        )
        club_filter.grid(row=2, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")

        class_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todas turmas"],
            width=170,
        )
        class_filter.grid(row=3, column=0, columnspan=2, sticky="ew")

        learning_level_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos niveis"],
            width=170,
        )
        learning_level_filter.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        tree_holder = ctk.CTkFrame(list_panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            tree_holder,
            [
                "id",
                "name",
                "surname",
                "club",
                "class",
                "learning_level",
                "type",
                "status",
                "rating",
                "category",
                "age_category",
                "rating_category",
                "tags",
                "phone",
                "email",
            ],
            {
                "id": "ID",
                "name": "Nome",
                "surname": "Sobrenome",
                "club": "Clube/Escola",
                "class": "Turma",
                "learning_level": "Nivel",
                "type": "Tipo",
                "status": "Status",
                "rating": "Rating",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "phone": "Telefone",
                "email": "E-mail",
            },
            {
                "id": 55,
                "name": 170,
                "surname": 150,
                "club": 160,
                "class": 140,
                "learning_level": 140,
                "type": 90,
                "status": 80,
                "rating": 70,
                "category": 110,
                "age_category": 85,
                "rating_category": 95,
                "tags": 150,
                "phone": 120,
                "email": 180,
            },
        )

        history_header = ctk.CTkFrame(list_panel, fg_color="transparent")
        history_header.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
        history_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            history_header,
            text="Historico de torneios do membro selecionado",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#0F172A",
        ).grid(row=0, column=0, sticky="w")

        history_holder = ctk.CTkFrame(list_panel, fg_color="transparent")
        history_holder.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        history_holder.grid_columnconfigure(0, weight=1)
        history_holder.grid_rowconfigure(0, weight=1)
        history_tree = self._make_tree(
            history_holder,
            ["tournament", "status", "points", "position", "rounds", "record", "last"],
            {
                "tournament": "Torneio",
                "status": "Status",
                "points": "Pts",
                "position": "Pos",
                "rounds": "Rodadas",
                "record": "V/E/D/B",
                "last": "Ultimo",
            },
            {
                "tournament": 260,
                "status": 90,
                "points": 60,
                "position": 55,
                "rounds": 75,
                "record": 90,
                "last": 90,
            },
        )
        history_tournament_map: dict[str, int] = {}

        def club_label(club: dict[str, Any]) -> str:
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            return f"{club['id']} - {club['name']} ({kind})"

        def load_club_options(selected_id: int | None = None) -> None:
            club_option_map.clear()
            values = []
            for club in self.db.list_clubs(active_only=True):
                label = club_label(club)
                values.append(label)
                club_option_map[label] = int(club["id"])
            if not values:
                values = ["1 - Clube padrao (Clube)"]
                club_option_map[values[0]] = 1
            club_option.configure(values=values)
            chosen = next(
                (label for label, club_id in club_option_map.items() if club_id == selected_id),
                values[0],
            )
            club_option.set(chosen)
            load_class_options(club_option_map[chosen], None)

            filter_values = ["Todos clubes"] + values
            current_filter = club_filter.get()
            club_filter.configure(values=filter_values)
            club_filter.set(current_filter if current_filter in filter_values else "Todos clubes")
            load_class_filter_options()

        def load_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            class_option_map.clear()
            class_option_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    class_option_map[label] = int(class_data["id"])
            class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in class_option_map.items() if class_id == selected_id),
                "Sem turma",
            )
            class_option.set(chosen)

        def load_class_filter_options(club_id: int | None = None) -> None:
            class_filter_map.clear()
            values = ["Todas turmas"]
            for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                label = f"{class_data['id']} - {class_data['name']}"
                values.append(label)
                class_filter_map[label] = int(class_data["id"])
            current_filter = class_filter.get()
            class_filter.configure(values=values)
            class_filter.set(current_filter if current_filter in values else "Todas turmas")

        def load_learning_level_options(selected_id: int | None = None) -> None:
            learning_level_option_map.clear()
            learning_level_option_map["Sem nivel"] = None
            values = ["Sem nivel"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                learning_level_option_map[label] = int(level["id"])
            learning_level_option.configure(values=values)
            chosen = next(
                (label for label, level_id in learning_level_option_map.items() if level_id == selected_id),
                "Sem nivel",
            )
            learning_level_option.set(chosen)

        def load_learning_level_filter_options() -> None:
            learning_level_filter_map.clear()
            values = ["Todos niveis"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                learning_level_filter_map[label] = int(level["id"])
            current_filter = learning_level_filter.get()
            learning_level_filter.configure(values=values)
            learning_level_filter.set(current_filter if current_filter in values else "Todos niveis")

        def on_club_option_change(_value: str) -> None:
            load_class_options(club_option_map.get(club_option.get()), None)

        def member_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["member_type"] = MEMBER_TYPE_VALUES[member_type_option.get()]
            payload["status"] = MEMBER_STATUS_VALUES[status_option.get()]
            payload["club_id"] = club_option_map.get(club_option.get(), 1)
            payload["class_id"] = class_option_map.get(class_option.get())
            payload["learning_level_id"] = learning_level_option_map.get(learning_level_option.get())
            return payload

        def load_member_history(member_id: int | None = None) -> None:
            history_tree.delete(*history_tree.get_children())
            history_tournament_map.clear()
            if not member_id:
                return
            for item in self.member_service.tournament_history(member_id):
                record = f"{item['wins']}/{item['draws']}/{item['losses']}/{item['byes']}"
                row_id = history_tree.insert(
                    "",
                    "end",
                    values=(
                        item["name"],
                        item["status"],
                        item["points"],
                        item["position"],
                        item["rounds_played"],
                        record,
                        item["last_result"],
                    ),
                )
                history_tournament_map[row_id] = int(item["tournament_id"])

        def show_history_details(_event: Any = None) -> None:
            member_id = selected_member_id["value"]
            selected = history_tree.selection()
            if not member_id or not selected:
                return
            tournament_id = history_tournament_map.get(selected[0])
            if not tournament_id:
                return
            results = self.member_service.tournament_results(member_id, tournament_id)
            if not results:
                self._show_info("Este membro ainda nao possui resultados neste torneio.")
                return
            lines = []
            for result in results:
                points = "" if result["points"] is None else f"{result['points']:g} pt"
                raw_result = result["result"] or "Pendente"
                lines.append(
                    "Rodada {round_number}, mesa {board_number}: {color} x {opponent} - "
                    "{result} ({outcome}{points})".format(
                        round_number=result["round_number"],
                        board_number=result["board_number"],
                        color=result["color"],
                        opponent=result["opponent"],
                        result=raw_result,
                        outcome=result["outcome"],
                        points=f", {points}" if points else "",
                    )
                )
            self._show_info("\n".join(lines))

        def clear_form() -> None:
            selected_member_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            member_type_option.set(MEMBER_TYPE_LABELS["socio"])
            status_option.set(MEMBER_STATUS_LABELS["active"])
            load_club_options()
            load_learning_level_options()
            load_member_history()

        def load_members() -> None:
            tree.delete(*tree.get_children())
            query = search_entry.get().strip().casefold()
            type_value = type_filter.get()
            status_value = status_filter.get()
            category_value = category_filter.get()
            club_value = club_filter.get()
            class_value = class_filter.get()
            learning_level_value = learning_level_filter.get()
            for member in self.db.list_members(active_only=False):
                if type_value != "Todos os tipos" and member["member_type"] != MEMBER_TYPE_VALUES[type_value]:
                    continue
                if status_value != "Todos os status" and member["status"] != MEMBER_STATUS_VALUES[status_value]:
                    continue
                if category_value != "Todas as categorias" and member["category"] != category_value:
                    continue
                if club_value != "Todos clubes" and member.get("club_id") != club_option_map.get(club_value):
                    continue
                if class_value != "Todas turmas" and member.get("active_class_id") != class_filter_map.get(class_value):
                    continue
                if (
                    learning_level_value != "Todos niveis"
                    and member.get("learning_level_id") != learning_level_filter_map.get(learning_level_value)
                ):
                    continue
                searchable = " ".join(
                    [
                        str(member["name"] or ""),
                        str(member.get("surname") or ""),
                        str(member.get("club_name") or ""),
                        str(member.get("active_class_name") or ""),
                        str(member.get("learning_level_name") or ""),
                        str(member["phone"] or ""),
                        str(member["email"] or ""),
                        str(member["category"] or ""),
                        str(member.get("age_category") or ""),
                        str(member.get("rating_category") or ""),
                        str(member.get("prize_tags") or ""),
                        str(member["member_type"] or ""),
                        str(member["status"] or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                tree.insert(
                    "",
                    "end",
                    values=(
                        member["id"],
                        member["name"],
                        member.get("surname") or "",
                        member.get("club_name") or "",
                        member.get("active_class_name") or "",
                        member.get("learning_level_name") or "",
                        MEMBER_TYPE_LABELS.get(member["member_type"], member["member_type"]),
                        MEMBER_STATUS_LABELS.get(member["status"], member["status"]),
                        member["rating"],
                        member["category"],
                        member.get("age_category", ""),
                        member.get("rating_category", ""),
                        member.get("prize_tags", ""),
                        member["phone"],
                        member["email"],
                    ),
                )

        def load_category_filter() -> None:
            selected = category_filter.get()
            categories = sorted(
                {
                    str(member["category"]).strip()
                    for member in self.db.list_members(active_only=False)
                    if str(member["category"]).strip()
                }
            )
            values = ["Todas as categorias"] + categories
            category_filter.configure(values=values)
            category_filter.set(selected if selected in values else "Todas as categorias")

        def selected_member() -> dict[str, Any] | None:
            selected = tree.selection()
            if not selected:
                return None
            member_id = int(tree.item(selected[0], "values")[0])
            return self.db.get_member(member_id)

        def show_rating_history() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                history = self.internal_rating_service.member_rating_history(int(member["id"]))
                if not history:
                    self._show_info("Este membro ainda nao possui historico de rating interno.")
                    return
                lines = []
                for item in history:
                    old_rating = int(item["old_rating"] or 0)
                    new_rating = int(item["new_rating"] or 0)
                    delta = new_rating - old_rating
                    sign = "+" if delta >= 0 else ""
                    tournament_name = item.get("tournament_name") or "Torneio removido"
                    lines.append(
                        "{created_at} - {tournament}: {old} -> {new} ({sign}{delta}), "
                        "perf. {performance}, {games} partidas, {points:g} pts".format(
                            created_at=item["created_at"],
                            tournament=tournament_name,
                            old=old_rating,
                            new=new_rating,
                            sign=sign,
                            delta=delta,
                            performance=item["performance"],
                            games=item["games"],
                            points=float(item["points"] or 0.0),
                        )
                    )
                self._show_info("\n".join(lines))
            except Exception as exc:
                self._show_error(exc)

        def export_evolution() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                safe_name = self._safe_filename(str(member["name"]), "membro")
                file_path = filedialog.asksaveasfilename(
                    title="Exportar evolucao do membro",
                    initialdir=str(self._default_export_dir()),
                    initialfile=f"{safe_name}_evolucao.xlsx",
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
                member_id = int(member["id"])
                self._run_background(
                    lambda: self.export_service.export_member_evolution(member_id, path),
                    lambda _result: self._show_info(f"Relatorio exportado:\n{path}"),
                    "Exportando evolucao do membro...",
                )
            except Exception as exc:
                self._show_error(exc)

        def on_select(_event: Any = None) -> None:
            member = selected_member()
            if not member:
                return
            selected_member_id["value"] = member["id"]
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(member.get(key) or ""))
            member_type_option.set(MEMBER_TYPE_LABELS.get(member["member_type"], MEMBER_TYPE_LABELS["socio"]))
            status_option.set(MEMBER_STATUS_LABELS.get(member["status"], MEMBER_STATUS_LABELS["active"]))
            load_club_options(int(member.get("club_id") or 1))
            load_class_options(int(member.get("club_id") or 1), member.get("active_class_id"))
            load_learning_level_options(member.get("learning_level_id"))
            load_member_history(member["id"])

        def add_member() -> None:
            try:
                self.member_service.create_member(member_payload())
                clear_form()
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        def update_member() -> None:
            try:
                member_id = selected_member_id["value"]
                if not member_id:
                    raise AppError("Selecione um membro.")
                self.member_service.update_member(member_id, member_payload())
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        def toggle_member() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                self.member_service.toggle_member_status(member["id"])
                clear_form()
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        tree.bind("<<TreeviewSelect>>", on_select)
        history_tree.bind("<Double-1>", show_history_details)
        search_entry.bind("<KeyRelease>", lambda _event: load_members())
        type_filter.configure(command=lambda _value: load_members())
        status_filter.configure(command=lambda _value: load_members())
        category_filter.configure(command=lambda _value: load_members())
        club_filter.configure(command=lambda _value: load_members())
        class_filter.configure(command=lambda _value: load_members())
        learning_level_filter.configure(command=lambda _value: load_members())
        club_option.configure(command=on_club_option_change)

        def import_ratings() -> None:
            file_path = filedialog.askopenfilename(
                title="Importar lista de Rating",
                initialdir=str(self._default_export_dir()),
                filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return

            dialog = ctk.CTkToplevel(self)
            dialog.title("Tipo de Rating")
            dialog.geometry("320x150")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Selecione o tipo de rating do arquivo CSV:").pack(pady=(20, 10))
            
            def do_import(rating_type: str) -> None:
                dialog.destroy()
                try:
                    result = self.import_service.import_rating_list_csv(file_path, rating_type)
                    msg = (
                        f"Importacao de rating ({rating_type.upper()}) concluida.\n"
                        f"Membros atualizados: {result['updated']}\n"
                        f"Linhas ignoradas: {result['skipped']}\n"
                        f"Erros encontrados: {len(result['errors'])}"
                    )
                    self._show_info(msg)
                    if result['errors']:
                        logger.warning("Erros na importacao de rating: %s", result['errors'])
                    load_members()
                except Exception as exc:
                    self._show_error(exc)

            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack(pady=10)
            ctk.CTkButton(btn_frame, text="FIDE", command=lambda: do_import("fide"), width=100).pack(side="left", padx=10)
            ctk.CTkButton(btn_frame, text="CBX", command=lambda: do_import("cbx"), width=100).pack(side="left", padx=10)

        buttons = [
            ("Adicionar", add_member),
            ("Atualizar", update_member),
            ("Ativar/Inativar", toggle_member),
            ("Hist. rating", show_rating_history),
            ("Exportar evolucao", export_evolution),
            ("Importar Ratings", import_ratings),
            ("Limpar", clear_form),
        ]
        self._grid_form_buttons(form, buttons, option_row + 10)

        clear_form()
        type_filter.set("Todos os tipos")
        status_filter.set("Todos os status")
        load_category_filter()
        load_learning_level_filter_options()
        load_members()

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
        ctk.CTkLabel(
            minors_header,
            text="Alunos menores sem responsavel",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#0F172A",
        ).grid(row=0, column=0, sticky="w")

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


