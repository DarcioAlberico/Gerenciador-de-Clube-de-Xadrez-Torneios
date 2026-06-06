from __future__ import annotations

from ..support import *


# Sub-mixin de Admin: calendario, ranking interno e comunicacoes.
class CalendarRankingMixin:
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
                    self._show_toast("Aviso salvo com sucesso!", kind="success")
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
        ctk.CTkButton(btn_frame, text="Excluir Aviso", command=del_announcement, fg_color=THEME_DANGER, hover_color=THEME_DANGER_HOVER).pack(side="left")

        # Painel Direito: Envio de Mensagens e Logs
        right_panel = self._make_panel(body)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        ctk.CTkLabel(right_panel, text="Envio de Mensagens (Logs)", font=("Inter", 16, "bold")).pack(pady=16, padx=16, anchor="w")
        ctk.CTkLabel(right_panel, text="Em breve: Integração com Email e WhatsApp.\nAtualmente, os registros são feitos automaticamente pelas rotinas financeiras e de secretaria.", text_color="gray", justify="left").pack(padx=16, anchor="w")

        load_announcements()
