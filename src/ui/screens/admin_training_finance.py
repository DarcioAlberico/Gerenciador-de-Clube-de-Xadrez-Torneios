from __future__ import annotations

from ..support import *
from ..components import danger_button, debounce


# Sub-mixin de Admin: treinos e financeiro.
class TrainingFinanceMixin:
    def show_training(self) -> None:
        self._clear_content()
        self._page_title(
            "Aulas e presencas",
            "Cadastre aulas, treinos e chamadas por turma ou clube.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("title", "Título"),
            ("session_date", "Data"),
            ("start_time", "Inicio"),
            ("end_time", "Fim"),
            ("instructor", "Instrutor"),
            ("location", "Local"),
            ("objective", "Objetivo"),
            ("content", "Conteudo"),
            ("homework", "Tarefa"),
            ("notes", "Observações"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            if key == "session_date":
                entry = self._make_date_entry(form, width=30)
            else:
                entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=list(TRAINING_TYPE_VALUES.keys()), width=260)
        type_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Status").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        status_option = ctk.CTkOptionMenu(form, values=list(TRAINING_STATUS_VALUES.keys()), width=260)
        status_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        club_option = ctk.CTkOptionMenu(form, values=[""], width=260)
        club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Turma").grid(row=option_row + 6, column=0, padx=16, pady=(8, 0), sticky="w")
        class_option = ctk.CTkOptionMenu(form, values=["Sem turma"], width=260)
        class_option.grid(row=option_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Nível pedagogico").grid(
            row=option_row + 8,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        level_option = ctk.CTkOptionMenu(form, values=["Sem nivel"], width=260)
        level_option.grid(row=option_row + 9, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Lista de treino").grid(
            row=option_row + 10,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        training_list_option = ctk.CTkOptionMenu(form, values=["Sem lista"], width=260)
        training_list_option.grid(row=option_row + 11, column=0, padx=16, pady=(2, 0), sticky="ew")

        selected_session_id: dict[str, int | None] = {"value": None}
        club_option_map: dict[str, int] = {}
        class_option_map: dict[str, int | None] = {"Sem turma": None}
        level_option_map: dict[str, int | None] = {"Sem nivel": None}
        training_list_option_map: dict[str, int | None] = {"Sem lista": None}
        attendance_member_map: dict[str, int] = {}

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=2)
        right_panel.grid_rowconfigure(3, weight=2)

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por titulo, turma, instrutor ou local")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        start_filter = ctk.CTkEntry(controls, placeholder_text="Inicio", width=120)
        start_filter.grid(row=0, column=1, padx=4)
        end_filter = ctk.CTkEntry(controls, placeholder_text="Fim", width=120)
        end_filter.grid(row=0, column=2, padx=4)

        sessions_holder = self._make_panel(right_panel)
        sessions_holder.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        sessions_holder.grid_columnconfigure(0, weight=1)
        sessions_holder.grid_rowconfigure(0, weight=1)
        sessions_tree = self._make_tree(
            sessions_holder,
            [
                "id",
                "title",
                "date",
                "time",
                "club",
                "class",
                "level",
                "training_list",
                "type",
                "status",
                "present",
                "absent",
            ],
            {
                "id": "ID",
                "title": "Aula/Treino",
                "date": "Data",
                "time": "Horario",
                "club": "Clube/Escola",
                "class": "Turma",
                "level": "Nível",
                "training_list": "Lista",
                "type": "Tipo",
                "status": "Status",
                "present": "Pres.",
                "absent": "Faltas",
            },
            {
                "id": 55,
                "title": 220,
                "date": 95,
                "time": 105,
                "club": 150,
                "class": 140,
                "level": 120,
                "training_list": 160,
                "type": 80,
                "status": 90,
                "present": 60,
                "absent": 60,
            },
        )

        attendance_controls = self._make_panel(right_panel)
        attendance_controls.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        attendance_controls.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(attendance_controls, text="Presenca").grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        attendance_status_option = ctk.CTkOptionMenu(
            attendance_controls,
            values=list(ATTENDANCE_STATUS_VALUES.keys()),
            width=150,
        )
        attendance_status_option.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")
        ctk.CTkLabel(attendance_controls, text="Observações").grid(row=0, column=1, padx=8, pady=(10, 2), sticky="w")
        attendance_notes_entry = ctk.CTkEntry(attendance_controls, width=240)
        attendance_notes_entry.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="ew")
        attendance_actions = ctk.CTkFrame(attendance_controls, fg_color="transparent")
        attendance_actions.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="ew")
        attendance_actions.grid_columnconfigure(0, weight=1)
        attendance_actions.grid_columnconfigure(1, weight=1)

        attendance_holder = self._make_panel(right_panel)
        attendance_holder.grid(row=3, column=0, sticky="nsew")
        attendance_holder.grid_columnconfigure(0, weight=1)
        attendance_holder.grid_rowconfigure(0, weight=1)
        attendance_tree = self._make_tree(
            attendance_holder,
            ["id", "name", "class", "category", "status", "notes"],
            {
                "id": "ID",
                "name": "Membro",
                "class": "Turma",
                "category": "Categoria",
                "status": "Presenca",
                "notes": "Obs.",
            },
            {"id": 55, "name": 240, "class": 150, "category": 100, "status": 110, "notes": 220},
        )

        def club_label(club: dict[str, Any]) -> str:
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            return f"{club['id']} - {club['name']} ({kind})"

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

        def load_level_options(selected_id: int | None = None) -> None:
            level_option_map.clear()
            level_option_map["Sem nivel"] = None
            values = ["Sem nivel"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                level_option_map[label] = int(level["id"])
            level_option.configure(values=values)
            chosen = next(
                (label for label, level_id in level_option_map.items() if level_id == selected_id),
                "Sem nivel",
            )
            level_option.set(chosen)

        def load_training_list_options(selected_id: int | None = None) -> None:
            training_list_option_map.clear()
            training_list_option_map["Sem lista"] = None
            values = ["Sem lista"]
            club_id = club_option_map.get(club_option.get(), 1)
            class_id = class_option_map.get(class_option.get())
            for training_list in self.db.list_training_lists(
                club_id=club_id,
                class_id=class_id,
                include_archived=False,
            ):
                label = f"{training_list['id']} - {training_list['name']}"
                values.append(label)
                training_list_option_map[label] = int(training_list["id"])
            training_list_option.configure(values=values)
            chosen = next(
                (
                    label
                    for label, training_list_id in training_list_option_map.items()
                    if training_list_id == selected_id
                ),
                "Sem lista",
            )
            training_list_option.set(chosen)

        def on_club_change(_value: str) -> None:
            load_class_options(club_option_map.get(club_option.get()), None)
            load_training_list_options()

        def on_class_change(_value: str) -> None:
            load_training_list_options()

        def session_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["session_type"] = TRAINING_TYPE_VALUES[type_option.get()]
            payload["status"] = TRAINING_STATUS_VALUES[status_option.get()]
            payload["club_id"] = club_option_map.get(club_option.get(), 1)
            payload["class_id"] = class_option_map.get(class_option.get())
            payload["learning_level_id"] = level_option_map.get(level_option.get())
            payload["training_list_id"] = training_list_option_map.get(training_list_option.get())
            return payload

        def clear_form() -> None:
            selected_session_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            type_option.set(TRAINING_SESSION_TYPES["aula"])
            status_option.set(TRAINING_SESSION_STATUSES["planned"])
            attendance_notes_entry.delete(0, "end")
            attendance_status_option.set(ATTENDANCE_STATUSES["present"])
            load_club_options()
            load_level_options()
            load_training_list_options()
            attendance_tree.delete(*attendance_tree.get_children())
            attendance_member_map.clear()

        def load_attendance(session_id: int | None = None) -> None:
            attendance_tree.delete(*attendance_tree.get_children())
            attendance_member_map.clear()
            if not session_id:
                return
            for member in self.db.list_session_members_for_attendance(session_id):
                status = str(member.get("attendance_status") or "")
                row_id = attendance_tree.insert(
                    "",
                    "end",
                    values=(
                        member["id"],
                        member["name"],
                        member.get("active_class_name") or "",
                        member["category"],
                        ATTENDANCE_STATUSES.get(status, "Nao marcado"),
                        member.get("attendance_notes") or "",
                    ),
                )
                attendance_member_map[row_id] = int(member["id"])

        def load_sessions() -> None:
            sessions_tree.delete(*sessions_tree.get_children())
            query = search_entry.get().strip().casefold()
            for session in self.db.list_training_sessions(
                start_date=start_filter.get().strip(),
                end_date=end_filter.get().strip(),
            ):
                searchable = " ".join(
                    [
                        str(session["title"] or ""),
                        str(session.get("club_name") or ""),
                        str(session.get("class_name") or ""),
                        str(session.get("learning_level_name") or ""),
                        str(session.get("training_list_name") or ""),
                        str(session.get("instructor") or ""),
                        str(session.get("location") or ""),
                        str(session.get("objective") or ""),
                        str(session.get("content") or ""),
                        str(session.get("homework") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                time_value = f"{session['start_time']} - {session['end_time']}".strip(" -")
                sessions_tree.insert(
                    "",
                    "end",
                    values=(
                        session["id"],
                        session["title"],
                        session["session_date"],
                        time_value,
                        session.get("club_name") or "",
                        session.get("class_name") or "",
                        session.get("learning_level_name") or "",
                        session.get("training_list_name") or "",
                        TRAINING_SESSION_TYPES.get(session["session_type"], session["session_type"]),
                        TRAINING_SESSION_STATUSES.get(session["status"], session["status"]),
                        session["present_count"],
                        session["absent_count"],
                    ),
                )

        def selected_session() -> dict[str, Any] | None:
            selected = sessions_tree.selection()
            if not selected:
                return None
            session_id = int(sessions_tree.item(selected[0], "values")[0])
            return self.db.get_training_session(session_id)

        def select_session_in_tree(session_id: int) -> None:
            for item_id in sessions_tree.get_children():
                values = sessions_tree.item(item_id, "values")
                if values and int(values[0]) == session_id:
                    sessions_tree.selection_set(item_id)
                    sessions_tree.see(item_id)
                    on_session_select()
                    return

        def on_session_select(_event: Any = None) -> None:
            session = selected_session()
            if not session:
                return
            selected_session_id["value"] = int(session["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(session.get(key) or ""))
            type_option.set(TRAINING_SESSION_TYPES.get(session["session_type"], TRAINING_SESSION_TYPES["aula"]))
            status_option.set(TRAINING_SESSION_STATUSES.get(session["status"], TRAINING_SESSION_STATUSES["planned"]))
            load_club_options(int(session.get("club_id") or 1))
            load_class_options(int(session.get("club_id") or 1), session.get("class_id"))
            load_level_options(session.get("learning_level_id"))
            load_training_list_options(session.get("training_list_id"))
            load_attendance(int(session["id"]))

        def save_session() -> None:
            try:
                session_id = self.training_service.save_session(
                    session_payload(),
                    selected_session_id["value"],
                )
                load_sessions()
                select_session_in_tree(session_id)
            except Exception as exc:
                self._show_error(exc)

        def mark_selected_attendance() -> None:
            try:
                session_id = selected_session_id["value"]
                selected = attendance_tree.selection()
                if not session_id or not selected:
                    raise AppError("Selecione uma aula e um membro.")
                member_id = attendance_member_map.get(selected[0])
                if not member_id:
                    raise AppError("Selecione um membro valido.")
                self.training_service.record_attendance(
                    session_id,
                    [
                        {
                            "member_id": member_id,
                            "status": ATTENDANCE_STATUS_VALUES[attendance_status_option.get()],
                            "notes": attendance_notes_entry.get(),
                        }
                    ],
                )
                attendance_notes_entry.delete(0, "end")
                load_attendance(session_id)
                load_sessions()
                select_session_in_tree(session_id)
            except Exception as exc:
                self._show_error(exc)

        def mark_all_present() -> None:
            try:
                session_id = selected_session_id["value"]
                if not session_id:
                    raise AppError("Selecione uma aula/treino.")
                rows = [
                    {"member_id": member_id, "status": "present"}
                    for member_id in attendance_member_map.values()
                ]
                if not rows:
                    raise AppError("Nao ha membros para chamada.")
                self.training_service.record_attendance(session_id, rows)
                load_attendance(session_id)
                load_sessions()
                select_session_in_tree(session_id)
            except Exception as exc:
                self._show_error(exc)

        def on_attendance_select(_event: Any = None) -> None:
            selected = attendance_tree.selection()
            if not selected:
                return
            values = attendance_tree.item(selected[0], "values")
            status_label = str(values[4] or "")
            if status_label in ATTENDANCE_STATUS_VALUES:
                attendance_status_option.set(status_label)
            attendance_notes_entry.delete(0, "end")
            attendance_notes_entry.insert(0, str(values[5] or ""))

        buttons = [
            ("Nova aula", clear_form),
            ("Salvar aula", save_session),
        ]
        self._grid_form_buttons(form, buttons, option_row + 12)

        ctk.CTkButton(controls, text="Filtrar", command=load_sessions).grid(row=0, column=3, padx=(8, 0))
        ctk.CTkButton(attendance_actions, text="Marcar selecionado", command=mark_selected_attendance).grid(
            row=0,
            column=0,
            padx=(0, 4),
            sticky="ew",
        )
        ctk.CTkButton(attendance_actions, text="Todos presentes", command=mark_all_present).grid(
            row=0,
            column=1,
            padx=(4, 0),
            sticky="ew",
        )

        sessions_tree.bind("<<TreeviewSelect>>", on_session_select)
        attendance_tree.bind("<<TreeviewSelect>>", on_attendance_select)
        search_entry.bind("<KeyRelease>", debounce(search_entry, load_sessions))
        start_filter.bind("<KeyRelease>", debounce(start_filter, load_sessions))
        end_filter.bind("<KeyRelease>", debounce(end_filter, load_sessions))
        club_option.configure(command=on_club_change)
        class_option.configure(command=on_class_change)

        clear_form()
        load_sessions()

    def show_finance(self) -> None:
        self._clear_content()
        self._page_title(
            "Financeiro",
            "Controle planos, mensalidades, pagamentos e pendencias dos membros.",
        )

        tabs = ctk.CTkTabview(self.content)
        tabs.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        tab_mensalidades = tabs.add("Mensalidades e Planos")
        tab_caixa = tabs.add("Fluxo de Caixa")
        tab_patrocinios = tabs.add("Patrocínios")

        body = ctk.CTkFrame(tab_mensalidades, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_plan_id: dict[str, int | None] = {"value": None}
        selected_payment_id: dict[str, int | None] = {"value": None}
        member_option_map: dict[str, int] = {}
        plan_option_map: dict[str, int | None] = {"Sem plano": None}

        ctk.CTkLabel(
            form,
            text="Plano",
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        plan_entries: dict[str, ctk.CTkEntry] = {}
        plan_fields = [
            ("name", "Nome"),
            ("amount", "Valor"),
            ("notes", "Observações"),
        ]
        for index, (key, label) in enumerate(plan_fields, start=1):
            ctk.CTkLabel(form, text=label).grid(row=index * 2 - 1, column=0, padx=16, pady=(6, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2, column=0, padx=16, pady=(2, 0), sticky="ew")
            plan_entries[key] = entry
        plan_cycle_option = ctk.CTkOptionMenu(form, values=list(BILLING_CYCLE_VALUES.keys()), width=260)
        ctk.CTkLabel(form, text="Ciclo").grid(row=7, column=0, padx=16, pady=(6, 0), sticky="w")
        plan_cycle_option.grid(row=8, column=0, padx=16, pady=(2, 0), sticky="ew")
        plan_active_check = ctk.CTkCheckBox(form, text="Ativo")
        plan_active_check.grid(row=9, column=0, padx=16, pady=(8, 0), sticky="w")

        ctk.CTkLabel(
            form,
            text="Lancamento",
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=13, column=0, padx=16, pady=(18, 4), sticky="w")

        ctk.CTkLabel(form, text="Membro").grid(row=14, column=0, padx=16, pady=(6, 0), sticky="w")
        member_option = ctk.CTkOptionMenu(form, values=["Sem membros"], width=260)
        member_option.grid(row=15, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Plano").grid(row=16, column=0, padx=16, pady=(6, 0), sticky="w")
        payment_plan_option = ctk.CTkOptionMenu(form, values=["Sem plano"], width=260)
        payment_plan_option.grid(row=17, column=0, padx=16, pady=(2, 0), sticky="ew")

        payment_entries: dict[str, ctk.CTkEntry] = {}
        payment_fields = [
            ("description", "Descrição"),
            ("reference_period", "Referencia"),
            ("due_date", "Vencimento"),
            ("payment_date", "Pagamento"),
            ("amount", "Valor"),
            ("method", "Metodo"),
            ("notes", "Observações"),
        ]
        base_row = 18
        for index, (key, label) in enumerate(payment_fields):
            row = base_row + index * 2
            ctk.CTkLabel(form, text=label).grid(row=row, column=0, padx=16, pady=(6, 0), sticky="w")
            if key in {"due_date", "payment_date"}:
                entry = self._make_date_entry(form, width=30)
            else:
                entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            payment_entries[key] = entry

        status_row = base_row + len(payment_fields) * 2
        ctk.CTkLabel(form, text="Status").grid(row=status_row, column=0, padx=16, pady=(6, 0), sticky="w")
        payment_status_option = ctk.CTkOptionMenu(form, values=list(PAYMENT_STATUS_VALUES.keys()), width=260)
        payment_status_option.grid(row=status_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=2)
        right_panel.grid_rowconfigure(3, weight=1)

        summary_panel = self._make_panel(right_panel)
        summary_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(5):
            summary_panel.grid_columnconfigure(column, weight=1)
        summary_labels: dict[str, ctk.CTkLabel] = {}
        summary_items = [
            ("net_balance", "Saldo (Líquido)"),
            ("paid_amount", "Mensalidades"),
            ("income_amount", "Outras Receitas"),
            ("expense_amount", "Despesas"),
            ("late_amount", "Em Atraso"),
        ]
        for index, (key, label) in enumerate(summary_items):
            card = ctk.CTkFrame(summary_panel, fg_color=THEME_APP_BG, corner_radius=8)
            card.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            value_label = ctk.CTkLabel(card, text="0", font=font_kpi_value())
            value_label.pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=12, pady=(0, 10))
            summary_labels[key] = value_label

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por membro, plano ou descricao")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        start_filter = ctk.CTkEntry(controls, placeholder_text="Inicio", width=120)
        start_filter.grid(row=0, column=1, padx=4)
        end_filter = ctk.CTkEntry(controls, placeholder_text="Fim", width=120)
        end_filter.grid(row=0, column=2, padx=4)
        status_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos"] + list(PAYMENT_STATUS_VALUES.keys()),
            width=140,
        )
        status_filter.grid(row=0, column=3, padx=4)

        payments_holder = self._make_panel(right_panel)
        payments_holder.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        payments_holder.grid_columnconfigure(0, weight=1)
        payments_holder.grid_rowconfigure(0, weight=1)
        payments_tree = self._make_tree(
            payments_holder,
            ["id", "member", "description", "reference", "due", "paid", "amount", "status", "plan"],
            {
                "id": "ID",
                "member": "Membro",
                "description": "Descrição",
                "reference": "Ref.",
                "due": "Venc.",
                "paid": "Pago em",
                "amount": "Valor",
                "status": "Status",
                "plan": "Plano",
            },
            {
                "id": 55,
                "member": 190,
                "description": 180,
                "reference": 80,
                "due": 90,
                "paid": 90,
                "amount": 80,
                "status": 90,
                "plan": 130,
            },
        )
        payments_tree.tag_configure("late", foreground=THEME_DANGER[0] if ctk.get_appearance_mode() == 'Light' else THEME_DANGER[1])

        plans_holder = self._make_panel(right_panel)
        plans_holder.grid(row=3, column=0, sticky="nsew")
        plans_holder.grid_columnconfigure(0, weight=1)
        plans_holder.grid_rowconfigure(0, weight=1)
        plans_tree = self._make_tree(
            plans_holder,
            ["id", "name", "amount", "cycle", "active", "payments"],
            {
                "id": "ID",
                "name": "Plano",
                "amount": "Valor",
                "cycle": "Ciclo",
                "active": "Ativo",
                "payments": "Lanc.",
            },
            {"id": 55, "name": 240, "amount": 90, "cycle": 120, "active": 70, "payments": 70},
        )

        def clear_plan_form() -> None:
            selected_plan_id["value"] = None
            for entry in plan_entries.values():
                entry.delete(0, "end")
            plan_cycle_option.set(BILLING_CYCLES["monthly"])
            plan_active_check.select()

        def clear_payment_form() -> None:
            selected_payment_id["value"] = None
            for entry in payment_entries.values():
                entry.delete(0, "end")
            payment_status_option.set(PAYMENT_STATUSES["pending"])
            if member_option_map:
                member_option.set(next(iter(member_option_map)))
            payment_plan_option.set("Sem plano")

        def load_member_options(selected_id: int | None = None) -> None:
            member_option_map.clear()
            values = []
            for member in self.db.list_members(active_only=False):
                label = f"{member['id']} - {self._member_display_name(member)}"
                values.append(label)
                member_option_map[label] = int(member["id"])
            if not values:
                values = ["Sem membros"]
            member_option.configure(values=values)
            chosen = next(
                (label for label, member_id in member_option_map.items() if member_id == selected_id),
                values[0],
            )
            member_option.set(chosen)

        def load_plan_options(selected_id: int | None = None) -> None:
            plan_option_map.clear()
            plan_option_map["Sem plano"] = None
            values = ["Sem plano"]
            for plan in self.db.list_membership_plans(active_only=True):
                label = f"{plan['id']} - {plan['name']} ({plan['amount']})"
                values.append(label)
                plan_option_map[label] = int(plan["id"])
            payment_plan_option.configure(values=values)
            chosen = next(
                (label for label, plan_id in plan_option_map.items() if plan_id == selected_id),
                "Sem plano",
            )
            payment_plan_option.set(chosen)

        def plan_payload() -> dict[str, Any]:
            return {
                "name": plan_entries["name"].get(),
                "amount": plan_entries["amount"].get(),
                "billing_cycle": BILLING_CYCLE_VALUES[plan_cycle_option.get()],
                "active": plan_active_check.get(),
                "notes": plan_entries["notes"].get(),
            }

        def payment_payload() -> dict[str, Any]:
            return {
                "member_id": member_option_map.get(member_option.get()),
                "plan_id": plan_option_map.get(payment_plan_option.get()),
                "description": payment_entries["description"].get(),
                "reference_period": payment_entries["reference_period"].get(),
                "due_date": payment_entries["due_date"].get(),
                "payment_date": payment_entries["payment_date"].get(),
                "amount": payment_entries["amount"].get(),
                "status": PAYMENT_STATUS_VALUES[payment_status_option.get()],
                "method": payment_entries["method"].get(),
                "notes": payment_entries["notes"].get(),
            }

        def load_summary() -> None:
            summary = self.finance_service.finance_summary(start_filter.get(), end_filter.get())
            for key, label in summary_labels.items():
                value = summary.get(key, 0)
                if key in ("net_balance", "paid_amount", "income_amount", "expense_amount", "late_amount", "pending_amount"):
                    label.configure(text=f"R$ {value:,.2f}")
                else:
                    label.configure(text=str(value))

        def load_plans() -> None:
            plans_tree.delete(*plans_tree.get_children())
            for plan in self.db.list_membership_plans(active_only=False):
                plans_tree.insert(
                    "",
                    "end",
                    values=(
                        plan["id"],
                        plan["name"],
                        plan["amount"],
                        BILLING_CYCLES.get(plan["billing_cycle"], plan["billing_cycle"]),
                        "Sim" if plan.get("active") else "Nao",
                        plan["payments_count"],
                    ),
                )

        def load_payments() -> None:
            payments_tree.delete(*payments_tree.get_children())
            query = search_entry.get().strip().casefold()
            selected_status = status_filter.get()
            for payment in self.finance_service.payments_report(start_filter.get(), end_filter.get()):
                if (
                    selected_status != "Todos"
                    and payment["effective_status"] != PAYMENT_STATUS_VALUES[selected_status]
                ):
                    continue
                searchable = " ".join(
                    [
                        str(payment.get("member_name") or ""),
                        str(payment.get("plan_name") or ""),
                        str(payment.get("description") or ""),
                        str(payment.get("reference_period") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                tags = ()
                if payment["effective_status"] == "late":
                    tags = ("late",)

                payments_tree.insert(
                    "",
                    "end",
                    values=(
                        payment["id"],
                        payment["member_name"],
                        payment["description"],
                        payment["reference_period"],
                        payment["due_date"],
                        payment["payment_date"],
                        payment["amount"],
                        PAYMENT_STATUSES.get(payment["effective_status"], payment["effective_status"]),
                        payment.get("plan_name") or "",
                    ),
                    tags=tags,
                )
            load_summary()

        def select_plan_in_tree(plan_id: int) -> None:
            for item_id in plans_tree.get_children():
                values = plans_tree.item(item_id, "values")
                if values and int(values[0]) == plan_id:
                    plans_tree.selection_set(item_id)
                    plans_tree.see(item_id)
                    on_plan_select()
                    return

        def select_payment_in_tree(payment_id: int) -> None:
            for item_id in payments_tree.get_children():
                values = payments_tree.item(item_id, "values")
                if values and int(values[0]) == payment_id:
                    payments_tree.selection_set(item_id)
                    payments_tree.see(item_id)
                    on_payment_select()
                    return

        def on_plan_select(_event: Any = None) -> None:
            selected = plans_tree.selection()
            if not selected:
                return
            plan_id = int(plans_tree.item(selected[0], "values")[0])
            plan = self.db.get_membership_plan(plan_id)
            if not plan:
                return
            selected_plan_id["value"] = plan_id
            for key, entry in plan_entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(plan.get(key) or ""))
            plan_cycle_option.set(BILLING_CYCLES.get(plan["billing_cycle"], BILLING_CYCLES["monthly"]))
            plan_active_check.select() if plan.get("active") else plan_active_check.deselect()

        def on_payment_select(_event: Any = None) -> None:
            selected = payments_tree.selection()
            if not selected:
                return
            payment_id = int(payments_tree.item(selected[0], "values")[0])
            payment = self.db.get_payment(payment_id)
            if not payment:
                return
            selected_payment_id["value"] = payment_id
            load_member_options(int(payment["member_id"]))
            load_plan_options(payment.get("plan_id"))
            for key, entry in payment_entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(payment.get(key) or ""))
            payment_status_option.set(PAYMENT_STATUSES.get(payment["status"], PAYMENT_STATUSES["pending"]))

        def save_plan() -> None:
            try:
                plan_id = self.finance_service.save_plan(plan_payload(), selected_plan_id["value"])
                load_plans()
                load_plan_options()
                select_plan_in_tree(plan_id)
            except Exception as exc:
                self._show_error(exc)

        def toggle_plan() -> None:
            try:
                if not selected_plan_id["value"]:
                    raise AppError("Selecione um plano.")
                plan_id = selected_plan_id["value"]
                self.finance_service.toggle_plan_active(plan_id)
                load_plans()
                load_plan_options()
                select_plan_in_tree(plan_id)
            except Exception as exc:
                self._show_error(exc)

        def save_payment() -> None:
            try:
                payment_id = self.finance_service.save_payment(payment_payload(), selected_payment_id["value"])
                load_payments()
                load_plans()
                select_payment_in_tree(payment_id)
            except Exception as exc:
                self._show_error(exc)

        def mark_selected_paid() -> None:
            try:
                if not selected_payment_id["value"]:
                    raise AppError("Selecione um lancamento.")
                payment_id = selected_payment_id["value"]
                self.finance_service.mark_payment_paid(
                    payment_id,
                    payment_entries["payment_date"].get(),
                    payment_entries["method"].get(),
                )
                load_payments()
                select_payment_in_tree(payment_id)
            except Exception as exc:
                self._show_error(exc)

        def generate_recurring_payments() -> None:
            try:
                plan_id = plan_option_map.get(payment_plan_option.get()) or selected_plan_id["value"]
                if not plan_id:
                    raise AppError("Selecione um plano para gerar mensalidades.")
                reference_period = payment_entries["reference_period"].get().strip()
                due_date = payment_entries["due_date"].get().strip()
                if not self._confirm_action(
                    "Gerar mensalidades",
                    "Gerar mensalidades para todos os socios/alunos ativos? "
                    "Lancamentos ja existentes na mesma referencia serao pulados.",
                ):
                    return
                result = self.finance_service.generate_recurring_payments(
                    int(plan_id),
                    reference_period,
                    due_date,
                )
                load_payments()
                load_plans()
                if result["payment_ids"]:
                    select_payment_in_tree(int(result["payment_ids"][0]))
                self._show_info(
                    "Mensalidades geradas:\n"
                    f"Plano: {result['plan_name']}\n"
                    f"Referencia: {result['reference_period']}\n"
                    f"Criadas: {result['created']}\n"
                    f"Puladas: {result['skipped']}"
                )
            except Exception as exc:
                self._show_error(exc)

        def export_receipt() -> None:
            try:
                if not selected_payment_id["value"]:
                    raise AppError("Selecione um lancamento.")
                payment_id = selected_payment_id["value"]
                file_path = filedialog.asksaveasfilename(
                    title="Exportar recibo",
                    initialdir=str(self._default_export_dir()),
                    initialfile=f"recibo_{payment_id:06d}.pdf",
                    defaultextension=".pdf",
                    filetypes=[
                        ("PDF", "*.pdf"),
                        ("Excel", "*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                self._run_background(
                    lambda: self.export_service.export_payment_receipt(payment_id, Path(file_path)),
                    lambda result_path: self._show_info(f"Recibo exportado:\n{result_path}"),
                    "Exportando recibo...",
                )
            except Exception as exc:
                self._show_error(exc)

        def print_receipt() -> None:
            try:
                import tempfile
                import os
                payment_id = selected_payment_id()
                if not payment_id:
                    raise AppError("Selecione um pagamento.")

                fd, temp_path_str = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                path = Path(temp_path_str)

                self._run_background(
                    lambda: self.export_service.export_payment_receipt(payment_id, path),
                    lambda result_path: self._print_document(path),
                    "Preparando impressão...",
                )
            except Exception as exc:
                self._show_error(exc)

        plan_buttons = [
            ("Novo plano", clear_plan_form),
            ("Salvar plano", save_plan),
            ("Ativar/Inativar plano", toggle_plan),
        ]
        self._grid_form_buttons(form, plan_buttons, 10)

        payment_button_row = status_row + 2
        payment_buttons = [
            ("Novo lancamento", clear_payment_form),
            ("Salvar lancamento", save_payment),
            ("Marcar pago", mark_selected_paid),
            ("Gerar mensalidades", generate_recurring_payments),
            ("Exportar recibo", export_receipt),
            ("Imprimir recibo", print_receipt),
        ]
        self._grid_form_buttons(form, payment_buttons, payment_button_row)

        ctk.CTkButton(controls, text="Filtrar", command=load_payments).grid(row=0, column=4, padx=(8, 0))
        plans_tree.bind("<<TreeviewSelect>>", on_plan_select)
        payments_tree.bind("<<TreeviewSelect>>", on_payment_select)
        search_entry.bind("<KeyRelease>", debounce(search_entry, load_payments))
        start_filter.bind("<KeyRelease>", debounce(start_filter, load_payments))
        end_filter.bind("<KeyRelease>", debounce(end_filter, load_payments))
        status_filter.configure(command=lambda _value: load_payments())

        load_member_options()
        load_plan_options()
        clear_plan_form()
        clear_payment_form()
        status_filter.set("Todos")
        load_plans()
        load_payments()

        # --- FLUXO DE CAIXA ---
        caixa_body = ctk.CTkFrame(tab_caixa, fg_color="transparent")
        caixa_body.pack(fill="both", expand=True)
        caixa_body.grid_columnconfigure(1, weight=1)
        caixa_body.grid_rowconfigure(0, weight=1)

        caixa_form = self._make_scrollable_panel(caixa_body, width=302)
        caixa_form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_transaction_id: dict[str, int | None] = {"value": None}

        ctk.CTkLabel(
            caixa_form, text="Transacao", font=font_section(), text_color=THEME_TEXT_MAIN
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        trans_entries: dict[str, ctk.CTkEntry] = {}
        trans_fields = [
            ("description", "Descrição"),
            ("amount", "Valor"),
            ("transaction_date", "Data (AAAA-MM-DD)"),
            ("category", "Categoria"),
            ("payment_method", "Metodo"),
            ("notes", "Observações"),
        ]
        
        ctk.CTkLabel(caixa_form, text="Tipo").grid(row=1, column=0, padx=16, pady=(6, 0), sticky="w")
        trans_type_option = ctk.CTkOptionMenu(caixa_form, values=["income", "expense"], width=260)
        trans_type_option.grid(row=2, column=0, padx=16, pady=(2, 0), sticky="ew")

        base_trans_row = 3
        for index, (key, label) in enumerate(trans_fields):
            row = base_trans_row + index * 2
            ctk.CTkLabel(caixa_form, text=label).grid(row=row, column=0, padx=16, pady=(6, 0), sticky="w")
            placeholder = "AAAA-MM-DD" if "date" in key else ""
            entry = ctk.CTkEntry(caixa_form, width=260, placeholder_text=placeholder)
            entry.grid(row=row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            trans_entries[key] = entry

        caixa_right_panel = ctk.CTkFrame(caixa_body, fg_color="transparent")
        caixa_right_panel.grid(row=0, column=1, sticky="nsew")
        caixa_right_panel.grid_columnconfigure(0, weight=1)
        caixa_right_panel.grid_rowconfigure(0, weight=1)

        trans_holder = self._make_panel(caixa_right_panel)
        trans_holder.grid(row=0, column=0, sticky="nsew")
        trans_holder.grid_columnconfigure(0, weight=1)
        trans_holder.grid_rowconfigure(0, weight=1)

        trans_tree = self._make_tree(
            trans_holder,
            ["id", "date", "type", "description", "category", "amount", "method"],
            {
                "id": "ID", "date": "Data", "type": "Tipo", "description": "Descrição",
                "category": "Categoria", "amount": "Valor", "method": "Metodo"
            },
            {"id": 55, "date": 90, "type": 80, "description": 250, "category": 120, "amount": 80, "method": 100}
        )

        def clear_trans_form() -> None:
            import datetime
            selected_transaction_id["value"] = None
            trans_type_option.set("income")
            for entry in trans_entries.values():
                entry.delete(0, "end")
            trans_entries["transaction_date"].insert(0, datetime.date.today().isoformat())

        def trans_payload() -> dict[str, Any]:
            return {
                "type": trans_type_option.get(),
                **{k: v.get() for k, v in trans_entries.items()}
            }

        def load_transactions() -> None:
            trans_tree.delete(*trans_tree.get_children())
            for tx in self.finance_service.list_transactions():
                trans_tree.insert("", "end", values=(
                    tx["id"], tx["transaction_date"], tx["type"], tx["description"],
                    tx["category"], tx["amount"], tx["payment_method"]
                ))
            load_summary()

        def on_trans_select(_event: Any = None) -> None:
            selected = trans_tree.selection()
            if not selected:
                return
            tx_id = int(trans_tree.item(selected[0], "values")[0])
            tx = next((t for t in self.finance_service.list_transactions() if t["id"] == tx_id), None)
            if not tx:
                return
            selected_transaction_id["value"] = tx_id
            trans_type_option.set(tx["type"])
            for key, entry in trans_entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(tx.get(key) or ""))

        trans_tree.bind("<<TreeviewSelect>>", on_trans_select)

        def save_trans() -> None:
            try:
                self.finance_service.save_transaction(trans_payload(), selected_transaction_id["value"])
                self._show_toast("Transação salva com sucesso!", kind="success")
                clear_trans_form()
                load_transactions()
            except Exception as e:
                self._show_toast(str(e), is_error=True)

        def delete_trans() -> None:
            tx_id = selected_transaction_id["value"]
            if not tx_id:
                return
            self.finance_service.delete_transaction(tx_id)
            self._show_toast("Transação excluída!", kind="success")
            clear_trans_form()
            load_transactions()

        # --- PATROCÍNIOS ---
        sponsors_body = ctk.CTkFrame(tab_patrocinios, fg_color="transparent")
        sponsors_body.pack(fill="both", expand=True)
        sponsors_body.grid_columnconfigure(1, weight=1)
        sponsors_body.grid_rowconfigure(0, weight=1)

        spon_form = self._make_scrollable_panel(sponsors_body, width=302)
        spon_form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_sponsor_id: dict[str, int | None] = {"value": None}

        ctk.CTkLabel(spon_form, text="Patrocinador", font=font_section()).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        
        spon_entries: dict[str, ctk.CTkEntry] = {}
        spon_fields = [
            ("name", "Nome/Empresa"),
            ("sponsor_type", "Tipo (Ex: Empresa, Prefeitura)"),
            ("contribution_amount", "Valor Contribuição"),
            ("frequency", "Frequência (Ex: Mensal, Anual)"),
            ("benefits_notes", "Contrapartidas/Notas"),
        ]
        for idx, (key, label) in enumerate(spon_fields):
            ctk.CTkLabel(spon_form, text=label).grid(row=idx*2+1, column=0, padx=16, pady=(6,0), sticky="w")
            entry = ctk.CTkEntry(spon_form, width=260)
            entry.grid(row=idx*2+2, column=0, padx=16, pady=(2,0), sticky="ew")
            spon_entries[key] = entry

        spon_holder = self._make_panel(sponsors_body)
        spon_holder.grid(row=0, column=1, sticky="nsew")
        spon_holder.grid_columnconfigure(0, weight=1)
        spon_holder.grid_rowconfigure(0, weight=1)

        spon_tree = self._make_tree(
            spon_holder,
            ["id", "name", "type", "amount", "frequency"],
            {"id": "ID", "name": "Nome", "type": "Tipo", "amount": "Valor", "frequency": "Frequência"},
            {"id": 50, "name": 200, "type": 150, "amount": 100, "frequency": 100}
        )

        def clear_spon_form() -> None:
            selected_sponsor_id["value"] = None
            for entry in spon_entries.values():
                entry.delete(0, "end")

        def load_sponsors() -> None:
            spon_tree.delete(*spon_tree.get_children())
            for sp in self.finance_service.list_sponsors():
                spon_tree.insert("", "end", values=(
                    sp["id"], sp["name"], sp["sponsor_type"], sp["contribution_amount"], sp["frequency"]
                ))

        def on_spon_select(_event: Any = None) -> None:
            selected = spon_tree.selection()
            if not selected:
                return
            sp_id = int(spon_tree.item(selected[0], "values")[0])
            sp = next((s for s in self.finance_service.list_sponsors() if s["id"] == sp_id), None)
            if not sp:
                return
            selected_sponsor_id["value"] = sp_id
            for key, entry in spon_entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(sp.get(key) or ""))

        spon_tree.bind("<<TreeviewSelect>>", on_spon_select)

        def save_spon() -> None:
            try:
                payload = {k: v.get() for k, v in spon_entries.items()}
                self.finance_service.save_sponsor(payload, selected_sponsor_id["value"])
                self._show_toast("Patrocinador salvo com sucesso!", kind="success")
                clear_spon_form()
                load_sponsors()
            except Exception as e:
                self._show_toast(str(e), is_error=True)

        def delete_spon() -> None:
            sp_id = selected_sponsor_id["value"]
            if not sp_id:
                return
            self.finance_service.delete_sponsor(sp_id)
            self._show_toast("Patrocinador excluído!", kind="success")
            clear_spon_form()
            load_sponsors()

        ctk.CTkButton(spon_form, text="Salvar Patrocinador", command=save_spon).grid(row=20, column=0, padx=16, pady=(16, 8), sticky="ew")
        ctk.CTkButton(spon_form, text="Novo", command=clear_spon_form, fg_color="transparent", border_width=1).grid(row=21, column=0, padx=16, pady=4, sticky="ew")
        danger_button(spon_form, "Excluir", delete_spon).grid(row=22, column=0, padx=16, pady=4, sticky="ew")

        load_sponsors()
        clear_trans_form()
        load_transactions()
