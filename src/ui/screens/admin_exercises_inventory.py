from __future__ import annotations

from ..support import *
from ..components import WrapRow, debounce


# Sub-mixin de Admin: exercicios e inventario.
class ExercisesInventoryMixin:
    def show_exercises(self) -> None:
        self._clear_content()
        self._page_title(
            "Exercícios e listas",
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
            ("title", "Título"),
            ("theme", "Tema"),
            ("source", "Fonte"),
            ("fen", "FEN"),
            ("pgn", "PGN"),
            ("solution", "Solucao"),
            ("objective", "Objetivo"),
            ("tags", "Tags"),
            ("notes", "Observações"),
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

        ctk.CTkLabel(form, text="Nível pedagogico").grid(
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

        # Faixa que quebra em quantas linhas couberem (continuacao da B-8).
        controls = WrapRow(right_panel)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_entry = controls.add(
            ctk.CTkEntry(
                controls.frame, placeholder_text="Buscar exercicio, tema, FEN, PGN, solucao ou tags"
            ),
            width=240,
            grow=True,
        )
        difficulty_filter = controls.add(
            ctk.CTkOptionMenu(
                controls.frame,
                values=["Todas", *EXERCISE_DIFFICULTY_VALUES.keys()],
                width=145,
            ),
            width=145,
        )
        active_filter = controls.add(
            ctk.CTkOptionMenu(controls.frame, values=["Ativos", "Todos"], width=105), width=105
        )

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
                "level": "Nível",
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
        # Seis campos da lista de treino numa linha rigida: era o que segurava
        # esta tela em 1.272px, depois da faixa de busca (continuacao da B-8).
        list_fields = WrapRow(list_form)
        list_fields.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        list_name_entry = list_fields.add(
            ctk.CTkEntry(list_fields.frame, placeholder_text="Nome da lista"),
            width=200,
            grow=True,
        )
        list_date_entry = list_fields.add(
            self._make_date_entry(list_fields.frame, width=12), width=120
        )
        list_status_option = list_fields.add(
            ctk.CTkOptionMenu(
                list_fields.frame, values=list(TRAINING_LIST_STATUS_VALUES.keys()), width=130
            ),
            width=130,
        )
        list_club_option = list_fields.add(
            ctk.CTkOptionMenu(list_fields.frame, values=[""], width=180), width=180
        )
        list_class_option = list_fields.add(
            ctk.CTkOptionMenu(list_fields.frame, values=["Sem turma"], width=150), width=150
        )
        list_level_option = list_fields.add(
            ctk.CTkOptionMenu(list_fields.frame, values=["Sem nivel"], width=150), width=150
        )
        list_buttons = ctk.CTkFrame(list_fields.frame, fg_color="transparent")
        list_fields.add(list_buttons, width=160)
        list_description_entry = ctk.CTkEntry(list_form, placeholder_text="Descrição da lista")
        list_description_entry.grid(row=1, column=0, padx=12, pady=(4, 10), sticky="ew")

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
                "level": "Nível",
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

        item_controls = WrapRow(right_panel)
        item_controls.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        item_controls.add(
            ctk.CTkButton(
                item_controls.frame,
                text="Adicionar exercicio selecionado",
                command=lambda: add_selected_exercise(),
                width=240,
            ),
            width=240,
        )
        item_controls.add(
            ctk.CTkButton(
                item_controls.frame,
                text="Remover da lista",
                command=lambda: remove_selected_item(),
                width=150,
            ),
            width=150,
        )
        item_controls.bind_to(self.content)

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
                "level": "Nível",
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

        controls.add(
            ctk.CTkButton(controls.frame, text="Filtrar", command=refresh_all, width=100),
            width=100,
        )
        controls.bind_to(self.content)
        ctk.CTkButton(list_buttons, text="Nova", width=70, command=clear_list_form).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(list_buttons, text="Salvar", width=80, command=save_training_list).grid(row=0, column=1)
        list_fields.bind_to(self.content)

        exercises_tree.bind("<<TreeviewSelect>>", on_exercise_select)
        lists_tree.bind("<<TreeviewSelect>>", on_list_select)
        search_entry.bind("<KeyRelease>", debounce(search_entry, refresh_all))
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
            ("code", "Código"),
            ("name", "Nome"),
            ("quantity_total", "Quantidade"),
            ("storage_location", "Local"),
            ("acquisition_date", "Aquisicao"),
            ("acquisition_value", "Valor"),
            ("notes", "Observações"),
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
            ("open_maintenance", "Manutenção"),
        ]
        for index, (key, label) in enumerate(summary_items):
            card = ctk.CTkFrame(summary_panel, fg_color=THEME_APP_BG, corner_radius=8)
            card.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            value_label = ctk.CTkLabel(card, text="0", font=font_kpi_value())
            value_label.pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=12, pady=(0, 10))
            summary_labels[key] = value_label

        # Faixa que quebra em quantas linhas couberem (continuacao da B-8).
        controls = WrapRow(right_panel)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        search_entry = controls.add(
            ctk.CTkEntry(
                controls.frame, placeholder_text="Buscar por codigo, item, local ou observacao"
            ),
            width=240,
            grow=True,
        )
        type_filter = controls.add(
            ctk.CTkOptionMenu(
                controls.frame, values=["Todos", *INVENTORY_ITEM_TYPE_VALUES.keys()], width=140
            ),
            width=140,
        )
        active_filter = controls.add(
            ctk.CTkOptionMenu(controls.frame, values=["Ativos", "Todos"], width=105), width=105
        )

        items_holder = self._make_panel(right_panel)
        items_holder.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        items_holder.grid_columnconfigure(0, weight=1)
        items_holder.grid_rowconfigure(0, weight=1)
        items_tree = self._make_tree(
            items_holder,
            ["id", "code", "name", "type", "total", "available", "condition", "location", "club"],
            {
                "id": "ID",
                "code": "Código",
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
        ctk.CTkLabel(loan_box, text="Emprestimo", font=font_subsection()).grid(
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
        loan_notes_entry = ctk.CTkEntry(loan_box, placeholder_text="Observações")
        loan_notes_entry.grid(row=2, column=0, columnspan=2, padx=(0, 6), pady=4, sticky="ew")
        loan_actions = ctk.CTkFrame(loan_box, fg_color="transparent")
        loan_actions.grid(row=2, column=2, columnspan=2, pady=4, sticky="e")

        maintenance_box = ctk.CTkFrame(detail_form, fg_color="transparent")
        maintenance_box.grid(row=1, column=0, columnspan=2, padx=12, pady=(4, 10), sticky="ew")
        maintenance_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(maintenance_box, text="Manutenção", font=font_subsection()).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
        )
        maintenance_description_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Descrição")
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
        maintenance_notes_entry = ctk.CTkEntry(maintenance_box, placeholder_text="Observações")
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
                "description": "Manutenção",
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

        controls.add(
            ctk.CTkButton(controls.frame, text="Filtrar", command=refresh_all, width=100),
            width=100,
        )
        controls.bind_to(self.content)
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
        search_entry.bind("<KeyRelease>", debounce(search_entry, refresh_all))
        type_filter.configure(command=lambda _value: refresh_all())
        active_filter.configure(command=lambda _value: refresh_all())

        clear_item_form()
        refresh_all()
