from __future__ import annotations

import json
import tkinter as tk
from typing import Any

from ..support import *
from ..components import report_dialog
from src.services.clock_integration_service import CLOCK_EVENT_TYPES


class IntegrationPagesMixin:
    def show_integrations(self) -> None:
        self._clear_content()
        self._page_title(
            "Integrações Operacionais",
            "Eventos de relógio e ausência, e publicação do álbum de fotos.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(body, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(8, weight=1)

        events_label = ctk.CTkLabel(toolbar, text="")
        events_label.grid(row=0, column=0, padx=(0, 16), sticky="w")

        ctk.CTkButton(toolbar, text="Atualizar", width=120, command=lambda: load_all()).grid(
            row=0, column=7, padx=(8, 0), sticky="e"
        )

        # RG2-38 (D5): a sincronização com dispositivos saiu inteira — fila,
        # dispositivos e servidor. Ficam o relógio/ausência e o álbum.
        tabs = ctk.CTkTabview(body)
        tabs.grid(row=1, column=0, sticky="nsew")
        clock_tab = tabs.add("Relógio/Ausência")
        album_tab = tabs.add("Álbum/FTP")
        for tab in (clock_tab, album_tab):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)

        clock_tree, pairing_option, event_option, side_option, seconds_entry, note_entry = self._build_clock_tab(clock_tab)
        self._build_ftp_tab(album_tab)

        devices_enabled_var = tk.StringVar(value="0")
        notifications_enabled_var = tk.StringVar(value="0")
        pairing_option_map: dict[str, int | None] = {"Sem mesa vinculada": None}
        clock_cache: dict[str, dict[str, Any]] = {}

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
            events = (
                len(self.clock_integration_service.list_clock_events(int(self.current_tournament_id), limit=5000))
                if self.current_tournament_id
                else 0
            )
            events_label.configure(text=f"Eventos: {events}")

        def load_all() -> None:
            load_settings()
            load_pairings()
            load_clock()
            load_metrics()

        def load_settings() -> None:
            settings = self.db.get_app_settings()
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
                    "device_integrations_enabled": devices_enabled_var.get(),
                    "notifications_enabled": notifications_enabled_var.get(),
                }
            )
            self._show_toast("Configurações de integração salvas.", kind="success")

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

        def show_clock_detail(_event: Any = None) -> None:
            selected = clock_tree.selection()
            if not selected:
                self._show_error(AppError("Selecione um evento de relógio/ausência."))
                return
            self._show_json_detail("Evento de relógio/ausência", clock_cache.get(str(selected[0]), {}))

        clock_buttons = ctk.CTkFrame(clock_tab, fg_color="transparent")
        clock_buttons.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 0))
        ctk.CTkButton(clock_buttons, text="Registrar evento", command=record_clock_event).pack(side="left")
        ctk.CTkButton(clock_buttons, text="Ver alertas", command=show_alerts).pack(side="left", padx=(8, 0))
        ctk.CTkButton(clock_buttons, text="Detalhes", command=show_clock_detail).pack(side="left", padx=(8, 0))
        # Os interruptores do relógio (eram da aba Sincronização) ficam na barra
        # do topo, que tem espaço até em 800 px de largura.
        ctk.CTkSwitch(
            toolbar, text="Dispositivos", variable=devices_enabled_var, onvalue="1", offvalue="0"
        ).grid(row=0, column=1, padx=(0, 10), sticky="w")
        ctk.CTkSwitch(
            toolbar, text="Notificações", variable=notifications_enabled_var, onvalue="1", offvalue="0"
        ).grid(row=0, column=2, padx=(0, 10), sticky="w")
        ctk.CTkButton(toolbar, text="Salvar configurações", width=170, command=save_settings).grid(
            row=0, column=6, padx=(8, 0), sticky="e"
        )

        clock_tree.bind("<Double-1>", show_clock_detail)

        load_all()

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

        # Numa linha própria: na mesma linha dos outros campos, o formulário
        # passava de 800 px (aparecia quando o relógio virou a primeira aba).
        ctk.CTkLabel(form, text="Observação").grid(row=2, column=0, pady=(6, 0), sticky="w")
        note_entry = ctk.CTkEntry(form, width=300)
        note_entry.grid(row=3, column=0, columnspan=6, sticky="ew")

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
            text="Publique um álbum de fotos do torneio em um servidor FTP (passo opcional, offline-first). "
            "A senha é guardada protegida (DPAPI) e nunca exibida.",
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
            ("Usuário", user_entry, config.get("user", "")),
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
                self._show_toast("Configuração FTP salva.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def test_connection() -> None:
            try:
                self.photo_album_service.save_config(current_config())
                self._run_background(
                    lambda: self.photo_album_service.test_connection(),
                    lambda _ok: self._show_info("Conexão FTP bem-sucedida."),
                    "Testando conexão FTP...",
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
                    "Publicando álbum por FTP...",
                )
            except Exception as exc:
                self._show_error(exc)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=len(fields) + 1, column=1, padx=(0, 16), pady=(10, 12), sticky="w")
        ctk.CTkButton(actions, text="Salvar config", command=save_config, width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Testar conexão", command=test_connection, width=140).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Publicar pasta...", command=publish_album, width=150).pack(side="left")

    def _show_json_detail(self, title: str, payload: dict[str, Any]) -> None:
        """Detalhe tecnico do evento — texto que se le e se copia (F5.7/P3-10)."""
        report_dialog(self, title, self._format_json_detail(payload))

    @staticmethod
    def _format_json_detail(payload: dict[str, Any]) -> str:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str) and key.endswith("_json") and value:
                try:
                    normalized[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass  # não é JSON: o detalhe mostra o texto como veio
            normalized[key] = value
        return json.dumps(normalized, indent=2, ensure_ascii=False, default=str)
