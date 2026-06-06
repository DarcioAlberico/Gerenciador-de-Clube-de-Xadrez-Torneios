from __future__ import annotations

from ..support import *

from .settings_certificates_ui import SettingsCertificatesMixin
from .settings_reports_ui import SettingsReportsMixin
from .settings_users_ui import SettingsUsersMixin


def _cloud_status_label(status: str) -> str:
    """Texto amigavel para o status de copia do backup para a nuvem."""
    status = (status or "").strip()
    if status == "success":
        return "copiado para a pasta de nuvem."
    if status == "not_configured":
        return "pasta de nuvem nao configurada."
    if status == "invalid_directory":
        return "pasta de nuvem invalida (verifique o caminho)."
    if status.startswith("error:"):
        return f"falha ao copiar ({status[len('error:'):].strip()})."
    return status or "sem informacao."


class SettingsPagesMixin(SettingsReportsMixin, SettingsCertificatesMixin, SettingsUsersMixin):
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
                        self._show_info(
                            f"Backup criado:\n{result['path']}\n\n"
                            f"Nuvem: {_cloud_status_label(result.get('cloud_status', ''))}"
                        ),
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

