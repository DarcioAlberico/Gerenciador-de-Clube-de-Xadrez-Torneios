from __future__ import annotations

from ..support import *

from tkinter import TclError

from src.services.pairing.point_adjustments import (
    ADJUSTMENT_LEGEND,
    has_adjustment,
    mark_adjusted,
)

from .pairing_arbitration import ArbitrationPagesMixin
from .pairing_results import PairingResultsMixin


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
                text="A classificação está oculta nas configurações do torneio.",
                text_color=THEME_TEXT_SUB,
            ).pack(anchor="w", padx=16, pady=16)
            return

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        # Linha 0 toolbar, 1 faixa do motor de desempate (TBK-02), 2 tabela.
        body.grid_rowconfigure(2, weight=1)

        toolbar = self._make_panel(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        if tournament and tournament.get("competition_type") == "team":
            ctk.CTkButton(
                toolbar, text="Recalcular", command=self._recalculate_standings
            ).pack(side="left", padx=12, pady=12)
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
            table_panel.grid(row=2, column=0, sticky="nsew")
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

            team_standings = self._standings_or_empty(
                lambda: self.pairing_service.team_standings(self.current_tournament_id)
            )
            for item in team_standings:
                row_id = tree.insert(
                    "",
                    "end",
                    values=(
                        item["position"],
                        item["name"],
                        item.get("club", ""),
                        item.get("captain", ""),
                        mark_adjusted(
                            item["match_points"],
                            float(item.get("adjustment_match_points") or 0.0),
                        ),
                        mark_adjusted(
                            item["game_points"],
                            float(item.get("adjustment_game_points") or 0.0),
                        ),
                        item["wins"],
                        item["draws"],
                        item["losses"],
                        item["byes"],
                        item["buchholz"],
                        "Ativa" if item.get("active") else "Inativa",
                    ),
                )
                row_team_ids[row_id] = int(item["team_id"])

            self._standings_adjustment_legend(table_panel, team_standings)
            self._standings_engine_banner(body)

            def show_team_crosstable_detail() -> None:
                selected = tree.selection()
                if not selected:
                    self._show_warning("Selecione uma equipe na classificação.")
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

        ctk.CTkButton(
            toolbar, text="Recalcular", command=self._recalculate_standings
        ).pack(side="left", padx=12, pady=12)
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
        table_panel.grid(row=2, column=0, sticky="nsew")
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
                "wins": "Vitórias",
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
                self._show_warning("Selecione um jogador na classificação.")
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

            self._show_report("Por que esta posição?", "\n".join(lines))

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
            visible = []
            carregadas = self._standings_or_empty(
                lambda: self.pairing_service.standings(self.current_tournament_id)
            )
            for item in carregadas:
                if category != "Todas" and item["category"] != category:
                    continue
                visible.append(item)
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
                        mark_adjusted(item["points"], float(item.get("adjustment_points") or 0.0)),
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

            self._standings_adjustment_legend(table_panel, visible)

        category_option.configure(command=lambda _value: load_standings())
        load_standings()
        # Depois de carregar, e não antes: a faixa conta o que ACABOU de
        # acontecer. Montada primeiro, mostraria o motor do cálculo anterior — e
        # numa tela recém-aberta diria "tudo bem" ao lado de uma tabela vazia.
        self._standings_engine_banner(body)

    # ---- Motor de desempate: faixa, recálculo e tabela ausente (TBK-02) ---- #

    def _standings_engine_banner(self, body: Any) -> None:
        """Faixa permanente com o motor que assinou a classificação.

        Permanente inclusive quando está tudo bem. Uma faixa que só aparece no
        erro ensina o árbitro a não olhar para aquele canto; uma que sempre diz
        qual motor assinou a tabela é um lugar onde se olha — e no dia em que o
        Gacrux cair, o aviso chega onde os olhos já estão.
        """
        faixa = self.pairing_service.tiebreak_engine_badge(int(self.current_tournament_id))
        cores = {
            "ok": THEME_TEXT_SUB,
            "warning": THEME_WARNING_TEXT,
            "danger": THEME_DANGER,
        }
        painel = self._make_panel(body)
        painel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        painel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            painel,
            text=faixa["label"],
            text_color=cores.get(faixa["tone"], THEME_TEXT_SUB),
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")
        if not faixa["detail"]:
            painel.grid_configure(pady=(0, 12))
            return
        # O detalhe embrulha porque diz o que muda na prática (adversário
        # virtual, ordem dos empatados) — recado que não cabe em meia linha.
        detalhe = ctk.CTkLabel(
            painel,
            text=faixa["detail"],
            text_color=THEME_TEXT_SUB,
            anchor="w",
            justify="left",
            wraplength=900,
        )
        detalhe.grid(row=1, column=0, padx=12, pady=(2, 4), sticky="ew")
        ctk.CTkButton(
            painel,
            text=t("standings.engine.retry"),
            command=self._recalculate_standings,
        ).grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")

    def _recalculate_standings(self) -> None:
        """Esquece o cálculo cacheado e remonta a tela.

        O "Recalcular" antes só repintava — e desde que a falha do motor passou a
        ser cacheada (para não disparar um subprocesso por repintura), repintar
        não bastaria para sair de uma falha passageira. Agora o botão faz o que
        o nome diz.
        """
        if self.current_tournament_id:
            self.pairing_service.reset_tiebreak_engine(int(self.current_tournament_id))
        self.show_standings()

    def _standings_or_empty(self, carregar: Any) -> list[dict[str, Any]]:
        """Classificação, ou lista vazia quando o modo estrito barrou o cálculo.

        Em modo estrito a falha do motor levanta `AppError` de propósito — é o
        "bloquear a publicação" da TBK-02. Aqui ela não pode virar um traceback:
        a faixa acima da tabela já explica o que aconteceu e oferece o
        recálculo, então a tabela apenas fica vazia.
        """
        try:
            return list(carregar())
        except AppError as exc:
            logger.warning("Classificacao indisponivel: %s", exc)
            return []

    def _standings_adjustment_legend(self, painel: Any, standings: list[dict[str, Any]]) -> None:
        """Legenda do asterisco, só quando existe asterisco na tabela (TBK-01).

        Uma linha embaixo do painel da tabela; recriada a cada carga (o filtro
        de categoria pode esconder justamente o jogador ajustado), por isso a
        anterior é destruída antes. Sem ajuste, nenhuma legenda — o rodapé
        permanente viraria ruído nos 99% dos torneios que não têm ajuste.
        """
        anterior = getattr(self, "_standings_legend_label", None)
        if anterior is not None:
            # A referência sobrevive ao `_clear_content` que destruiu o widget;
            # perguntar ao Tk por um filho que já morreu é TclError, não False.
            try:
                if anterior.winfo_exists():
                    anterior.destroy()
            except TclError:
                pass
        self._standings_legend_label = None
        if not any(has_adjustment(item) for item in standings):
            return
        legenda = ctk.CTkLabel(
            painel,
            text=ADJUSTMENT_LEGEND,
            text_color=THEME_TEXT_SUB,
            anchor="w",
        )
        legenda.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._standings_legend_label = legenda

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


