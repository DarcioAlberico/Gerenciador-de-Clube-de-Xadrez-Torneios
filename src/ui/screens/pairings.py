from __future__ import annotations

from ..support import *

from .pairing_arbitration import ArbitrationPagesMixin
from .pairing_results_ui import PairingResultsMixin


class PairingPagesMixin(ArbitrationPagesMixin, PairingResultsMixin):
    def show_standings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}
        self._clear_content()
        self._page_title(
            "Classificação",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("standings")

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
            botao_cruzada = ctk.CTkButton(toolbar, text="Exportar tabela cruzada")
            # O botao entra no proprio comando (F5.9): e ele que o
            # `_run_background` esmaece enquanto a exportacao roda. Sem isso a
            # espera so aparecia na barra de 6px do rodape, longe de onde o
            # clique aconteceu (P3-11).
            botao_cruzada.configure(
                command=lambda b=botao_cruzada: self._export_crosstable_from_standings(b)
            )
            botao_cruzada.pack(side="left", padx=(0, 12), pady=12)

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
            row_team_ids: dict[str, int] = {}

            for item in self.pairing_service.team_standings(self.current_tournament_id):
                row_id = tree.insert(
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
                row_team_ids[row_id] = int(item["team_id"])

            def show_team_crosstable_detail() -> None:
                selected = tree.selection()
                if not selected:
                    self._show_warning("Selecione uma equipe na classificacao.")
                    return
                team_id = row_team_ids.get(selected[0])
                payload = self.pairing_service.team_crosstable(int(self.current_tournament_id))
                team_row = next((item for item in payload["rows"] if int(item["team_id"]) == team_id), None)
                if not team_row:
                    return
                lines = [f"Tabela cruzada - {team_row['name']}"]
                for round_number in payload["rounds"]:
                    cell = team_row["rounds"][round_number]
                    lines.append(f"\nRodada {round_number}: {cell['label']}")
                    for board in cell.get("boards", []):
                        lines.append(
                            f"- Tabuleiro {board['board_number']}: "
                            f"{board.get('white_player_name') or ''} x "
                            f"{board.get('black_player_name') or ''} "
                            f"{board.get('result') or ''}"
                        )
                self._show_report("Detalhe dos tabuleiros", "\n".join(lines))

            ctk.CTkButton(
                toolbar,
                text="Detalhar tabuleiros",
                command=show_team_crosstable_detail,
            ).pack(side="left", padx=(0, 12), pady=12)
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
        botao_cruzada = ctk.CTkButton(toolbar, text="Exportar tabela cruzada")
        botao_cruzada.configure(
            command=lambda b=botao_cruzada: self._export_crosstable_from_standings(b)
        )
        botao_cruzada.pack(side="left", padx=(0, 12), pady=12)
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
        row_player_ids: dict[str, int] = {}

        def show_tiebreak_detail(criterion: str = "") -> None:
            selected = tree.selection()
            if not selected:
                self._show_warning("Selecione um jogador na classificacao.")
                return
            player_id = row_player_ids.get(selected[0])
            if not player_id:
                return
            standings = self.pairing_service.tiebreak_report(
                int(self.current_tournament_id),
                player_id=player_id,
            )
            if not standings:
                self._show_warning("Nao ha componentes de desempate para este jogador.")
                return

            narrative = self.pairing_service.tiebreak_narrative(
                int(self.current_tournament_id),
                int(player_id),
            )
            lines: list[str] = list(narrative.get("lines") or [])

            # Detalhes técnicos do(s) critério(s) — abaixo da narrativa.
            components = standings[0].get("tiebreak_components") or {}
            keys = [criterion] if criterion else [
                "buchholz",
                "buchholz_median",
                "sonneborn_berger",
                "direct_encounter",
                "wins",
                "performance",
            ]
            detail_lines: list[str] = []
            for key in keys:
                component = components.get(key) or {}
                if not component:
                    continue
                detail_lines.append("")
                detail_lines.append(f"{component.get('label', key)}: {component.get('value', '')}")
                detail_lines.append(str(component.get("formula", "")))
                for opponent in component.get("opponents", [])[:8]:
                    value = opponent.get("contribution", opponent.get("points", ""))
                    detail_lines.append(f"- {opponent.get('opponent_name', '')}: {value}")
                if "used_scores" in component:
                    detail_lines.append(f"- Usados: {component.get('used_scores', [])}")
                    if component.get("cut_low") is not None:
                        detail_lines.append(f"- Corte menor: {component.get('cut_low')}")
                    if component.get("cut_high") is not None:
                        detail_lines.append(f"- Corte maior: {component.get('cut_high')}")
                for game in component.get("games", [])[:8]:
                    detail_lines.append(f"- {game.get('opponent_name', '')}: {game.get('earned', '')}")

            if detail_lines:
                lines.append("")
                lines.append("— Detalhes técnicos —")
                lines.extend(detail_lines)

            self._show_report("Por que esta posicao?", "\n".join(lines))

        ctk.CTkButton(
            toolbar,
            text="Explicar desempate",
            command=lambda: show_tiebreak_detail(),
        ).pack(side="left", padx=(0, 12), pady=12)

        for column, criterion in {
            "buchholz": "buchholz",
            "median": "buchholz_median",
            "sb": "sonneborn_berger",
            "wins": "wins",
            "performance": "performance",
        }.items():
            tree.heading(
                column,
                text=tree.heading(column)["text"],
                command=lambda selected_criterion=criterion: show_tiebreak_detail(selected_criterion),
            )

        def load_standings() -> None:
            tree.delete(*tree.get_children())
            row_player_ids.clear()
            category = category_option.get()
            for item in self.pairing_service.standings(self.current_tournament_id):
                if category != "Todas" and item["category"] != category:
                    continue
                row_id = tree.insert(
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
                row_player_ids[row_id] = int(item["player_id"])

        category_option.configure(command=lambda _value: load_standings())
        load_standings()

    def _export_crosstable_from_standings(self, botao: Any | None = None) -> None:
        try:
            if not self.current_tournament_id:
                raise AppError("Selecione um torneio.")
            tournament = self.db.get_tournament(int(self.current_tournament_id))
            safe_name = self._safe_filename(str(tournament.get("name") if tournament else "torneio"), "torneio")
            default_path = self._default_export_dir() / f"{safe_name}_tabela_cruzada.xlsx"
            file_path = filedialog.asksaveasfilename(
                title="Exportar tabela cruzada",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel", "*.xlsx"),
                    ("CSV", "*.csv"),
                    ("PDF", "*.pdf"),
                    ("HTML", "*.html"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() not in {".csv", ".xlsx", ".pdf", ".html"}:
                path = path.with_suffix(".xlsx")
            self._run_background(
                lambda: self.export_service.export_crosstable(int(self.current_tournament_id), path),
                lambda _result: self._show_info(f"Tabela cruzada exportada:\n{path}"),
                "Exportando tabela cruzada...",
                busy_widget=botao,
            )
        except Exception as exc:
            self._show_error(exc)


