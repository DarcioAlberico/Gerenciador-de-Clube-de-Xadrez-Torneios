from __future__ import annotations

import json
import tkinter as tk
from typing import Any

from ..support import *
from src.services.clock_integration_service import CLOCK_EVENT_TYPES


class IntegrationPagesMixin:
    def show_integrations(self) -> None:
        self._clear_content()
        self._page_title(
            "Integrações Operacionais",
            "Monitore sincronização, dispositivos e eventos auxiliares de relógio/ausência.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(body, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(8, weight=1)

        pending_label = ctk.CTkLabel(toolbar, text="")
        pending_label.grid(row=0, column=0, padx=(0, 16), sticky="w")
        devices_label = ctk.CTkLabel(toolbar, text="")
        devices_label.grid(row=0, column=1, padx=(0, 16), sticky="w")
        events_label = ctk.CTkLabel(toolbar, text="")
        events_label.grid(row=0, column=2, padx=(0, 16), sticky="w")

        ctk.CTkButton(toolbar, text="Atualizar", width=120, command=lambda: load_all()).grid(
            row=0, column=6, padx=(8, 0), sticky="e"
        )
        ctk.CTkButton(toolbar, text="Sincronizar pendentes", width=170, command=lambda: sync_pending()).grid(
            row=0, column=7, padx=(8, 0), sticky="e"
        )

        tabs = ctk.CTkTabview(body)
        tabs.grid(row=1, column=0, sticky="nsew")
        sync_tab = tabs.add("Sincronização")
        devices_tab = tabs.add("Dispositivos")
        clock_tab = tabs.add("Relógio/Ausência")
        album_tab = tabs.add("Álbum/FTP")
        for tab in (sync_tab, devices_tab, clock_tab, album_tab):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)

        sync_tree, sync_url_entry, sync_enabled_var, devices_enabled_var, notifications_enabled_var = (
            self._build_sync_tab(sync_tab)
        )
        devices_tree = self._build_devices_tab(devices_tab)
        clock_tree, pairing_option, event_option, side_option, seconds_entry, note_entry = self._build_clock_tab(clock_tab)
        self._build_ftp_tab(album_tab)

        pairing_option_map: dict[str, int | None] = {"Sem mesa vinculada": None}
        sync_cache: dict[str, dict[str, Any]] = {}
        device_cache: dict[str, dict[str, Any]] = {}
        clock_cache: dict[str, dict[str, Any]] = {}

        def load_sync() -> None:
            sync_tree.delete(*sync_tree.get_children())
            sync_cache.clear()
            for row in self.db.list_sync_outbox(status="", limit=500):
                sync_cache[str(row["id"])] = row
                sync_tree.insert(
                    "",
                    "end",
                    iid=str(row["id"]),
                    values=(
                        row["id"],
                        row["status"],
                        row["action"],
                        row.get("tournament_id") or "",
                        row.get("round_id") or "",
                        row.get("attempts") or 0,
                        row.get("last_error") or "",
                        row.get("created_at") or "",
                    ),
                )

        def load_devices() -> None:
            devices_tree.delete(*devices_tree.get_children())
            device_cache.clear()
            for row in self.sync_service.list_devices():
                device_cache[str(row["device_id"])] = row
                devices_tree.insert(
                    "",
                    "end",
                    iid=str(row["device_id"]),
                    values=(
                        row["device_id"],
                        row["name"],
                        row["role"],
                        row["status"],
                        row.get("last_seen_at") or "",
                        row.get("updated_at") or "",
                    ),
                )

        def load_pairings() -> None:
            pairing_option_map.clear()
            pairing_option_map["Sem mesa vinculada"] = None
            if self.current_tournament_id:
                players = {
                    int(player["id"]): player_pairing_name(player)
                    for player in self.db.list_players(int(self.current_tournament_id), active_only=False)
                }
                for pairing in self.db.get_pairings_for_tournament(int(self.current_tournament_id)):
                    white = players.get(int(pairing.get("white_player_id") or 0), "Brancas")
                    black = "BYE" if pairing.get("is_bye") else players.get(int(pairing.get("black_player_id") or 0), "Pretas")
                    label = f"R{pairing['round_number']} M{pairing['board_number']} - {white} x {black}"
                    pairing_option_map[label] = int(pairing["id"])
            values = list(pairing_option_map.keys())
            pairing_option.configure(values=values)
            pairing_option.set(values[0])

        def load_clock() -> None:
            clock_tree.delete(*clock_tree.get_children())
            clock_cache.clear()
            if not self.current_tournament_id:
                return
            for row in self.clock_integration_service.list_clock_events(int(self.current_tournament_id), limit=500):
                clock_cache[str(row["id"])] = row
                clock_tree.insert(
                    "",
                    "end",
                    iid=str(row["id"]),
                    values=(
                        row["id"],
                        row["occurred_at"],
                        row["event_type"],
                        row.get("source") or "",
                        row.get("board_number") or "",
                        row.get("side") or "",
                        row.get("seconds_remaining") if row.get("seconds_remaining") is not None else "",
                        row.get("note") or "",
                    ),
                )

        def load_metrics() -> None:
            pending = len(self.db.list_sync_outbox(status="pending", limit=5000))
            devices = len(self.sync_service.list_devices())
            events = (
                len(self.clock_integration_service.list_clock_events(int(self.current_tournament_id), limit=5000))
                if self.current_tournament_id
                else 0
            )
            pending_label.configure(text=f"Pendentes: {pending}")
            devices_label.configure(text=f"Dispositivos: {devices}")
            events_label.configure(text=f"Eventos: {events}")

        def load_all() -> None:
            load_settings()
            load_pairings()
            load_sync()
            load_devices()
            load_clock()
            load_metrics()

        def load_settings() -> None:
            settings = self.db.get_app_settings()
            sync_url_entry.delete(0, "end")
            sync_url_entry.insert(0, str(settings.get("sync_server_url") or ""))
            sync_enabled_var.set("1" if str(settings.get("sync_enabled") or "0") in {"1", "true", "True", "sim"} else "0")
            devices_enabled_var.set(
                "1"
                if str(settings.get("device_integrations_enabled") or "0") in {"1", "true", "True", "sim"}
                else "0"
            )
            notifications_enabled_var.set(
                "1" if str(settings.get("notifications_enabled") or "0") in {"1", "true", "True", "sim"} else "0"
            )

        def save_settings() -> None:
            self.db.save_app_settings(
                {
                    "sync_server_url": sync_url_entry.get().strip(),
                    "sync_enabled": sync_enabled_var.get(),
                    "device_integrations_enabled": devices_enabled_var.get(),
                    "notifications_enabled": notifications_enabled_var.get(),
                }
            )
            self._show_toast("Configurações de integração salvas.", kind="success")

        def sync_pending() -> None:
            try:
                if sync_enabled_var.get() != "1":
                    raise AppError("Habilite a sincronização antes de enviar eventos.")
                server_url = sync_url_entry.get().strip()
                if not server_url:
                    raise AppError("Informe a URL do servidor de sincronização.")
                self.db.save_app_settings({"sync_server_url": server_url, "sync_enabled": "1"})
                summary = self.sync_service.sync_pending(server_url=server_url)
                self._show_info(
                    "Sincronização concluída:\n"
                    f"Enviados: {summary['sent']}\n"
                    f"Sincronizados: {summary['synced']}\n"
                    f"Rejeitados: {summary['rejected']}\n"
                    f"Falhas: {summary['failed']}"
                )
                load_all()
            except Exception as exc:
                self._show_error(exc)

        def register_device() -> None:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Autorizar dispositivo")
            dialog.geometry("420x280")
            dialog.grab_set()
            dialog.grid_columnconfigure(0, weight=1)

            form = ctk.CTkFrame(dialog, fg_color="transparent")
            form.grid(row=0, column=0, padx=18, pady=18, sticky="nsew")
            form.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(form, text="Nome").grid(row=0, column=0, sticky="w")
            name_entry = ctk.CTkEntry(form, width=330)
            name_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12))
            ctk.CTkLabel(form, text="Perfil").grid(row=2, column=0, sticky="w")
            role_option = ctk.CTkOptionMenu(form, values=["assistant", "desktop", "viewer"], width=180)
            role_option.grid(row=3, column=0, sticky="w", pady=(4, 12))
            ctk.CTkLabel(form, text="ID do dispositivo").grid(row=4, column=0, sticky="w")
            device_entry = ctk.CTkEntry(form, width=330, placeholder_text="Opcional")
            device_entry.grid(row=5, column=0, sticky="ew", pady=(4, 18))

            def save() -> None:
                try:
                    self.sync_service.register_device(
                        name_entry.get().strip() or "Dispositivo",
                        role=role_option.get(),
                        device_id=device_entry.get().strip(),
                    )
                    dialog.destroy()
                    load_all()
                except Exception as exc:
                    self._show_error(exc)

            ctk.CTkButton(form, text="Autorizar", command=save).grid(row=6, column=0, sticky="ew")

        def revoke_selected_device() -> None:
            selected = devices_tree.selection()
            if not selected:
                self._show_error(AppError("Selecione um dispositivo."))
                return
            try:
                self.sync_service.revoke_device(str(selected[0]))
                load_all()
            except Exception as exc:
                self._show_error(exc)

        def record_clock_event() -> None:
            if not self.current_tournament_id:
                self._show_error(AppError("Selecione um torneio."))
                return
            try:
                seconds_text = seconds_entry.get().strip()
                self.clock_integration_service.record_manual_event(
                    int(self.current_tournament_id),
                    event_option.get(),
                    pairing_id=pairing_option_map.get(pairing_option.get()),
                    side=side_option.get(),
                    seconds_remaining=int(seconds_text) if seconds_text else None,
                    note=note_entry.get().strip(),
                )
                note_entry.delete(0, "end")
                seconds_entry.delete(0, "end")
                load_all()
            except Exception as exc:
                self._show_error(exc)

        def show_alerts() -> None:
            if not self.current_tournament_id:
                self._show_error(AppError("Selecione um torneio."))
                return
            alerts = self.clock_integration_service.anomaly_alerts(int(self.current_tournament_id))
            if not alerts:
                self._show_toast("Nenhum alerta operacional encontrado.", kind="info")
                return
            text = "\n".join(f"- {item['message']}" for item in alerts[:12])
            extra = f"\n... e mais {len(alerts) - 12} alerta(s)." if len(alerts) > 12 else ""
            self._show_info(f"Alertas:\n{text}{extra}")

        def show_sync_detail(_event: Any = None) -> None:
            selected = sync_tree.selection()
            if not selected:
                self._show_error(AppError("Selecione um evento de sincronização."))
                return
            self._show_json_detail("Evento de sincronização", sync_cache.get(str(selected[0]), {}))

        def show_device_detail(_event: Any = None) -> None:
            selected = devices_tree.selection()
            if not selected:
                self._show_error(AppError("Selecione um dispositivo."))
                return
            self._show_json_detail("Dispositivo", device_cache.get(str(selected[0]), {}))

        def show_clock_detail(_event: Any = None) -> None:
            selected = clock_tree.selection()
            if not selected:
                self._show_error(AppError("Selecione um evento de relógio/ausência."))
                return
            self._show_json_detail("Evento de relógio/ausência", clock_cache.get(str(selected[0]), {}))

        devices_buttons = ctk.CTkFrame(devices_tab, fg_color="transparent")
        devices_buttons.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 0))
        ctk.CTkButton(devices_buttons, text="Autorizar dispositivo", command=register_device).pack(side="left")
        ctk.CTkButton(devices_buttons, text="Revogar selecionado", command=revoke_selected_device).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkButton(devices_buttons, text="Detalhes", command=show_device_detail).pack(side="left", padx=(8, 0))

        clock_buttons = ctk.CTkFrame(clock_tab, fg_color="transparent")
        clock_buttons.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 0))
        ctk.CTkButton(clock_buttons, text="Registrar evento", command=record_clock_event).pack(side="left")
        ctk.CTkButton(clock_buttons, text="Ver alertas", command=show_alerts).pack(side="left", padx=(8, 0))
        ctk.CTkButton(clock_buttons, text="Detalhes", command=show_clock_detail).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sync_tab, text="Salvar configurações", command=save_settings).grid(
            row=2, column=0, padx=8, pady=(8, 0), sticky="w"
        )
        ctk.CTkButton(sync_tab, text="Detalhes do evento", command=show_sync_detail).grid(
            row=2, column=0, padx=(170, 8), pady=(8, 0), sticky="w"
        )

        sync_tree.bind("<Double-1>", show_sync_detail)
        devices_tree.bind("<Double-1>", show_device_detail)
        clock_tree.bind("<Double-1>", show_clock_detail)

        load_all()

    def _build_sync_tab(
        self,
        parent: ctk.CTkFrame,
    ) -> tuple[ttk.Treeview, ctk.CTkEntry, tk.StringVar, tk.StringVar, tk.StringVar]:
        settings_panel = ctk.CTkFrame(parent, fg_color="transparent")
        settings_panel.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        settings_panel.grid_columnconfigure(1, weight=1)

        sync_enabled_var = tk.StringVar(value="0")
        devices_enabled_var = tk.StringVar(value="0")
        notifications_enabled_var = tk.StringVar(value="0")

        ctk.CTkLabel(settings_panel, text="Servidor").grid(row=0, column=0, padx=(0, 8), sticky="w")
        sync_url_entry = ctk.CTkEntry(settings_panel, width=360, placeholder_text="https://servidor/api")
        sync_url_entry.grid(row=0, column=1, padx=(0, 12), sticky="ew")
        ctk.CTkSwitch(settings_panel, text="Sync", variable=sync_enabled_var, onvalue="1", offvalue="0").grid(
            row=0, column=2, padx=(0, 10), sticky="w"
        )
        ctk.CTkSwitch(
            settings_panel,
            text="Dispositivos",
            variable=devices_enabled_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=0, column=3, padx=(0, 10), sticky="w")
        ctk.CTkSwitch(
            settings_panel,
            text="Notificações",
            variable=notifications_enabled_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=0, column=4, sticky="w")

        panel = self._make_panel(parent)
        panel.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            panel,
            ["id", "status", "action", "tournament", "round", "attempts", "error", "created"],
            {
                "id": "ID",
                "status": "Status",
                "action": "Ação",
                "tournament": "Torneio",
                "round": "Rodada",
                "attempts": "Tent.",
                "error": "Último erro",
                "created": "Criado em",
            },
            {"id": 60, "status": 100, "action": 170, "tournament": 80, "round": 80, "attempts": 60, "error": 280, "created": 150},
            visible_rows=16,
        )
        return tree, sync_url_entry, sync_enabled_var, devices_enabled_var, notifications_enabled_var

    def _build_devices_tab(self, parent: ctk.CTkFrame) -> ttk.Treeview:
        panel = self._make_panel(parent)
        panel.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)
        return self._make_tree(
            panel,
            ["device_id", "name", "role", "status", "last_seen", "updated"],
            {
                "device_id": "ID",
                "name": "Nome",
                "role": "Perfil",
                "status": "Status",
                "last_seen": "Último acesso",
                "updated": "Atualizado",
            },
            {"device_id": 190, "name": 180, "role": 100, "status": 110, "last_seen": 150, "updated": 150},
            visible_rows=16,
        )

    def _build_clock_tab(
        self,
        parent: ctk.CTkFrame,
    ) -> tuple[ttk.Treeview, ctk.CTkOptionMenu, ctk.CTkOptionMenu, ctk.CTkOptionMenu, ctk.CTkEntry, ctk.CTkEntry]:
        form = ctk.CTkFrame(parent, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        for col in range(6):
            form.grid_columnconfigure(col, weight=0)
        form.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(form, text="Mesa").grid(row=0, column=0, sticky="w")
        pairing_option = ctk.CTkOptionMenu(form, values=["Sem mesa vinculada"], width=300)
        pairing_option.grid(row=1, column=0, padx=(0, 8), sticky="w")

        ctk.CTkLabel(form, text="Evento").grid(row=0, column=1, sticky="w")
        event_option = ctk.CTkOptionMenu(form, values=sorted(CLOCK_EVENT_TYPES), width=150)
        event_option.grid(row=1, column=1, padx=(0, 8), sticky="w")

        ctk.CTkLabel(form, text="Lado").grid(row=0, column=2, sticky="w")
        side_option = ctk.CTkOptionMenu(form, values=["", "white", "black"], width=95)
        side_option.grid(row=1, column=2, padx=(0, 8), sticky="w")

        ctk.CTkLabel(form, text="Segundos").grid(row=0, column=3, sticky="w")
        seconds_entry = ctk.CTkEntry(form, width=90)
        seconds_entry.grid(row=1, column=3, padx=(0, 8), sticky="w")

        ctk.CTkLabel(form, text="Observação").grid(row=0, column=4, sticky="w")
        note_entry = ctk.CTkEntry(form, width=300)
        note_entry.grid(row=1, column=4, columnspan=2, sticky="ew")

        panel = self._make_panel(parent)
        panel.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)
        tree = self._make_tree(
            panel,
            ["id", "occurred", "event", "source", "board", "side", "seconds", "note"],
            {
                "id": "ID",
                "occurred": "Data",
                "event": "Evento",
                "source": "Origem",
                "board": "Mesa",
                "side": "Lado",
                "seconds": "Seg.",
                "note": "Observação",
            },
            {"id": 55, "occurred": 150, "event": 130, "source": 100, "board": 70, "side": 75, "seconds": 70, "note": 320},
            visible_rows=14,
        )
        return tree, pairing_option, event_option, side_option, seconds_entry, note_entry

    def _build_ftp_tab(self, parent: ctk.CTkFrame) -> None:
        config = self.photo_album_service.get_config()

        ctk.CTkLabel(
            parent,
            text="Publique um album de fotos do torneio em um servidor FTP (passo opcional, offline-first). "
            "A senha e guardada protegida (DPAPI) e nunca exibida.",
            text_color=THEME_TEXT_SUB,
            anchor="w",
            justify="left",
            wraplength=900,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))

        panel = self._make_panel(parent)
        panel.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(1, weight=1)

        host_entry = ctk.CTkEntry(panel, placeholder_text="ftp.exemplo.com")
        port_entry = ctk.CTkEntry(panel, width=90)
        user_entry = ctk.CTkEntry(panel)
        pass_entry = ctk.CTkEntry(panel, show="*")
        remote_entry = ctk.CTkEntry(panel, placeholder_text="/public_html/fotos")
        tls_var = tk.StringVar(value="1" if config.get("use_tls") else "0")
        passive_var = tk.StringVar(value="1" if config.get("passive", True) else "0")

        fields = [
            ("Host", host_entry, config.get("host", "")),
            ("Porta", port_entry, str(config.get("port", 21))),
            ("Usuario", user_entry, config.get("user", "")),
            ("Senha", pass_entry, config.get("password", "")),
            ("Pasta remota", remote_entry, config.get("remote_dir", "")),
        ]
        for index, (label, entry, value) in enumerate(fields):
            ctk.CTkLabel(panel, text=label).grid(row=index, column=0, padx=(16, 8), pady=6, sticky="w")
            entry.grid(row=index, column=1, padx=(0, 16), pady=6, sticky="ew")
            if value:
                entry.insert(0, str(value))

        switches = ctk.CTkFrame(panel, fg_color="transparent")
        switches.grid(row=len(fields), column=1, padx=(0, 16), pady=6, sticky="w")
        ctk.CTkSwitch(switches, text="FTPS (TLS)", variable=tls_var, onvalue="1", offvalue="0").pack(
            side="left", padx=(0, 16)
        )
        ctk.CTkSwitch(switches, text="Modo passivo", variable=passive_var, onvalue="1", offvalue="0").pack(side="left")

        def current_config() -> dict[str, Any]:
            return {
                "host": host_entry.get().strip(),
                "port": port_entry.get().strip() or "21",
                "user": user_entry.get(),
                "password": pass_entry.get(),
                "remote_dir": remote_entry.get().strip(),
                "use_tls": tls_var.get() == "1",
                "passive": passive_var.get() == "1",
            }

        def save_config() -> None:
            try:
                self.photo_album_service.save_config(current_config())
                self._show_toast("Configuracao FTP salva.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def test_connection() -> None:
            try:
                self.photo_album_service.save_config(current_config())
                self._run_background(
                    lambda: self.photo_album_service.test_connection(),
                    lambda _ok: self._show_info("Conexao FTP bem-sucedida."),
                    "Testando conexao FTP...",
                )
            except Exception as exc:
                self._show_error(exc)

        def publish_album() -> None:
            try:
                self.photo_album_service.save_config(current_config())
                directory = filedialog.askdirectory(
                    title="Pasta de fotos para publicar",
                    initialdir=str(self._default_export_dir()),
                )
                if not directory:
                    return

                def show_result(result: dict[str, Any]) -> None:
                    self._show_info(
                        f"{result['total']} arquivos publicados"
                        + (" (com galeria index.html)." if result.get("gallery") else ".")
                    )

                self._run_background(
                    lambda: self.photo_album_service.publish_album(directory),
                    show_result,
                    "Publicando album por FTP...",
                )
            except Exception as exc:
                self._show_error(exc)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=len(fields) + 1, column=1, padx=(0, 16), pady=(10, 12), sticky="w")
        ctk.CTkButton(actions, text="Salvar config", command=save_config, width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Testar conexao", command=test_connection, width=140).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Publicar pasta...", command=publish_album, width=150).pack(side="left")

    def _show_json_detail(self, title: str, payload: dict[str, Any]) -> None:
        formatted = self._format_json_detail(payload)
        modal = ctk.CTkToplevel(self)
        modal.title(title)
        modal.geometry("720x520")
        modal.grab_set()
        modal.grid_columnconfigure(0, weight=1)
        modal.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(modal, text=title, font=font_section()).grid(
            row=0,
            column=0,
            padx=12,
            pady=(12, 8),
            sticky="w",
        )
        text = ctk.CTkTextbox(modal, wrap="none")
        text.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        text.insert("1.0", formatted)
        text.configure(state="disabled")

    @staticmethod
    def _format_json_detail(payload: dict[str, Any]) -> str:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str) and key.endswith("_json") and value:
                try:
                    normalized[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            normalized[key] = value
        return json.dumps(normalized, indent=2, ensure_ascii=False, default=str)
