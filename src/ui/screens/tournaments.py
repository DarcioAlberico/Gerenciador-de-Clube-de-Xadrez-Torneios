from __future__ import annotations

from ..support import *
from ..components import danger_button

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
from .tournament_players_ui import TournamentPlayersMixin
from .tournament_settings_ui import TournamentSettingsMixin


class TournamentPagesMixin(TournamentPlayersMixin, TournamentSettingsMixin):
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
        btn_create.grid(row=option_row + 8, column=0, padx=16, pady=(18, 4), sticky="ew")
        self._disable_if_unauthorized(btn_create, "tournament_write")

        def import_trf_file() -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title="Importar torneio do Swiss-Manager (TRF)",
                    filetypes=[("Arquivos TRF", "*.trf"), ("Todos os arquivos", "*.*")],
                )
                if not file_path:
                    return
                result = self.import_service.import_trf(file_path)
                self._set_current_tournament(result["tournament_id"])
                self._show_toast(
                    f"Torneio '{result['name']}' importado com {result['players_imported']} jogadores.",
                    kind="success",
                )
                self.show_players()
            except Exception as exc:
                self._show_error(exc)

        btn_import_trf = ctk.CTkButton(
            form, text="Importar TRF (Swiss-Manager)", command=import_trf_file
        )
        btn_import_trf.grid(row=option_row + 9, column=0, padx=16, pady=(0, 14), sticky="ew")
        self._disable_if_unauthorized(btn_import_trf, "tournament_write")

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
                confirmed = self._confirm_action(
                    "Excluir torneio",
                    f"Excluir o torneio '{name}' e todos os jogadores/rodadas vinculados?",
                    danger=True,
                )
                if not confirmed:
                    return
                self.tournament_service.delete_tournament(tournament_id)
                if self.current_tournament_id == tournament_id:
                    self.current_tournament_id = None
                    self.current_round_id = None
                    self.tournament_label.configure(text="Nenhum torneio selecionado")
                load_tournaments()
                self._show_toast("Torneio excluido.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def split_selected() -> None:
            try:
                tournament_id = selected_tournament_id()
                if not tournament_id:
                    raise AppError("Selecione um torneio para dividir.")
                answer = self._ask_string("Dividir torneio", "Em quantos grupos (2 ou mais)?")
                if answer is None:
                    return
                child_ids = self.tournament_service.split_tournament(tournament_id, answer.strip())
                load_tournaments()
                self._show_info(
                    f"Torneio dividido em {len(child_ids)} grupos (A, B, ...) por ranking inicial."
                )
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
        btn_split = ctk.CTkButton(actions, text="Dividir", command=split_selected, width=90)
        btn_split.pack(side="left", padx=(0, 8))
        self._disable_if_unauthorized(btn_split, "tournament_write")
        btn_delete = danger_button(actions, "Excluir", delete_selected, width=90)
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
            font=font_section(),
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
                font=font_section(),
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
            ("notes", "Observações"),
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
            font=font_section(),
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
            font=font_section(),
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
            font=font_section(),
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
                self._show_toast("Equipe criada.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def update_team() -> None:
            try:
                team_id = selected_team_id["value"]
                if not team_id:
                    raise AppError("Selecione uma equipe.")
                self.team_service.update_team(team_id, team_payload())
                load_teams()
                self._show_toast("Equipe atualizada.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def delete_team() -> None:
            try:
                team_id = selected_team_id["value"]
                if not team_id:
                    raise AppError("Selecione uma equipe.")
                if not self._confirm_action(
                    "Excluir equipe",
                    "Excluir esta equipe e sua escalacao? Equipes usadas em rodadas devem ser inativadas.",
                    danger=True,
                ):
                    return
                self.team_service.delete_team(team_id)
                clear_team_form()
                load_teams()
                self._show_toast("Equipe excluida.", kind="success")
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
        dialog.geometry("900x550")
        dialog.transient(self)
        dialog.grab_set()
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        main_frame.grid_columnconfigure(0, weight=1, minsize=380)
        main_frame.grid_columnconfigure(1, weight=1, minsize=420)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Coluna Esquerda: Formulários (Painel Rolável)
        left_column = ctk.CTkScrollableFrame(main_frame, fg_color=THEME_PANEL_BG, corner_radius=8)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_column.grid_columnconfigure(0, weight=1)
        
        # Coluna Direita: Listagem e Ações
        right_column = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_column.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_column.grid_columnconfigure(0, weight=1)
        right_column.grid_rowconfigure(1, weight=1)
        
        # SEÇÃO 1: Vincular Árbitro Existente
        ctk.CTkLabel(left_column, text="Vincular Árbitro Existente", font=font_section()).grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")
        
        form_assign = ctk.CTkFrame(left_column, fg_color="transparent")
        form_assign.grid(row=1, column=0, padx=16, pady=4, sticky="ew")
        form_assign.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(form_assign, text="Selecione o Árbitro:").grid(row=0, column=0, sticky="w", pady=(4, 0))
        
        ref_option = ctk.CTkOptionMenu(form_assign, values=["Carregando..."], width=300)
        ref_option.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        
        ctk.CTkLabel(form_assign, text="Papel / Função no Torneio:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        
        role_option = ctk.CTkOptionMenu(form_assign, values=["Árbitro Principal", "Árbitro Auxiliar", "Diretor"], width=300)
        role_option.grid(row=3, column=0, sticky="ew", pady=(2, 10))
        
        # SEÇÃO 2: Cadastrar Novo Árbitro
        ctk.CTkLabel(left_column, text="Cadastrar Novo Árbitro", font=font_section()).grid(row=2, column=0, padx=16, pady=(20, 6), sticky="w")
        
        form_register = ctk.CTkFrame(left_column, fg_color="transparent")
        form_register.grid(row=3, column=0, padx=16, pady=4, sticky="ew")
        form_register.grid_columnconfigure(1, weight=1)
        
        reg_fields = [
            ("name", "Nome *"),
            ("fide_id", "FIDE ID"),
            ("cbx_id", "CBX ID"),
            ("federation_id", "ID Federação"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("notes", "Observações")
        ]
        
        reg_entries = {}
        for index, (key, label) in enumerate(reg_fields):
            ctk.CTkLabel(form_register, text=label).grid(row=index, column=0, padx=(0, 10), pady=4, sticky="w")
            entry = ctk.CTkEntry(form_register, width=220)
            entry.grid(row=index, column=1, padx=0, pady=4, sticky="ew")
            reg_entries[key] = entry
            
        # Campo Categoria
        cat_index = len(reg_fields)
        ctk.CTkLabel(form_register, text="Categoria:").grid(row=cat_index, column=0, padx=(0, 10), pady=4, sticky="w")
        cat_option = ctk.CTkOptionMenu(form_register, values=["AN", "AR", "AF", "AI", "Outro"], width=220)
        cat_option.grid(row=cat_index, column=1, padx=0, pady=4, sticky="ew")
        cat_option.set("AN")
        
        # Campo Função no Torneio para o Novo Árbitro
        role_new_index = cat_index + 1
        ctk.CTkLabel(form_register, text="Papel Torneio:").grid(row=role_new_index, column=0, padx=(0, 10), pady=4, sticky="w")
        role_new_option = ctk.CTkOptionMenu(form_register, values=["Árbitro Principal", "Árbitro Auxiliar", "Diretor"], width=220)
        role_new_option.grid(row=role_new_index, column=1, padx=0, pady=4, sticky="ew")
        role_new_option.set("Árbitro Auxiliar")
        
        # Coluna Direita: Tabela de Árbitros Vinculados
        ctk.CTkLabel(right_column, text="Árbitros Vinculados ao Torneio", font=font_section()).grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        
        list_frame = ctk.CTkFrame(right_column)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        tree = self._make_tree(
            list_frame,
            ["id", "name", "role", "category"],
            {"id": "ID", "name": "Nome", "role": "Papel", "category": "Cat."},
            {"id": 40, "name": 200, "role": 150, "category": 60}
        )
        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ref_map = {}
        
        def refresh_referee_options():
            nonlocal ref_map
            all_referees = self.referee_service.list_referees(active_only=True)
            ref_map = {f"{r['name']} ({r['category']})": r["id"] for r in all_referees}
            values = list(ref_map.keys()) if ref_map else ["Nenhum árbitro ativo"]
            ref_option.configure(values=values)
            if values:
                ref_option.set(values[0])
                
        def load_tournament_refs():
            tree.delete(*tree.get_children())
            refs = self.referee_service.list_tournament_referees(self.current_tournament_id)
            for r in refs:
                tree.insert("", "end", values=(r["referee_id"], r["name"], r["role"], r["category"]))
                
        def add_referee():
            if not ref_map:
                return
            selected_val = ref_option.get()
            ref_id = ref_map.get(selected_val)
            if not ref_id:
                return
            self.referee_service.assign_tournament_referee(self.current_tournament_id, ref_id, role_option.get())
            load_tournament_refs()
            self._show_toast("Árbitro vinculado com sucesso.", kind="success")
            
        def remove_referee():
            selected = tree.selection()
            if not selected:
                return
            ref_id = int(tree.item(selected[0], "values")[0])
            self.referee_service.remove_tournament_referee(self.current_tournament_id, ref_id)
            load_tournament_refs()
            self._show_toast("Árbitro removido do torneio.", kind="success")
            
        def register_and_add_referee():
            name = reg_entries["name"].get().strip()
            if not name:
                self._show_toast("Nome do árbitro é obrigatório.", kind="error")
                return
                
            payload = {
                "name": name,
                "phone": reg_entries["phone"].get().strip(),
                "email": reg_entries["email"].get().strip(),
                "federation_id": reg_entries["federation_id"].get().strip(),
                "fide_id": reg_entries["fide_id"].get().strip(),
                "cbx_id": reg_entries["cbx_id"].get().strip(),
                "category": cat_option.get(),
                "active": 1,
                "notes": reg_entries["notes"].get().strip()
            }
            
            try:
                # 1. Cadastra o árbitro globalmente no banco de dados
                new_ref_id = self.referee_service.create_referee(payload)
                
                # 2. Vincula o árbitro ao torneio atual com a função selecionada
                role = role_new_option.get()
                self.referee_service.assign_tournament_referee(self.current_tournament_id, new_ref_id, role)
                
                # 3. Atualiza as listas na tela
                refresh_referee_options()
                load_tournament_refs()
                
                # 4. Limpa os campos do formulário
                for entry in reg_entries.values():
                    entry.delete(0, "end")
                cat_option.set("AN")
                role_new_option.set("Árbitro Auxiliar")
                
                self._show_toast("Árbitro cadastrado e vinculado com sucesso.", kind="success")
            except Exception as exc:
                self._show_error(exc)
                
        # Botão de Ação para vincular árbitro existente
        btn_add = ctk.CTkButton(form_assign, text="Vincular ao Torneio", command=add_referee)
        btn_add.grid(row=4, column=0, sticky="ew", pady=(10, 5))
        
        # Botão de Ação para cadastrar e vincular novo árbitro
        btn_register = ctk.CTkButton(form_register, text="Cadastrar e Vincular", command=register_and_add_referee)
        btn_register.grid(row=role_new_index + 1, column=0, columnspan=2, sticky="ew", pady=(15, 10))
        
        # Botões de Ação na coluna da direita (abaixo da tabela)
        btn_frame = ctk.CTkFrame(right_column, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        btn_remove = danger_button(btn_frame, "Remover Selecionado", remove_referee)
        btn_remove.pack(side="right")
        
        # Carregamentos iniciais
        refresh_referee_options()
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
