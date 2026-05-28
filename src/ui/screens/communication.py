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
        tab_whatsapp = tabview.add("WhatsApp")
        tab_config = tabview.add("Config. SMTP")

        self._build_email_tab(tab_email, msg_service)
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
