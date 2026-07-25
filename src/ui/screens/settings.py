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
            "Configurações do aplicativo",
            "Ajuste preferencias locais, pasta de exportacao e rotinas de backup.",
        )

        settings = self.db.get_app_settings()
        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        settings_tabs = ctk.CTkTabview(body)
        settings_tabs.grid(row=0, column=0, padx=(0, 16), sticky="nsew")
        tab_appearance = self._settings_tab(settings_tabs, "Aparência")
        tab_folders = self._settings_tab(settings_tabs, "Pastas e backup")
        tab_tools = self._settings_tab(settings_tabs, "Segurança e dados")
        stack = self._settings_stack

        # --- Aba: Aparencia ---
        # Galeria de temas curados (paletas combinadas) + modo avancado.
        appearance_ctl = self._build_appearance_tab(tab_appearance, settings)
        appearance_option = appearance_ctl["appearance_option"]
        appearance_values = appearance_ctl["appearance_values"]
        accent_option = appearance_ctl["accent_option"]
        bg_option = appearance_ctl["bg_option"]
        frame_bg_option = appearance_ctl["frame_bg_option"]
        ui_scale_entry = appearance_ctl["ui_scale_entry"]

        # --- Aba: Pastas e backup ---
        export_dir_entry = ctk.CTkEntry(tab_folders, width=320)
        stack(tab_folders, export_dir_entry, label="Pasta de exportação")
        export_dir_entry.insert(0, str(settings.get("default_export_dir") or default_export_dir()))

        def choose_export_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta de exportação",
                initialdir=str(self._default_export_dir()),
            )
            if directory:
                export_dir_entry.delete(0, "end")
                export_dir_entry.insert(0, directory)

        stack(tab_folders, ctk.CTkButton(tab_folders, text="Escolher exportação", command=choose_export_dir))

        backup_dir_entry = ctk.CTkEntry(tab_folders, width=320)
        stack(tab_folders, backup_dir_entry, label="Pasta de backups")
        backup_dir_entry.insert(0, str(settings.get("backup_dir") or self.db.backup_dir))

        def choose_backup_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta de backups",
                initialdir=str(self.db.backup_dir),
            )
            if directory:
                backup_dir_entry.delete(0, "end")
                backup_dir_entry.insert(0, directory)

        stack(tab_folders, ctk.CTkButton(tab_folders, text="Escolher backups", command=choose_backup_dir))

        cloud_dir_entry = ctk.CTkEntry(tab_folders, width=320)
        stack(tab_folders, cloud_dir_entry, label="Pasta de Nuvem (Google Drive/Dropbox)")
        cloud_dir_entry.insert(0, str(settings.get("cloud_sync_dir", "")))

        def choose_cloud_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta sincronizada em nuvem",
                initialdir="/",
            )
            if directory:
                cloud_dir_entry.delete(0, "end")
                cloud_dir_entry.insert(0, directory)

        stack(tab_folders, ctk.CTkButton(tab_folders, text="Escolher nuvem", command=choose_cloud_dir))

        retention_entry = ctk.CTkEntry(tab_folders, width=120)
        stack(tab_folders, retention_entry, label="Manter últimos backups")
        retention_entry.insert(0, str(settings.get("backup_retention_count") or "10"))

        # --- Aba: Seguranca e dados ---
        def open_users_manager() -> None:
            self._show_users_manager()

        stack(
            tab_tools,
            ctk.CTkButton(tab_tools, text="Gerenciar Usuários do Sistema", command=open_users_manager),
            label="Segurança operacional",
            section=True,
        )

        def download_fide() -> None:
            # Download longo (minutos): vai para o helper unico de background, que
            # desabilita o botao, liga o indicador de progresso e manda erro p/ toast.
            self._run_background(
                self.official_rating_service.import_fide_list_from_url,
                on_success=lambda res: self._show_info(
                    f"{res['imported']} jogadores da FIDE importados."
                ),
                busy_message="Baixando lista da FIDE...",
                busy_widget=fide_button,
            )
            self._show_info("Download da FIDE iniciado — pode levar alguns minutos.")

        fide_button = ctk.CTkButton(
            tab_tools,
            text="Baixar e Sincronizar FIDE",
            command=download_fide,
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
        )
        stack(tab_tools, fide_button, label="Sincronização de Ratings", section=True)

        def _import_cbx_file(path: str) -> dict:
            """Parte pesada da importacao CBX — roda fora da thread da UI."""
            suffix = str(path).lower()
            if suffix.endswith(".xml"):
                return self.official_rating_service.import_official_xml(path, "CBX", "")
            if suffix.endswith(".xls") or suffix.endswith(".xlsx"):
                return self.official_rating_service.import_official_excel(path, "CBX", "")
            return self.official_rating_service.import_official_csv(path, "CBX", "")

        def import_cbx() -> None:
            from tkinter import filedialog
            path = filedialog.askopenfilename(filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("XML", "*.xml"), ("Texto", "*.txt")])
            if not path:
                return
            self._run_background(
                lambda: _import_cbx_file(path),
                on_success=lambda res: self._show_info(f"{res['imported']} jogadores CBX importados!"),
                busy_message="Importando lista CBX...",
                busy_widget=cbx_button,
            )

        cbx_button = ctk.CTkButton(tab_tools, text="Importar Lista CBX (Excel / CSV / XML)", command=import_cbx)
        stack(tab_tools, cbx_button)

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
                "description": "Descrição",
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
            try:
                _default_border = ctk.ThemeManager.theme["CTkEntry"]["border_color"]
            except Exception:
                _default_border = None

            def _flag_field(entry: Any, message: str) -> None:
                try:
                    entry.configure(border_color=THEME_DANGER)
                except Exception:
                    pass
                raise AppError(message)

            for _entry in (ui_scale_entry, retention_entry):
                if _default_border is not None:
                    try:
                        _entry.configure(border_color=_default_border)
                    except Exception:
                        pass

            export_dir = Path(export_dir_entry.get().strip() or default_export_dir())
            backup_dir = Path(backup_dir_entry.get().strip() or default_backup_dir())
            try:
                ui_scale_percent = int(ui_scale_entry.get().strip() or "120")
            except ValueError:
                _flag_field(ui_scale_entry, "Tamanho da fonte/interface deve ser um numero entre 80 e 160.")
            if ui_scale_percent < 80 or ui_scale_percent > 160:
                _flag_field(ui_scale_entry, "Tamanho da fonte/interface deve ficar entre 80 e 160.")
            retention_raw = retention_entry.get().strip()
            if not retention_raw.isdigit() or int(retention_raw) < 1:
                _flag_field(retention_entry, "Manter ultimos backups: informe um inteiro maior ou igual a 1.")

            # Resolve chaves a partir dos labels selecionados
            _accent_lbl_to_key = {v: k for k, v in ACCENT_PRESET_LABELS.items()}
            _bg_lbl_to_key     = {v: k for k, v in BG_COLOR_PRESET_LABELS.items()}
            _frame_lbl_to_key  = {v: k for k, v in FRAME_BG_PRESET_LABELS.items()}
            _new_accent    = _accent_lbl_to_key.get(accent_option.get(), "blue")
            _new_bg        = _bg_lbl_to_key.get(bg_option.get(), "slate")
            _new_frame_bg  = _frame_lbl_to_key.get(frame_bg_option.get(), "slate")

            export_dir.mkdir(parents=True, exist_ok=True)
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.db.save_app_settings(
                {
                    "appearance_mode": appearance_values[appearance_option.get()],
                    "accent_preset":   _new_accent,
                    "bg_preset":       _new_bg,
                    "frame_bg_preset": _new_frame_bg,
                    "curated_theme":   appearance_ctl["get_curated"](),
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

            _needs_rebuild = (
                settings.get("accent_preset", "blue") != _new_accent
                or settings.get("bg_preset", "slate") != _new_bg
                or settings.get("frame_bg_preset", "slate") != _new_frame_bg
                or settings.get("appearance_mode", "System") != appearance_values[appearance_option.get()]
            )
            if _needs_rebuild:
                # Algum preset de cor mudou: reestiliza o que ja esta na tela.
                # Nada e destruido, entao a tela continua onde estava (F1.2).
                self._rebuild_ui_after_theme_change()

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
                confirmed = self._confirm_action(
                    "Restaurar backup",
                    "A restauracao substitui o banco atual. Um backup de seguranca sera criado antes. Continuar?",
                    danger=True,
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
                # Salva apenas a retencao sem disparar rebuild de tema.
                # persist_settings() compara snapshots e pode triggerar _rebuild_ui;
                # aqui so nos importa salvar o retention_count e executar a limpeza.
                retention_raw = retention_entry.get().strip()
                if not retention_raw.isdigit() or int(retention_raw) < 1:
                    self._show_error("Manter ultimos backups: informe um inteiro maior ou igual a 1.")
                    return
                self.security_service.save_security_settings(
                    {"backup_retention_count": retention_raw}
                )
                deleted = self.security_service.enforce_backup_retention()
                load_backups()
                load_audit_logs()
                self._show_toast(f"Retencao aplicada. {len(deleted)} backup(s) removido(s).", kind="success")
            except Exception as exc:
                self._show_error(exc)


        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=1, column=0, padx=(0, 16), pady=(10, 0), sticky="ew")
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

    def _build_appearance_tab(self, tab: Any, settings: dict[str, Any]) -> dict[str, Any]:
        """Monta a aba Aparencia: galeria de temas curados + modo avancado.

        Os tres dropdowns (destaque/fundo/frames) continuam existindo como fonte
        de verdade dos valores; os cartoes de tema apenas os preenchem. Devolve
        os controles que ``persist_settings`` consome.
        """
        stack = self._settings_stack
        state = {"theme": "custom"}

        appearance_labels = {"System": "Sistema", "Light": "Claro", "Dark": "Escuro"}
        appearance_values = {label: value for value, label in appearance_labels.items()}

        # Presets salvos, com compatibilidade de chaves legadas.
        _saved_accent = settings.get("accent_preset") or settings.get("color_theme") or "blue"
        _saved_accent = {
            "dark-blue": "indigo", "violet": "violet", "teal": "teal",
            "orange": "orange", "rose": "rose",
        }.get(_saved_accent, _saved_accent)
        if _saved_accent not in ACCENT_PRESET_LABELS:
            _saved_accent = "blue"
        _saved_bg = settings.get("bg_preset") or "slate"
        _saved_bg = {"default": "slate"}.get(_saved_bg, _saved_bg)
        if _saved_bg not in BG_COLOR_PRESET_LABELS:
            _saved_bg = "slate"
        _saved_frame = settings.get("frame_bg_preset") or "slate"
        if _saved_frame not in FRAME_BG_PRESET_LABELS:
            _saved_frame = "slate"

        # --- Controles avancados (ocultos ate o usuario pedir) ---
        advanced = ctk.CTkFrame(tab, fg_color="transparent")
        advanced.grid_columnconfigure(0, weight=1)
        appearance_option = ctk.CTkOptionMenu(advanced, values=list(appearance_values.keys()), width=240)
        accent_option = ctk.CTkOptionMenu(advanced, values=list(ACCENT_PRESET_LABELS.values()), width=240)
        bg_option = ctk.CTkOptionMenu(advanced, values=list(BG_COLOR_PRESET_LABELS.values()), width=240)
        frame_bg_option = ctk.CTkOptionMenu(advanced, values=list(FRAME_BG_PRESET_LABELS.values()), width=240)
        for idx, (lbl, opt) in enumerate([
            ("Aparência (claro / escuro)", appearance_option),
            ("Cor de destaque (botoes, links)", accent_option),
            ("Cor de fundo (janela)", bg_option),
            ("Cor dos frames (cards, paineis)", frame_bg_option),
        ]):
            ctk.CTkLabel(advanced, text=lbl).grid(row=idx * 2, column=0, sticky="w", padx=4, pady=(6, 0))
            opt.grid(row=idx * 2 + 1, column=0, sticky="ew", padx=4, pady=(2, 4))
        appearance_option.set(appearance_labels.get(settings.get("appearance_mode", "System"), "Sistema"))
        accent_option.set(ACCENT_PRESET_LABELS[_saved_accent])
        bg_option.set(BG_COLOR_PRESET_LABELS[_saved_bg])
        frame_bg_option.set(FRAME_BG_PRESET_LABELS[_saved_frame])

        # --- Galeria de temas curados ---
        gallery = ctk.CTkFrame(tab, fg_color="transparent")
        gallery.grid_columnconfigure(0, weight=1)
        cards: dict[str, ctk.CTkFrame] = {}

        def refresh_cards() -> None:
            for key, card in cards.items():
                on = state["theme"] == key
                card.configure(
                    border_width=2 if on else 1,
                    border_color=THEME_ACCENT if on else THEME_PANEL_BG,
                )

        def select_curated(key: str) -> None:
            theme = CURATED_THEMES[key]
            state["theme"] = key
            appearance_option.set(appearance_labels.get(theme["appearance"], "Sistema"))
            accent_option.set(ACCENT_PRESET_LABELS[theme["accent"]])
            bg_option.set(BG_COLOR_PRESET_LABELS[theme["bg"]])
            frame_bg_option.set(FRAME_BG_PRESET_LABELS[theme["frame"]])
            advanced_switch.deselect()
            advanced.grid_remove()
            refresh_cards()

        for row, key in enumerate(CURATED_THEMES):
            card = self._curated_theme_card(gallery, key, lambda k=key: select_curated(k))
            card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            cards[key] = card
        stack(tab, gallery, label="Tema visual")

        # --- Alternancia para o modo avancado ---
        def toggle_advanced() -> None:
            if advanced_switch.get():
                state["theme"] = "custom"
                advanced.grid()
                refresh_cards()
            else:
                advanced.grid_remove()

        advanced_switch = ctk.CTkSwitch(tab, text="Personalizar cores (avancado)", command=toggle_advanced)
        stack(tab, advanced_switch)
        stack(tab, advanced)

        def on_advanced_change(_value: Any = None) -> None:
            state["theme"] = "custom"
            refresh_cards()

        for opt in (appearance_option, accent_option, bg_option, frame_bg_option):
            opt.configure(command=on_advanced_change)

        # --- Tamanho da fonte/interface ---
        ui_scale_entry = ctk.CTkEntry(tab, width=120)
        stack(tab, ui_scale_entry, label="Tamanho da fonte/interface (%)")
        ui_scale_entry.insert(0, str(settings.get("ui_scale_percent") or "120"))

        # --- Selecao inicial: tema curado correspondente, senao modo avancado ---
        saved_curated = settings.get("curated_theme") or ""
        initial = saved_curated if saved_curated in CURATED_THEMES else match_curated_theme(
            _saved_accent, _saved_bg, _saved_frame
        )
        if initial:
            state["theme"] = initial
            advanced.grid_remove()
        else:
            state["theme"] = "custom"
            advanced_switch.select()
        refresh_cards()

        return {
            "appearance_option": appearance_option,
            "appearance_values": appearance_values,
            "accent_option": accent_option,
            "bg_option": bg_option,
            "frame_bg_option": frame_bg_option,
            "ui_scale_entry": ui_scale_entry,
            "get_curated": lambda: state["theme"],
        }

    def _curated_theme_card(self, parent: Any, key: str, on_click: Callable[[], None]) -> ctk.CTkFrame:
        """Cartao clicavel de tema curado: mini-preview + nome + modo."""
        theme = CURATED_THEMES[key]
        sw = curated_theme_swatches(key)

        card = ctk.CTkFrame(
            parent, fg_color=THEME_PANEL_BG, corner_radius=8,
            border_width=1, border_color=THEME_PANEL_BG,
        )
        card.grid_columnconfigure(1, weight=1)

        # Mini-preview da janela (fundo + statusbar + card + chip de destaque).
        prev = ctk.CTkFrame(card, width=96, height=58, fg_color=sw["app"], corner_radius=6)
        prev.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        prev.grid_propagate(False)
        prev.grid_columnconfigure(0, weight=1)
        prev.grid_rowconfigure(1, weight=1)
        ctk.CTkFrame(prev, height=11, fg_color=sw["statusbar"], corner_radius=0).grid(
            row=0, column=0, sticky="ew"
        )
        mini = ctk.CTkFrame(prev, fg_color=sw["panel"], corner_radius=4)
        mini.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))
        ctk.CTkLabel(
            mini, text="24", font=ctk.CTkFont(size=SIZE_SUBSECTION, weight="bold"), text_color=sw["text"]
        ).pack(anchor="w", padx=8, pady=(5, 0))
        ctk.CTkFrame(mini, height=7, width=32, fg_color=sw["accent"], corner_radius=3).pack(
            anchor="w", padx=8, pady=(3, 0)
        )

        # Nome + modo (e selo de recomendado, quando aplicavel).
        ctk.CTkLabel(
            card, text=theme["label"], font=font_subsection(),
            text_color=THEME_TEXT_MAIN, anchor="w", justify="left", wraplength=150,
        ).grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(12, 0))
        mode_txt = "Escuro" if theme["appearance"] == "Dark" else "Claro"
        subtitle = f"Recomendado · {mode_txt}" if theme.get("recommended") else mode_txt
        ctk.CTkLabel(
            card, text=subtitle, font=ctk.CTkFont(size=SIZE_BODY),
            text_color=THEME_TEXT_SUB, anchor="w", justify="left", wraplength=150,
        ).grid(row=1, column=1, sticky="nw", padx=(0, 10), pady=(0, 12))

        def _bind(widget: Any) -> None:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _event: on_click())
            for child in widget.winfo_children():
                _bind(child)

        _bind(card)
        return card

