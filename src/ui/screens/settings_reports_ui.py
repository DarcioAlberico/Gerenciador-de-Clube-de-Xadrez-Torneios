from __future__ import annotations

from ..support import *


class SettingsReportsMixin:
    def show_reports(self) -> None:
        self._clear_content()
        self._page_title(
            "Relatorios",
            "Gere relatorios administrativos do clube, de membros e de torneios por periodo.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        panel = self._make_panel(body)
        panel.grid(row=0, column=0, sticky="ew")
        for column in range(5):
            panel.grid_columnconfigure(column, weight=0)

        members = self.db.list_members(active_only=False)
        member_map: dict[str, int] = {
            f"{member['id']} - {self._member_display_name(member)}": int(member["id"])
            for member in members
        }
        member_values = list(member_map.keys()) or ["Sem membros"]
        club_map: dict[str, int | None] = {"Todos clubes": None}
        for club in self.db.list_clubs(active_only=True):
            club_map[f"{club['id']} - {club['name']}"] = int(club["id"])
        club_values = list(club_map.keys())
        class_map: dict[str, int | None] = {"Todas turmas": None}

        ctk.CTkLabel(panel, text="Relatorio").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        report_option = ctk.CTkOptionMenu(
            panel,
            values=[
                "Geral do clube",
                "Membro individual",
                "Torneios por periodo",
                "Presencas por periodo",
                "Financeiro por periodo",
                "Eventos por periodo",
                "Ranking interno",
                "Portal do clube/turma",
                "Pacote administrativo",
            ],
            width=190,
        )
        report_option.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(panel, text="Formato").grid(row=0, column=1, padx=16, pady=(16, 4), sticky="w")
        format_option = ctk.CTkOptionMenu(panel, values=["xlsx", "csv", "pdf"], width=110)
        format_option.grid(row=1, column=1, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(panel, text="Membro").grid(row=0, column=2, padx=16, pady=(16, 4), sticky="w")
        member_option = ctk.CTkOptionMenu(panel, values=member_values, width=220)
        member_option.grid(row=1, column=2, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(panel, text="Clube/Escola").grid(row=2, column=2, padx=16, pady=(4, 4), sticky="w")
        club_option = ctk.CTkOptionMenu(panel, values=club_values, width=190)
        club_option.grid(row=3, column=2, padx=16, pady=(0, 16), sticky="w")

        ctk.CTkLabel(panel, text="Turma").grid(row=2, column=3, padx=16, pady=(4, 4), sticky="w")
        class_option = ctk.CTkOptionMenu(panel, values=["Todas turmas"], width=190)
        class_option.grid(row=3, column=3, padx=16, pady=(0, 16), sticky="w")

        ctk.CTkLabel(panel, text="Inicio").grid(row=2, column=0, padx=16, pady=(4, 4), sticky="w")
        start_entry = ctk.CTkEntry(panel, placeholder_text="AAAA-MM-DD", width=130)
        start_entry.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="w")

        ctk.CTkLabel(panel, text="Fim").grid(row=2, column=1, padx=16, pady=(4, 4), sticky="w")
        end_entry = ctk.CTkEntry(panel, placeholder_text="AAAA-MM-DD", width=130)
        end_entry.grid(row=3, column=1, padx=16, pady=(0, 16), sticky="w")

        help_label = ctk.CTkLabel(
            panel,
            text="Use datas no formato ISO para filtrar torneios, presencas, financeiro ou eventos por periodo.",
            text_color=THEME_TEXT_SUB,
        )
        help_label.grid(row=4, column=0, columnspan=4, padx=16, pady=(0, 16), sticky="w")

        def selected_club_id() -> int | None:
            return club_map.get(club_option.get())

        def selected_class_id() -> int | None:
            return class_map.get(class_option.get())

        def load_class_options(club_id: int | None = None) -> None:
            current = class_option.get()
            class_map.clear()
            class_map["Todas turmas"] = None
            values = ["Todas turmas"]
            for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                label = f"{class_data['id']} - {class_data['name']}"
                values.append(label)
                class_map[label] = int(class_data["id"])
            class_option.configure(values=values)
            class_option.set(current if current in values else "Todas turmas")

        def update_fields(_value: str | None = None) -> None:
            report = report_option.get()
            member_option.configure(state="normal" if report == "Membro individual" else "disabled")
            format_option.configure(state="disabled" if report == "Portal do clube/turma" else "normal")
            portal_state = "normal" if report == "Portal do clube/turma" else "disabled"
            club_option.configure(state=portal_state)
            class_option.configure(state=portal_state)
            date_state = (
                "normal"
                if report in {
                    "Torneios por periodo",
                    "Presencas por periodo",
                    "Financeiro por periodo",
                    "Eventos por periodo",
                    "Pacote administrativo",
                }
                else "disabled"
            )
            start_entry.configure(state=date_state)
            end_entry.configure(state=date_state)

        def default_filename(report: str, extension: str) -> str:
            if report == "Membro individual" and member_option.get() in member_map:
                member_name = member_option.get().split(" - ", maxsplit=1)[1]
                safe_member_name = self._safe_filename(member_name, "relatorio")
                return f"{safe_member_name}_relatorio.{extension}"
            names = {
                "Geral do clube": "clube_relatorio",
                "Torneios por periodo": "torneios_periodo",
                "Presencas por periodo": "presencas_periodo",
                "Financeiro por periodo": "financeiro_periodo",
                "Eventos por periodo": "eventos_periodo",
                "Ranking interno": "ranking_interno",
                "Portal do clube/turma": "portal_clube",
                "Pacote administrativo": "pacote_administrativo",
            }
            return f"{names.get(report, 'relatorio')}.{extension}"

        def export_report() -> None:
            try:
                report = report_option.get()
                extension = format_option.get()
                if report == "TRF FIDE":
                    extension = "txt"
                elif report == "PGN (Partidas)":
                    extension = "pgn"
                if report == "Portal do clube/turma":
                    directory = filedialog.askdirectory(
                        title="Escolha a pasta do portal",
                        initialdir=str(self._default_export_dir()),
                    )
                    if not directory:
                        return
                    self._run_background(
                        lambda: self.export_service.export_club_portal(
                            directory,
                            club_id=selected_club_id(),
                            class_id=selected_class_id(),
                        ),
                        lambda index_path: self._show_info(f"Portal exportado:\n{index_path}"),
                        "Exportando portal...",
                    )
                    return

                file_path = filedialog.asksaveasfilename(
                    title="Gerar relatorio",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_filename(report, extension),
                    defaultextension=f".{extension}",
                    filetypes=[
                        (extension.upper(), f"*.{extension}"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != f".{extension}":
                    path = path.with_suffix(f".{extension}")

                start_date = start_entry.get()
                end_date = end_entry.get()
                member_id = member_map.get(member_option.get())

                def write_report() -> None:
                    if report == "Geral do clube":
                        self.export_service.export_club_report(path)
                    elif report == "Membro individual":
                        if not member_id:
                            raise AppError("Selecione um membro.")
                        self.export_service.export_member_report(member_id, path)
                    elif report == "Torneios por periodo":
                        self.export_service.export_tournaments_period_report(path, start_date, end_date)
                    elif report == "Presencas por periodo":
                        self.export_service.export_attendance_report(path, start_date, end_date)
                    elif report == "Financeiro por periodo":
                        self.export_service.export_financial_report(path, start_date, end_date)
                    elif report == "Eventos por periodo":
                        self.export_service.export_events_report(path, start_date, end_date)
                    elif report == "Ranking interno":
                        self.export_service.export_internal_ranking_report(path)
                    elif report == "Pacote administrativo":
                        self.export_service.export_administrative_package(path, start_date, end_date)
                    else:
                        raise AppError("Tipo de relatorio invalido.")

                self._run_background(
                    write_report,
                    lambda _result: self._show_info(f"Relatorio exportado:\n{path}"),
                    "Gerando relatorio...",
                )
            except Exception as exc:
                self._show_error(exc)

        report_option.configure(command=update_fields)
        club_option.configure(
            command=lambda _value: (
                load_class_options(selected_club_id()),
                update_fields(),
            )
        )
        load_class_options()
        update_fields()
        ctk.CTkButton(panel, text="Gerar relatorio", command=export_report).grid(
            row=5,
            column=0,
            padx=16,
            pady=(0, 16),
            sticky="w",
        )

    def show_export(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        self._clear_content()
        self._page_title(
            "Exportar",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("export")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")

        panel = self._make_panel(body)
        panel.pack(anchor="nw", fill="x", padx=0, pady=0)

        rounds = sorted(
            self.db.list_rounds(self.current_tournament_id),
            key=lambda item: item["number"],
        )
        export_round_map: dict[str, int] = {}
        round_values = []
        for round_data in rounds:
            label = f"Rodada {round_data['number']} - {round_data['status']}"
            round_values.append(label)
            export_round_map[label] = round_data["id"]
        if not round_values:
            round_values = ["Sem rodadas"]

        report_values = [
            "Completo",
            "Classificacao",
            "Tabela cruzada",
            "Taxas de rating",
            "Rating FIDE",
            "Premiacao",
            "Estatistica de federacoes",
            "Estatistica de partidas",
            "Fichas individuais",
            "Normas FIDE",
            "Formulario de arbitro (IA/FA)",
            "Ata final",
            "Podio (poster)",
            "Desempates",
            "Rodada especifica",
            "Boletim da rodada",
            "Todas as rodadas",
            "Jogadores",
            "Site HTML",
            "JSON publico",
            "Access (banco)",
            "Chess-Results (TRF16)",
            "TRF FIDE",
            "Pendencias TRF",
            "PGN (Partidas)",
        ]
        if tournament and tournament.get("competition_type") == "team":
            report_values.insert(5, "Equipes")
            report_values.insert(6, "Escalacoes equipes")

        ctk.CTkLabel(panel, text="Relatorio").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        report_option = ctk.CTkOptionMenu(
            panel,
            values=report_values,
            width=230,
        )
        report_option.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(panel, text="Formato").grid(row=0, column=1, padx=16, pady=(16, 4), sticky="w")
        format_option = ctk.CTkOptionMenu(panel, values=["csv", "xlsx", "pdf"], width=140)
        format_option.grid(row=1, column=1, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(panel, text="Rodada").grid(row=0, column=2, padx=16, pady=(16, 4), sticky="w")
        round_option = ctk.CTkOptionMenu(panel, values=round_values, width=190)
        round_option.grid(row=1, column=2, padx=16, pady=(0, 12), sticky="w")

        status_text = (
            f"Status do torneio: {tournament['status']}"
            if tournament
            else "Nenhum torneio selecionado"
        )
        ctk.CTkLabel(panel, text=status_text, text_color=THEME_TEXT_SUB).grid(
            row=2,
            column=0,
            columnspan=4,
            padx=16,
            pady=(0, 16),
            sticky="w",
        )

        def update_round_state(_value: str | None = None) -> None:
            if report_option.get() in ("Rodada especifica", "Boletim da rodada") and export_round_map:
                round_option.configure(state="normal")
            else:
                round_option.configure(state="disabled")
            if report_option.get() == "Tabela cruzada":
                formats = ["csv", "xlsx", "pdf", "html"]
            elif report_option.get() == "Taxas de rating":
                formats = ["xlsx", "pdf"]
            else:
                formats = ["csv", "xlsx", "pdf"]
            format_option.configure(values=formats)
            if format_option.get() not in formats:
                format_option.set(formats[0])
            if report_option.get() in ("Site HTML", "JSON publico", "Access (banco)", "Podio (poster)", "Chess-Results (TRF16)", "TRF FIDE", "PGN (Partidas)"):
                format_option.configure(state="disabled")
            else:
                format_option.configure(state="normal")

        report_option.configure(command=update_round_state)
        update_round_state()

        def default_filename(report: str, extension: str) -> str:
            tournament_name = tournament["name"] if tournament else "torneio"
            safe_name = self._safe_filename(tournament_name, "torneio")
            names = {
                "Completo": f"{safe_name}_completo",
                "Classificacao": f"{safe_name}_classificacao",
                "Tabela cruzada": f"{safe_name}_tabela_cruzada",
                "Taxas de rating": f"{safe_name}_taxas_rating",
                "Rating FIDE": f"{safe_name}_rating_fide",
                "Premiacao": f"{safe_name}_premiacao",
                "Estatistica de federacoes": f"{safe_name}_estatistica_federacoes",
                "Estatistica de partidas": f"{safe_name}_estatistica_partidas",
                "Fichas individuais": f"{safe_name}_fichas",
                "Normas FIDE": f"{safe_name}_normas_fide",
                "Formulario de arbitro (IA/FA)": f"{safe_name}_arbitro_ia_fa",
                "Ata final": f"{safe_name}_ata_final",
                "Podio (poster)": f"{safe_name}_podio",
                "Desempates": f"{safe_name}_desempates",
                "Rodada especifica": f"{safe_name}_rodada",
                "Boletim da rodada": f"{safe_name}_boletim",
                "Todas as rodadas": f"{safe_name}_rodadas",
                "Jogadores": f"{safe_name}_jogadores",
                "Equipes": f"{safe_name}_equipes",
                "Escalacoes equipes": f"{safe_name}_escalacoes_equipes",
                "JSON publico": f"{safe_name}_publico",
                "Chess-Results (TRF16)": f"{safe_name}_chess_results_trf16",
                "TRF FIDE": f"{safe_name}_fide",
                "Pendencias TRF": f"{safe_name}_pendencias_trf",
                "PGN (Partidas)": f"{safe_name}_partidas",
            }
            if report in ("Rodada especifica", "Boletim da rodada") and round_option.get() in export_round_map:
                round_number = round_option.get().split(" ", maxsplit=2)[1]
                suffix = "boletim" if report == "Boletim da rodada" else "rodada"
                names[report] = f"{safe_name}_{suffix}_{round_number}"
            return f"{names[report]}.{extension}"

        trf_warning_label = ctk.CTkLabel(
            panel,
            text="Clique em Validar TRF FIDE para conferir pendencias antes de gerar o arquivo.",
            text_color=THEME_TEXT_SUB,
            justify="left",
            anchor="w",
            wraplength=980,
        )
        trf_warning_label.grid(row=3, column=0, columnspan=5, padx=16, pady=(0, 16), sticky="ew")

        def set_trf_validation_text(message: str) -> None:
            trf_warning_label.configure(text=message)

        def validate_trf() -> None:
            try:
                tournament_id = int(self.current_tournament_id)
                warnings = self.export_service.validate_chess_results_trf(tournament_id)
                if warnings:
                    warning_text = "\n".join(f"- {item}" for item in warnings)
                    set_trf_validation_text(f"TRF pode ser gerado, mas ha avisos:\n\n{warning_text}")
                    return
                set_trf_validation_text("TRF validado. Nenhum aviso encontrado.")
            except Exception as exc:
                set_trf_validation_text(f"TRF nao pode ser gerado:\n\n{exc}")
                self._show_error(exc)

        def export() -> None:
            try:
                report = report_option.get()
                extension = format_option.get()
                if report in ("Chess-Results (TRF16)", "TRF FIDE"):
                    extension = "trf"
                elif report == "JSON publico":
                    extension = "json"
                elif report == "PGN (Partidas)":
                    extension = "pgn"
                elif report == "Podio (poster)":
                    extension = "pdf"
                tournament_id = int(self.current_tournament_id)
                if report == "Site HTML":
                    directory = filedialog.askdirectory(
                        title="Escolha a pasta do site",
                        initialdir=str(self._default_export_dir()),
                    )
                    if not directory:
                        return
                    self._run_background(
                        lambda: self.export_service.export_site(tournament_id, directory),
                        lambda index_path: self._show_info(f"Site exportado:\n{index_path}"),
                        "Exportando site HTML...",
                    )
                    return

                if report == "Access (banco)":
                    directory = filedialog.askdirectory(
                        title="Pasta para o banco Access",
                        initialdir=str(self._default_export_dir()),
                    )
                    if not directory:
                        return

                    def show_access(result: dict[str, Any]) -> None:
                        tables = ", ".join(result.get("tables") or [])
                        message = (
                            f"Pacote Access gerado em:\n{directory}\n\n"
                            f"Tabelas: {tables}.\nCSV + schema.ini (Dados Externos -> Arquivo de Texto no Access)."
                        )
                        if result.get("accdb"):
                            message += f"\n\nBanco .accdb real: {result['accdb']}"
                        else:
                            message += (
                                "\n\n(.accdb real indisponivel: instale o driver Microsoft Access "
                                "para gerar o banco nativo; o pacote CSV ja e importavel.)"
                            )
                        self._show_info(message)

                    self._run_background(
                        lambda: self.export_service.export_access(tournament_id, directory),
                        show_access,
                        "Gerando banco Access...",
                    )
                    return

                file_path = filedialog.asksaveasfilename(
                    title="Gerar exportacao",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_filename(report, extension),
                    defaultextension=f".{extension}",
                    filetypes=[
                        (extension.upper(), f"*.{extension}"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != f".{extension}":
                    path = path.with_suffix(f".{extension}")

                round_id = export_round_map.get(round_option.get())

                def write_export() -> object:
                    if report == "Completo":
                        self.export_service.export_complete(tournament_id, path)
                    elif report == "Classificacao":
                        self.export_service.export_standings(tournament_id, path)
                    elif report == "Tabela cruzada":
                        self.export_service.export_crosstable(tournament_id, path)
                    elif report == "Taxas de rating":
                        self.export_service.export_rating_fee_report(tournament_id, path)
                    elif report == "Rating FIDE":
                        self.export_service.export_fide_rating_report(tournament_id, path, "fide")
                    elif report == "Premiacao":
                        self.export_service.export_prize_report(tournament_id, path)
                    elif report == "Estatistica de federacoes":
                        self.export_service.export_federation_statistics(tournament_id, path)
                    elif report == "Estatistica de partidas":
                        self.export_service.export_game_statistics(tournament_id, path)
                    elif report == "Fichas individuais":
                        self.export_service.export_player_cards(tournament_id, path)
                    elif report == "Normas FIDE":
                        self.export_service.export_norm_report(tournament_id, path)
                    elif report == "Formulario de arbitro (IA/FA)":
                        self.export_service.export_arbiter_norm_report(tournament_id, path)
                    elif report == "Ata final":
                        self.export_service.export_tournament_minutes(tournament_id, path)
                    elif report == "Podio (poster)":
                        self.export_service.export_podium(tournament_id, path)
                    elif report == "Desempates":
                        self.export_service.export_tiebreak_report(tournament_id, path)
                    elif report == "Rodada especifica":
                        if not round_id:
                            raise AppError("Selecione uma rodada para exportar.")
                        self.export_service.export_pairings(round_id, path)
                    elif report == "Boletim da rodada":
                        if not round_id:
                            raise AppError("Selecione uma rodada para o boletim.")
                        self.export_service.export_round_bulletin(round_id, path)
                    elif report == "Todas as rodadas":
                        self.export_service.export_all_rounds(tournament_id, path)
                    elif report == "Jogadores":
                        self.export_service.export_players(tournament_id, path)
                    elif report == "Equipes":
                        self.export_service.export_teams(tournament_id, path)
                    elif report == "Escalacoes equipes":
                        self.export_service.export_team_lineups(tournament_id, path)
                    elif report == "JSON publico":
                        self.export_service.export_public_json(tournament_id, path)
                    elif report == "Chess-Results (TRF16)":
                        return self.export_service.export_chess_results_trf(tournament_id, path)
                    elif report == "TRF FIDE":
                        return self.export_service.export_chess_results_trf25(tournament_id, path)
                    elif report == "Pendencias TRF":
                        self.export_service.export_chess_results_trf_validation_report(tournament_id, path)
                    elif report == "PGN (Partidas)":
                        self.export_service.export_pgn(tournament_id, path)
                    else:
                        raise AppError("Tipo de relatorio invalido.")
                    return None

                def show_export_success(result: object) -> None:
                    warnings = result if isinstance(result, list) else []
                    if warnings:
                        warning_text = "\n".join(str(item) for item in warnings[:8])
                        extra = f"\n... e mais {len(warnings) - 8} aviso(s)." if len(warnings) > 8 else ""
                        self._show_info(f"Arquivo exportado:\n{path}\n\nAvisos:\n{warning_text}{extra}")
                        return
                    self._show_info(f"Arquivo exportado:\n{path}")

                self._run_background(
                    write_export,
                    show_export_success,
                    "Gerando exportacao...",
                )
            except Exception as exc:
                self._show_error(exc)

        ctk.CTkButton(panel, text="Gerar arquivo", command=export).grid(
            row=1,
            column=3,
            padx=16,
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(panel, text="Validar TRF FIDE", command=validate_trf).grid(
            row=1,
            column=4,
            padx=(0, 16),
            pady=(0, 12),
            sticky="w",
        )
        ctk.CTkButton(panel, text="Geracao em lote", command=self._open_batch_export_dialog).grid(
            row=1,
            column=5,
            padx=(0, 16),
            pady=(0, 12),
            sticky="w",
        )

        trf_help_panel = self._make_panel(body)
        trf_help_panel.pack(anchor="nw", fill="x", pady=(12, 0))
        trf_help_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            trf_help_panel,
            text="Preparacao FIDE/TRF",
            font=font_section(),
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            trf_help_panel,
            text=(
                "Antes de gerar o TRF, confira em Config. Torneio: local, datas, ritmo, federacao e arbitro-chefe. "
                "Em Jogadores, confira FIDE ID, rating FIDE, federacao/clube e nascimento."
            ),
            text_color=THEME_TEXT_SUB,
            wraplength=920,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            trf_help_panel,
            text="Corrigir Config. Torneio",
            command=self.show_tournament_settings,
        ).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")
        ctk.CTkButton(
            trf_help_panel,
            text="Corrigir Jogadores",
            command=self.show_players,
        ).grid(row=2, column=1, padx=(0, 16), pady=(0, 16), sticky="w")
        ctk.CTkButton(
            trf_help_panel,
            text="Importar/atualizar ratings oficiais",
            command=self.show_players,
        ).grid(row=2, column=2, padx=(0, 16), pady=(0, 16), sticky="w")

    def _open_batch_export_dialog(self) -> None:
        if not self._require_tournament():
            return
        tournament_id = int(self.current_tournament_id)
        try:
            reports = self.batch_export_service.available_reports(tournament_id)
        except Exception as exc:
            self._show_error(exc)
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Geracao em lote (multi-destino)")
        dialog.geometry("560x640")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Selecione os relatorios e formatos para gerar de uma vez na mesma pasta.",
            text_color=THEME_TEXT_SUB,
            anchor="w",
            justify="left",
            wraplength=520,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")

        reports_frame = ctk.CTkScrollableFrame(dialog, label_text="Relatorios")
        reports_frame.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="nsew")
        report_checks: dict[str, ctk.CTkCheckBox] = {}
        for spec in reports:
            check = ctk.CTkCheckBox(
                reports_frame,
                text=f"{spec['label']}  ({'/'.join(spec['formats'])})",
                onvalue="1",
                offvalue="0",
            )
            check.deselect()
            check.pack(anchor="w", padx=8, pady=2)
            report_checks[spec["key"]] = check

        formats_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        formats_frame.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(formats_frame, text="Formatos:").pack(side="left", padx=(0, 8))
        format_checks: dict[str, ctk.CTkCheckBox] = {}
        for fmt in ("csv", "xlsx", "pdf", "html"):
            check = ctk.CTkCheckBox(formats_frame, text=fmt.upper(), onvalue="1", offvalue="0", width=70)
            if fmt == "pdf":
                check.select()
            else:
                check.deselect()
            check.pack(side="left", padx=4)
            format_checks[fmt] = check

        options_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        options_frame.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        html_switch = ctk.CTkSwitch(options_frame, text="Tambem gerar site HTML", onvalue="1", offvalue="0")
        html_switch.deselect()
        html_switch.pack(side="left", padx=(0, 16))
        printer_switch = ctk.CTkSwitch(options_frame, text="Enviar PDFs para impressora", onvalue="1", offvalue="0")
        printer_switch.deselect()
        printer_switch.pack(side="left")

        def run() -> None:
            keys = [key for key, check in report_checks.items() if check.get() == "1"]
            fmts = [fmt for fmt, check in format_checks.items() if check.get() == "1"]
            if not keys:
                self._show_warning("Selecione ao menos um relatorio.")
                return
            if not fmts:
                self._show_warning("Selecione ao menos um formato.")
                return
            directory = filedialog.askdirectory(
                title="Pasta de destino do lote",
                initialdir=str(self._default_export_dir()),
            )
            if not directory:
                return
            also_html = html_switch.get() == "1"
            printer_cb = self._print_document if printer_switch.get() == "1" else None
            dialog.destroy()

            def show_result(result: dict[str, Any]) -> None:
                message = f"{result['count']} arquivos gerados em:\n{directory}"
                if result.get("skipped"):
                    message += "\n\nIgnorados:\n" + "\n".join(result["skipped"][:8])
                if result.get("errors"):
                    message += "\n\nErros:\n" + "\n".join(result["errors"][:8])
                self._show_info(message)

            self._run_background(
                lambda: self.batch_export_service.run_batch(
                    tournament_id, keys, fmts, directory, also_html=also_html, printer_cb=printer_cb
                ),
                show_result,
                "Gerando lote multi-destino...",
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
        ctk.CTkButton(buttons, text="Escolher pasta e gerar", command=run).pack(side="left")
