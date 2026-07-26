from __future__ import annotations

from ..support import *
from ..components import debounce

from src.services.pairing.acceleration import acceleration_spec
from src.services.pairing import (
    DEFAULT_PLAYER_TIEBREAKS,
    DEFAULT_TEAM_TIEBREAKS,
    PLAYER_TIEBREAKS,
    TEAM_TIEBREAKS,
    parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
)
from src.services.prizes import PRIZE_POLICIES
from src.services.list_layouts import DEFAULT_STANDINGS_COLUMNS, STANDINGS_COLUMNS
from src.services.chess_results import normalize_results_url


class TournamentPlayersMixin:
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
            ("title", "Título"),
            ("sex", "Sexo"),
            ("rating", "Rating principal"),
            ("national_rating", "Rating nacional"),
            ("international_rating", "Rating internacional"),
            ("fide_id", "FIDE ID"),
            ("cbx_id", "CBX ID"),
            ("lbx_id", "LBX ID"),
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
            
            if key in ["fide_id", "cbx_id", "lbx_id"]:
                def autofill_from_official(event, current_key=key):
                    val = entries[current_key].get().strip()
                    if not val:
                        return
                    
                    params = {current_key: val}
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
                        update_if_empty("lbx_id", player.get("lbx_id"))
                    elif current_key == "cbx_id":
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

        ctk.CTkLabel(form, text="Grupo Scheveningen").grid(
            row=control_row + 7, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        scheveningen_group_labels = {"": "Sem grupo", "A": "Grupo A", "B": "Grupo B"}
        scheveningen_group_values = {label: code for code, label in scheveningen_group_labels.items()}
        scheveningen_group_option = ctk.CTkOptionMenu(
            form, values=list(scheveningen_group_labels.values()), width=240
        )
        scheveningen_group_option.grid(row=control_row + 8, column=0, padx=16, pady=(4, 4), sticky="ew")
        scheveningen_group_option.set("Sem grupo")

        def update_scheveningen_group() -> None:
            try:
                player = selected_player()
                if not player:
                    raise AppError("Selecione um jogador.")
                self.db.set_player_scheveningen_group(
                    int(player["id"]),
                    scheveningen_group_values.get(scheveningen_group_option.get(), ""),
                )
                load_players()
                self._show_toast("Grupo Scheveningen definido.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        btn_scheveningen_group = ctk.CTkButton(
            form, text="Definir grupo Scheveningen", command=update_scheveningen_group
        )
        btn_scheveningen_group.grid(row=control_row + 9, column=0, padx=16, pady=(0, 8), sticky="ew")
        self._disable_if_unauthorized(btn_scheveningen_group, "tournament_write")

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
            "lbx",
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
                "lbx": "LBX",
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
                "lbx": 90,
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
                        str(player.get("lbx_id") or ""),
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
                        player.get("lbx_id", ""),
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
            scheveningen_group_option.set(
                scheveningen_group_labels.get(
                    str(player.get("scheveningen_group") or "").strip().upper(), "Sem grupo"
                )
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
                # Modo Livre: se ha rodadas encerradas, pergunta 0,0 ou meio-ponto
                # (0,5) por rodada ausente. Fora do Modo Livre devolve (True, None)
                # e o calculo padrao de late_entry_points segue intacto.
                proceed, late_points = self.prepare_late_entry(
                    self.current_tournament_id
                )
                if not proceed:
                    return
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
                    lbx_id=entries["lbx_id"].get(),
                    national_rating=national_rating,
                    international_rating=international_rating,
                    player_status=PLAYER_STATUS_VALUES[player_status_option.get()],
                    starting_points=late_points,
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
                    lbx_id=entries["lbx_id"].get(),
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
                confirmed = self._confirm_action(
                    "Excluir jogador",
                    "Excluir este jogador do torneio?\n\n"
                    "A exclusao so e permitida se ele ainda nao apareceu em nenhuma rodada.",
                    danger=True,
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
                self._show_toast("Jogador excluido do torneio.", kind="success")
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

        def show_online_registration_preview(
            result: dict[str, Any], importer: Callable[[], dict[str, Any]]
        ) -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Inscrições online")
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
                font=font_section(),
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
                    importer,
                    show_result,
                    "Importando inscricoes online...",
                )

            ctk.CTkButton(actions, text="Cancelar", fg_color=THEME_NEUTRAL, hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy).pack(
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
                    lambda result: show_online_registration_preview(
                        result,
                        lambda: self.import_service.import_online_registrations(tournament_id, file_path),
                    ),
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
                    lambda result: show_online_registration_preview(
                        result,
                        lambda: self.import_service.import_online_registrations(tournament_id, source_url),
                    ),
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

        def show_form_link_dialog(result: dict[str, str]) -> None:
            responder_url = result.get("responder_url", "")
            edit_url = result.get("edit_url", "")
            dialog = ctk.CTkToplevel(self)
            dialog.title("Formulario criado no Google Forms")
            dialog.geometry("640x300")
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                dialog,
                text="Formulario criado! Envie o link de resposta aos jogadores:",
                font=font_section(),
                text_color=THEME_TEXT_MAIN,
                wraplength=600,
                justify="left",
            ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

            link_box = ctk.CTkTextbox(dialog, height=70, wrap="word")
            link_box.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
            link_box.insert("1.0", f"Link para jogadores:\n{responder_url}\n\nEdicao (arbitro):\n{edit_url}")
            link_box.configure(state="disabled")

            ctk.CTkLabel(
                dialog,
                text=(
                    "No Google Forms, abra Respostas > vincular a uma planilha. Depois "
                    "baixe a planilha como CSV e importe em 'Importar link Forms/Sheets'."
                ),
                text_color=THEME_TEXT_SUB,
                wraplength=600,
                justify="left",
            ).grid(row=2, column=0, padx=16, pady=(0, 8), sticky="w")

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="e")

            def copy_link() -> None:
                self.clipboard_clear()
                self.clipboard_append(responder_url)

            def open_link() -> None:
                if responder_url:
                    webbrowser.open(responder_url)

            ctk.CTkButton(actions, text="Copiar link", command=copy_link).pack(side="left", padx=(0, 8))
            ctk.CTkButton(actions, text="Abrir formulario", command=open_link).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions, text="Fechar", fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy,
            ).pack(side="left")

        def generate_form_script(tournament_id: int, info_prefix: str = "") -> None:
            file_path = filedialog.asksaveasfilename(
                title="Gerar script do formulario (Google Apps Script)",
                initialdir=str(self._default_export_dir()),
                initialfile="formulario_inscricao.gs",
                defaultextension=".gs",
                filetypes=[("Google Apps Script", "*.gs"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return

            def show_result(result: dict[str, Any]) -> None:
                self._show_info(
                    info_prefix
                    + "Script do formulario gerado.\n\n"
                    f"Script (cole em script.google.com):\n{result['script_path']}\n\n"
                    f"Definicao dos campos:\n{result['definition_path']}\n\n"
                    "Abra o script, execute a funcao criarFormularioInscricao e siga o "
                    "passo a passo no cabecalho."
                )

            self._run_background(
                lambda: self.export_service.export_registration_form(file_path, tournament_id),
                show_result,
                "Gerando script do formulario...",
            )

        def generate_registration_form() -> None:
            try:
                tournament_id = int(self.current_tournament_id)
                tournament = self.db.get_tournament(tournament_id)
                title = (
                    f"Inscrição - {tournament['name']}"
                    if tournament and tournament.get("name")
                    else "Inscrição no torneio"
                )

                if not self.google_forms_service.is_configured():
                    reason = self.google_forms_service.unavailable_reason()
                    if not self._confirm_action(
                        "Criar formulario online",
                        "A criacao automatica no Google Forms ainda nao esta configurada.\n\n"
                        f"{reason}\n\n"
                        "Deseja gerar o script para criar o formulario manualmente "
                        "(cole 1x em script.google.com)?",
                    ):
                        return
                    generate_form_script(tournament_id)
                    return

                def work() -> dict[str, Any]:
                    try:
                        created = self.google_forms_service.create_registration_form(title)
                        return {"mode": "live", **created}
                    except Exception as exc:  # rede/credencial/autorizacao
                        return {"mode": "error", "reason": str(exc)}

                def show_result(result: dict[str, Any]) -> None:
                    if result.get("mode") == "live":
                        show_form_link_dialog(result)
                        return
                    if self._confirm_action(
                        "Criar formulario online",
                        "Nao foi possivel criar o formulario no Google Forms agora.\n\n"
                        f"{result.get('reason', '')}\n\n"
                        "Deseja gerar o script para criar manualmente?",
                    ):
                        generate_form_script(tournament_id)

                self._run_background(work, show_result, "Criando formulario no Google Forms...")
            except Exception as exc:
                self._show_error(exc)

        def show_share_link_dialog(url: str) -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Link de inscricao")
            dialog.geometry("640x260")
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                dialog,
                text="Link de inscricao (nome do torneio ja preenchido). Envie aos jogadores:",
                font=font_section(),
                text_color=THEME_TEXT_MAIN,
                wraplength=600,
                justify="left",
            ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

            link_box = ctk.CTkTextbox(dialog, height=80, wrap="word")
            link_box.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
            link_box.insert("1.0", url)
            link_box.configure(state="disabled")

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="e")

            def copy_link() -> None:
                self.clipboard_clear()
                self.clipboard_append(url)

            ctk.CTkButton(actions, text="Copiar link", command=copy_link).pack(side="left", padx=(0, 8))
            ctk.CTkButton(actions, text="Abrir no navegador", command=lambda: webbrowser.open(url)).pack(
                side="left", padx=(0, 8)
            )
            ctk.CTkButton(
                actions, text="Fechar", fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy,
            ).pack(side="left")

        def configure_registration_form() -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Configurar formulario de inscricao (link)")
            dialog.geometry("700x440")
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                dialog,
                text=(
                    "Como obter o link (uma vez):\n"
                    "1) Abra seu formulario no Google Forms.\n"
                    "2) Menu (tres pontos) > 'Receber link preenchido automaticamente'.\n"
                    "3) Preencha SO o campo do torneio com um exemplo e clique em obter link.\n"
                    "4) Cole o link gerado abaixo e clique em Analisar."
                ),
                justify="left",
                wraplength=660,
                text_color=THEME_TEXT_SUB,
            ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

            current = self.export_service.registration_form_config()
            status = "Atual: nao configurado" if not current["base_url"] else f"Atual: {current['base_url']}"
            ctk.CTkLabel(dialog, text=status, text_color=THEME_TEXT_SUB, wraplength=660, justify="left").grid(
                row=1, column=0, padx=16, pady=(0, 6), sticky="w"
            )

            link_box = ctk.CTkTextbox(dialog, height=90, wrap="word")
            link_box.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

            entry_var = ctk.StringVar(value="")
            entry_menu = ctk.CTkOptionMenu(
                dialog, values=["(analise o link primeiro)"], variable=entry_var, width=620
            )
            entry_menu.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
            label_to_entry: dict[str, str] = {}

            def analyze() -> None:
                try:
                    parsed = self.export_service.parse_prefill_link(link_box.get("1.0", "end").strip())
                    labels = []
                    label_to_entry.clear()
                    for eid, value in parsed["entries"]:
                        label = f"{eid} = {value}" if value else eid
                        labels.append(label)
                        label_to_entry[label] = eid
                    entry_menu.configure(values=labels)
                    entry_var.set(labels[0])
                except Exception as exc:
                    self._show_error(exc)

            def save() -> None:
                try:
                    eid = label_to_entry.get(entry_var.get(), "")
                    if not eid:
                        self._show_error(AppError("Analise o link e selecione o campo do torneio."))
                        return
                    self.export_service.save_registration_form_config(
                        link_box.get("1.0", "end").strip(), eid
                    )
                    dialog.destroy()
                    self._show_info("Formulario de inscricao configurado.")
                except Exception as exc:
                    self._show_error(exc)

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="e")
            ctk.CTkButton(actions, text="Analisar", command=analyze).pack(side="left", padx=(0, 8))
            ctk.CTkButton(actions, text="Salvar", command=save).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions, text="Cancelar", fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy,
            ).pack(side="left")

        def share_registration_form() -> None:
            try:
                tournament_id = int(self.current_tournament_id)
                try:
                    url = self.export_service.registration_prefill_url(tournament_id)
                except AppError as exc:
                    if self._confirm_action(
                        "Formulario de inscricao",
                        f"{exc}\n\nDeseja configurar agora?",
                    ):
                        configure_registration_form()
                    return
                show_share_link_dialog(url)
            except Exception as exc:
                self._show_error(exc)

        def show_mapping_dialog(inspection: dict[str, Any], source: str) -> None:
            headers = list(inspection["headers"])
            fields = list(inspection["fields"])
            ignore_label = "(ignorar)"
            options = [ignore_label, *headers]

            dialog = ctk.CTkToplevel(self)
            dialog.title("Importar com mapeamento de colunas")
            dialog.geometry("760x640")
            dialog.minsize(640, 520)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_rowconfigure(3, weight=1)

            sample = inspection["sample_rows"][0] if inspection["sample_rows"] else {}
            reference = "Colunas detectadas: " + ", ".join(headers)
            if sample:
                reference += "\n\n1a linha: " + " | ".join(
                    f"{header}={str(sample.get(header, '')).strip()}" for header in headers
                )
            ctk.CTkLabel(
                dialog,
                text=(
                    f"Origem: {source}\n{inspection['total_rows']} linha(s). "
                    "Associe cada campo do Albericus a uma coluna. 'Idade' vira ano de "
                    "nascimento; 'Sobrenome, Nome' e dividido automaticamente."
                ),
                font=font_section(),
                text_color=THEME_TEXT_MAIN,
                justify="left",
                wraplength=720,
            ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
            ctk.CTkLabel(
                dialog,
                text=reference,
                text_color=THEME_TEXT_SUB,
                justify="left",
                wraplength=720,
            ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

            field_vars: dict[str, ctk.StringVar] = {}

            def apply_mapping_to_vars(mapping: dict[str, str]) -> None:
                for field in fields:
                    chosen = mapping.get(field["key"], "")
                    field_vars[field["key"]].set(chosen if chosen in headers else ignore_label)

            def current_mapping() -> dict[str, str]:
                mapping: dict[str, str] = {}
                for field in fields:
                    value = field_vars[field["key"]].get()
                    if value and value != ignore_label:
                        mapping[field["key"]] = value
                return mapping

            # --- perfis de mapeamento -------------------------------------
            profiles_row = ctk.CTkFrame(dialog, fg_color="transparent")
            profiles_row.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="ew")
            profiles = self.import_service.list_mapping_profiles()
            profile_var = ctk.StringVar(
                value=next(iter(profiles), "") if profiles else ""
            )
            ctk.CTkLabel(profiles_row, text="Perfil:").pack(side="left", padx=(0, 6))
            profile_menu = ctk.CTkOptionMenu(
                profiles_row,
                values=list(profiles) or ["(nenhum)"],
                variable=profile_var,
                width=200,
            )
            profile_menu.pack(side="left", padx=(0, 6))

            def apply_profile() -> None:
                saved = self.import_service.list_mapping_profiles().get(profile_var.get())
                if saved:
                    apply_mapping_to_vars(saved)

            def save_profile() -> None:
                name = self._ask_string("Perfil de mapeamento", "Nome do perfil:")
                if not name:
                    return
                try:
                    self.import_service.save_mapping_profile(name, current_mapping())
                    refreshed = list(self.import_service.list_mapping_profiles()) or ["(nenhum)"]
                    profile_menu.configure(values=refreshed)
                    profile_var.set(name)
                    self._show_info(f"Perfil '{name}' salvo.")
                except Exception as exc:
                    self._show_error(exc)

            def delete_profile() -> None:
                name = profile_var.get()
                if not name or name == "(nenhum)":
                    return
                self.import_service.delete_mapping_profile(name)
                refreshed = list(self.import_service.list_mapping_profiles()) or ["(nenhum)"]
                profile_menu.configure(values=refreshed)
                profile_var.set(refreshed[0])

            ctk.CTkButton(profiles_row, text="Aplicar", width=80, command=apply_profile).pack(side="left", padx=4)
            ctk.CTkButton(profiles_row, text="Salvar", width=80, command=save_profile).pack(side="left", padx=4)
            ctk.CTkButton(
                profiles_row, text="Excluir", width=80,
                fg_color=THEME_NEUTRAL, hover_color=THEME_NEUTRAL_HOVER, command=delete_profile,
            ).pack(side="left", padx=4)

            # --- seletores por campo --------------------------------------
            selectors = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
            selectors.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="nsew")
            selectors.grid_columnconfigure(1, weight=1)
            for index, field in enumerate(fields):
                label = field["label"] + (" *" if field["required"] else "")
                ctk.CTkLabel(selectors, text=label).grid(
                    row=index, column=0, padx=(0, 10), pady=4, sticky="w"
                )
                var = ctk.StringVar(value=ignore_label)
                field_vars[field["key"]] = var
                ctk.CTkOptionMenu(selectors, values=options, variable=var, width=320).grid(
                    row=index, column=1, pady=4, sticky="ew"
                )
            apply_mapping_to_vars(inspection["suggested_mapping"])

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="e")

            def preview_and_continue() -> None:
                mapping = current_mapping()
                if not mapping.get("name"):
                    self._show_error(AppError("Mapeie a coluna do nome do jogador."))
                    return
                tournament_id = int(self.current_tournament_id)
                dialog.destroy()
                self._run_background(
                    lambda: self.import_service.preview_mapped_registrations(tournament_id, source, mapping),
                    lambda result: show_online_registration_preview(
                        result,
                        lambda: self.import_service.import_mapped_registrations(tournament_id, source, mapping),
                    ),
                    "Conferindo dados mapeados...",
                )

            ctk.CTkButton(
                actions, text="Cancelar", fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER, command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(actions, text="Pre-visualizar e importar", command=preview_and_continue).pack(side="left")

        def import_with_mapping() -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title="Importar com mapeamento (planilha nao padronizada)",
                    filetypes=[
                        ("Planilhas e CSV", "*.csv;*.xls;*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Excel", "*.xls;*.xlsx"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                self._run_background(
                    lambda: self.import_service.inspect_source(file_path),
                    lambda inspection: show_mapping_dialog(inspection, file_path),
                    "Lendo planilha...",
                )
            except Exception as exc:
                self._show_error(exc)

        def import_with_mapping_url() -> None:
            try:
                source_url = self._ask_string(
                    "Importar com mapeamento",
                    "Cole o link CSV publicado do Google Sheets/Forms:",
                )
                if not source_url:
                    return
                source_url = source_url.strip()
                self._run_background(
                    lambda: self.import_service.inspect_source(source_url),
                    lambda inspection: show_mapping_dialog(inspection, source_url),
                    "Lendo planilha...",
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

        def show_official_update_preview(result: dict[str, Any]) -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Pre-visualizacao da atualizacao oficial")
            dialog.geometry("1180x700")
            dialog.minsize(920, 560)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_rowconfigure(1, weight=2)
            dialog.grid_rowconfigure(3, weight=1)

            summary = (
                f"Inscritos: {result['total']} | Correspondencias: {result['matched']} | "
                f"Alteracoes: {result['changed']} | Sem mudanca: {result['unchanged']} | "
                f"Sem correspondencia: {result['unmatched_count']}"
            )
            ctk.CTkLabel(
                dialog,
                text=summary,
                font=font_section(),
                text_color=THEME_TEXT_MAIN,
            ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

            comparison_panel = ctk.CTkFrame(dialog, fg_color="transparent")
            comparison_panel.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")
            comparison_panel.grid_columnconfigure(0, weight=1)
            comparison_panel.grid_rowconfigure(0, weight=1)
            comparison_tree = self._make_tree(
                comparison_panel,
                ["status", "player", "changes", "before", "after"],
                {
                    "status": "Status",
                    "player": "Jogador inscrito",
                    "changes": "Campos alterados",
                    "before": "Antes",
                    "after": "Depois",
                },
                {
                    "status": 90,
                    "player": 210,
                    "changes": 210,
                    "before": 300,
                    "after": 300,
                },
                visible_rows=12,
            )
            comparison_tree.configure(selectmode="extended")
            changed_row_map: dict[str, int] = {}

            def comparison_text(values: dict[str, Any]) -> str:
                return (
                    f"{values['name']} | {values['club']} | {values['title']} | "
                    f"R {values['rating']} / N {values['national_rating']} / I {values['international_rating']}"
                )

            for row in result["rows"]:
                row_id = comparison_tree.insert(
                    "",
                    "end",
                    values=(
                        row["status_label"],
                        row["name"],
                        row["changes_label"],
                        comparison_text(row["before"]),
                        comparison_text(row["after"]),
                    ),
                )
                if row["status"] == "changed":
                    changed_row_map[row_id] = int(row["player_id"])

            selected_count_label = ctk.CTkLabel(
                comparison_panel,
                text="Selecionadas para aplicar: 0",
                text_color=THEME_TEXT_SUB,
            )
            selected_count_label.grid(row=1, column=0, pady=(8, 0), sticky="w")

            ctk.CTkLabel(
                dialog,
                text="Sem correspondencia na base oficial",
                font=font_section(),
                text_color=THEME_TEXT_MAIN,
            ).grid(row=2, column=0, padx=16, pady=(0, 6), sticky="w")
            unmatched_panel = ctk.CTkFrame(dialog, fg_color="transparent")
            unmatched_panel.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
            unmatched_panel.grid_columnconfigure(0, weight=1)
            unmatched_panel.grid_rowconfigure(0, weight=1)
            unmatched_tree = self._make_tree(
                unmatched_panel,
                ["player", "fide", "cbx", "lbx"],
                {"player": "Jogador", "fide": "FIDE ID", "cbx": "CBX ID", "lbx": "LBX ID"},
                {"player": 300, "fide": 150, "cbx": 150, "lbx": 150},
                visible_rows=5,
            )
            for row in result["unmatched"]:
                unmatched_tree.insert(
                    "",
                    "end",
                    values=(row["name"], row["fide_id"], row["cbx_id"], row["lbx_id"]),
                )

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="e")

            def apply_updates() -> None:
                changed_player_ids = [
                    changed_row_map[row_id]
                    for row_id in comparison_tree.selection()
                    if row_id in changed_row_map
                ]
                if not changed_player_ids:
                    return
                dialog.destroy()
                tournament_id = int(self.current_tournament_id)

                def show_update_result(update_result: dict[str, Any]) -> None:
                    load_players()
                    message = f"{update_result['updated']} jogadores atualizados pela base oficial."
                    if update_result["unmatched"]:
                        message += "\n\nSem correspondencia:\n" + "\n".join(update_result["unmatched"][:12])
                    self._show_info(message)

                self._run_background(
                    lambda: self.official_rating_service.apply_tournament_player_updates(
                        tournament_id,
                        changed_player_ids,
                    ),
                    show_update_result,
                    "Aplicando atualizacoes oficiais...",
                )

            def update_selected_count(_event: Any = None) -> None:
                selected = sum(1 for row_id in comparison_tree.selection() if row_id in changed_row_map)
                selected_count_label.configure(text=f"Selecionadas para aplicar: {selected}")
                apply_button.configure(state="normal" if selected else "disabled")

            def select_changed_rows() -> None:
                comparison_tree.selection_set(*changed_row_map)
                update_selected_count()

            def clear_selected_rows() -> None:
                comparison_tree.selection_remove(*comparison_tree.selection())
                update_selected_count()

            ctk.CTkButton(
                actions,
                text="Cancelar",
                fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER,
                command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions,
                text="Limpar selecao",
                fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER,
                command=clear_selected_rows,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions,
                text="Selecionar divergencias",
                command=select_changed_rows,
            ).pack(side="left", padx=(0, 8))
            apply_button = ctk.CTkButton(actions, text="Confirmar alteracoes", command=apply_updates)
            apply_button.pack(side="left")
            comparison_tree.bind("<<TreeviewSelect>>", update_selected_count)
            select_changed_rows()

        def update_official_ratings() -> None:
            try:
                tournament_id = int(self.current_tournament_id)
                self._run_background(
                    lambda: self.official_rating_service.preview_tournament_player_updates(tournament_id),
                    show_official_update_preview,
                    "Comparando ratings oficiais...",
                )
            except Exception as exc:
                self._show_error(exc)

        def update_lbx_base() -> None:
            try:
                def show_import_result(result: dict[str, Any]) -> None:
                    message = f"{result['imported']} jogadores importados da LBX pela internet."
                    if result["errors"]:
                        message += "\n\nErros:\n" + "\n".join(result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    self.official_rating_service.import_lbx_lists_from_url,
                    show_import_result,
                    "Baixando listas LBX...",
                )
            except Exception as exc:
                self._show_error(exc)

        def import_foreign_rating_list() -> None:
            try:
                federations = self.official_rating_service.list_foreign_federations()
            except Exception as exc:
                self._show_error(exc)
                return
            options = [f"{code} - {info.get('name', code)}" for code, info in sorted(federations.items())]

            dialog = ctk.CTkToplevel(self)
            dialog.title("Importar lista de rating estrangeira")
            dialog.geometry("480x300")
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(dialog, text="Federação", font=font_subsection()).grid(
                row=0, column=0, padx=16, pady=(16, 4), sticky="w"
            )
            fed_option = ctk.CTkOptionMenu(dialog, values=options or ["(sem federacoes)"])
            fed_option.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

            ctk.CTkLabel(
                dialog,
                text="Adicionar federacao (codigo + nome) - opcional",
                text_color=THEME_TEXT_SUB,
            ).grid(row=2, column=0, padx=16, pady=(0, 2), sticky="w")
            add_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            add_frame.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="ew")
            add_frame.grid_columnconfigure(1, weight=1)
            code_entry = ctk.CTkEntry(add_frame, width=80, placeholder_text="POR")
            code_entry.grid(row=0, column=0, padx=(0, 8))
            name_entry = ctk.CTkEntry(add_frame, placeholder_text="Nome da federacao")
            name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

            def add_fed() -> None:
                try:
                    code = self.official_rating_service.add_foreign_federation(
                        code_entry.get(), name_entry.get()
                    )
                    self._show_toast(f"Federacao {code} adicionada.", kind="success")
                    dialog.destroy()
                    import_foreign_rating_list()
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(add_frame, text="Adicionar", width=100, command=add_fed).grid(row=0, column=2)

            def do_import() -> None:
                selection = fed_option.get()
                code = selection.split(" - ", maxsplit=1)[0].strip()
                if not code or code == "(sem federacoes)":
                    self._show_warning("Selecione ou adicione uma federacao.")
                    return
                file_path = filedialog.askopenfilename(
                    title=f"Lista de rating {code}",
                    filetypes=[("Planilhas e CSV", "*.csv;*.xls;*.xlsx"), ("Todos os arquivos", "*.*")],
                )
                if not file_path:
                    return
                dialog.destroy()

                def show_result(result: dict[str, Any]) -> None:
                    message = f"{result['imported']} jogadores importados para a base {result['source']}."
                    if result["errors"]:
                        message += "\n\nAvisos:\n" + "\n".join(result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    lambda: self.official_rating_service.import_foreign_list(file_path, code),
                    show_result,
                    f"Importando lista {code}...",
                )

            buttons = ctk.CTkFrame(dialog, fg_color="transparent")
            buttons.grid(row=4, column=0, padx=16, pady=(8, 16), sticky="e")
            ctk.CTkButton(
                buttons,
                text="Cancelar",
                fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER,
                command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(buttons, text="Importar arquivo", command=do_import).pack(side="left")

        def import_chess_results_entries() -> None:
            try:
                if not self.current_tournament_id:
                    raise AppError("Selecione um torneio.")
                file_path = filedialog.askopenfilename(
                    title="Importar inscricoes do Chess-Results (CSV)",
                    filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
                )
                if not file_path:
                    return
                tournament_id = int(self.current_tournament_id)

                def show_result(result: dict[str, Any]) -> None:
                    load_players()
                    message = f"{result['imported']} inscricoes importadas do Chess-Results."
                    if result["errors"]:
                        message += "\n\nAvisos:\n" + "\n".join(result["errors"][:10])
                    self._show_info(message)

                self._run_background(
                    lambda: self.chess_results_service.import_entries(tournament_id, file_path),
                    show_result,
                    "Importando inscricoes do Chess-Results...",
                )
            except Exception as exc:
                self._show_error(exc)

        def show_chess_results_package(result: dict[str, Any]) -> None:
            tournament_id = int(self.current_tournament_id)
            dialog = ctk.CTkToplevel(self)
            dialog.title("Publicar no Chess-Results.com")
            dialog.geometry("700x540")
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                dialog, text="Ponte Chess-Results (envio manual)", font=font_section()
            ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
            ctk.CTkLabel(
                dialog,
                text=f"TRF16 gerado:\n{result['trf_path']}",
                justify="left",
                anchor="w",
                wraplength=640,
                text_color=THEME_TEXT_SUB,
            ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

            steps_box = ctk.CTkTextbox(dialog, height=180, wrap="word")
            steps_box.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
            steps_box.insert("1.0", "\n".join(result["steps"]))
            if result.get("warnings"):
                steps_box.insert("end", "\n\nAvisos do TRF:\n" + "\n".join(f"- {w}" for w in result["warnings"]))
            steps_box.configure(state="disabled")

            link_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            link_frame.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
            link_frame.grid_columnconfigure(0, weight=1)
            link_entry = ctk.CTkEntry(link_frame, placeholder_text="https://chess-results.com/tnr....aspx")
            link_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            if result.get("published_url"):
                link_entry.insert(0, result["published_url"])

            def save_link() -> None:
                try:
                    saved = self.chess_results_service.set_published_url(tournament_id, link_entry.get())
                    self._show_toast("Link salvo." if saved else "Link removido.", kind="success")
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(link_frame, text="Salvar link", command=save_link, width=110).grid(row=0, column=1)

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=4, column=0, padx=16, pady=(4, 16), sticky="e")
            ctk.CTkButton(
                actions,
                text="Abrir pagina de registro",
                command=lambda: webbrowser.open(result["register_url"]),
            ).pack(side="left", padx=(0, 8))

            def open_published() -> None:
                normalized = normalize_results_url(link_entry.get())
                if normalized:
                    webbrowser.open(normalized)
                else:
                    self._show_warning("Salve um link valido do Chess-Results primeiro.")

            ctk.CTkButton(actions, text="Abrir torneio publicado", command=open_published).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions,
                text="Fechar",
                fg_color=THEME_NEUTRAL,
                hover_color=THEME_NEUTRAL_HOVER,
                command=dialog.destroy,
            ).pack(side="left")

        def prepare_chess_results() -> None:
            try:
                if not self.current_tournament_id:
                    raise AppError("Selecione um torneio.")
                directory = filedialog.askdirectory(
                    title="Pasta para o pacote Chess-Results (TRF16)",
                    initialdir=str(self._default_export_dir()),
                )
                if not directory:
                    return
                tournament_id = int(self.current_tournament_id)
                self._run_background(
                    lambda: self.chess_results_service.prepare_upload(tournament_id, directory),
                    show_chess_results_package,
                    "Preparando pacote Chess-Results...",
                )
            except Exception as exc:
                self._show_error(exc)

        tree.bind("<<TreeviewSelect>>", on_select)
        search_entry.bind("<KeyRelease>", debounce(search_entry, load_players))
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
            ("Compartilhar inscricao (link)", share_registration_form),
            ("Configurar formulario (link)", configure_registration_form),
            ("Gerar formulario (Google Forms)", generate_registration_form),
            ("Importar inscricoes online", import_online_registrations),
            ("Importar link Forms/Sheets", import_online_registrations_url),
            ("Importar com mapeamento", import_with_mapping),
            ("Importar link com mapeamento", import_with_mapping_url),
            ("Importar FIDE", lambda: import_official_ratings("FIDE")),
            ("Importar CBX", lambda: import_official_ratings("CBX")),
            ("Importar LBX arquivo", lambda: import_official_ratings("LBX")),
            ("Importar lista estrangeira", import_foreign_rating_list),
            ("Atualizar base LBX", update_lbx_base),
            ("Comparar ratings oficiais", update_official_ratings),
            ("Importar inscricoes Chess-Results", import_chess_results_entries),
            ("Publicar no Chess-Results", prepare_chess_results),
        ]
        self._grid_form_buttons(form, button_specs, control_row + 7, required_action="tournament_write")

        load_players()
        load_member_options()
