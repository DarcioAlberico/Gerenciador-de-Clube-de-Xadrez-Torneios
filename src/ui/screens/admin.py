from __future__ import annotations

from ..support import *


class AdminPagesMixin:
    def show_exercises(self) -> None:
        self._clear_content()
        self._page_title(
            "Exercicios e listas",
            "Cadastre posicoes, temas taticos e listas de treino para aulas ou turmas.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_exercise_id: dict[str, int | None] = {"value": None}
        selected_list_id: dict[str, int | None] = {"value": None}
        exercise_club_map: dict[str, int] = {}
        exercise_level_map: dict[str, int | None] = {"Sem nivel": None}
        list_club_map: dict[str, int] = {}
        list_class_map: dict[str, int | None] = {"Sem turma": None}
        list_level_map: dict[str, int | None] = {"Sem nivel": None}

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("title", "Titulo"),
            ("theme", "Tema"),
            ("source", "Fonte"),
            ("fen", "FEN"),
            ("pgn", "PGN"),
            ("solution", "Solucao"),
            ("objective", "Objetivo"),
            ("tags", "Tags"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Dificuldade").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        difficulty_option = ctk.CTkOptionMenu(
            form,
            values=list(EXERCISE_DIFFICULTY_VALUES.keys()),
            width=260,
        )
        difficulty_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Status").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        exercise_active_option = ctk.CTkOptionMenu(form, values=["Ativo", "Inativo"], width=260)
        exercise_active_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        exercise_club_option = ctk.CTkOptionMenu(form, values=[""], width=260)
        exercise_club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Nivel pedagogico").grid(
            row=option_row + 6,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        exercise_level_option = ctk.CTkOptionMenu(form, values=["Sem nivel"], width=260)
        exercise_level_option.grid(row=option_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=2)
        right_panel.grid_rowconfigure(3, weight=1)
        right_panel.grid_rowconfigure(5, weight=1)

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar exercicio, tema, FEN, PGN, solucao ou tags")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        difficulty_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todas", *EXERCISE_DIFFICULTY_VALUES.keys()],
            width=145,
        )
        difficulty_filter.grid(row=0, column=1, padx=4)
        active_filter = ctk.CTkOptionMenu(controls, values=["Ativos", "Todos"], width=105)
        active_filter.grid(row=0, column=2, padx=4)

        exercises_holder = self._make_panel(right_panel)
        exercises_holder.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        exercises_holder.grid_columnconfigure(0, weight=1)
        exercises_holder.grid_rowconfigure(0, weight=1)
        exercises_tree = self._make_tree(
            exercises_holder,
            ["id", "title", "theme", "difficulty", "level", "active", "lists", "attempts"],
            {
                "id": "ID",
                "title": "Exercicio",
                "theme": "Tema",
                "difficulty": "Dif.",
                "level": "Nivel",
                "active": "Ativo",
                "lists": "Listas",
                "attempts": "Tent.",
            },
            {
                "id": 55,
                "title": 230,
                "theme": 130,
                "difficulty": 105,
                "level": 120,
                "active": 65,
                "lists": 60,
                "attempts": 60,
            },
        )

        list_form = self._make_panel(right_panel)
        list_form.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        list_form.grid_columnconfigure(0, weight=1)
        list_name_entry = ctk.CTkEntry(list_form, placeholder_text="Nome da lista")
        list_name_entry.grid(row=0, column=0, padx=(12, 6), pady=(10, 4), sticky="ew")
        list_date_entry = self._make_date_entry(list_form, width=12)
        list_date_entry.grid(row=0, column=1, padx=4, pady=(10, 4))
        list_status_option = ctk.CTkOptionMenu(
            list_form,
            values=list(TRAINING_LIST_STATUS_VALUES.keys()),
            width=130,
        )
        list_status_option.grid(row=0, column=2, padx=4, pady=(10, 4))
        list_buttons = ctk.CTkFrame(list_form, fg_color="transparent")
        list_buttons.grid(row=0, column=3, padx=(4, 12), pady=(10, 4), sticky="e")
        list_club_option = ctk.CTkOptionMenu(list_form, values=[""], width=180)
        list_club_option.grid(row=1, column=0, padx=(12, 6), pady=4, sticky="ew")
        list_class_option = ctk.CTkOptionMenu(list_form, values=["Sem turma"], width=150)
        list_class_option.grid(row=1, column=1, padx=4, pady=4)
        list_level_option = ctk.CTkOptionMenu(list_form, values=["Sem nivel"], width=150)
        list_level_option.grid(row=1, column=2, padx=4, pady=4)
        list_description_entry = ctk.CTkEntry(list_form, placeholder_text="Descricao da lista")
        list_description_entry.grid(row=2, column=0, columnspan=4, padx=12, pady=(4, 10), sticky="ew")

        lists_holder = self._make_panel(right_panel)
        lists_holder.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        lists_holder.grid_columnconfigure(0, weight=1)
        lists_holder.grid_rowconfigure(0, weight=1)
        lists_tree = self._make_tree(
            lists_holder,
            ["id", "name", "club", "class", "level", "date", "status", "items", "attempts"],
            {
                "id": "ID",
                "name": "Lista",
                "club": "Clube",
                "class": "Turma",
                "level": "Nivel",
                "date": "Data",
                "status": "Status",
                "items": "Ex.",
                "attempts": "Tent.",
            },
            {
                "id": 55,
                "name": 190,
                "club": 130,
                "class": 120,
                "level": 110,
                "date": 95,
                "status": 95,
                "items": 55,
                "attempts": 60,
            },
        )

        item_controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        item_controls.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        item_controls.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(item_controls, text="Adicionar exercicio selecionado", command=lambda: add_selected_exercise()).grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="w",
        )
        ctk.CTkButton(item_controls, text="Remover da lista", command=lambda: remove_selected_item()).grid(
            row=0,
            column=1,
            padx=4,
            sticky="w",
        )

        items_holder = self._make_panel(right_panel)
        items_holder.grid(row=5, column=0, sticky="nsew")
        items_holder.grid_columnconfigure(0, weight=1)
        items_holder.grid_rowconfigure(0, weight=1)
        list_items_tree = self._make_tree(
            items_holder,
            ["order", "exercise_id", "title", "theme", "difficulty", "level"],
            {
                "order": "#",
                "exercise_id": "ID",
                "title": "Exercicio na lista",
                "theme": "Tema",
                "difficulty": "Dif.",
                "level": "Nivel",
            },
            {
                "order": 45,
                "exercise_id": 55,
                "title": 240,
                "theme": 140,
                "difficulty": 110,
                "level": 130,
            },
        )

        def club_label(club: dict[str, Any]) -> str:
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            return f"{club['id']} - {club['name']} ({kind})"

        def load_exercise_club_options(selected_id: int | None = None) -> None:
            exercise_club_map.clear()
            values = []
            for club in self.db.list_clubs(active_only=True):
                label = club_label(club)
                values.append(label)
                exercise_club_map[label] = int(club["id"])
            if not values:
                values = ["1 - Clube padrao (Clube)"]
                exercise_club_map[values[0]] = 1
            exercise_club_option.configure(values=values)
            chosen = next(
                (label for label, club_id in exercise_club_map.items() if club_id == selected_id),
                values[0],
            )
            exercise_club_option.set(chosen)

        def load_exercise_level_options(selected_id: int | None = None) -> None:
            exercise_level_map.clear()
            exercise_level_map["Sem nivel"] = None
            values = ["Sem nivel"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                exercise_level_map[label] = int(level["id"])
            exercise_level_option.configure(values=values)
            chosen = next(
                (label for label, level_id in exercise_level_map.items() if level_id == selected_id),
                "Sem nivel",
            )
            exercise_level_option.set(chosen)

        def load_list_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            list_class_map.clear()
            list_class_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    list_class_map[label] = int(class_data["id"])
            list_class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in list_class_map.items() if class_id == selected_id),
                "Sem turma",
            )
            list_class_option.set(chosen)

        def load_list_club_options(selected_id: int | None = None, selected_class_id: int | None = None) -> None:
            list_club_map.clear()
            values = []
            for club in self.db.list_clubs(active_only=True):
                label = club_label(club)
                values.append(label)
                list_club_map[label] = int(club["id"])
            if not values:
                values = ["1 - Clube padrao (Clube)"]
                list_club_map[values[0]] = 1
            list_club_option.configure(values=values)
            chosen = next((label for label, club_id in list_club_map.items() if club_id == selected_id), values[0])
            list_club_option.set(chosen)
            load_list_class_options(list_club_map[chosen], selected_class_id)

        def load_list_level_options(selected_id: int | None = None) -> None:
            list_level_map.clear()
            list_level_map["Sem nivel"] = None
            values = ["Sem nivel"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                list_level_map[label] = int(level["id"])
            list_level_option.configure(values=values)
            chosen = next((label for label, level_id in list_level_map.items() if level_id == selected_id), "Sem nivel")
            list_level_option.set(chosen)

        def exercise_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["difficulty"] = EXERCISE_DIFFICULTY_VALUES[difficulty_option.get()]
            payload["active"] = 1 if exercise_active_option.get() == "Ativo" else 0
            payload["club_id"] = exercise_club_map.get(exercise_club_option.get(), 1)
            payload["learning_level_id"] = exercise_level_map.get(exercise_level_option.get())
            return payload

        def training_list_payload() -> dict[str, Any]:
            return {
                "name": list_name_entry.get(),
                "description": list_description_entry.get(),
                "target_date": list_date_entry.get(),
                "status": TRAINING_LIST_STATUS_VALUES[list_status_option.get()],
                "club_id": list_club_map.get(list_club_option.get(), 1),
                "class_id": list_class_map.get(list_class_option.get()),
                "learning_level_id": list_level_map.get(list_level_option.get()),
            }

        def clear_exercise_form() -> None:
            selected_exercise_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            difficulty_option.set(EXERCISE_DIFFICULTIES["basic"])
            exercise_active_option.set("Ativo")
            load_exercise_club_options()
            load_exercise_level_options()

        def clear_list_form() -> None:
            selected_list_id["value"] = None
            list_name_entry.delete(0, "end")
            list_date_entry.delete(0, "end")
            list_description_entry.delete(0, "end")
            list_status_option.set(TRAINING_LIST_STATUSES["draft"])
            load_list_club_options()
            load_list_level_options()
            list_items_tree.delete(*list_items_tree.get_children())

        def load_exercises() -> None:
            exercises_tree.delete(*exercises_tree.get_children())
            difficulty = ""
            if difficulty_filter.get() != "Todas":
                difficulty = EXERCISE_DIFFICULTY_VALUES[difficulty_filter.get()]
            for exercise in self.db.list_exercises(
                search=search_entry.get().strip(),
                difficulty=difficulty,
                active_only=active_filter.get() == "Ativos",
            ):
                exercises_tree.insert(
                    "",
                    "end",
                    values=(
                        exercise["id"],
                        exercise["title"],
                        exercise.get("theme") or "",
                        EXERCISE_DIFFICULTIES.get(exercise["difficulty"], exercise["difficulty"]),
                        exercise.get("learning_level_name") or "",
                        "Sim" if exercise.get("active") else "Nao",
                        exercise["list_usage_count"],
                        exercise["attempt_count"],
                    ),
                )

        def load_lists() -> None:
            lists_tree.delete(*lists_tree.get_children())
            query = search_entry.get().strip().casefold()
            for training_list in self.db.list_training_lists():
                searchable = " ".join(
                    [
                        str(training_list.get("name") or ""),
                        str(training_list.get("description") or ""),
                        str(training_list.get("club_name") or ""),
                        str(training_list.get("class_name") or ""),
                        str(training_list.get("learning_level_name") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                lists_tree.insert(
                    "",
                    "end",
                    values=(
                        training_list["id"],
                        training_list["name"],
                        training_list.get("club_name") or "",
                        training_list.get("class_name") or "",
                        training_list.get("learning_level_name") or "",
                        training_list.get("target_date") or "",
                        TRAINING_LIST_STATUSES.get(training_list["status"], training_list["status"]),
                        training_list["exercise_count"],
                        training_list["attempt_count"],
                    ),
                )

        def load_list_items(list_id: int | None = None) -> None:
            list_items_tree.delete(*list_items_tree.get_children())
            if not list_id:
                return
            for item in self.db.list_training_list_exercises(list_id):
                list_items_tree.insert(
                    "",
                    "end",
                    values=(
                        item["position_order"],
                        item["exercise_id"],
                        item["title"],
                        item.get("theme") or "",
                        EXERCISE_DIFFICULTIES.get(item["difficulty"], item["difficulty"]),
                        item.get("learning_level_name") or "",
                    ),
                )

        def refresh_all() -> None:
            load_exercises()
            load_lists()
            load_list_items(selected_list_id["value"])

        def selected_exercise() -> dict[str, Any] | None:
            selected = exercises_tree.selection()
            if not selected:
                return None
            exercise_id = int(exercises_tree.item(selected[0], "values")[0])
            return self.db.get_exercise(exercise_id)

        def selected_training_list() -> dict[str, Any] | None:
            selected = lists_tree.selection()
            if not selected:
                return None
            list_id = int(lists_tree.item(selected[0], "values")[0])
            return self.db.get_training_list(list_id)

        def select_exercise_in_tree(exercise_id: int) -> None:
            for item_id in exercises_tree.get_children():
                values = exercises_tree.item(item_id, "values")
                if values and int(values[0]) == exercise_id:
                    exercises_tree.selection_set(item_id)
                    exercises_tree.see(item_id)
                    on_exercise_select()
                    return

        def select_list_in_tree(list_id: int) -> None:
            for item_id in lists_tree.get_children():
                values = lists_tree.item(item_id, "values")
                if values and int(values[0]) == list_id:
                    lists_tree.selection_set(item_id)
                    lists_tree.see(item_id)
                    on_list_select()
                    return

        def on_exercise_select(_event: Any = None) -> None:
            exercise = selected_exercise()
            if not exercise:
                return
            selected_exercise_id["value"] = int(exercise["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(exercise.get(key) or ""))
            difficulty_option.set(EXERCISE_DIFFICULTIES.get(exercise["difficulty"], EXERCISE_DIFFICULTIES["basic"]))
            exercise_active_option.set("Ativo" if exercise.get("active") else "Inativo")
            load_exercise_club_options(int(exercise.get("club_id") or 1))
            load_exercise_level_options(exercise.get("learning_level_id"))

        def on_list_select(_event: Any = None) -> None:
            training_list = selected_training_list()
            if not training_list:
                return
            selected_list_id["value"] = int(training_list["id"])
            list_name_entry.delete(0, "end")
            list_name_entry.insert(0, str(training_list.get("name") or ""))
            list_date_entry.delete(0, "end")
            list_date_entry.insert(0, str(training_list.get("target_date") or ""))
            list_description_entry.delete(0, "end")
            list_description_entry.insert(0, str(training_list.get("description") or ""))
            list_status_option.set(TRAINING_LIST_STATUSES.get(training_list["status"], TRAINING_LIST_STATUSES["draft"]))
            load_list_club_options(int(training_list.get("club_id") or 1), training_list.get("class_id"))
            load_list_level_options(training_list.get("learning_level_id"))
            load_list_items(int(training_list["id"]))

        def save_exercise() -> None:
            try:
                exercise_id = self.exercise_service.save_exercise(
                    exercise_payload(),
                    selected_exercise_id["value"],
                )
                refresh_all()
                select_exercise_in_tree(exercise_id)
            except Exception as exc:
                self._show_error(exc)

        def toggle_exercise() -> None:
            try:
                exercise_id = selected_exercise_id["value"]
                if not exercise_id:
                    raise AppError("Selecione um exercicio.")
                self.exercise_service.toggle_exercise_active(exercise_id)
                load_exercises()
                select_exercise_in_tree(exercise_id)
            except Exception as exc:
                self._show_error(exc)

        def save_training_list() -> None:
            try:
                list_id = self.exercise_service.save_training_list(
                    training_list_payload(),
                    selected_list_id["value"],
                )
                load_lists()
                select_list_in_tree(list_id)
            except Exception as exc:
                self._show_error(exc)

        def add_selected_exercise() -> None:
            try:
                list_id = selected_list_id["value"]
                exercise = selected_exercise()
                if not list_id or not exercise:
                    raise AppError("Selecione uma lista e um exercicio.")
                self.exercise_service.add_exercise_to_training_list(list_id, int(exercise["id"]))
                refresh_all()
                select_list_in_tree(list_id)
            except Exception as exc:
                self._show_error(exc)

        def remove_selected_item() -> None:
            try:
                list_id = selected_list_id["value"]
                selected = list_items_tree.selection()
                if not list_id or not selected:
                    raise AppError("Selecione um exercicio da lista.")
                exercise_id = int(list_items_tree.item(selected[0], "values")[1])
                self.exercise_service.remove_exercise_from_training_list(list_id, exercise_id)
                refresh_all()
                select_list_in_tree(list_id)
            except Exception as exc:
                self._show_error(exc)

        def on_list_club_change(_value: str) -> None:
            load_list_class_options(list_club_map.get(list_club_option.get()), None)

        buttons = [
            ("Novo exercicio", clear_exercise_form),
            ("Salvar exercicio", save_exercise),
            ("Ativar/Inativar", toggle_exercise),
        ]
        self._grid_form_buttons(form, buttons, option_row + 8)

        ctk.CTkButton(controls, text="Filtrar", command=refresh_all).grid(row=0, column=3, padx=(8, 0))
        ctk.CTkButton(list_buttons, text="Nova", width=70, command=clear_list_form).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(list_buttons, text="Salvar", width=80, command=save_training_list).grid(row=0, column=1)

        exercises_tree.bind("<<TreeviewSelect>>", on_exercise_select)
        lists_tree.bind("<<TreeviewSelect>>", on_list_select)
        search_entry.bind("<KeyRelease>", lambda _event: refresh_all())
        difficulty_filter.configure(command=lambda _value: refresh_all())
        active_filter.configure(command=lambda _value: refresh_all())
        list_club_option.configure(command=on_list_club_change)

        clear_exercise_form()
        clear_list_form()
        refresh_all()

    def show_inventory(self) -> None:
        self._clear_content()
        self._page_title(
            "Inventario",
            "Controle materiais, emprestimos e manutencoes do clube ou escola.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_item_id: dict[str, int | None] = {"value": None}
        selected_loan_id: dict[str, int | None] = {"value": None}
        selected_maintenance_id: dict[str, int | None] = {"value": None}
        club_option_map: dict[str, int] = {}
        member_option_map: dict[str, int] = {}

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("code", "Codigo"),
            ("name", "Nome"),
            ("quantity_total", "Quantidade"),
            ("storage_location", "Local"),
            ("acquisition_date", "Aquisicao"),
            ("acquisition_value", "Valor"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            if key == "acquisition_date":
                entry = self._make_date_entry(form, width=30)
            else:
                entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=list(INVENTORY_ITEM_TYPE_VALUES.keys()), width=260)
        type_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Estado").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        condition_option = ctk.CTkOptionMenu(form, values=list(INVENTORY_CONDITION_VALUES.keys()), width=260)
        condition_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        club_option = ctk.CTkOptionMenu(form, values=[""], width=260)
        club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        active_check = ctk.CTkCheckBox(form, text="Ativo")
        active_check.grid(row=option_row + 6, column=0, padx=16, pady=(10, 0), sticky="w")

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=2)
        right_panel.grid_rowconfigure(4, weight=1)

        summary_panel = self._make_panel(right_panel)
        summary_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for column in range(5):
            summary_panel.grid_columnconfigure(column, weight=1)
        summary_labels: dict[str, ctk.CTkLabel] = {}
        summary_items = [
            ("total_quantity", "Total"),
            ("available_quantity", "Disponivel"),
            ("borrowed_quantity", "Emprestado"),
            ("open_loans", "Em aberto"),
            ("open_maintenance", "Manutencao"),
        ]
        for index, (key, label) in enumerate(summary_items):
            card = ctk.CTkFrame(summary_panel, fg_color=THEME_APP_BG, corner_radius=8)
            card.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            value_label = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=18, weight="bold"))
            value_label.pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=12, pady=(0, 10))
            summary_labels[key] = value_label

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por codigo, item, local ou observacao")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        type_filter = ctk.CTkOptionMenu(controls, values=["Todos", *INVENTORY_ITEM_TYPE_VALUES.keys()], width=140)
        type_filter.grid(row=0, column=1, padx=4)
        active_filter = ctk.CTkOptionMenu(controls, values=["Ativos", "Todos"], width=105)
        active_filter.grid(row=0, column=2, padx=4)

        items_holder = self._make_panel(right_panel)
        items_holder.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        items_holder.grid_columnconfigure(0, weight=1)
        items_holder.grid_rowconfigure(0, weight=1)
        items_tree = self._make_tree(
            items_holder,
            ["id", "code", "name", "type", "total", "available", "condition", "location", "club"],
            {
                "id": "ID",
                "code": "Codigo",
                "name": "Item",
                "type": "Tipo",
                "total": "Total",
                "available": "Disp.",
                "condition": "Estado",
                "location": "Local",
                "club": "Clube",
            },
            {
                "id": 50,
                "code": 90,
                "name": 190,
                "type": 105,
                "total": 55,
                "available": 55,
                "condition": 95,
                "location": 120,
                "club": 130,
            },
        )

        detail_form = self._make_panel(right_panel)
        detail_form.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        detail_form.grid_columnconfigure(0, weight=1)
        detail_form.grid_columnconfigure(1, weight=1)

        loan_box = ctk.CTkFrame(detail_form, fg_color="transparent")
        loan_box.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="ew")
        loan_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(loan_box, text="Emprestimo", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
        )
        member_option = ctk.CTkOptionMenu(loan_box, values=["Sem membros"], width=190)
        member_option.grid(row=1, column=0, padx=(0, 6), pady=(8, 4), sticky="ew")
        loan_quantity_entry = ctk.CTkEntry(loan_box, placeholder_text="Qtd.", width=70)
        loan_quantity_entry.grid(row=1, column=1, padx=4, pady=(8, 4))
        loan_due_entry = ctk.CTkEntry(loan_box, placeholder_text="Devolver", width=105)
        loan_due_entry.grid(row=1, column=2, padx=4, pady=(8, 4))
        loan_status_option = ctk.CTkOptionMenu(
            loan_box,
            values=list(INVENTORY_LOAN_STATUS_VALUES.keys()),
            width=120,
        )
        loan_status_option.grid(row=1, column=3, padx=(4, 0), pady=(8, 4))
        loan_notes_entry = ctk.CTkEntry(loan_box, placeholder_text="Observacoes")
        loan_notes_entry.grid(row=2, column=0, columnspan=2, padx=(0, 6), pady=4, sticky="ew")
        loan_actions = ctk.CTkFrame(loan_box, fg_color="transparent")
        loan_actions.grid(row=2, column=2, columnspan=2, pady=4, sticky="e")

        maintenance_box = ctk.CTkFrame(detail_form, fg_color="transparent")
        maintenance_box.grid(row=1, column=0, columnspan=2, padx=12, pady=(4, 10), sticky="ew")
        maintenance_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(maintenance_box, text="Manutencao", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
        )
        maintenance_description_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Descricao")
        maintenance_description_entry.grid(row=1, column=0, padx=(0, 6), pady=(8, 4), sticky="ew")
        maintenance_cost_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Custo", width=80)
        maintenance_cost_entry.grid(row=1, column=1, padx=4, pady=(8, 4))
        maintenance_status_option = ctk.CTkOptionMenu(
            maintenance_box,
            values=list(INVENTORY_MAINTENANCE_STATUS_VALUES.keys()),
            width=125,
        )
        maintenance_status_option.grid(row=1, column=2, padx=4, pady=(8, 4))
        maintenance_vendor_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Fornecedor")
        maintenance_vendor_entry.grid(row=2, column=0, padx=(0, 6), pady=4, sticky="ew")
        maintenance_notes_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Observacoes")
        maintenance_notes_entry.grid(row=2, column=1, padx=4, pady=4, sticky="ew")
        maintenance_actions = ctk.CTkFrame(maintenance_box, fg_color="transparent")
        maintenance_actions.grid(row=2, column=2, pady=4, sticky="e")

        detail_holder = ctk.CTkFrame(right_panel, fg_color="transparent")
        detail_holder.grid(row=4, column=0, sticky="nsew")
        detail_holder.grid_columnconfigure(0, weight=1)
        detail_holder.grid_columnconfigure(1, weight=1)
        detail_holder.grid_rowconfigure(0, weight=1)

        loans_holder = self._make_panel(detail_holder)
        loans_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        loans_holder.grid_columnconfigure(0, weight=1)
        loans_holder.grid_rowconfigure(0, weight=1)
        loans_tree = self._make_tree(
            loans_holder,
            ["id", "member", "quantity", "loan", "due", "return", "status"],
            {
                "id": "ID",
                "member": "Membro",
                "quantity": "Qtd.",
                "loan": "Saida",
                "due": "Prev.",
                "return": "Retorno",
                "status": "Status",
            },
            {
                "id": 50,
                "member": 150,
                "quantity": 55,
                "loan": 85,
                "due": 85,
                "return": 85,
                "status": 100,
            },
        )

        maintenance_holder = self._make_panel(detail_holder)
        maintenance_holder.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        maintenance_holder.grid_columnconfigure(0, weight=1)
        maintenance_holder.grid_rowconfigure(0, weight=1)
        maintenance_tree = self._make_tree(
            maintenance_holder,
            ["id", "description", "opened", "resolved", "cost", "status"],
            {
                "id": "ID",
                "description": "Manutencao",
                "opened": "Aberta",
                "resolved": "Concl.",
                "cost": "Custo",
                "status": "Status",
            },
            {"id": 50, "description": 190, "opened": 85, "resolved": 85, "cost": 70, "status": 110},
        )

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
            chosen = next((label for label, club_id in club_option_map.items() if club_id == selected_id), values[0])
            club_option.set(chosen)

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

        def item_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["club_id"] = club_option_map.get(club_option.get(), 1)
            payload["item_type"] = INVENTORY_ITEM_TYPE_VALUES[type_option.get()]
            payload["condition_status"] = INVENTORY_CONDITION_VALUES[condition_option.get()]
            payload["active"] = active_check.get()
            return payload

        def loan_payload() -> dict[str, Any]:
            return {
                "item_id": selected_item_id["value"],
                "member_id": member_option_map.get(member_option.get()),
                "quantity": loan_quantity_entry.get(),
                "due_date": loan_due_entry.get(),
                "status": INVENTORY_LOAN_STATUS_VALUES[loan_status_option.get()],
                "notes": loan_notes_entry.get(),
            }

        def maintenance_payload() -> dict[str, Any]:
            return {
                "item_id": selected_item_id["value"],
                "description": maintenance_description_entry.get(),
                "cost": maintenance_cost_entry.get(),
                "status": INVENTORY_MAINTENANCE_STATUS_VALUES[maintenance_status_option.get()],
                "vendor": maintenance_vendor_entry.get(),
                "notes": maintenance_notes_entry.get(),
            }

        def clear_item_form() -> None:
            selected_item_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            entries["quantity_total"].insert(0, "1")
            type_option.set(INVENTORY_ITEM_TYPES["other"])
            condition_option.set(INVENTORY_CONDITIONS["good"])
            active_check.select()
            load_club_options()
            clear_loan_form()
            clear_maintenance_form()
            loans_tree.delete(*loans_tree.get_children())
            maintenance_tree.delete(*maintenance_tree.get_children())

        def clear_loan_form() -> None:
            selected_loan_id["value"] = None
            loan_quantity_entry.delete(0, "end")
            loan_quantity_entry.insert(0, "1")
            loan_due_entry.delete(0, "end")
            loan_notes_entry.delete(0, "end")
            loan_status_option.set(INVENTORY_LOAN_STATUSES["open"])
            load_member_options()

        def clear_maintenance_form() -> None:
            selected_maintenance_id["value"] = None
            maintenance_description_entry.delete(0, "end")
            maintenance_cost_entry.delete(0, "end")
            maintenance_vendor_entry.delete(0, "end")
            maintenance_notes_entry.delete(0, "end")
            maintenance_status_option.set(INVENTORY_MAINTENANCE_STATUSES["open"])

        def load_summary() -> None:
            summary = self.inventory_service.inventory_summary()
            for key, label in summary_labels.items():
                label.configure(text=str(summary.get(key, 0)))

        def load_items() -> None:
            items_tree.delete(*items_tree.get_children())
            selected_type = ""
            if type_filter.get() != "Todos":
                selected_type = INVENTORY_ITEM_TYPE_VALUES[type_filter.get()]
            for item in self.db.list_inventory_items(
                search=search_entry.get().strip(),
                item_type=selected_type,
                active_only=active_filter.get() == "Ativos",
            ):
                items_tree.insert(
                    "",
                    "end",
                    values=(
                        item["id"],
                        item.get("code") or "",
                        item["name"],
                        INVENTORY_ITEM_TYPES.get(item["item_type"], item["item_type"]),
                        item["quantity_total"],
                        item["available_quantity"],
                        INVENTORY_CONDITIONS.get(item["condition_status"], item["condition_status"]),
                        item.get("storage_location") or "",
                        item.get("club_name") or "",
                    ),
                )
            load_summary()

        def load_loans(item_id: int | None = None) -> None:
            loans_tree.delete(*loans_tree.get_children())
            if not item_id:
                return
            for loan in self.db.list_inventory_loans(item_id=item_id):
                loans_tree.insert(
                    "",
                    "end",
                    values=(
                        loan["id"],
                        loan["member_name"],
                        loan["quantity"],
                        loan.get("loan_date") or "",
                        loan.get("due_date") or "",
                        loan.get("return_date") or "",
                        INVENTORY_LOAN_STATUSES.get(loan["status"], loan["status"]),
                    ),
                )

        def load_maintenance(item_id: int | None = None) -> None:
            maintenance_tree.delete(*maintenance_tree.get_children())
            if not item_id:
                return
            for maintenance in self.db.list_inventory_maintenance(item_id=item_id):
                maintenance_tree.insert(
                    "",
                    "end",
                    values=(
                        maintenance["id"],
                        maintenance["description"],
                        maintenance.get("opened_date") or "",
                        maintenance.get("resolved_date") or "",
                        maintenance["cost"],
                        INVENTORY_MAINTENANCE_STATUSES.get(maintenance["status"], maintenance["status"]),
                    ),
                )

        def refresh_all() -> None:
            load_items()
            load_loans(selected_item_id["value"])
            load_maintenance(selected_item_id["value"])

        def selected_item() -> dict[str, Any] | None:
            selected = items_tree.selection()
            if not selected:
                return None
            item_id = int(items_tree.item(selected[0], "values")[0])
            return self.db.get_inventory_item(item_id)

        def select_item_in_tree(item_id: int) -> None:
            for item_row in items_tree.get_children():
                values = items_tree.item(item_row, "values")
                if values and int(values[0]) == item_id:
                    items_tree.selection_set(item_row)
                    items_tree.see(item_row)
                    on_item_select()
                    return

        def on_item_select(_event: Any = None) -> None:
            item = selected_item()
            if not item:
                return
            selected_item_id["value"] = int(item["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(item.get(key) or ""))
            type_option.set(INVENTORY_ITEM_TYPES.get(item["item_type"], INVENTORY_ITEM_TYPES["other"]))
            condition_option.set(INVENTORY_CONDITIONS.get(item["condition_status"], INVENTORY_CONDITIONS["good"]))
            active_check.select() if item.get("active") else active_check.deselect()
            load_club_options(int(item.get("club_id") or 1))
            clear_loan_form()
            clear_maintenance_form()
            load_loans(int(item["id"]))
            load_maintenance(int(item["id"]))

        def on_loan_select(_event: Any = None) -> None:
            selected = loans_tree.selection()
            if not selected:
                return
            loan_id = int(loans_tree.item(selected[0], "values")[0])
            loan = self.db.get_inventory_loan(loan_id)
            if not loan:
                return
            selected_loan_id["value"] = loan_id
            load_member_options(int(loan["member_id"]))
            loan_quantity_entry.delete(0, "end")
            loan_quantity_entry.insert(0, str(loan.get("quantity") or "1"))
            loan_due_entry.delete(0, "end")
            loan_due_entry.insert(0, str(loan.get("due_date") or ""))
            loan_notes_entry.delete(0, "end")
            loan_notes_entry.insert(0, str(loan.get("notes") or ""))
            loan_status_option.set(INVENTORY_LOAN_STATUSES.get(loan["status"], INVENTORY_LOAN_STATUSES["open"]))

        def on_maintenance_select(_event: Any = None) -> None:
            selected = maintenance_tree.selection()
            if not selected:
                return
            maintenance_id = int(maintenance_tree.item(selected[0], "values")[0])
            maintenance = self.db.get_inventory_maintenance(maintenance_id)
            if not maintenance:
                return
            selected_maintenance_id["value"] = maintenance_id
            maintenance_description_entry.delete(0, "end")
            maintenance_description_entry.insert(0, str(maintenance.get("description") or ""))
            maintenance_cost_entry.delete(0, "end")
            maintenance_cost_entry.insert(0, str(maintenance.get("cost") or ""))
            maintenance_vendor_entry.delete(0, "end")
            maintenance_vendor_entry.insert(0, str(maintenance.get("vendor") or ""))
            maintenance_notes_entry.delete(0, "end")
            maintenance_notes_entry.insert(0, str(maintenance.get("notes") or ""))
            maintenance_status_option.set(
                INVENTORY_MAINTENANCE_STATUSES.get(
                    maintenance["status"],
                    INVENTORY_MAINTENANCE_STATUSES["open"],
                )
            )

        def save_item() -> None:
            try:
                item_id = self.inventory_service.save_item(item_payload(), selected_item_id["value"])
                refresh_all()
                select_item_in_tree(item_id)
            except Exception as exc:
                self._show_error(exc)

        def toggle_item() -> None:
            try:
                item_id = selected_item_id["value"]
                if not item_id:
                    raise AppError("Selecione um item.")
                self.inventory_service.toggle_item_active(item_id)
                refresh_all()
                select_item_in_tree(item_id)
            except Exception as exc:
                self._show_error(exc)

        def save_loan() -> None:
            try:
                if not selected_item_id["value"]:
                    raise AppError("Selecione um item para emprestar.")
                loan_id = self.inventory_service.save_loan(loan_payload(), selected_loan_id["value"])
                refresh_all()
                load_loans(selected_item_id["value"])
                selected_loan_id["value"] = loan_id
            except Exception as exc:
                self._show_error(exc)

        def return_loan() -> None:
            try:
                loan_id = selected_loan_id["value"]
                if not loan_id:
                    raise AppError("Selecione um emprestimo.")
                self.inventory_service.return_loan(loan_id)
                clear_loan_form()
                refresh_all()
            except Exception as exc:
                self._show_error(exc)

        def save_maintenance() -> None:
            try:
                if not selected_item_id["value"]:
                    raise AppError("Selecione um item para manutencao.")
                maintenance_id = self.inventory_service.save_maintenance(
                    maintenance_payload(),
                    selected_maintenance_id["value"],
                )
                refresh_all()
                selected_maintenance_id["value"] = maintenance_id
            except Exception as exc:
                self._show_error(exc)

        def close_maintenance() -> None:
            try:
                maintenance_id = selected_maintenance_id["value"]
                if not maintenance_id:
                    raise AppError("Selecione uma manutencao.")
                self.inventory_service.close_maintenance(maintenance_id)
                clear_maintenance_form()
                refresh_all()
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Novo item", clear_item_form),
            ("Salvar item", save_item),
            ("Ativar/Inativar", toggle_item),
        ]
        self._grid_form_buttons(form, buttons, option_row + 7)

        ctk.CTkButton(controls, text="Filtrar", command=refresh_all).grid(row=0, column=3, padx=(8, 0))
        ctk.CTkButton(loan_actions, text="Salvar", width=76, command=save_loan).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(loan_actions, text="Devolver", width=82, command=return_loan).grid(row=0, column=1)
        ctk.CTkButton(maintenance_actions, text="Salvar", width=76, command=save_maintenance).grid(
            row=0,
            column=0,
            padx=(0, 4),
        )
        ctk.CTkButton(maintenance_actions, text="Concluir", width=82, command=close_maintenance).grid(row=0, column=1)

        items_tree.bind("<<TreeviewSelect>>", on_item_select)
        loans_tree.bind("<<TreeviewSelect>>", on_loan_select)
        maintenance_tree.bind("<<TreeviewSelect>>", on_maintenance_select)
        search_entry.bind("<KeyRelease>", lambda _event: refresh_all())
        type_filter.configure(command=lambda _value: refresh_all())
        active_filter.configure(command=lambda _value: refresh_all())

        clear_item_form()
        refresh_all()

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
            ("title", "Titulo"),
            ("session_date", "Data"),
            ("start_time", "Inicio"),
            ("end_time", "Fim"),
            ("instructor", "Instrutor"),
            ("location", "Local"),
            ("objective", "Objetivo"),
            ("content", "Conteudo"),
            ("homework", "Tarefa"),
            ("notes", "Observacoes"),
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

        ctk.CTkLabel(form, text="Nivel pedagogico").grid(
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
                "level": "Nivel",
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
        ctk.CTkLabel(attendance_controls, text="Observacoes").grid(row=0, column=1, padx=8, pady=(10, 2), sticky="w")
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
        search_entry.bind("<KeyRelease>", lambda _event: load_sessions())
        start_filter.bind("<KeyRelease>", lambda _event: load_sessions())
        end_filter.bind("<KeyRelease>", lambda _event: load_sessions())
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
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        plan_entries: dict[str, ctk.CTkEntry] = {}
        plan_fields = [
            ("name", "Nome"),
            ("amount", "Valor"),
            ("notes", "Observacoes"),
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
            font=ctk.CTkFont(size=14, weight="bold"),
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
            ("description", "Descricao"),
            ("reference_period", "Referencia"),
            ("due_date", "Vencimento"),
            ("payment_date", "Pagamento"),
            ("amount", "Valor"),
            ("method", "Metodo"),
            ("notes", "Observacoes"),
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
            value_label = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=18, weight="bold"))
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
                "description": "Descricao",
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
                if not messagebox.askyesno(
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
        search_entry.bind("<KeyRelease>", lambda _event: load_payments())
        start_filter.bind("<KeyRelease>", lambda _event: load_payments())
        end_filter.bind("<KeyRelease>", lambda _event: load_payments())
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
            caixa_form, text="Transacao", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME_TEXT_MAIN
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        trans_entries: dict[str, ctk.CTkEntry] = {}
        trans_fields = [
            ("description", "Descricao"),
            ("amount", "Valor"),
            ("transaction_date", "Data (AAAA-MM-DD)"),
            ("category", "Categoria"),
            ("payment_method", "Metodo"),
            ("notes", "Observacoes"),
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
                "id": "ID", "date": "Data", "type": "Tipo", "description": "Descricao",
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
                self._show_toast("Transação salva com sucesso!")
                clear_trans_form()
                load_transactions()
            except Exception as e:
                self._show_toast(str(e), is_error=True)

        def delete_trans() -> None:
            tx_id = selected_transaction_id["value"]
            if not tx_id:
                return
            self.finance_service.delete_transaction(tx_id)
            self._show_toast("Transação excluída!")
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

        ctk.CTkLabel(spon_form, text="Patrocinador", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        
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
                self._show_toast("Patrocinador salvo com sucesso!")
                clear_spon_form()
                load_sponsors()
            except Exception as e:
                self._show_toast(str(e), is_error=True)

        def delete_spon() -> None:
            sp_id = selected_sponsor_id["value"]
            if not sp_id:
                return
            self.finance_service.delete_sponsor(sp_id)
            self._show_toast("Patrocinador excluído!")
            clear_spon_form()
            load_sponsors()

        ctk.CTkButton(spon_form, text="Salvar Patrocinador", command=save_spon).grid(row=20, column=0, padx=16, pady=(16, 8), sticky="ew")
        ctk.CTkButton(spon_form, text="Novo", command=clear_spon_form, fg_color="transparent", border_width=1).grid(row=21, column=0, padx=16, pady=4, sticky="ew")
        ctk.CTkButton(spon_form, text="Excluir", command=delete_spon, fg_color=THEME_DANGER, hover_color="#C0392B").grid(row=22, column=0, padx=16, pady=4, sticky="ew")

        load_sponsors()
        clear_trans_form()
        load_transactions()

    def show_calendar(self) -> None:
        self._clear_content()
        self._page_title(
            "Calendario",
            "Organize eventos do clube e vincule torneios ao calendario.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=302)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("title", "Titulo"),
            ("event_date", "Data"),
            ("start_time", "Inicio"),
            ("end_time", "Fim"),
            ("location", "Local"),
            ("notes", "Observacoes"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            if key == "event_date":
                entry = self._make_date_entry(form, width=30)
            else:
                entry = ctk.CTkEntry(form, width=260)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=list(EVENT_TYPE_VALUES.keys()), width=260)
        type_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Status").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        status_option = ctk.CTkOptionMenu(form, values=list(EVENT_STATUS_VALUES.keys()), width=260)
        status_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        club_option = ctk.CTkOptionMenu(form, values=[""], width=260)
        club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Torneio vinculado").grid(row=option_row + 6, column=0, padx=16, pady=(8, 0), sticky="w")
        tournament_option = ctk.CTkOptionMenu(form, values=["Sem torneio"], width=260)
        tournament_option.grid(row=option_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        selected_event_id: dict[str, int | None] = {"value": None}
        club_option_map: dict[str, int] = {}
        tournament_option_map: dict[str, int | None] = {"Sem torneio": None}

        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por titulo, local, clube ou torneio")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        start_filter = ctk.CTkEntry(controls, placeholder_text="Inicio", width=120)
        start_filter.grid(row=0, column=1, padx=4)
        end_filter = ctk.CTkEntry(controls, placeholder_text="Fim", width=120)
        end_filter.grid(row=0, column=2, padx=4)
        status_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos"] + list(EVENT_STATUS_VALUES.keys()),
            width=140,
        )
        status_filter.grid(row=0, column=3, padx=4)

        events_holder = self._make_panel(right_panel)
        events_holder.grid(row=1, column=0, sticky="nsew")
        events_holder.grid_columnconfigure(0, weight=1)
        events_holder.grid_rowconfigure(0, weight=1)
        events_tree = self._make_tree(
            events_holder,
            ["id", "title", "type", "date", "time", "club", "tournament", "location", "status"],
            {
                "id": "ID",
                "title": "Evento",
                "type": "Tipo",
                "date": "Data",
                "time": "Horario",
                "club": "Clube/Escola",
                "tournament": "Torneio",
                "location": "Local",
                "status": "Status",
            },
            {
                "id": 55,
                "title": 220,
                "type": 100,
                "date": 95,
                "time": 105,
                "club": 150,
                "tournament": 170,
                "location": 140,
                "status": 95,
            },
        )

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

        def load_tournament_options(selected_id: int | None = None) -> None:
            tournament_option_map.clear()
            tournament_option_map["Sem torneio"] = None
            values = ["Sem torneio"]
            for tournament in self.db.list_tournaments():
                label = f"{tournament['id']} - {tournament['name']}"
                values.append(label)
                tournament_option_map[label] = int(tournament["id"])
            tournament_option.configure(values=values)
            chosen = next(
                (
                    label
                    for label, tournament_id in tournament_option_map.items()
                    if tournament_id == selected_id
                ),
                "Sem torneio",
            )
            tournament_option.set(chosen)

        def event_payload() -> dict[str, Any]:
            return {
                "club_id": club_option_map.get(club_option.get(), 1),
                "tournament_id": tournament_option_map.get(tournament_option.get()),
                "title": entries["title"].get(),
                "event_type": EVENT_TYPE_VALUES[type_option.get()],
                "event_date": entries["event_date"].get(),
                "start_time": entries["start_time"].get(),
                "end_time": entries["end_time"].get(),
                "location": entries["location"].get(),
                "status": EVENT_STATUS_VALUES[status_option.get()],
                "notes": entries["notes"].get(),
            }

        def clear_form() -> None:
            selected_event_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            type_option.set(EVENT_TYPES["other"])
            status_option.set(EVENT_STATUSES["planned"])
            load_club_options()
            load_tournament_options()

        def load_events() -> None:
            events_tree.delete(*events_tree.get_children())
            query = search_entry.get().strip().casefold()
            selected_status = status_filter.get()
            for event in self.event_service.events_report(start_filter.get(), end_filter.get()):
                if selected_status != "Todos" and event["status"] != EVENT_STATUS_VALUES[selected_status]:
                    continue
                searchable = " ".join(
                    [
                        str(event.get("title") or ""),
                        str(event.get("club_name") or ""),
                        str(event.get("tournament_name") or ""),
                        str(event.get("location") or ""),
                        str(event.get("event_type") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                time_value = f"{event['start_time']} - {event['end_time']}".strip(" -")
                events_tree.insert(
                    "",
                    "end",
                    values=(
                        event["id"],
                        event["title"],
                        EVENT_TYPES.get(event["event_type"], event["event_type"]),
                        event["event_date"],
                        time_value,
                        event.get("club_name") or "",
                        event.get("tournament_name") or "",
                        event["location"],
                        EVENT_STATUSES.get(event["status"], event["status"]),
                    ),
                )

        def selected_event() -> dict[str, Any] | None:
            selected = events_tree.selection()
            if not selected:
                return None
            event_id = int(events_tree.item(selected[0], "values")[0])
            return self.db.get_club_event(event_id)

        def select_event_in_tree(event_id: int) -> None:
            for item_id in events_tree.get_children():
                values = events_tree.item(item_id, "values")
                if values and int(values[0]) == event_id:
                    events_tree.selection_set(item_id)
                    events_tree.see(item_id)
                    on_event_select()
                    return

        def on_event_select(_event: Any = None) -> None:
            event = selected_event()
            if not event:
                return
            selected_event_id["value"] = int(event["id"])
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(event.get(key) or ""))
            type_option.set(EVENT_TYPES.get(event["event_type"], EVENT_TYPES["other"]))
            status_option.set(EVENT_STATUSES.get(event["status"], EVENT_STATUSES["planned"]))
            load_club_options(int(event.get("club_id") or 1))
            load_tournament_options(event.get("tournament_id"))

        def save_event() -> None:
            try:
                event_id = self.event_service.save_event(event_payload(), selected_event_id["value"])
                load_events()
                select_event_in_tree(event_id)
            except Exception as exc:
                self._show_error(exc)

        def sync_tournament_event() -> None:
            try:
                tournament_id = tournament_option_map.get(tournament_option.get())
                if not tournament_id:
                    raise AppError("Selecione um torneio.")
                event_id = self.event_service.sync_tournament_event(tournament_id)
                load_events()
                select_event_in_tree(event_id)
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Novo evento", clear_form),
            ("Salvar evento", save_event),
            ("Sincronizar torneio", sync_tournament_event),
        ]
        self._grid_form_buttons(form, buttons, option_row + 8)

        ctk.CTkButton(controls, text="Filtrar", command=load_events).grid(row=0, column=4, padx=(8, 0))
        events_tree.bind("<<TreeviewSelect>>", on_event_select)
        search_entry.bind("<KeyRelease>", lambda _event: load_events())
        start_filter.bind("<KeyRelease>", lambda _event: load_events())
        end_filter.bind("<KeyRelease>", lambda _event: load_events())
        status_filter.configure(command=lambda _value: load_events())

        clear_form()
        status_filter.set("Todos")
        load_events()

    def show_internal_ranking(self) -> None:
        self._clear_content()
        self._page_title(
            "Ranking interno",
            "Acompanhe rating, aproveitamento e historico esportivo dos membros.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(3, weight=1)

        categories = sorted(
            {
                str(member.get("category") or "").strip()
                for member in self.db.list_members(active_only=False)
                if str(member.get("category") or "").strip()
            },
            key=lambda value: value.casefold(),
        )
        ctk.CTkLabel(toolbar, text="Categoria").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        category_option = ctk.CTkOptionMenu(toolbar, values=["Todas"] + categories, width=170)
        category_option.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")

        club_option_map: dict[str, int | None] = {"Todos clubes": None}
        class_option_map: dict[str, int | None] = {"Todas turmas": None}

        ctk.CTkLabel(toolbar, text="Clube/Escola").grid(row=0, column=1, padx=(0, 12), pady=(12, 4), sticky="w")
        club_option = ctk.CTkOptionMenu(toolbar, values=["Todos clubes"], width=170)
        club_option.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="w")

        ctk.CTkLabel(toolbar, text="Turma").grid(row=0, column=2, padx=(0, 12), pady=(12, 4), sticky="w")
        class_option = ctk.CTkOptionMenu(toolbar, values=["Todas turmas"], width=160)
        class_option.grid(row=1, column=2, padx=(0, 12), pady=(0, 12), sticky="w")

        ctk.CTkLabel(toolbar, text="Busca").grid(row=0, column=3, padx=(0, 12), pady=(12, 4), sticky="w")
        search_entry = ctk.CTkEntry(toolbar, placeholder_text="Buscar por nome, clube, turma ou categoria")
        search_entry.grid(row=1, column=3, padx=(0, 12), pady=(0, 12), sticky="ew")

        ctk.CTkLabel(toolbar, text="Inicio").grid(row=0, column=4, padx=(0, 8), pady=(12, 4), sticky="w")
        start_filter = ctk.CTkEntry(toolbar, placeholder_text="AAAA-MM-DD", width=115)
        start_filter.grid(row=1, column=4, padx=(0, 8), pady=(0, 12), sticky="w")

        ctk.CTkLabel(toolbar, text="Fim").grid(row=0, column=5, padx=(0, 8), pady=(12, 4), sticky="w")
        end_filter = ctk.CTkEntry(toolbar, placeholder_text="AAAA-MM-DD", width=115)
        end_filter.grid(row=1, column=5, padx=(0, 8), pady=(0, 12), sticky="w")

        status_option = ctk.CTkOptionMenu(toolbar, values=["Ativos", "Todos"], width=120)
        status_option.grid(row=1, column=6, padx=(0, 12), pady=(0, 12), sticky="w")

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            table_panel,
            [
                "pos",
                "name",
                "rating",
                "delta",
                "games",
                "score",
                "record",
                "category",
                "age_category",
                "rating_category",
                "tags",
                "club",
                "class",
                "performance",
            ],
            {
                "pos": "Pos",
                "name": "Membro",
                "rating": "Rating",
                "delta": "Var.",
                "games": "Partidas",
                "score": "Aprov.",
                "record": "V/E/D/B",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "club": "Clube/Escola",
                "class": "Turma",
                "performance": "Ult. perf.",
            },
            {
                "pos": 55,
                "name": 220,
                "rating": 80,
                "delta": 70,
                "games": 75,
                "score": 75,
                "record": 95,
                "category": 110,
                "age_category": 85,
                "rating_category": 95,
                "tags": 150,
                "club": 160,
                "class": 140,
                "performance": 85,
            },
        )
        ranking_member_map: dict[str, int] = {}

        def selected_club_id() -> int | None:
            return club_option_map.get(club_option.get())

        def selected_class_id() -> int | None:
            return class_option_map.get(class_option.get())

        def load_class_options(club_id: int | None = None) -> None:
            current = class_option.get()
            class_option_map.clear()
            class_option_map["Todas turmas"] = None
            values = ["Todas turmas"]
            for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                label = f"{class_data['id']} - {class_data['name']}"
                values.append(label)
                class_option_map[label] = int(class_data["id"])
            class_option.configure(values=values)
            class_option.set(current if current in values else "Todas turmas")

        def load_club_options() -> None:
            current = club_option.get()
            club_option_map.clear()
            club_option_map["Todos clubes"] = None
            values = ["Todos clubes"]
            for club in self.db.list_clubs(active_only=True):
                label = f"{club['id']} - {club['name']}"
                values.append(label)
                club_option_map[label] = int(club["id"])
            club_option.configure(values=values)
            club_option.set(current if current in values else "Todos clubes")
            load_class_options(selected_club_id())

        def on_club_change(_value: str) -> None:
            load_class_options(selected_club_id())
            load_ranking()

        def selected_category() -> str:
            value = category_option.get()
            return "" if value == "Todas" else value

        def load_ranking() -> None:
            tree.delete(*tree.get_children())
            ranking_member_map.clear()
            query = search_entry.get().strip().casefold()
            ranking = self.internal_rating_service.ranking(
                category=selected_category(),
                active_only=status_option.get() == "Ativos",
                club_id=selected_club_id(),
                class_id=selected_class_id(),
                start_date=start_filter.get(),
                end_date=end_filter.get(),
            )
            for item in ranking:
                searchable = " ".join(
                    [
                        str(item.get("name") or ""),
                        str(item.get("club_name") or ""),
                        str(item.get("class_name") or ""),
                        str(item.get("category") or ""),
                        str(item.get("age_category") or ""),
                        str(item.get("rating_category") or ""),
                        str(item.get("prize_tags") or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                delta = int(item["last_delta"] or 0)
                row_id = tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item["rating"],
                        f"+{delta}" if delta > 0 else str(delta),
                        item["games"],
                        f"{item['score_rate']}%",
                        f"{item['wins']}/{item['draws']}/{item['losses']}/{item['byes']}",
                        item["category"],
                        item["age_category"],
                        item["rating_category"],
                        item["prize_tags"],
                        item["club_name"],
                        item["class_name"],
                        item["last_performance"],
                    ),
                )
                ranking_member_map[row_id] = int(item["member_id"])

        def selected_member_id() -> int | None:
            selected = tree.selection()
            if not selected:
                return None
            return ranking_member_map.get(selected[0])

        def show_rating_history() -> None:
            try:
                member_id = selected_member_id()
                if not member_id:
                    raise AppError("Selecione um membro.")
                history = self.internal_rating_service.member_rating_history(member_id)
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

        def apply_selected_tournament_rating() -> None:
            try:
                if not self.current_tournament_id:
                    raise AppError("Selecione um torneio antes de atualizar o rating interno.")
                tournament_id = int(self.current_tournament_id)

                def show_result(result: dict[str, Any]) -> None:
                    self._show_info(
                        "Ratings internos atualizados: {updated}\n"
                        "Ja aplicados anteriormente: {duplicates}\n"
                        "Sem performance suficiente: {skipped}\n"
                        "Convidados externos ignorados: {external}".format(**result)
                    )
                    load_ranking()

                self._run_background(
                    lambda: self.internal_rating_service.apply_tournament_ratings(tournament_id),
                    show_result,
                    "Atualizando rating interno...",
                )
            except Exception as exc:
                self._show_error(exc)

        def export_ranking() -> None:
            try:
                category = selected_category()
                safe_category = self._safe_filename(category or "geral", "geral")
                file_path = filedialog.asksaveasfilename(
                    title="Exportar ranking interno",
                    initialdir=str(self._default_export_dir()),
                    initialfile=f"ranking_interno_{safe_category}.xlsx",
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
                    lambda: self.export_service.export_internal_ranking_report(
                        path,
                        category=category,
                        club_id=selected_club_id(),
                        class_id=selected_class_id(),
                        start_date=start_filter.get(),
                        end_date=end_filter.get(),
                    ),
                    lambda _result: self._show_info(f"Relatorio exportado:\n{path}"),
                    "Exportando ranking interno...",
                )
            except Exception as exc:
                self._show_error(exc)

        def print_ranking() -> None:
            try:
                import tempfile
                import os
                category = selected_category()
                fd, temp_path_str = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                path = Path(temp_path_str)

                self._run_background(
                    lambda: self.export_service.export_internal_ranking_report(
                        path,
                        category=category,
                        club_id=selected_club_id(),
                        class_id=selected_class_id(),
                        start_date=start_filter.get(),
                        end_date=end_filter.get(),
                    ),
                    lambda _result: self._print_document(path),
                    "Preparando impressão...",
                )
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(toolbar, text="Recalcular", command=load_ranking).grid(
            row=2,
            column=0,
            padx=(12, 8),
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(toolbar, text="Aplicar torneio atual", command=apply_selected_tournament_rating).grid(
            row=2,
            column=1,
            padx=(0, 8),
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(toolbar, text="Historico", command=show_rating_history).grid(
            row=2,
            column=2,
            padx=(0, 8),
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(toolbar, text="Exportar", command=export_ranking).grid(
            row=2,
            column=3,
            padx=(0, 8),
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(toolbar, text="Imprimir", command=print_ranking).grid(
            row=2,
            column=4,
            padx=(0, 8),
            pady=(0, 12),
            sticky="w",
        )

        category_option.configure(command=lambda _value: load_ranking())
        club_option.configure(command=on_club_change)
        class_option.configure(command=lambda _value: load_ranking())
        status_option.configure(command=lambda _value: load_ranking())
        search_entry.bind("<KeyRelease>", lambda _event: load_ranking())
        start_filter.bind("<KeyRelease>", lambda _event: load_ranking())
        end_filter.bind("<KeyRelease>", lambda _event: load_ranking())
        tree.bind("<Double-1>", lambda _event: show_rating_history())
        category_option.set("Todas")
        status_option.set("Ativos")
        load_club_options()
        load_ranking()

    def show_communications(self) -> None:
        self._clear_content()
        self._page_title("Comunicação e Avisos", "Gerencie murais e envio de boletins.")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # Painel Esquerdo: Avisos Ativos
        left_panel = self._make_panel(body)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_panel, text="Mural de Avisos", font=("Inter", 16, "bold")).grid(row=0, column=0, padx=16, pady=16, sticky="w")
        
        columns = ["id", "title", "category", "expiration_date"]
        headings = {"id": "ID", "title": "Título", "category": "Categoria", "expiration_date": "Expira em"}
        widths = {"id": 50, "title": 200, "category": 100, "expiration_date": 100}
        
        tree_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        tree_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        tree = self._make_tree(tree_frame, columns, headings, widths)
        
        def load_announcements() -> None:
            for item in tree.get_children():
                tree.delete(item)
            try:
                announcements = self.communication_service.get_active_announcements()
                for a in announcements:
                    tree.insert("", "end", values=(
                        a.get("id", ""),
                        a.get("title", ""),
                        a.get("category", ""),
                        a.get("expiration_date", "Nunca") or "Nunca"
                    ))
            except Exception as e:
                logger.error(f"Erro ao carregar avisos: {e}")

        def add_announcement() -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Novo Aviso")
            dialog.geometry("400x350")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Título:").pack(pady=(10, 0), padx=10, anchor="w")
            title_entry = ctk.CTkEntry(dialog, width=380)
            title_entry.pack(pady=(0, 10), padx=10)

            ctk.CTkLabel(dialog, text="Categoria:").pack(pady=(0, 0), padx=10, anchor="w")
            cat_entry = ctk.CTkEntry(dialog, width=380, placeholder_text="Ex: Importante, Torneio, Geral")
            cat_entry.pack(pady=(0, 10), padx=10)

            ctk.CTkLabel(dialog, text="Expira em (YYYY-MM-DD):").pack(pady=(0, 0), padx=10, anchor="w")
            exp_entry = ctk.CTkEntry(dialog, width=380, placeholder_text="Deixe em branco para aviso permanente")
            exp_entry.pack(pady=(0, 10), padx=10)

            ctk.CTkLabel(dialog, text="Conteúdo:").pack(pady=(0, 0), padx=10, anchor="w")
            content_text = ctk.CTkTextbox(dialog, width=380, height=80)
            content_text.pack(pady=(0, 10), padx=10)

            def save():
                try:
                    payload = {
                        "title": title_entry.get().strip(),
                        "category": cat_entry.get().strip() or "general",
                        "expiration_date": exp_entry.get().strip(),
                        "content": content_text.get("1.0", "end").strip()
                    }
                    self.communication_service.save_announcement(payload)
                    dialog.destroy()
                    load_announcements()
                    self._show_info("Aviso salvo com sucesso!")
                except Exception as e:
                    self._show_error(e)

            ctk.CTkButton(dialog, text="Salvar", command=save).pack(pady=10)

        def del_announcement() -> None:
            selected = tree.selection()
            if not selected:
                self._show_info("Selecione um aviso para excluir.")
                return
            item_id = int(tree.item(selected[0], "values")[0])
            try:
                self.communication_service.delete_announcement(item_id)
                load_announcements()
            except Exception as e:
                self._show_error(e)

        btn_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        ctk.CTkButton(btn_frame, text="Novo Aviso", command=add_announcement).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Excluir Aviso", command=del_announcement, fg_color="#ef4444", hover_color="#dc2626").pack(side="left")

        # Painel Direito: Envio de Mensagens e Logs
        right_panel = self._make_panel(body)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        ctk.CTkLabel(right_panel, text="Envio de Mensagens (Logs)", font=("Inter", 16, "bold")).pack(pady=16, padx=16, anchor="w")
        ctk.CTkLabel(right_panel, text="Em breve: Integração com Email e WhatsApp.\nAtualmente, os registros são feitos automaticamente pelas rotinas financeiras e de secretaria.", text_color="gray", justify="left").pack(padx=16, anchor="w")

        load_announcements()


