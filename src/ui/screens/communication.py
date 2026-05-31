from __future__ import annotations

import threading
from ..support import *
from src.services.message_service import MessageService

class CommunicationPagesMixin:
    def show_communication(self) -> None:
        self.require_permission("settings_read")
        self._clear_content()
        self._page_title(
            "Comunicação",
            "Envie e-mails ou mensagens via WhatsApp para os membros do clube.",
        )

        settings = self.db.get_app_settings()
        msg_service = MessageService(
            smtp_server=settings.get("smtp_server", ""),
            smtp_port=int(settings.get("smtp_port", 587)),
            smtp_user=settings.get("smtp_user", ""),
            smtp_password=settings.get("smtp_password", "")
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tabview = ctk.CTkTabview(body)
        tabview.grid(row=0, column=0, sticky="nsew")
        tab_email = tabview.add("E-mail")
        tab_bulk = tabview.add("Disparo em massa")
        tab_whatsapp = tabview.add("WhatsApp")
        tab_config = tabview.add("Config. SMTP")

        self._build_email_tab(tab_email, msg_service)
        self._build_bulk_tab(tab_bulk, msg_service)
        self._build_whatsapp_tab(tab_whatsapp, msg_service)
        self._build_smtp_config_tab(tab_config, settings)

    def _build_email_tab(self, parent: ctk.CTkFrame, msg_service: MessageService) -> None:
        parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="Destinatário (E-mail):").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        to_entry = ctk.CTkEntry(parent, width=400)
        to_entry.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(parent, text="Assunto:").grid(row=2, column=0, padx=16, pady=(8, 4), sticky="w")
        subject_entry = ctk.CTkEntry(parent, width=400)
        subject_entry.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(parent, text="Mensagem:").grid(row=4, column=0, padx=16, pady=(8, 4), sticky="w")
        body_entry = ctk.CTkTextbox(parent, height=200)
        body_entry.grid(row=5, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="nsew")

        parent.grid_rowconfigure(5, weight=1)

        def do_send_email():
            to_email = to_entry.get().strip()
            subject = subject_entry.get().strip()
            body_text = body_entry.get("1.0", "end-1c").strip()

            if not to_email or not subject or not body_text:
                self._show_error("Preencha todos os campos do e-mail.")
                return

            def task():
                try:
                    msg_service.send_email(to_email, subject, body_text)
                    self.after(0, lambda: self._show_toast("E-mail enviado com sucesso!", kind="success"))
                except Exception as exc:
                    self.after(0, lambda error=exc: self._show_error(f"Falha ao enviar: {error}"))

            threading.Thread(target=task, daemon=True).start()

        btn = ctk.CTkButton(parent, text="Enviar E-mail", command=do_send_email)
        btn.grid(row=6, column=0, padx=16, pady=(0, 16), sticky="w")

    def _build_bulk_tab(self, parent: ctk.CTkFrame, msg_service: MessageService) -> None:
        parent.grid_columnconfigure(0, weight=1)

        # Publico-alvo: define como os destinatarios sao resolvidos.
        classes = self.db.list_classes(active_only=True)
        class_by_label = {f"{c['name']}": int(c["id"]) for c in classes}
        # Ordem de exibicao estavel, restrita aos tipos validos (sem drift).
        member_types = [t for t in ["socio", "aluno", "convidado", "visitante"] if t in MEMBER_TYPES]

        ctk.CTkLabel(parent, text="Publico-alvo:").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        audience_option = ctk.CTkOptionMenu(
            parent, width=240,
            values=["Todos os ativos", "Por turma", "Por tipo de membro"],
        )
        audience_option.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        filter_option = ctk.CTkOptionMenu(parent, width=240, values=[""])
        filter_option.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="w")

        def on_audience_change(choice: str) -> None:
            if choice == "Por turma":
                values = list(class_by_label.keys()) or ["(nenhuma turma)"]
                filter_option.configure(values=values, state="normal")
                filter_option.set(values[0])
            elif choice == "Por tipo de membro":
                filter_option.configure(values=member_types, state="normal")
                filter_option.set(member_types[0])
            else:
                filter_option.configure(values=[""], state="disabled")
                filter_option.set("")

        audience_option.configure(command=on_audience_change)
        on_audience_change("Todos os ativos")

        ctk.CTkLabel(parent, text="Assunto:").grid(row=3, column=0, padx=16, pady=(8, 4), sticky="w")
        subject_entry = ctk.CTkEntry(parent, width=400)
        subject_entry.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(parent, text="Mensagem:").grid(row=5, column=0, padx=16, pady=(8, 4), sticky="w")
        body_entry = ctk.CTkTextbox(parent, height=140)
        body_entry.grid(row=6, column=0, padx=16, pady=(0, 12), sticky="nsew")
        parent.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            parent, text="Agendar para (AAAA-MM-DD HH:MM, opcional):"
        ).grid(row=7, column=0, padx=16, pady=(0, 4), sticky="w")
        schedule_entry = ctk.CTkEntry(parent, width=240, placeholder_text="Vazio = enviar agora")
        schedule_entry.grid(row=8, column=0, padx=16, pady=(0, 4), sticky="w")
        ctk.CTkLabel(
            parent,
            text="Agendados so disparam com o app aberto (a fila e salva).",
            text_color="gray",
        ).grid(row=9, column=0, padx=16, pady=(0, 8), sticky="w")

        # Lista de agendamentos pendentes, com cancelamento.
        pending_holder = ctk.CTkScrollableFrame(parent, height=120, label_text="Agendados pendentes")
        pending_holder.grid(row=11, column=0, padx=16, pady=(8, 12), sticky="nsew")
        pending_holder.grid_columnconfigure(0, weight=1)

        def load_pending() -> None:
            for child in pending_holder.winfo_children():
                child.destroy()
            pending = self.communication_service.list_scheduled_messages(status="pending")
            if not pending:
                ctk.CTkLabel(pending_holder, text="Nenhum agendamento pendente.", text_color="gray").grid(
                    row=0, column=0, sticky="w", padx=4, pady=4
                )
                return
            for idx, item in enumerate(pending):
                row = ctk.CTkFrame(pending_holder, fg_color="transparent")
                row.grid(row=idx, column=0, sticky="ew", pady=2)
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(
                    row, anchor="w",
                    text=f"{item['scheduled_at']} - {item['subject']}",
                ).grid(row=0, column=0, sticky="ew", padx=(4, 8))
                ctk.CTkButton(
                    row, text="Cancelar", width=80,
                    command=lambda mid=int(item["id"]): (
                        self.communication_service.cancel_scheduled_message(mid),
                        load_pending(),
                    ),
                ).grid(row=0, column=1)

        def resolve_audience() -> tuple[dict, str, str, str]:
            """Devolve (kwargs_imediato, audience_kind, audience_value, descricao)."""
            audience = audience_option.get()
            if audience == "Por turma":
                class_id = class_by_label.get(filter_option.get())
                if not class_id:
                    raise AppError("Selecione uma turma valida.")
                return ({"active_only": True, "class_id": class_id},
                        "class", str(class_id), f"turma {filter_option.get()}")
            if audience == "Por tipo de membro":
                member_type = filter_option.get()
                return ({"active_only": True, "member_type": member_type},
                        "member_type", member_type, f"membros do tipo {member_type}")
            return ({"active_only": True}, "all_active", "", "todos os membros ativos")

        def do_send_bulk() -> None:
            subject = subject_entry.get().strip()
            body_text = body_entry.get("1.0", "end-1c").strip()
            if not subject or not body_text:
                self._show_error("Preencha o assunto e a mensagem.")
                return
            try:
                kwargs, audience_kind, audience_value, audience_desc = resolve_audience()
            except AppError as exc:
                self._show_error(str(exc))
                return

            schedule_at = schedule_entry.get().strip()
            if schedule_at:
                try:
                    msg_id = self.communication_service.schedule_email(
                        subject, body_text, schedule_at,
                        audience_kind=audience_kind, audience_value=audience_value,
                    )
                except Exception as exc:
                    self._show_error(f"Falha ao agendar: {exc}")
                    return
                load_pending()
                self._show_toast(f"Agendado (#{msg_id}) para {schedule_at}.", kind="success")
                return

            if not self._confirm_action(
                "Disparo em massa",
                f"Enviar este e-mail para {audience_desc}? O envio usa o SMTP configurado.",
            ):
                return

            def task() -> None:
                try:
                    summary = self.communication_service.bulk_email_members(
                        msg_service, subject, body_text, **kwargs
                    )
                    self.after(0, lambda s=summary: self._show_info(
                        "Disparo concluido.\n\n"
                        f"Enviados: {s['sent_count']}\n"
                        f"Falhas: {s['failed_count']}\n"
                        f"Sem e-mail (ignorados): {s['skipped_no_email']}"
                    ))
                except Exception as exc:
                    self.after(0, lambda error=exc: self._show_error(f"Falha no disparo: {error}"))

            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(parent, text="Enviar / Agendar", command=do_send_bulk).grid(
            row=10, column=0, padx=16, pady=(0, 8), sticky="w"
        )
        load_pending()

    def _build_whatsapp_tab(self, parent: ctk.CTkFrame, msg_service: MessageService) -> None:
        parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="Número do WhatsApp (com DDD):").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        phone_entry = ctk.CTkEntry(parent, width=300, placeholder_text="Ex: 11999999999")
        phone_entry.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(parent, text="Mensagem:").grid(row=2, column=0, padx=16, pady=(8, 4), sticky="w")
        body_entry = ctk.CTkTextbox(parent, height=200)
        body_entry.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="nsew")

        parent.grid_rowconfigure(3, weight=1)

        def do_open_whatsapp():
            phone = phone_entry.get().strip()
            body_text = body_entry.get("1.0", "end-1c").strip()
            if not phone or not body_text:
                self._show_error("Preencha o número e a mensagem.")
                return
            msg_service.open_whatsapp(phone, body_text)

        btn = ctk.CTkButton(parent, text="Abrir no WhatsApp", command=do_open_whatsapp)
        btn.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="w")

    def _build_smtp_config_tab(self, parent: ctk.CTkFrame, settings: dict) -> None:
        form = self._make_scrollable_panel(parent, width=400)
        form.pack(fill="both", expand=True)

        ctk.CTkLabel(form, text="Servidor SMTP").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        server_entry = ctk.CTkEntry(form, width=300)
        server_entry.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
        server_entry.insert(0, settings.get("smtp_server", ""))

        ctk.CTkLabel(form, text="Porta SMTP").grid(row=2, column=0, padx=16, pady=(8, 4), sticky="w")
        port_entry = ctk.CTkEntry(form, width=100)
        port_entry.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="w")
        port_entry.insert(0, settings.get("smtp_port", "587"))

        ctk.CTkLabel(form, text="Usuário (E-mail)").grid(row=4, column=0, padx=16, pady=(8, 4), sticky="w")
        user_entry = ctk.CTkEntry(form, width=300)
        user_entry.grid(row=5, column=0, padx=16, pady=(0, 12), sticky="w")
        user_entry.insert(0, settings.get("smtp_user", ""))

        ctk.CTkLabel(form, text="Senha").grid(row=6, column=0, padx=16, pady=(8, 4), sticky="w")
        pass_entry = ctk.CTkEntry(form, width=300, show="*")
        pass_entry.grid(row=7, column=0, padx=16, pady=(0, 16), sticky="w")
        pass_entry.insert(0, settings.get("smtp_password", ""))

        def save_smtp():
            self.require_permission("settings_write")
            self.db.save_app_settings({
                "smtp_server": server_entry.get().strip(),
                "smtp_port": port_entry.get().strip(),
                "smtp_user": user_entry.get().strip(),
                "smtp_password": pass_entry.get().strip()
            })
            self._show_toast("Configurações SMTP salvas com sucesso.", kind="success")

        btn = ctk.CTkButton(form, text="Salvar Configurações", command=save_smtp)
        btn.grid(row=8, column=0, padx=16, pady=(0, 16), sticky="w")
