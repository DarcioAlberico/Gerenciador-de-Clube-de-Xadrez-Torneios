from __future__ import annotations

from ..support import *


class PairingPagesMixin:
    def show_pairings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        self.pairing_team_mode = bool(tournament and tournament.get("competition_type") == "team")
        self._clear_content()
        self._page_title(
            "Rodadas e resultados",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(toolbar, text="Gerar proxima rodada", command=self._generate_round).grid(
            row=0,
            column=0,
            padx=12,
            pady=12,
        )

        self.round_option = ctk.CTkOptionMenu(
            toolbar,
            values=["Sem rodadas"],
            command=lambda _value: self._load_selected_round_pairings(),
            width=190,
        )
        self.round_option.grid(row=0, column=1, padx=8, pady=12, sticky="w")

        self.result_option = ctk.CTkOptionMenu(toolbar, values=RESULTS, width=130)
        self.result_option.grid(row=0, column=2, padx=8, pady=12)
        ctk.CTkButton(toolbar, text="Salvar resultado", command=self._save_selected_result).grid(
            row=0,
            column=3,
            padx=8,
            pady=12,
        )
        round_actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        round_actions.grid(row=1, column=0, columnspan=4, padx=12, pady=(0, 12), sticky="ew")
        for column in range(4):
            round_actions.grid_columnconfigure(column, weight=1)
        ctk.CTkButton(round_actions, text="Trocar cores", command=self._swap_selected_colors).grid(
            row=0,
            column=0,
            padx=(0, 4),
            sticky="ew",
        )
        ctk.CTkButton(round_actions, text="Trocar jogador", command=self._open_player_swap_dialog).grid(
            row=0,
            column=1,
            padx=4,
            sticky="ew",
        )
        ctk.CTkButton(round_actions, text="Fechar rodada", command=self._close_current_round).grid(
            row=0,
            column=2,
            padx=4,
            sticky="ew",
        )
        ctk.CTkButton(round_actions, text="Excluir gerada", command=self._delete_current_round).grid(
            row=0,
            column=3,
            padx=(4, 0),
            sticky="ew",
        )

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        if self.pairing_team_mode:
            self.pairing_tree = self._make_tree(
                table_panel,
                ["match", "white_team", "match_result", "black_team", "board", "white", "result", "black"],
                {
                    "match": "Match",
                    "white_team": "Equipe A",
                    "match_result": "Placar",
                    "black_team": "Equipe B",
                    "board": "Tab.",
                    "white": "Brancas",
                    "result": "Resultado",
                    "black": "Pretas",
                },
                {
                    "match": 70,
                    "white_team": 170,
                    "match_result": 110,
                    "black_team": 170,
                    "board": 60,
                    "white": 230,
                    "result": 105,
                    "black": 230,
                },
            )
        else:
            self.pairing_tree = self._make_tree(
                table_panel,
                ["board", "white", "white_rating", "result", "black", "black_rating"],
                {
                    "board": "Mesa",
                    "white": "Brancas",
                    "white_rating": "Rating",
                    "result": "Resultado",
                    "black": "Pretas",
                    "black_rating": "Rating",
                },
                {
                    "board": 70,
                    "white": 260,
                    "white_rating": 90,
                    "result": 110,
                    "black": 260,
                    "black_rating": 90,
                },
            )
        self.pairing_tree.bind("<<TreeviewSelect>>", self._on_pairing_select)
        self._load_round_options()

    def _load_round_options(self) -> None:
        if not hasattr(self, "round_option"):
            return
        rounds = self.db.list_rounds(self.current_tournament_id)
        self.round_option_map = {}
        if not rounds:
            self.current_round_id = None
            self.round_option.configure(values=["Sem rodadas"])
            self.round_option.set("Sem rodadas")
            self.pairing_row_map = {}
            self.pairing_detail_map = {}
            if hasattr(self, "pairing_tree"):
                self.pairing_tree.delete(*self.pairing_tree.get_children())
            return

        values = []
        for round_data in rounds:
            label = f"Rodada {round_data['number']} - {round_data['status']}"
            values.append(label)
            self.round_option_map[label] = round_data["id"]

        self.round_option.configure(values=values)
        first = values[0]
        self.round_option.set(first)
        self.current_round_id = self.round_option_map[first]
        self._load_selected_round_pairings()

    def _load_selected_round_pairings(self) -> None:
        if not hasattr(self, "pairing_tree"):
            return
        selected_label = self.round_option.get()
        self.current_round_id = self.round_option_map.get(selected_label)
        self.pairing_tree.delete(*self.pairing_tree.get_children())
        self.pairing_row_map = {}
        self.pairing_detail_map = {}
        if not self.current_round_id:
            return
        if getattr(self, "pairing_team_mode", False):
            self._load_selected_team_round()
            return
        pairings = self.db.get_pairings_for_round(self.current_round_id)
        for pairing in pairings:
            white_name = pairing_player_name(pairing, "white")
            black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
            item_id = self.pairing_tree.insert(
                "",
                "end",
                values=(
                    pairing["board_number"],
                    white_name,
                    pairing["white_rating"],
                    pairing["result"],
                    black_name,
                    "" if pairing["is_bye"] else pairing["black_rating"],
                ),
            )
            self.pairing_row_map[item_id] = pairing["id"]
            self.pairing_detail_map[item_id] = {
                **pairing,
                "row_type": "individual_pairing",
                "white_display_name": white_name,
                "black_display_name": black_name,
            }

    def _load_selected_team_round(self) -> None:
        if not self.current_round_id:
            return
        matches = self.db.list_team_matches_for_round(self.current_round_id)
        for match in matches:
            black_team_name = "BYE" if match["is_bye"] else str(match.get("black_team_name") or "")
            match_result = ""
            if match.get("result"):
                match_result = str(match["result"])
                if match["result"] != "BYE":
                    match_result = (
                        f"{match['white_game_points']}-{match['black_game_points']} "
                        f"({match['white_match_points']}-{match['black_match_points']})"
                    )
            if match["is_bye"]:
                item_id = self.pairing_tree.insert(
                    "",
                    "end",
                    values=(
                        match["match_number"],
                        match["white_team_name"],
                        "BYE",
                        black_team_name,
                        "",
                        "",
                        "BYE",
                        "",
                    ),
                )
                self.pairing_detail_map[item_id] = {**match, "row_type": "team_bye"}
                continue

            for board in self.db.list_team_boards(int(match["id"])):
                white_name = player_pairing_name(
                    {
                        "name": board.get("white_player_name"),
                        "surname": board.get("white_player_surname"),
                        "given_name": board.get("white_player_given_name"),
                    }
                )
                black_name = player_pairing_name(
                    {
                        "name": board.get("black_player_name"),
                        "surname": board.get("black_player_surname"),
                        "given_name": board.get("black_player_given_name"),
                    }
                )
                item_id = self.pairing_tree.insert(
                    "",
                    "end",
                    values=(
                        match["match_number"],
                        match["white_team_name"],
                        match_result,
                        black_team_name,
                        board["board_number"],
                        white_name,
                        board["result"],
                        black_name,
                    ),
                )
                self.pairing_row_map[item_id] = int(board["id"])
                self.pairing_detail_map[item_id] = {
                    **board,
                    "row_type": "team_board",
                    "team_match_id": int(match["id"]),
                    "white_team_name": match["white_team_name"],
                    "black_team_name": black_team_name,
                }

    def _selected_pairing_id(self) -> int | None:
        if not hasattr(self, "pairing_tree"):
            return None
        selected = self.pairing_tree.selection()
        if not selected:
            return None
        return self.pairing_row_map.get(selected[0])

    def _selected_pairing(self) -> dict[str, Any] | None:
        if not hasattr(self, "pairing_tree"):
            return None
        selected = self.pairing_tree.selection()
        if not selected:
            return None
        return self.pairing_detail_map.get(selected[0])

    def _on_pairing_select(self, _event: Any = None) -> None:
        selected = self.pairing_tree.selection()
        if not selected:
            return
        values = self.pairing_tree.item(selected[0], "values")
        result = values[6] if getattr(self, "pairing_team_mode", False) and len(values) > 6 else values[3] if len(values) > 3 else ""
        if result in RESULTS:
            self.result_option.set(result)

    def _generate_round(self) -> None:
        try:
            self.pairing_service.generate_next_round(self.current_tournament_id)
            self._load_round_options()
        except Exception as exc:
            self._show_error(exc)

    def _save_selected_result(self) -> None:
        try:
            pairing_id = self._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione um tabuleiro." if getattr(self, "pairing_team_mode", False) else "Selecione uma mesa.")
            result = self.result_option.get()
            if result not in RESULTS:
                raise AppError("Resultado invalido.")
            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
                    if not settings.get("allow_dangerous_changes"):
                        raise AppError(
                            "Habilite mudancas perigosas nas configuracoes do torneio para alterar rodada fechada."
                        )
                    confirmed = messagebox.askyesno(
                        "Confirmar",
                        "Esta rodada ja esta fechada. Alterar o resultado mesmo assim?",
                    )
                    if not confirmed:
                        return
            self.pairing_service.update_result(self.current_tournament_id, pairing_id, result)
            self._load_selected_round_pairings()
        except Exception as exc:
            self._show_error(exc)

    def _swap_selected_colors(self) -> None:
        try:
            if getattr(self, "pairing_team_mode", False):
                raise AppError("Troca manual de cores por equipes sera tratada em uma etapa propria.")
            pairing_id = self._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione uma mesa.")
            if self.current_round_id:
                round_data = self.db.get_round(self.current_round_id)
                if round_data and round_data["status"] == "closed":
                    raise AppError("Rodada fechada nao pode ser ajustada.")
            self.db.swap_pairing_colors(pairing_id)
            logger.info("Cores trocadas na mesa %s", pairing_id)
            self._load_selected_round_pairings()
        except Exception as exc:
            self._show_error(exc)

    def _open_player_swap_dialog(self) -> None:
        try:
            if getattr(self, "pairing_team_mode", False):
                raise AppError("Troca manual de jogadores por equipes sera tratada em uma etapa propria.")
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            pairing = self._selected_pairing()
            if not pairing:
                raise AppError("Selecione uma mesa.")

            players = self.db.list_players(self.current_tournament_id, active_only=True)
            if not players:
                raise AppError("Nao ha jogadores ativos para trocar.")

            player_options = [
                f"{player['id']} - {player_pairing_name(player)} ({player['rating']})"
                for player in players
            ]
            player_map = {option: int(option.split(" ", maxsplit=1)[0]) for option in player_options}
            slot_options = ["Brancas"]
            if not pairing["is_bye"]:
                slot_options.append("Pretas")

            dialog = ctk.CTkToplevel(self)
            dialog.title("Trocar jogador")
            dialog.geometry("430x260")
            dialog.resizable(False, False)
            dialog.transient(self)
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            title = (
                f"Mesa {pairing['board_number']}: "
                f"{pairing['white_display_name']} x "
                f"{pairing['black_display_name']}"
            )
            ctk.CTkLabel(
                dialog,
                text=title,
                font=ctk.CTkFont(size=15, weight="bold"),
                wraplength=380,
                justify="left",
            ).grid(row=0, column=0, padx=18, pady=(18, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Lado a trocar").grid(row=1, column=0, padx=18, pady=(4, 4), sticky="w")
            slot_option = ctk.CTkOptionMenu(dialog, values=slot_options, width=180)
            slot_option.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

            ctk.CTkLabel(dialog, text="Jogador").grid(row=3, column=0, padx=18, pady=(4, 4), sticky="w")
            player_option = ctk.CTkOptionMenu(dialog, values=player_options, width=360)
            player_option.grid(row=4, column=0, padx=18, pady=(0, 16), sticky="w")

            actions = ctk.CTkFrame(dialog, fg_color="transparent")
            actions.grid(row=5, column=0, padx=18, pady=(2, 18), sticky="e")

            def apply_swap() -> None:
                try:
                    color = "white" if slot_option.get() == "Brancas" else "black"
                    replacement_id = player_map[player_option.get()]
                    self.pairing_service.adjust_pairing_player(
                        self.current_tournament_id,
                        self.current_round_id,
                        pairing["id"],
                        color,
                        replacement_id,
                    )
                    dialog.destroy()
                    self._load_selected_round_pairings()
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(actions, text="Cancelar", fg_color="#64748B", command=dialog.destroy).pack(
                side="left",
                padx=(0, 8),
            )
            ctk.CTkButton(actions, text="Aplicar", command=apply_swap).pack(side="left")
        except Exception as exc:
            self._show_error(exc)

    def _close_current_round(self) -> None:
        try:
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            self.pairing_service.close_round(self.current_tournament_id, self.current_round_id)
            self._load_round_options()
            self._show_info("Rodada fechada.")
        except Exception as exc:
            self._show_error(exc)

    def _delete_current_round(self) -> None:
        try:
            if not self.current_round_id:
                raise AppError("Selecione uma rodada.")
            if not messagebox.askyesno("Confirmar", "Excluir a rodada gerada selecionada?"):
                return
            self.pairing_service.delete_generated_round(self.current_round_id)
            self._load_round_options()
        except Exception as exc:
            self._show_error(exc)

    def show_standings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
        self._clear_content()
        self._page_title(
            "Classificacao",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )

        if settings.get("hide_standings"):
            body = ctk.CTkFrame(self.content, fg_color="transparent")
            body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
            panel = self._make_panel(body)
            panel.pack(anchor="nw", fill="x")
            ctk.CTkLabel(
                panel,
                text="A classificacao esta oculta nas configuracoes do torneio.",
                text_color=THEME_TEXT_SUB,
            ).pack(anchor="w", padx=16, pady=16)
            return

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        if tournament and tournament.get("competition_type") == "team":
            ctk.CTkButton(toolbar, text="Recalcular", command=self.show_standings).pack(
                side="left",
                padx=12,
                pady=12,
            )

            table_panel = self._make_panel(body)
            table_panel.grid(row=1, column=0, sticky="nsew")
            table_panel.grid_columnconfigure(0, weight=1)
            table_panel.grid_rowconfigure(0, weight=1)

            tree = self._make_tree(
                table_panel,
                [
                    "pos",
                    "team",
                    "club",
                    "captain",
                    "match_points",
                    "game_points",
                    "wins",
                    "draws",
                    "losses",
                    "byes",
                    "buchholz",
                    "status",
                ],
                {
                    "pos": "Pos",
                    "team": "Equipe",
                    "club": "Clube/Cidade",
                    "captain": "Capitao",
                    "match_points": "MP",
                    "game_points": "GP",
                    "wins": "V",
                    "draws": "E",
                    "losses": "D",
                    "byes": "Byes",
                    "buchholz": "Buchholz",
                    "status": "Status",
                },
                {
                    "pos": 60,
                    "team": 240,
                    "club": 170,
                    "captain": 150,
                    "match_points": 70,
                    "game_points": 70,
                    "wins": 55,
                    "draws": 55,
                    "losses": 55,
                    "byes": 65,
                    "buchholz": 90,
                    "status": 90,
                },
            )
            self.standings_tree = tree

            for item in self.pairing_service.team_standings(self.current_tournament_id):
                tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item.get("club", ""),
                        item.get("captain", ""),
                        item["match_points"],
                        item["game_points"],
                        item["wins"],
                        item["draws"],
                        item["losses"],
                        item["byes"],
                        item["buchholz"],
                        "Ativa" if item.get("active") else "Inativa",
                    ),
                )
            return

        def apply_internal_rating() -> None:
            try:
                result = self.internal_rating_service.apply_tournament_ratings(
                    int(self.current_tournament_id)
                )
                self._show_info(
                    "Ratings internos atualizados: {updated}\n"
                    "Ja aplicados anteriormente: {duplicates}\n"
                    "Sem performance suficiente: {skipped}\n"
                    "Convidados externos ignorados: {external}".format(**result)
                )
                self.show_standings()
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(toolbar, text="Recalcular", command=self.show_standings).pack(
            side="left",
            padx=12,
            pady=12,
        )
        ctk.CTkButton(
            toolbar,
            text="Atualizar rating interno",
            command=apply_internal_rating,
        ).pack(side="left", padx=(0, 12), pady=12)
        categories = sorted(
            {
                str(player["category"]).strip()
                for player in self.db.list_players(self.current_tournament_id, active_only=False)
                if str(player["category"]).strip()
            }
        )
        ctk.CTkLabel(toolbar, text="Categoria").pack(side="left", padx=(10, 6), pady=12)
        category_option = ctk.CTkOptionMenu(toolbar, values=["Todas"] + categories, width=170)
        category_option.pack(side="left", padx=(0, 12), pady=12)

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            table_panel,
            [
                "pos",
                "name",
                "category",
                "age_category",
                "rating_category",
                "tags",
                "points",
                "buchholz",
                "median",
                "sb",
                "wins",
                "performance",
                "rating",
                "club",
            ],
            {
                "pos": "Pos",
                "name": "Nome",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "points": "Pts",
                "buchholz": "Buchholz",
                "median": "Buchholz M",
                "sb": "SB",
                "wins": "Vitorias",
                "performance": "Perf.",
                "rating": "Rating",
                "club": "Clube",
            },
            {
                "pos": 60,
                "name": 220,
                "category": 105,
                "age_category": 85,
                "rating_category": 90,
                "tags": 150,
                "points": 70,
                "buchholz": 90,
                "median": 100,
                "sb": 80,
                "wins": 80,
                "performance": 80,
                "rating": 80,
                "club": 180,
            },
        )
        self.standings_tree = tree

        def load_standings() -> None:
            tree.delete(*tree.get_children())
            category = category_option.get()
            for item in self.pairing_service.standings(self.current_tournament_id):
                if category != "Todas" and item["category"] != category:
                    continue
                tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item.get("category", ""),
                        item.get("age_category", ""),
                        item.get("rating_category", ""),
                        item.get("prize_tags", ""),
                        item["points"],
                        item["buchholz"],
                        item["buchholz_median"],
                        item["sonneborn_berger"],
                        item["wins"],
                        item["performance"],
                        item["rating"],
                        item["club"],
                    ),
                )

        category_option.configure(command=lambda _value: load_standings())
        load_standings()


