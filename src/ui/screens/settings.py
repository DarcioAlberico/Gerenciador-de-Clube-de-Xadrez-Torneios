from __future__ import annotations

from ..support import *


class SettingsPagesMixin:
    def show_app_settings(self) -> None:
        self._clear_content()
        self._page_title(
            "Configuracoes do aplicativo",
            "Ajuste preferencias locais, pasta de exportacao e rotinas de backup.",
        )

        settings = self.db.get_app_settings()
        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        settings_panel = self._make_scrollable_panel(body, width=340)
        settings_panel.grid(row=0, column=0, padx=(0, 16), sticky="ns")

        appearance_labels = {"System": "Sistema", "Light": "Claro", "Dark": "Escuro"}
        appearance_values = {label: value for value, label in appearance_labels.items()}
        ctk.CTkLabel(settings_panel, text="Aparencia").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 4),
            sticky="w",
        )
        appearance_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(appearance_values.keys()),
            width=250,
        )
        appearance_option.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        appearance_option.set(appearance_labels.get(settings.get("appearance_mode", "System"), "Sistema"))

        color_theme_labels = {"blue": "Azul (Padrao)", "green": "Verde", "dark-blue": "Azul Escuro"}
        color_theme_values = {label: value for value, label in color_theme_labels.items()}
        ctk.CTkLabel(settings_panel, text="Cor de destaque").grid(
            row=2,
            column=0,
            padx=16,
            pady=(8, 4),
            sticky="w",
        )
        color_theme_option = ctk.CTkOptionMenu(
            settings_panel,
            values=list(color_theme_values.keys()),
            width=250,
        )
        color_theme_option.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="ew")
        color_theme_option.set(color_theme_labels.get(settings.get("color_theme", "blue"), "Azul (Padrao)"))

        ctk.CTkLabel(settings_panel, text="Pasta de exportacao").grid(
            row=4,
            column=0,
            padx=16,
            pady=(8, 4),
            sticky="w",
        )
        export_dir_entry = ctk.CTkEntry(settings_panel, width=320)
        export_dir_entry.grid(row=5, column=0, padx=16, pady=(0, 8), sticky="ew")
        export_dir_entry.insert(0, str(settings.get("default_export_dir") or default_export_dir()))

        ctk.CTkLabel(settings_panel, text="Pasta de backups").grid(
            row=6,
            column=0,
            padx=16,
            pady=(8, 4),
            sticky="w",
        )
        backup_dir_entry = ctk.CTkEntry(settings_panel, width=320)
        backup_dir_entry.grid(row=7, column=0, padx=16, pady=(0, 8), sticky="ew")
        backup_dir_entry.insert(0, str(settings.get("backup_dir") or self.db.backup_dir))

        def choose_export_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta de exportacao",
                initialdir=str(self._default_export_dir()),
            )
            if directory:
                export_dir_entry.delete(0, "end")
                export_dir_entry.insert(0, directory)

        def choose_backup_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta de backups",
                initialdir=str(self.db.backup_dir),
            )
            if directory:
                backup_dir_entry.delete(0, "end")
                backup_dir_entry.insert(0, directory)

        ctk.CTkButton(settings_panel, text="Escolher exportacao", command=choose_export_dir).grid(
            row=8,
            column=0,
            padx=16,
            pady=(0, 8),
            sticky="ew",
        )
        ctk.CTkButton(settings_panel, text="Escolher backups", command=choose_backup_dir).grid(
            row=11,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="ew",
        )


        ctk.CTkLabel(settings_panel, text="Pasta de Nuvem (Google Drive/Dropbox)").grid(
            row=12,
            column=0,
            padx=16,
            pady=(8, 4),
            sticky="w",
        )
        cloud_dir_entry = ctk.CTkEntry(settings_panel, width=320)
        cloud_dir_entry.grid(row=13, column=0, padx=16, pady=(0, 8), sticky="ew")
        cloud_dir_entry.insert(0, str(settings.get("cloud_sync_dir", "")))

        def choose_cloud_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta sincronizada em nuvem",
                initialdir="/",
            )
            if directory:
                cloud_dir_entry.delete(0, "end")
                cloud_dir_entry.insert(0, directory)

        ctk.CTkButton(settings_panel, text="Escolher nuvem", command=choose_cloud_dir).grid(
            row=14,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="ew",
        )

        self._section_title(settings_panel, "Seguranca operacional").grid(
            row=15, column=0, padx=16, pady=(6, 4), sticky="w"
        )
        def open_users_manager() -> None:
            self._show_users_manager()

        ctk.CTkButton(
            settings_panel,
            text="Gerenciar Usuarios do Sistema",
            command=open_users_manager,
        ).grid(row=16, column=0, padx=16, pady=(10, 8), sticky="ew")

        ctk.CTkLabel(settings_panel, text="Manter ultimos backups").grid(
            row=17,
            column=0,
            padx=16,
            pady=(6, 4),
            sticky="w",
        )
        retention_entry = ctk.CTkEntry(settings_panel, width=120)
        retention_entry.grid(row=18, column=0, padx=16, pady=(0, 14), sticky="w")
        retention_entry.insert(0, str(settings.get("backup_retention_count") or "10"))

        ctk.CTkLabel(settings_panel, text="Tamanho da fonte/interface (%)").grid(
            row=19,
            column=0,
            padx=16,
            pady=(6, 4),
            sticky="w",
        )
        ui_scale_entry = ctk.CTkEntry(settings_panel, width=120)
        ui_scale_entry.grid(row=20, column=0, padx=16, pady=(0, 14), sticky="w")
        ui_scale_entry.insert(0, str(settings.get("ui_scale_percent") or "120"))

        self._section_title(settings_panel, "Sincronizacao de Ratings").grid(
            row=21, column=0, padx=16, pady=(16, 4), sticky="w"
        )

        def download_fide() -> None:
            import threading
            from tkinter import messagebox
            
            def worker():
                try:
                    res = self.official_rating_service.import_fide_list_from_url()
                    msg = f"{res['imported']} jogadores da FIDE importados."
                    self.after(0, lambda m=msg: messagebox.showinfo("Sucesso", m))
                except Exception as exc:
                    err_msg = str(exc)
                    self.after(0, lambda m=err_msg: messagebox.showerror("Erro", m))
            
            threading.Thread(target=worker, daemon=True).start()
            messagebox.showinfo("Aviso", "Download da FIDE iniciado em segundo plano (pode levar alguns minutos).")

        ctk.CTkButton(
            settings_panel,
            text="Baixar e Sincronizar FIDE",
            command=download_fide,
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
        ).grid(row=22, column=0, padx=16, pady=(10, 8), sticky="ew")

        def import_cbx() -> None:
            from tkinter import filedialog, messagebox
            path = filedialog.askopenfilename(filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("XML", "*.xml"), ("Texto", "*.txt")])
            if not path:
                return
            try:
                suffix = str(path).lower()
                if suffix.endswith(".xml"):
                    res = self.official_rating_service.import_official_xml(path, "CBX", "")
                elif suffix.endswith(".xls") or suffix.endswith(".xlsx"):
                    res = self.official_rating_service.import_official_excel(path, "CBX", "")
                else:
                    res = self.official_rating_service.import_official_csv(path, "CBX", "")
                messagebox.showinfo("Sucesso", f"{res['imported']} jogadores CBX importados!")
            except Exception as exc:
                messagebox.showerror("Erro", str(exc))

        ctk.CTkButton(
            settings_panel,
            text="Importar Lista CBX (Excel / CSV / XML)",
            command=import_cbx,
        ).grid(row=23, column=0, padx=16, pady=(0, 14), sticky="ew")

        backup_panel = self._make_panel(body)
        backup_panel.grid(row=0, column=1, sticky="nsew")
        backup_panel.grid_columnconfigure(0, weight=1)
        backup_panel.grid_rowconfigure(1, weight=2)
        backup_panel.grid_rowconfigure(3, weight=1)

        backup_header = ctk.CTkFrame(backup_panel, fg_color="transparent")
        backup_header.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        backup_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            backup_header,
            text="Backups disponiveis",
            font=font_section(),
        ).grid(row=0, column=0, sticky="w")

        backup_holder = ctk.CTkFrame(backup_panel, fg_color="transparent")
        backup_holder.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        backup_holder.grid_columnconfigure(0, weight=1)
        backup_holder.grid_rowconfigure(0, weight=1)
        backup_tree = self._make_tree(
            backup_holder,
            ["name", "modified", "size"],
            {"name": "Arquivo", "modified": "Modificado em", "size": "Tamanho"},
            {"name": 330, "modified": 150, "size": 90},
        )
        backup_paths: dict[str, str] = {}

        audit_header = ctk.CTkFrame(backup_panel, fg_color="transparent")
        audit_header.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
        audit_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            audit_header,
            text="Auditoria recente",
            font=font_section(),
        ).grid(row=0, column=0, sticky="w")
        audit_holder = ctk.CTkFrame(backup_panel, fg_color="transparent")
        audit_holder.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        audit_holder.grid_columnconfigure(0, weight=1)
        audit_holder.grid_rowconfigure(0, weight=1)
        audit_tree = self._make_tree(
            audit_holder,
            ["created", "actor", "role", "action", "description"],
            {
                "created": "Data",
                "actor": "Operador",
                "role": "Perfil",
                "action": "Acao",
                "description": "Descricao",
            },
            {"created": 145, "actor": 120, "role": 100, "action": 140, "description": 260},
            visible_rows=6,
        )

        def backup_size_label(size_bytes: int) -> str:
            if size_bytes >= 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            return f"{size_bytes / 1024:.1f} KB"

        def load_backups() -> None:
            backup_tree.delete(*backup_tree.get_children())
            backup_paths.clear()
            for backup in self.db.list_backups():
                row_id = backup_tree.insert(
                    "",
                    "end",
                    values=(
                        backup["name"],
                        backup["modified_at"],
                        backup_size_label(int(backup["size_bytes"])),
                    ),
                )
                backup_paths[row_id] = str(backup["path"])

        def load_audit_logs() -> None:
            audit_tree.delete(*audit_tree.get_children())
            for row in self.security_service.list_audit_logs(limit=100):
                audit_tree.insert(
                    "",
                    "end",
                    values=(
                        row["created_at"],
                        row.get("actor") or "",
                        OPERATOR_ROLES.get(row.get("role"), row.get("role") or ""),
                        row["action"],
                        row.get("description") or "",
                    ),
                )

        def persist_settings() -> None:
            export_dir = Path(export_dir_entry.get().strip() or default_export_dir())
            backup_dir = Path(backup_dir_entry.get().strip() or default_backup_dir())
            try:
                ui_scale_percent = int(ui_scale_entry.get().strip() or "120")
            except ValueError as exc:
                raise AppError("Tamanho da fonte/interface deve ser um numero entre 80 e 160.") from exc
            if ui_scale_percent < 80 or ui_scale_percent > 160:
                raise AppError("Tamanho da fonte/interface deve ficar entre 80 e 160.")
            export_dir.mkdir(parents=True, exist_ok=True)
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.db.save_app_settings(
                {
                    "appearance_mode": appearance_values[appearance_option.get()],
                    "color_theme": color_theme_values[color_theme_option.get()],
                    "default_export_dir": str(export_dir),
                    "backup_dir": str(backup_dir),
                    "cloud_sync_dir": cloud_dir_entry.get().strip(),
                    "ui_scale_percent": str(ui_scale_percent),
                }
            )
            self.security_service.save_security_settings(
                {
                    "backup_retention_count": retention_entry.get(),
                }
            )
            ctk.set_appearance_mode(appearance_values[appearance_option.get()])
            self._apply_app_settings()
            self._configure_tree_style(register_callback=False)
            
            if settings.get("color_theme") != color_theme_values[color_theme_option.get()]:
                self._show_info("Reinicie o aplicativo para aplicar o novo tema de cores.")

            self.status_label.configure(text=f"Banco: {Path(self.db.db_path).name}")
            load_backups()
            load_audit_logs()

        def save_settings(show_message: bool = True) -> None:
            try:
                persist_settings()
                if show_message:
                    self._show_toast("Configuracoes salvas.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def create_backup() -> None:
            try:
                persist_settings()
                self._run_background(
                    lambda: self.security_service.create_backup("manual"),
                    lambda result: (
                        load_backups(),
                        load_audit_logs(),
                        self._show_info(f"Backup criado:\n{result['path']}"),
                    ),
                    "Criando backup...",
                )
            except Exception as exc:
                self._show_error(exc)

        def restore_selected() -> None:
            try:
                selected = backup_tree.selection()
                if not selected:
                    raise AppError("Selecione um backup para restaurar.")
                backup_path = backup_paths.get(selected[0])
                if not backup_path:
                    raise AppError("Backup selecionado invalido.")
                confirmed = messagebox.askyesno(
                    "Restaurar backup",
                    "A restauracao substitui o banco atual. Um backup de seguranca sera criado antes. Continuar?",
                )
                if not confirmed:
                    return
                def show_restore_result(safety_backup: Path) -> None:
                    self._apply_app_settings()
                    load_backups()
                    load_audit_logs()
                    self._show_info(f"Backup restaurado.\nCopia de seguranca criada em:\n{safety_backup}")
                    self.show_club()

                self._run_background(
                    lambda: self.security_service.restore_backup(backup_path),
                    show_restore_result,
                    "Restaurando backup...",
                )
            except Exception as exc:
                self._show_error(exc)

        def apply_retention() -> None:
            try:
                persist_settings()
                deleted = self.security_service.enforce_backup_retention()
                load_backups()
                load_audit_logs()
                self._show_toast(f"Retencao aplicada. {len(deleted)} backup(s) removido(s).", kind="success")
            except Exception as exc:
                self._show_error(exc)

        actions = ctk.CTkFrame(settings_panel, fg_color="transparent")
        actions.grid(row=24, column=0, padx=16, pady=(0, 16), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        btn_save = ctk.CTkButton(actions, text="Salvar configuracoes", command=lambda: save_settings())
        btn_save.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        self._disable_if_unauthorized(btn_save, "settings_write")
        
        btn_backup = ctk.CTkButton(actions, text="Criar backup agora", command=create_backup)
        btn_backup.grid(row=1, column=0, pady=(0, 8), sticky="ew")
        self._disable_if_unauthorized(btn_backup, "settings_write")
        
        btn_retention = ctk.CTkButton(actions, text="Aplicar retencao", command=apply_retention)
        btn_retention.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        self._disable_if_unauthorized(btn_retention, "settings_write")
        
        btn_restore = ctk.CTkButton(actions, text="Restaurar selecionado", command=restore_selected)
        btn_restore.grid(row=3, column=0, sticky="ew")
        self._disable_if_unauthorized(btn_restore, "settings_write")

        load_backups()
        load_audit_logs()

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
            "Desempates",
            "Rodada especifica",
            "Todas as rodadas",
            "Jogadores",
            "Site HTML",
            "JSON publico",
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
            if report_option.get() == "Rodada especifica" and export_round_map:
                round_option.configure(state="normal")
            else:
                round_option.configure(state="disabled")
            if report_option.get() in ("Site HTML", "JSON publico", "Chess-Results (TRF16)", "TRF FIDE", "PGN (Partidas)"):
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
                "Desempates": f"{safe_name}_desempates",
                "Rodada especifica": f"{safe_name}_rodada",
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
            if report == "Rodada especifica" and round_option.get() in export_round_map:
                round_number = round_option.get().split(" ", maxsplit=2)[1]
                names[report] = f"{safe_name}_rodada_{round_number}"
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
                    elif report == "Desempates":
                        self.export_service.export_tiebreak_report(tournament_id, path)
                    elif report == "Rodada especifica":
                        if not round_id:
                            raise AppError("Selecione uma rodada para exportar.")
                        self.export_service.export_pairings(round_id, path)
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

    def _show_certificates_tournament_only(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        self._clear_content()
        self._page_title(
            "Diplomas",
            f"Torneio: {tournament['name'] if tournament else ''}",
        )
        self._build_tournament_nav("certificates")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form_panel = self._make_scrollable_panel(body, width=340)
        form_panel.grid(row=0, column=0, padx=(0, 14), sticky="nsw")

        table_panel = self._make_panel(body)
        table_panel.grid(row=0, column=1, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)

        type_labels = {value: label for label, value in CERTIFICATE_TYPE_VALUES.items()}
        orientation_labels = {value: label for label, value in CERTIFICATE_ORIENTATION_VALUES.items()}
        templates = self.certificate_service.list_templates(active_only=True)
        template_map = {str(template["name"]): template for template in templates}
        template_values = list(template_map) or ["Sem modelo"]
        recipient_values = ["Todos", "Top N geral", "Top N por categoria", "Selecionados na lista"]
        standings = (
            self.pairing_service.standings(self.current_tournament_id)
            if tournament and tournament.get("competition_type") != "team"
            else []
        )
        categories = sorted(
            {
                str(item.get("category") or "").strip()
                for item in standings
                if str(item.get("category") or "").strip()
            },
            key=lambda value: value.casefold(),
        )
        category_values = ["Todas"] + categories if categories else ["Todas"]
        selected_template_id: dict[str, int | None] = {
            "value": int(templates[0]["id"]) if templates else None,
        }

        ctk.CTkLabel(form_panel, text="Modelo salvo").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        template_option = ctk.CTkOptionMenu(form_panel, values=template_values, width=270)
        template_option.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Nome do modelo").grid(row=2, column=0, padx=16, pady=(2, 4), sticky="w")
        template_name_entry = ctk.CTkEntry(form_panel, width=270)
        template_name_entry.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Tipo").grid(row=4, column=0, padx=16, pady=(2, 4), sticky="w")
        type_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_TYPE_VALUES.keys()), width=270)
        type_option.grid(row=5, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Orientacao").grid(row=6, column=0, padx=16, pady=(2, 4), sticky="w")
        orientation_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_ORIENTATION_VALUES.keys()), width=270)
        orientation_option.grid(row=7, column=0, padx=16, pady=(0, 10), sticky="ew")

        assets_frame = ctk.CTkFrame(form_panel, fg_color="transparent")
        assets_frame.grid(row=8, column=0, padx=16, pady=(2, 10), sticky="ew")
        assets_frame.grid_columnconfigure(0, weight=1)

        def choose_image(entry: ctk.CTkEntry, title: str) -> None:
            file_path = filedialog.askopenfilename(
                title=title,
                initialdir=str(BASE_DIR),
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if file_path:
                entry.delete(0, "end")
                entry.insert(0, file_path)
                update_count()

        ctk.CTkLabel(assets_frame, text="Logo principal").grid(row=0, column=0, pady=(0, 4), sticky="w")
        logo_entry = ctk.CTkEntry(assets_frame, width=270)
        logo_entry.grid(row=1, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo principal",
            command=lambda: choose_image(logo_entry, "Escolher logo principal"),
        ).grid(row=2, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Logo secundario").grid(row=3, column=0, pady=(0, 4), sticky="w")
        secondary_logo_entry = ctk.CTkEntry(assets_frame, width=270)
        secondary_logo_entry.grid(row=4, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo secundario",
            command=lambda: choose_image(secondary_logo_entry, "Escolher logo secundario"),
        ).grid(row=5, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Imagem de fundo").grid(row=6, column=0, pady=(0, 4), sticky="w")
        background_image_entry = ctk.CTkEntry(assets_frame, width=270)
        background_image_entry.grid(row=7, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher fundo",
            command=lambda: choose_image(background_image_entry, "Escolher imagem de fundo"),
        ).grid(row=8, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Opacidade do fundo").grid(row=9, column=0, pady=(0, 4), sticky="w")
        background_opacity_entry = ctk.CTkEntry(assets_frame, width=90)
        background_opacity_entry.grid(row=10, column=0, pady=(0, 0), sticky="w")
        background_opacity_entry.insert(0, "0.18")

        ctk.CTkLabel(form_panel, text="Cor principal").grid(row=11, column=0, padx=16, pady=(2, 4), sticky="w")
        primary_color_entry = ctk.CTkEntry(form_panel, width=140)
        primary_color_entry.grid(row=12, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Cor de destaque").grid(row=13, column=0, padx=16, pady=(2, 4), sticky="w")
        accent_color_entry = ctk.CTkEntry(form_panel, width=140)
        accent_color_entry.grid(row=14, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do titulo").grid(row=15, column=0, padx=16, pady=(2, 4), sticky="w")
        title_font_entry = ctk.CTkEntry(form_panel, width=80)
        title_font_entry.grid(row=16, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do texto").grid(row=17, column=0, padx=16, pady=(2, 4), sticky="w")
        body_font_entry = ctk.CTkEntry(form_panel, width=80)
        body_font_entry.grid(row=18, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do rodape").grid(row=19, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_font_entry = ctk.CTkEntry(form_panel, width=80)
        footer_font_entry.grid(row=20, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Titulo").grid(row=21, column=0, padx=16, pady=(2, 4), sticky="w")
        title_entry = ctk.CTkEntry(form_panel, width=270)
        title_entry.grid(row=22, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Texto principal").grid(row=23, column=0, padx=16, pady=(2, 4), sticky="w")
        body_textbox = ctk.CTkTextbox(form_panel, width=270, height=110)
        body_textbox.grid(row=24, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Rodape").grid(row=25, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_entry = ctk.CTkEntry(form_panel, width=270)
        footer_entry.grid(row=26, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura esquerda").grid(row=27, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_left_entry = ctk.CTkEntry(form_panel, width=270)
        signature_left_entry.grid(row=28, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura direita").grid(row=29, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_right_entry = ctk.CTkEntry(form_panel, width=270)
        signature_right_entry.grid(row=30, column=0, padx=16, pady=(0, 14), sticky="ew")

        ctk.CTkLabel(form_panel, text="Destinatarios").grid(row=31, column=0, padx=16, pady=(4, 4), sticky="w")
        recipient_option = ctk.CTkOptionMenu(form_panel, values=recipient_values, width=230)
        recipient_option.grid(row=32, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Limite").grid(row=33, column=0, padx=16, pady=(2, 4), sticky="w")
        top_entry = ctk.CTkEntry(form_panel, width=120)
        top_entry.grid(row=34, column=0, padx=16, pady=(0, 10), sticky="w")
        top_entry.insert(0, "3")

        ctk.CTkLabel(form_panel, text="Categoria").grid(row=35, column=0, padx=16, pady=(2, 4), sticky="w")
        category_option = ctk.CTkOptionMenu(form_panel, values=category_values, width=230)
        category_option.grid(row=36, column=0, padx=16, pady=(0, 10), sticky="ew")

        count_label = ctk.CTkLabel(form_panel, text="", text_color=THEME_TEXT_SUB, wraplength=250, justify="left")
        count_label.grid(row=37, column=0, padx=16, pady=(0, 14), sticky="w")

        ctk.CTkLabel(
            table_panel,
            text="Selecione jogadores na lista apenas quando usar destinatarios selecionados.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        tree_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            tree_holder,
            ["pos", "name", "category", "points", "status"],
            {
                "pos": "Pos",
                "name": "Nome",
                "category": "Categoria",
                "points": "Pts",
                "status": "Status",
            },
            {
                "pos": 60,
                "name": 280,
                "category": 140,
                "points": 80,
                "status": 130,
            },
            visible_rows=16,
        )
        tree.configure(selectmode="extended")
        player_row_map: dict[str, int] = {}
        for item in standings:
            item_id = tree.insert(
                "",
                "end",
                values=(
                    item.get("position", ""),
                    item.get("name", ""),
                    item.get("category", ""),
                    item.get("points", 0),
                    PLAYER_STATUSES.get(item.get("player_status", "active"), "Ativo"),
                ),
            )
            player_row_map[item_id] = int(item["player_id"])

        if tournament and tournament.get("competition_type") == "team":
            count_label.configure(text="Diplomas por equipes ficam para uma etapa futura.")
            tree.configure(selectmode="none")

        def set_entry(entry: ctk.CTkEntry, value: Any) -> None:
            entry.delete(0, "end")
            entry.insert(0, str(value or ""))

        def set_textbox(textbox: ctk.CTkTextbox, value: Any) -> None:
            textbox.delete("1.0", "end")
            textbox.insert("1.0", str(value or ""))

        def textbox_value(textbox: ctk.CTkTextbox) -> str:
            return textbox.get("1.0", "end").strip()

        def current_template_payload() -> dict[str, Any]:
            return {
                "name": template_name_entry.get().strip(),
                "certificate_type": CERTIFICATE_TYPE_VALUES[type_option.get()],
                "orientation": CERTIFICATE_ORIENTATION_VALUES[orientation_option.get()],
                "title_template": title_entry.get().strip(),
                "body_template": textbox_value(body_textbox),
                "footer_template": footer_entry.get().strip(),
                "signature_left": signature_left_entry.get().strip(),
                "signature_right": signature_right_entry.get().strip(),
                "logo_path": logo_entry.get().strip(),
                "background_image_path": background_image_entry.get().strip(),
                "background_opacity": background_opacity_entry.get().strip(),
                "secondary_logo_path": secondary_logo_entry.get().strip(),
                "primary_color": primary_color_entry.get().strip(),
                "accent_color": accent_color_entry.get().strip(),
                "title_font_size": title_font_entry.get().strip(),
                "body_font_size": body_font_entry.get().strip(),
                "footer_font_size": footer_font_entry.get().strip(),
                "active": 1,
            }

        def load_template_fields(template: dict[str, Any]) -> None:
            selected_template_id["value"] = int(template["id"])
            set_entry(template_name_entry, template.get("name", ""))
            type_option.set(type_labels.get(template.get("certificate_type"), "Participacao"))
            orientation_option.set(orientation_labels.get(template.get("orientation"), "Paisagem"))
            set_entry(title_entry, template.get("title_template", ""))
            set_textbox(body_textbox, template.get("body_template", ""))
            set_entry(footer_entry, template.get("footer_template", ""))
            set_entry(signature_left_entry, template.get("signature_left", ""))
            set_entry(signature_right_entry, template.get("signature_right", ""))
            set_entry(logo_entry, template.get("logo_path", ""))
            set_entry(background_image_entry, template.get("background_image_path", ""))
            set_entry(background_opacity_entry, template.get("background_opacity", 0.18))
            set_entry(secondary_logo_entry, template.get("secondary_logo_path", ""))
            set_entry(primary_color_entry, template.get("primary_color", "#1E3A8A"))
            set_entry(accent_color_entry, template.get("accent_color", "#93C5FD"))
            set_entry(title_font_entry, template.get("title_font_size", 32))
            set_entry(body_font_entry, template.get("body_font_size", 18))
            set_entry(footer_font_entry, template.get("footer_font_size", 10))

        def reload_templates(select_id: int | None = None) -> None:
            nonlocal templates, template_map
            templates = self.certificate_service.list_templates(active_only=True)
            template_map = {str(template["name"]): template for template in templates}
            values = list(template_map) or ["Sem modelo"]
            template_option.configure(values=values)
            selected = next(
                (template for template in templates if select_id and int(template["id"]) == select_id),
                templates[0] if templates else None,
            )
            if selected:
                template_option.set(str(selected["name"]))
                load_template_fields(selected)

        def on_template_select(value: str) -> None:
            template = template_map.get(value)
            if template:
                load_template_fields(template)
                update_count()

        def selected_player_ids() -> list[int]:
            return [player_row_map[item_id] for item_id in tree.selection() if item_id in player_row_map]

        def request_payload() -> dict[str, Any]:
            certificate_type = CERTIFICATE_TYPE_VALUES[type_option.get()]
            recipient_mode = recipient_option.get()
            category = "" if category_option.get() == "Todas" else category_option.get()
            top_n = top_entry.get().strip()
            if recipient_mode == "Todos":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": 0,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N geral":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N por categoria":
                return {
                    "certificate_type": certificate_type,
                    "category": category,
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": True,
                }
            player_ids = selected_player_ids()
            if not player_ids:
                raise AppError("Selecione ao menos um jogador na lista.")
            return {
                "certificate_type": certificate_type,
                "category": "",
                "top_n": 0,
                "player_ids": player_ids,
                "by_category": False,
            }

        def update_count(_value: str | None = None) -> None:
            if tournament and tournament.get("competition_type") == "team":
                return
            try:
                payload = request_payload()
                recipients = self.certificate_service.tournament_recipients(
                    self.current_tournament_id,
                    **payload,
                )
                preview_payload = payload.copy()
                preview_payload.pop("certificate_type", None)
                preview = self.certificate_service.preview_template_data(
                    self.current_tournament_id,
                    current_template_payload(),
                    **preview_payload,
                )
                count_label.configure(text=f"{len(recipients)} diploma(s). Preview: {preview['title']}")
            except Exception as exc:
                count_label.configure(text=str(exc))

        def apply_type_defaults(_value: str | None = None) -> None:
            model = CERTIFICATE_TYPE_VALUES[type_option.get()]
            if model == "participation":
                recipient_option.set("Todos")
            elif model == "overall_award":
                recipient_option.set("Top N geral")
            else:
                recipient_option.set("Top N por categoria")
            update_count()

        def default_filename() -> str:
            tournament_name = tournament["name"] if tournament else "torneio"
            model_name = self._safe_filename(template_name_entry.get(), "diplomas")
            return f"{self._safe_filename(tournament_name, 'torneio')}_{model_name}.pdf"

        def save_template() -> None:
            try:
                template_id = selected_template_id["value"]
                if not template_id:
                    raise AppError("Selecione um modelo.")
                self.certificate_service.update_template(template_id, current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo salvo.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def save_template_as_new() -> None:
            try:
                template_id = self.certificate_service.create_template(current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo criado.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def export_certificates() -> None:
            try:
                if tournament and tournament.get("competition_type") == "team":
                    raise AppError("Diplomas para torneios por equipes ficam para uma etapa futura.")
                payload = request_payload()
                template_payload = current_template_payload()
                file_path = filedialog.asksaveasfilename(
                    title="Gerar diplomas",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_filename(),
                    defaultextension=".pdf",
                    filetypes=[
                        ("PDF", "*.pdf"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != ".pdf":
                    path = path.with_suffix(".pdf")

                self._run_background(
                    lambda: self.certificate_service.export_tournament_certificates(
                        self.current_tournament_id,
                        path,
                        template_data=template_payload,
                        **payload,
                    ),
                    lambda result: self._show_info(
                        f"{result['exported']} diploma(s) exportados:\n{result['path']}"
                    ),
                    "Gerando diplomas...",
                )
            except Exception as exc:
                self._show_error(exc)

        template_option.configure(command=on_template_select)
        type_option.configure(command=apply_type_defaults)
        orientation_option.configure(command=update_count)
        recipient_option.configure(command=update_count)
        category_option.configure(command=update_count)
        tree.bind("<<TreeviewSelect>>", update_count)
        if templates:
            load_template_fields(templates[0])
            apply_type_defaults()

        self._grid_form_buttons(
            form_panel,
            [
                ("Salvar modelo", save_template),
                ("Salvar como novo", save_template_as_new),
                ("Gerar PDF", export_certificates),
            ],
            start_row=38,
        )

    def show_certificates(self) -> None:
        tournament = (
            self.db.get_tournament(self.current_tournament_id)
            if getattr(self, "current_tournament_id", None)
            else None
        )
        self._clear_content()
        self._page_title(
            "Diplomas",
            f"Torneio atual: {tournament['name']}" if tournament else "Gere certificados e diplomas por contexto.",
        )
        if tournament:
            self._build_tournament_nav("certificates")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form_panel = self._make_scrollable_panel(body, width=360)
        form_panel.grid(row=0, column=0, padx=(0, 14), sticky="nsw")

        table_panel = self._make_panel(body)
        table_panel.grid(row=0, column=1, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)

        context_values = [
            "Torneio",
            "Membros/alunos",
            "Aula/turma",
            "Evento",
            "Ranking interno",
        ]
        context_keys = {
            "Torneio": "tournament",
            "Membros/alunos": "members",
            "Aula/turma": "training",
            "Evento": "event",
            "Ranking interno": "ranking",
        }
        context_default_types = {
            "tournament": "participation",
            "members": "member_certificate",
            "training": "training_participation",
            "event": "event_participation",
            "ranking": "internal_ranking",
        }
        source_labels = {
            "tournament": "Torneio",
            "members": "Origem",
            "training": "Aula/turma",
            "event": "Evento",
            "ranking": "Origem",
        }
        history_context_labels = {
            "tournament": "Torneio",
            "members": "Membros",
            "training": "Aula",
            "event": "Evento",
            "ranking": "Ranking",
        }
        recipient_modes = {
            "tournament": ["Todos", "Top N geral", "Top N por categoria", "Selecionados na lista"],
            "members": ["Todos", "Selecionados na lista"],
            "training": ["Todos", "Selecionados na lista"],
            "event": ["Todos", "Selecionados na lista"],
            "ranking": ["Todos", "Top N geral", "Selecionados na lista"],
        }
        type_labels = {value: label for label, value in CERTIFICATE_TYPE_VALUES.items()}
        orientation_labels = {value: label for label, value in CERTIFICATE_ORIENTATION_VALUES.items()}
        templates = self.certificate_service.list_templates(active_only=True)
        template_map = {str(template["name"]): template for template in templates}
        template_values = list(template_map) or ["Sem modelo"]
        selected_template_id: dict[str, int | None] = {
            "value": int(templates[0]["id"]) if templates else None,
        }
        source_map: dict[str, int] = {}
        recipient_row_map: dict[str, int] = {}

        ctk.CTkLabel(form_panel, text="Contexto").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        context_option = ctk.CTkOptionMenu(form_panel, values=context_values, width=290)
        context_option.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        source_label = ctk.CTkLabel(form_panel, text="Torneio")
        source_label.grid(row=2, column=0, padx=16, pady=(2, 4), sticky="w")
        source_option = ctk.CTkOptionMenu(form_panel, values=["Nenhum registro"], width=290)
        source_option.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Modelo salvo").grid(row=4, column=0, padx=16, pady=(2, 4), sticky="w")
        template_option = ctk.CTkOptionMenu(form_panel, values=template_values, width=290)
        template_option.grid(row=5, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Nome do modelo").grid(row=6, column=0, padx=16, pady=(2, 4), sticky="w")
        template_name_entry = ctk.CTkEntry(form_panel, width=290)
        template_name_entry.grid(row=7, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Tipo").grid(row=8, column=0, padx=16, pady=(2, 4), sticky="w")
        type_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_TYPE_VALUES.keys()), width=290)
        type_option.grid(row=9, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Orientacao").grid(row=10, column=0, padx=16, pady=(2, 4), sticky="w")
        orientation_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_ORIENTATION_VALUES.keys()), width=290)
        orientation_option.grid(row=11, column=0, padx=16, pady=(0, 10), sticky="ew")

        assets_frame = ctk.CTkFrame(form_panel, fg_color="transparent")
        assets_frame.grid(row=12, column=0, padx=16, pady=(2, 10), sticky="ew")
        assets_frame.grid_columnconfigure(0, weight=1)

        def choose_image(entry: ctk.CTkEntry, title: str) -> None:
            file_path = filedialog.askopenfilename(
                title=title,
                initialdir=str(BASE_DIR),
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if file_path:
                entry.delete(0, "end")
                entry.insert(0, file_path)
                update_count()

        ctk.CTkLabel(assets_frame, text="Logo principal").grid(row=0, column=0, pady=(0, 4), sticky="w")
        logo_entry = ctk.CTkEntry(assets_frame, width=290)
        logo_entry.grid(row=1, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo principal",
            command=lambda: choose_image(logo_entry, "Escolher logo principal"),
        ).grid(row=2, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Logo secundario").grid(row=3, column=0, pady=(0, 4), sticky="w")
        secondary_logo_entry = ctk.CTkEntry(assets_frame, width=290)
        secondary_logo_entry.grid(row=4, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo secundario",
            command=lambda: choose_image(secondary_logo_entry, "Escolher logo secundario"),
        ).grid(row=5, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Imagem de fundo").grid(row=6, column=0, pady=(0, 4), sticky="w")
        background_image_entry = ctk.CTkEntry(assets_frame, width=290)
        background_image_entry.grid(row=7, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher fundo",
            command=lambda: choose_image(background_image_entry, "Escolher imagem de fundo"),
        ).grid(row=8, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Opacidade do fundo").grid(row=9, column=0, pady=(0, 4), sticky="w")
        background_opacity_entry = ctk.CTkEntry(assets_frame, width=90)
        background_opacity_entry.grid(row=10, column=0, pady=(0, 0), sticky="w")
        background_opacity_entry.insert(0, "0.18")

        ctk.CTkLabel(form_panel, text="Cor principal").grid(row=15, column=0, padx=16, pady=(2, 4), sticky="w")
        primary_color_entry = ctk.CTkEntry(form_panel, width=140)
        primary_color_entry.grid(row=16, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Cor de destaque").grid(row=17, column=0, padx=16, pady=(2, 4), sticky="w")
        accent_color_entry = ctk.CTkEntry(form_panel, width=140)
        accent_color_entry.grid(row=18, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do titulo").grid(row=19, column=0, padx=16, pady=(2, 4), sticky="w")
        title_font_entry = ctk.CTkEntry(form_panel, width=80)
        title_font_entry.grid(row=20, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do texto").grid(row=21, column=0, padx=16, pady=(2, 4), sticky="w")
        body_font_entry = ctk.CTkEntry(form_panel, width=80)
        body_font_entry.grid(row=22, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do rodape").grid(row=23, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_font_entry = ctk.CTkEntry(form_panel, width=80)
        footer_font_entry.grid(row=24, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Titulo").grid(row=25, column=0, padx=16, pady=(2, 4), sticky="w")
        title_entry = ctk.CTkEntry(form_panel, width=290)
        title_entry.grid(row=26, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Texto principal").grid(row=27, column=0, padx=16, pady=(2, 4), sticky="w")
        body_textbox = ctk.CTkTextbox(form_panel, width=290, height=110)
        body_textbox.grid(row=28, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Rodape").grid(row=29, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_entry = ctk.CTkEntry(form_panel, width=290)
        footer_entry.grid(row=30, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura esquerda").grid(row=31, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_left_entry = ctk.CTkEntry(form_panel, width=290)
        signature_left_entry.grid(row=32, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura direita").grid(row=33, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_right_entry = ctk.CTkEntry(form_panel, width=290)
        signature_right_entry.grid(row=34, column=0, padx=16, pady=(0, 14), sticky="ew")

        ctk.CTkLabel(form_panel, text="Destinatarios").grid(row=35, column=0, padx=16, pady=(4, 4), sticky="w")
        recipient_option = ctk.CTkOptionMenu(form_panel, values=recipient_modes["tournament"], width=250)
        recipient_option.grid(row=36, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Limite").grid(row=37, column=0, padx=16, pady=(2, 4), sticky="w")
        top_entry = ctk.CTkEntry(form_panel, width=120)
        top_entry.grid(row=38, column=0, padx=16, pady=(0, 10), sticky="w")
        top_entry.insert(0, "3")

        ctk.CTkLabel(form_panel, text="Categoria").grid(row=39, column=0, padx=16, pady=(2, 4), sticky="w")
        category_option = ctk.CTkOptionMenu(form_panel, values=["Todas"], width=250)
        category_option.grid(row=40, column=0, padx=16, pady=(0, 10), sticky="ew")

        count_label = ctk.CTkLabel(form_panel, text="", text_color=THEME_TEXT_SUB, wraplength=270, justify="left")
        count_label.grid(row=41, column=0, padx=16, pady=(0, 14), sticky="w")

        ctk.CTkLabel(form_panel, text="Codigo de verificacao").grid(row=42, column=0, padx=16, pady=(2, 4), sticky="w")
        verification_code_entry = ctk.CTkEntry(form_panel, width=250)
        verification_code_entry.grid(row=43, column=0, padx=16, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(
            table_panel,
            text="Selecione destinatarios na lista apenas quando usar destinatarios selecionados.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        tree_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            tree_holder,
            ["pos", "name", "category", "points", "status"],
            {
                "pos": "Pos",
                "name": "Nome",
                "category": "Categoria",
                "points": "Pts",
                "status": "Status",
            },
            {
                "pos": 60,
                "name": 280,
                "category": 140,
                "points": 80,
                "status": 130,
            },
            visible_rows=16,
        )
        tree.configure(selectmode="extended")

        ctk.CTkLabel(
            table_panel,
            text="Historico recente de emissoes",
            text_color=THEME_TEXT_SUB,
        ).grid(row=2, column=0, padx=16, pady=(0, 8), sticky="w")

        history_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        history_holder.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        history_holder.grid_columnconfigure(0, weight=1)
        history_holder.grid_rowconfigure(0, weight=1)
        history_tree = self._make_tree(
            history_holder,
            ["issued_at", "recipient", "context", "code", "status"],
            {
                "issued_at": "Emissao",
                "recipient": "Destinatario",
                "context": "Contexto",
                "code": "Codigo",
                "status": "Status",
            },
            {
                "issued_at": 130,
                "recipient": 240,
                "context": 90,
                "code": 130,
                "status": 90,
            },
            visible_rows=5,
        )
        history_row_map: dict[str, dict[str, Any]] = {}

        def context_key() -> str:
            return context_keys.get(context_option.get(), "tournament")

        def selected_source_id() -> int | None:
            return source_map.get(source_option.get())

        def source_id_required(label: str) -> int:
            source_id = selected_source_id()
            if not source_id:
                raise AppError(f"Selecione {label}.")
            return source_id

        def selected_recipient_ids() -> list[int]:
            return [recipient_row_map[item_id] for item_id in tree.selection() if item_id in recipient_row_map]

        def selected_category() -> str:
            return "" if category_option.get() == "Todas" else category_option.get()

        def set_entry(entry: ctk.CTkEntry, value: Any) -> None:
            entry.delete(0, "end")
            entry.insert(0, str(value or ""))

        def set_textbox(textbox: ctk.CTkTextbox, value: Any) -> None:
            textbox.delete("1.0", "end")
            textbox.insert("1.0", str(value or ""))

        def textbox_value(textbox: ctk.CTkTextbox) -> str:
            return textbox.get("1.0", "end").strip()

        def current_template_payload() -> dict[str, Any]:
            return {
                "name": template_name_entry.get().strip(),
                "certificate_type": CERTIFICATE_TYPE_VALUES[type_option.get()],
                "orientation": CERTIFICATE_ORIENTATION_VALUES[orientation_option.get()],
                "title_template": title_entry.get().strip(),
                "body_template": textbox_value(body_textbox),
                "footer_template": footer_entry.get().strip(),
                "signature_left": signature_left_entry.get().strip(),
                "signature_right": signature_right_entry.get().strip(),
                "logo_path": logo_entry.get().strip(),
                "background_image_path": background_image_entry.get().strip(),
                "background_opacity": background_opacity_entry.get().strip(),
                "secondary_logo_path": secondary_logo_entry.get().strip(),
                "primary_color": primary_color_entry.get().strip(),
                "accent_color": accent_color_entry.get().strip(),
                "title_font_size": title_font_entry.get().strip(),
                "body_font_size": body_font_entry.get().strip(),
                "footer_font_size": footer_font_entry.get().strip(),
                "active": 1,
            }

        def load_template_fields(template: dict[str, Any]) -> None:
            selected_template_id["value"] = int(template["id"])
            set_entry(template_name_entry, template.get("name", ""))
            type_option.set(type_labels.get(template.get("certificate_type"), "Participacao"))
            orientation_option.set(orientation_labels.get(template.get("orientation"), "Paisagem"))
            set_entry(title_entry, template.get("title_template", ""))
            set_textbox(body_textbox, template.get("body_template", ""))
            set_entry(footer_entry, template.get("footer_template", ""))
            set_entry(signature_left_entry, template.get("signature_left", ""))
            set_entry(signature_right_entry, template.get("signature_right", ""))
            set_entry(logo_entry, template.get("logo_path", ""))
            set_entry(background_image_entry, template.get("background_image_path", ""))
            set_entry(background_opacity_entry, template.get("background_opacity", 0.18))
            set_entry(secondary_logo_entry, template.get("secondary_logo_path", ""))
            set_entry(primary_color_entry, template.get("primary_color", "#1E3A8A"))
            set_entry(accent_color_entry, template.get("accent_color", "#93C5FD"))
            set_entry(title_font_entry, template.get("title_font_size", 32))
            set_entry(body_font_entry, template.get("body_font_size", 18))
            set_entry(footer_font_entry, template.get("footer_font_size", 10))

        def select_template_for_type(certificate_type: str) -> None:
            selected = next(
                (template for template in templates if template.get("certificate_type") == certificate_type),
                templates[0] if templates else None,
            )
            if selected:
                template_option.set(str(selected["name"]))
                load_template_fields(selected)

        def reload_templates(select_id: int | None = None) -> None:
            nonlocal templates, template_map
            templates = self.certificate_service.list_templates(active_only=True)
            template_map = {str(template["name"]): template for template in templates}
            values = list(template_map) or ["Sem modelo"]
            template_option.configure(values=values)
            selected = next(
                (template for template in templates if select_id and int(template["id"]) == select_id),
                None,
            )
            if not selected:
                selected = next(
                    (
                        template
                        for template in templates
                        if template.get("certificate_type") == context_default_types[context_key()]
                    ),
                    templates[0] if templates else None,
                )
            if selected:
                template_option.set(str(selected["name"]))
                load_template_fields(selected)
                update_count()

        def on_template_select(value: str) -> None:
            template = template_map.get(value)
            if template:
                load_template_fields(template)
                update_count()

        def source_label_for(record: dict[str, Any], title_key: str, date_key: str = "") -> str:
            title = str(record.get(title_key) or f"Registro {record.get('id')}")
            date_value = str(record.get(date_key) or "").strip() if date_key else ""
            prefix = f"{date_value} - " if date_value else ""
            return f"{prefix}{title} (#{record.get('id')})"

        def reload_sources() -> None:
            source_map.clear()
            current_context = context_key()
            source_label.configure(text=source_labels[current_context])
            if current_context == "tournament":
                records = self.db.list_tournaments()
                values = [source_label_for(item, "name") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = getattr(self, "current_tournament_id", None)
            elif current_context == "training":
                records = self.db.list_training_sessions()
                values = [source_label_for(item, "title", "session_date") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = None
            elif current_context == "event":
                records = self.db.list_club_events()
                values = [source_label_for(item, "title", "event_date") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = None
            else:
                values = ["Todos os membros"]
                source_map["Todos os membros"] = 0
                selected_id = 0

            if not values:
                values = ["Nenhum registro"]
            source_option.configure(values=values)
            selected_label = next(
                (label for label, item_id in source_map.items() if selected_id and item_id == selected_id),
                values[0],
            )
            source_option.set(selected_label)

        def configure_recipient_modes() -> None:
            values = recipient_modes[context_key()]
            recipient_option.configure(values=values)
            if recipient_option.get() not in values:
                recipient_option.set("Top N geral" if context_key() == "ranking" else values[0])

        def refresh_category_values() -> None:
            current_context = context_key()
            categories: list[str] = []
            try:
                if current_context == "tournament" and selected_source_id():
                    categories = self.certificate_service.tournament_categories(source_id_required("um torneio"))
                elif current_context == "ranking":
                    categories = sorted(
                        {
                            str(member.get("category") or "").strip()
                            for member in self.db.list_members(active_only=True)
                            if str(member.get("category") or "").strip()
                        },
                        key=lambda value: value.casefold(),
                    )
            except Exception:
                categories = []
            values = ["Todas"] + categories if categories else ["Todas"]
            current = category_option.get()
            category_option.configure(values=values)
            category_option.set(current if current in values else "Todas")

        def update_tree_headings() -> None:
            headings = {
                "tournament": ("Pos", "Nome", "Categoria", "Pts", "Status"),
                "members": ("#", "Nome", "Turma", "Rating", "Status"),
                "training": ("#", "Nome", "Turma", "Presenca", "Status"),
                "event": ("#", "Nome", "Clube", "Categoria", "Status"),
                "ranking": ("Pos", "Nome", "Categoria", "Rating", "Jogos"),
            }[context_key()]
            for column, text in zip(("pos", "name", "category", "points", "status"), headings, strict=False):
                tree.heading(column, text=text)

        def clear_recipient_table() -> None:
            recipient_row_map.clear()
            for item_id in tree.get_children():
                tree.delete(item_id)

        def add_recipient_row(values: tuple[Any, Any, Any, Any, Any], recipient_id: int) -> None:
            item_id = tree.insert("", "end", values=values)
            recipient_row_map[item_id] = recipient_id

        def issuance_status_label(item: dict[str, Any]) -> str:
            return "Revogado" if item.get("revoked") else "Valido"

        def issuance_context_label(item: dict[str, Any]) -> str:
            return history_context_labels.get(str(item.get("context_type") or ""), str(item.get("context_type") or ""))

        def refresh_history() -> None:
            history_row_map.clear()
            for item_id in history_tree.get_children():
                history_tree.delete(item_id)
            for item in self.certificate_service.list_issuances(limit=40):
                row_id = history_tree.insert(
                    "",
                    "end",
                    values=(
                        item.get("issued_at", ""),
                        item.get("recipient_name", ""),
                        issuance_context_label(item),
                        item.get("verification_code", ""),
                        issuance_status_label(item),
                    ),
                )
                history_row_map[row_id] = item

        def selected_history_issuance() -> dict[str, Any] | None:
            selection = history_tree.selection()
            if not selection:
                return None
            return history_row_map.get(selection[0])

        def fill_verification_from_history(_event: Any | None = None) -> None:
            issuance = selected_history_issuance()
            if not issuance:
                return
            verification_code_entry.delete(0, "end")
            verification_code_entry.insert(0, str(issuance.get("verification_code") or ""))

        def verify_certificate_code() -> None:
            try:
                code = verification_code_entry.get().strip()
                if not code:
                    issuance = selected_history_issuance()
                    code = str(issuance.get("verification_code") or "") if issuance else ""
                if not code:
                    raise AppError("Informe ou selecione um codigo de verificacao.")
                issuance = self.certificate_service.verify_issuance(code)
                status = issuance_status_label(issuance)
                self._show_info(
                    "Diploma encontrado:\n"
                    f"Codigo: {issuance['verification_code']}\n"
                    f"Status: {status}\n"
                    f"Destinatario: {issuance['recipient_name']}\n"
                    f"Contexto: {issuance_context_label(issuance)}\n"
                    f"Origem: {issuance.get('source_title') or ''}\n"
                    f"Arquivo: {issuance.get('file_path') or ''}"
                )
            except Exception as exc:
                self._show_error(exc)

        def export_verification_site() -> None:
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Exportar verificador de diplomas",
                    initialdir=str(self._default_export_dir()),
                    initialfile="verificador_diplomas.html",
                    defaultextension=".html",
                    filetypes=[
                        ("HTML", "*.html"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != ".html":
                    path = path.with_suffix(".html")
                self._run_background(
                    lambda: self.certificate_service.export_verification_site(path),
                    lambda result_path: self._show_info(f"Verificador exportado:\n{result_path}"),
                    "Exportando verificador...",
                )
            except Exception as exc:
                self._show_error(exc)

        def refresh_recipient_table(_value: str | None = None) -> None:
            clear_recipient_table()
            update_tree_headings()
            try:
                current_context = context_key()
                if current_context == "tournament":
                    tournament_id = source_id_required("um torneio")
                    selected_tournament = self.db.get_tournament(tournament_id)
                    if selected_tournament and selected_tournament.get("competition_type") == "team":
                        count_label.configure(text="Diplomas por equipes ficam para uma etapa futura.")
                        return
                    for item in self.pairing_service.standings(tournament_id):
                        add_recipient_row(
                            (
                                item.get("position", ""),
                                item.get("name", ""),
                                item.get("category", ""),
                                item.get("points", 0),
                                PLAYER_STATUSES.get(item.get("player_status", "active"), "Ativo"),
                            ),
                            int(item["player_id"]),
                        )
                elif current_context == "members":
                    for index, recipient in enumerate(self.certificate_service.member_recipients(), start=1):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("class_name", ""),
                                recipient.get("rating", ""),
                                recipient.get("status", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                elif current_context == "training":
                    session_id = source_id_required("uma aula/turma")
                    for index, recipient in enumerate(
                        self.certificate_service.training_recipients(session_id, present_only=False),
                        start=1,
                    ):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("class_name", ""),
                                recipient.get("status", ""),
                                recipient.get("type_label", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                elif current_context == "event":
                    event_id = source_id_required("um evento")
                    for index, recipient in enumerate(self.certificate_service.event_recipients(event_id), start=1):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("club", ""),
                                recipient.get("category", ""),
                                recipient.get("status", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                else:
                    for recipient in self.certificate_service.ranking_recipients(top_n=0):
                        add_recipient_row(
                            (
                                recipient.get("position", ""),
                                recipient.get("name", ""),
                                recipient.get("category", ""),
                                recipient.get("rating", ""),
                                recipient.get("games", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                update_count()
            except Exception as exc:
                count_label.configure(text=str(exc))

        def tournament_payload() -> dict[str, Any]:
            certificate_type = CERTIFICATE_TYPE_VALUES[type_option.get()]
            recipient_mode = recipient_option.get()
            category = selected_category()
            top_n = top_entry.get().strip()
            if recipient_mode == "Todos":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": 0,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N geral":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N por categoria":
                return {
                    "certificate_type": certificate_type,
                    "category": category,
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": True,
                }
            player_ids = selected_recipient_ids()
            if not player_ids:
                raise AppError("Selecione ao menos um destinatario na lista.")
            return {
                "certificate_type": certificate_type,
                "category": "",
                "top_n": 0,
                "player_ids": player_ids,
                "by_category": False,
            }

        def context_payload() -> dict[str, Any]:
            recipient_mode = recipient_option.get()
            selected_ids = selected_recipient_ids() if recipient_mode == "Selecionados na lista" else None
            if recipient_mode == "Selecionados na lista" and not selected_ids:
                raise AppError("Selecione ao menos um destinatario na lista.")
            current_context = context_key()
            if current_context == "members":
                return {"member_ids": selected_ids, "class_id": None}
            if current_context == "training":
                return {
                    "session_id": source_id_required("uma aula/turma"),
                    "member_ids": selected_ids,
                    "present_only": False,
                }
            if current_context == "event":
                return {"event_id": source_id_required("um evento"), "member_ids": selected_ids}
            if current_context == "ranking":
                return {
                    "member_ids": selected_ids,
                    "category": "" if selected_ids else selected_category(),
                    "top_n": 0 if recipient_mode == "Todos" or selected_ids else top_entry.get().strip(),
                }
            raise AppError("Contexto de diploma invalido.")

        def current_recipients() -> list[dict[str, Any]]:
            current_context = context_key()
            if current_context == "tournament":
                return self.certificate_service.tournament_recipients(
                    source_id_required("um torneio"),
                    **tournament_payload(),
                )
            payload = context_payload()
            if current_context == "members":
                return self.certificate_service.member_recipients(**payload)
            if current_context == "training":
                session_id = int(payload.pop("session_id"))
                return self.certificate_service.training_recipients(session_id, **payload)
            if current_context == "event":
                event_id = int(payload.pop("event_id"))
                return self.certificate_service.event_recipients(event_id, **payload)
            if current_context == "ranking":
                return self.certificate_service.ranking_recipients(**payload)
            raise AppError("Contexto de diploma invalido.")

        def update_count(_value: str | None = None) -> None:
            try:
                recipients = current_recipients()
                preview = self.certificate_service.preview_template_recipient(
                    current_template_payload(),
                    recipients[0],
                )
                count_label.configure(text=f"{len(recipients)} diploma(s). Preview: {preview['title']}")
            except Exception as exc:
                count_label.configure(text=str(exc))

        def apply_type_defaults(_value: str | None = None) -> None:
            current_context = context_key()
            model = CERTIFICATE_TYPE_VALUES[type_option.get()]
            values = recipient_modes[current_context]
            if current_context == "tournament":
                if model == "participation":
                    recipient_option.set("Todos")
                elif model == "overall_award":
                    recipient_option.set("Top N geral")
                else:
                    recipient_option.set("Top N por categoria")
            elif current_context == "ranking" and "Top N geral" in values:
                recipient_option.set("Top N geral")
            else:
                recipient_option.set(values[0])
            update_count()

        def on_source_select(_value: str | None = None) -> None:
            if context_key() == "tournament" and selected_source_id():
                self.current_tournament_id = selected_source_id()
            refresh_category_values()
            refresh_recipient_table()

        def on_context_select(_value: str | None = None) -> None:
            reload_sources()
            configure_recipient_modes()
            refresh_category_values()
            select_template_for_type(context_default_types[context_key()])
            apply_type_defaults()
            refresh_recipient_table()

        def default_filename() -> str:
            context_name = self._safe_filename(context_option.get(), "diplomas")
            source_name = self._safe_filename(source_option.get(), context_name)
            model_name = self._safe_filename(template_name_entry.get(), "modelo")
            return f"{context_name}_{source_name}_{model_name}.pdf"

        def save_template() -> None:
            try:
                template_id = selected_template_id["value"]
                if not template_id:
                    raise AppError("Selecione um modelo.")
                self.certificate_service.update_template(template_id, current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo salvo.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def save_template_as_new() -> None:
            try:
                template_id = self.certificate_service.create_template(current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo criado.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def export_certificates() -> None:
            try:
                template_payload = current_template_payload()
                export_context = context_key()
                export_source_id: int | None = None
                export_kwargs: dict[str, Any]
                if export_context == "tournament":
                    export_source_id = source_id_required("um torneio")
                    export_kwargs = tournament_payload()
                else:
                    export_kwargs = context_payload()
                    if export_context == "training":
                        export_source_id = int(export_kwargs.pop("session_id"))
                    elif export_context == "event":
                        export_source_id = int(export_kwargs.pop("event_id"))

                file_path = filedialog.asksaveasfilename(
                    title="Gerar diplomas",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_filename(),
                    defaultextension=".pdf",
                    filetypes=[
                        ("PDF", "*.pdf"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != ".pdf":
                    path = path.with_suffix(".pdf")

                def write_export() -> dict[str, Any]:
                    if export_context == "tournament":
                        return self.certificate_service.export_tournament_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "members":
                        return self.certificate_service.export_member_certificates(
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "training":
                        return self.certificate_service.export_training_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "event":
                        return self.certificate_service.export_event_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "ranking":
                        return self.certificate_service.export_ranking_certificates(
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    raise AppError("Contexto de diploma invalido.")

                def export_done(result: dict[str, Any]) -> None:
                    refresh_history()
                    codes = result.get("verification_codes") or []
                    code_preview = ", ".join(str(code) for code in codes[:3])
                    if len(codes) > 3:
                        code_preview = f"{code_preview}..."
                    suffix = f"\nCodigos: {code_preview}" if code_preview else ""
                    self._show_info(
                        f"{result['exported']} diploma(s) exportados:\n{result['path']}{suffix}"
                    )

                self._run_background(
                    write_export,
                    export_done,
                    "Gerando diplomas...",
                )
            except Exception as exc:
                self._show_error(exc)

        context_option.configure(command=on_context_select)
        source_option.configure(command=on_source_select)
        template_option.configure(command=on_template_select)
        type_option.configure(command=apply_type_defaults)
        orientation_option.configure(command=update_count)
        recipient_option.configure(command=update_count)
        category_option.configure(command=update_count)
        tree.bind("<<TreeviewSelect>>", update_count)
        history_tree.bind("<<TreeviewSelect>>", fill_verification_from_history)

        context_option.set("Torneio")
        on_context_select("Torneio")
        refresh_history()

        ctk.CTkButton(form_panel, text="Consultar codigo", command=verify_certificate_code).grid(
            row=44,
            column=0,
            padx=16,
            pady=(0, 8),
            sticky="ew",
        )

        self._grid_form_buttons(
            form_panel,
            [
                ("Salvar modelo", save_template),
                ("Salvar como novo", save_template_as_new),
                ("Gerar PDF", export_certificates),
                # ("Imprimir", print_certificates),
                ("Exportar verificador", export_verification_site),
            ],
            start_row=45,
        )

    def _open_user_management_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Gerenciar Usuários")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()

        tree = self._make_tree(
            dialog,
            ["id", "username", "role", "created_at"],
            {"id": "ID", "username": "Usuário", "role": "Perfil", "created_at": "Criado em"},
            {"id": 40, "username": 150, "role": 120, "created_at": 150},
            visible_rows=10,
        )
        tree.pack(fill="both", expand=True, padx=20, pady=20)

        def load_users():
            tree.delete(*tree.get_children())
            for u in self.security_service.list_users():
                tree.insert("", "end", values=(u["id"], u["username"], OPERATOR_ROLES.get(u["role"], u["role"]), u["created_at"]))

        load_users()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        def create_user():
            add_dlg = ctk.CTkToplevel(dialog)
            add_dlg.title("Novo Usuário")
            add_dlg.geometry("300x350")
            add_dlg.transient(dialog)
            add_dlg.grab_set()

            ctk.CTkLabel(add_dlg, text="Usuário:").pack(pady=(10, 0))
            u_entry = ctk.CTkEntry(add_dlg)
            u_entry.pack(pady=5)

            ctk.CTkLabel(add_dlg, text="Senha:").pack(pady=(10, 0))
            p_entry = ctk.CTkEntry(add_dlg, show="*")
            p_entry.pack(pady=5)

            ctk.CTkLabel(add_dlg, text="Perfil:").pack(pady=(10, 0))
            r_option = ctk.CTkOptionMenu(add_dlg, values=list(OPERATOR_ROLE_VALUES.keys()))
            r_option.pack(pady=5)

            def save():
                try:
                    role_val = OPERATOR_ROLE_VALUES[r_option.get()]
                    self.security_service.create_user(u_entry.get().strip(), p_entry.get(), role_val)
                    load_users()
                    add_dlg.destroy()
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(add_dlg, text="Salvar", command=save).pack(pady=20)

        def delete_user():
            sel = tree.selection()
            if not sel:
                return
            uid = tree.item(sel[0])["values"][0]
            try:
                self.security_service.delete_user(int(uid))
                load_users()
            except Exception as e:
                self._show_error(str(e))

        ctk.CTkButton(btn_frame, text="Novo Usuário", command=create_user).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deletar Usuário", command=delete_user, fg_color="red").pack(side="left", padx=5)

    def show_membership_plans(self) -> None:
        self._clear_content()
        self._page_title(
            "Planos de Mensalidade",
            "Cadastre e gerencie os planos de mensalidade oferecidos pelo clube.",
        )

        top_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        top_frame.grid(row=1, column=0, padx=22, pady=(0, 10), sticky="ew")

        btn_new = ctk.CTkButton(
            top_frame,
            text="Novo Plano",
            command=self._show_plan_form,
        )
        btn_new.pack(side="left")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=2, column=0, padx=22, pady=(0, 22), sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        columns = ("id", "nome", "valor", "ciclo", "status")
        self.plans_tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            style="App.Treeview",
        )
        self.plans_tree.heading("id", text="ID")
        self.plans_tree.heading("nome", text="Nome do Plano")
        self.plans_tree.heading("valor", text="Valor (R$)")
        self.plans_tree.heading("ciclo", text="Ciclo")
        self.plans_tree.heading("status", text="Status")
        
        self.plans_tree.column("id", width=50, anchor="center")
        self.plans_tree.column("nome", width=300, anchor="w")
        self.plans_tree.column("valor", width=100, anchor="e")
        self.plans_tree.column("ciclo", width=100, anchor="center")
        self.plans_tree.column("status", width=100, anchor="center")

        self.plans_tree.pack(fill="both", expand=True)
        self.plans_tree.bind("<Double-1>", lambda e: self._on_plan_double_click())

        self._load_plans()

    def _load_plans(self) -> None:
        for row in self.plans_tree.get_children():
            self.plans_tree.delete(row)
        plans = self.db.list_membership_plans(active_only=False)
        for p in plans:
            status_text = "Ativo" if p["active"] else "Inativo"
            cycle_map = {"monthly": "Mensal", "yearly": "Anual", "quarterly": "Trimestral"}
            cycle_text = cycle_map.get(p["billing_cycle"], p["billing_cycle"])
            self.plans_tree.insert(
                "",
                "end",
                values=(
                    p["id"],
                    p["name"],
                    f"{p['amount']:.2f}",
                    cycle_text,
                    status_text
                ),
            )

    def _on_plan_double_click(self) -> None:
        sel = self.plans_tree.selection()
        if not sel:
            return
        plan_id = int(self.plans_tree.item(sel[0])["values"][0])
        plan = self.db.get_membership_plan(plan_id)
        if plan:
            self._show_plan_form(plan)

    def _show_plan_form(self, plan: dict[str, Any] | None = None) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Plano de Mensalidade" if plan else "Novo Plano")
        dlg.geometry("400x450")
        dlg.transient(self)
        dlg.grab_set()

        frame = ctk.CTkFrame(dlg)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nome do Plano:").pack(anchor="w", pady=(0, 5))
        name_entry = ctk.CTkEntry(frame)
        name_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(frame, text="Valor (R$):").pack(anchor="w", pady=(0, 5))
        amount_entry = ctk.CTkEntry(frame)
        amount_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(frame, text="Ciclo de Cobrança:").pack(anchor="w", pady=(0, 5))
        cycle_var = ctk.StringVar(value="monthly")
        cycle_menu = ctk.CTkOptionMenu(
            frame,
            variable=cycle_var,
            values=["monthly", "quarterly", "yearly"]
        )
        cycle_menu.pack(fill="x", pady=(0, 15))

        active_var = ctk.BooleanVar(value=True)
        active_cb = ctk.CTkCheckBox(frame, text="Plano Ativo", variable=active_var)
        active_cb.pack(anchor="w", pady=(0, 15))

        if plan:
            name_entry.insert(0, plan["name"])
            amount_entry.insert(0, str(plan["amount"]))
            cycle_var.set(plan["billing_cycle"])
            active_var.set(bool(plan["active"]))

        def save():
            try:
                amount = float(amount_entry.get().replace(",", "."))
            except ValueError:
                self._show_error("Valor inválido.")
                return

            name = name_entry.get().strip()
            if not name:
                self._show_error("Nome é obrigatório.")
                return

            if plan:
                self.db.update_membership_plan(
                    plan["id"],
                    name=name,
                    amount=amount,
                    billing_cycle=cycle_var.get(),
                    active=int(active_var.get()),
                    notes=""
                )
            else:
                self.db.create_membership_plan(
                    name=name,
                    amount=amount,
                    billing_cycle=cycle_var.get(),
                    notes=""
                )
            self._load_plans()
            dlg.destroy()

        ctk.CTkButton(frame, text="Salvar", command=save).pack(pady=20)

    def _show_users_manager(self) -> None:
        if self.security_service.current_operator().get("role") != "admin":
            self._show_error("Apenas o administrador pode gerenciar usuários.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Gerenciar Usuários")
        dlg.geometry("700x500")
        dlg.grab_set()

        frame = ctk.CTkFrame(dlg)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        top_bar = ctk.CTkFrame(frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))

        tree_frame = ctk.CTkFrame(frame)
        tree_frame.pack(fill="both", expand=True)

        users_tree = self._make_tree(
            tree_frame,
            ["username", "role", "created_at"],
            {"username": "Usuário", "role": "Perfil", "created_at": "Criado em"},
            {"username": 200, "role": 150, "created_at": 150}
        )
        users_tree.pack(fill="both", expand=True)

        user_ids = {}

        def load_users():
            users_tree.delete(*users_tree.get_children())
            user_ids.clear()
            for user in self.security_service.list_users():
                row_id = users_tree.insert("", "end", values=(
                    user["username"],
                    OPERATOR_ROLES.get(user["role"], user["role"]),
                    user["created_at"]
                ))
                user_ids[row_id] = user["id"]

        load_users()

        def add_user():
            add_dlg = ctk.CTkToplevel(dlg)
            add_dlg.title("Novo Usuário")
            add_dlg.geometry("400x400")
            add_dlg.grab_set()

            ctk.CTkLabel(add_dlg, text="Nome de Usuário").pack(pady=(20, 5))
            user_entry = ctk.CTkEntry(add_dlg, width=250)
            user_entry.pack()

            ctk.CTkLabel(add_dlg, text="Senha Provisória").pack(pady=(15, 5))
            pwd_entry = ctk.CTkEntry(add_dlg, width=250)
            pwd_entry.pack()

            ctk.CTkLabel(add_dlg, text="Perfil").pack(pady=(15, 5))
            role_var = ctk.StringVar(value="teacher")
            role_combo = ctk.CTkOptionMenu(add_dlg, variable=role_var, values=list(OPERATOR_ROLE_VALUES.keys()))
            role_combo.pack()

            def save():
                try:
                    self.security_service.create_user(
                        username=user_entry.get().strip(),
                        password_raw=pwd_entry.get().strip(),
                        role=OPERATOR_ROLE_VALUES.get(role_var.get(), "teacher")
                    )
                    load_users()
                    add_dlg.destroy()
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(add_dlg, text="Salvar", command=save).pack(pady=30)

        def delete_user():
            selected = users_tree.selection()
            if not selected:
                return
            uid = user_ids[selected[0]]
            try:
                self.security_service.delete_user(uid)
                load_users()
            except Exception as e:
                self._show_error(str(e))

        def change_pwd():
            selected = users_tree.selection()
            if not selected:
                return
            uid = user_ids[selected[0]]
            
            pwd_dlg = ctk.CTkToplevel(dlg)
            pwd_dlg.title("Redefinir Senha")
            pwd_dlg.geometry("400x250")
            pwd_dlg.grab_set()

            ctk.CTkLabel(pwd_dlg, text="Nova Senha").pack(pady=(20, 5))
            pwd_entry = ctk.CTkEntry(pwd_dlg, width=250)
            pwd_entry.pack()

            def save():
                try:
                    self.security_service.update_user_password(uid, pwd_entry.get().strip())
                    pwd_dlg.destroy()
                    self._show_toast("Senha atualizada.", kind="success")
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(pwd_dlg, text="Salvar", command=save).pack(pady=30)

        ctk.CTkButton(top_bar, text="Novo", command=add_user).pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Excluir", command=delete_user, fg_color="red").pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Redefinir Senha", command=change_pwd).pack(side="left", padx=5)
