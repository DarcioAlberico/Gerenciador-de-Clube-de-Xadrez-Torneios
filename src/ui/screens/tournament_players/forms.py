"""Formulário de inscrição online (Google Forms) — B-6.

Três caminhos, na ordem em que o operador os encontra:

1. **Compartilhar** — já existe um formulário configurado; o app monta o link
   com o nome do torneio preenchido e o árbitro manda no grupo;
2. **Configurar** — cola-se uma vez o link "pré-preenchido" do Forms para o app
   descobrir qual campo é o do torneio;
3. **Gerar** — não há formulário nenhum: ou o app cria via API, ou entrega um
   script do Apps Script para colar em script.google.com.

O caminho 3 cai no 3-manual sempre que a API não está configurada **ou** falha —
e falhar aqui é rotina (credencial, rede, autorização revogada). Por isso a
alternativa manual não é tratamento de erro escondido: é oferta explícita, com
o motivo à mostra.
"""
from __future__ import annotations

import webbrowser
from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...support import THEME_TEXT_MAIN, THEME_TEXT_SUB, filedialog, font_section
from . import file_types
from .actions import ScreenActions, guarded
from .dialogs import actions_row, close_button, modal

SCRIPT_FILENAME = "formulario_inscricao.gs"


class RegistrationFormActions(ScreenActions):
    """Ações do formulário de inscrição. Sem estado próprio: tudo vem do serviço."""

    def __init__(self, host: Any) -> None:
        super().__init__(host)
        self.export_service = host.export_service
        self.google_forms_service = host.google_forms_service

    # ---- Compartilhar ----------------------------------------------------- #

    @guarded
    def share(self) -> None:
        """Link pronto para os jogadores; sem configuração, oferece configurar."""
        from src.services.constants import AppError

        tournament_id = self.tournament_id
        try:
            url = self.export_service.registration_prefill_url(tournament_id)
        except AppError as exc:
            if self.host._confirm_action(
                t("players.form.share.title"), t("players.form.share.not_configured", motivo=exc)
            ):
                self.configure()
            return
        self._show_link_dialog(url)

    def _show_link_dialog(self, url: str) -> None:
        dialog = modal(self.host, t("players.form.link.title"), "640x260")

        ctk.CTkLabel(
            dialog,
            text=t("players.form.link.help"),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
            wraplength=600,
            justify="left",
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self._readonly_box(dialog, 1, url, height=80)

        faixa = actions_row(dialog, 2)
        ctk.CTkButton(faixa, text=t("players.form.copy_link"), command=lambda: self._copy(url)).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(
            faixa, text=t("players.form.open_browser"), command=lambda: webbrowser.open(url)
        ).pack(side="left", padx=(0, 8))
        close_button(faixa, t("dialog.close"), dialog)

    # ---- Configurar ------------------------------------------------------- #

    def configure(self) -> None:
        """Descobre, a partir de um link pré-preenchido, qual campo é o torneio."""
        dialog = modal(self.host, t("players.form.config.title"), "700x440")

        ctk.CTkLabel(
            dialog,
            text=t("players.form.config.steps"),
            justify="left",
            wraplength=660,
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

        atual = self.export_service.registration_form_config()
        estado = (
            t("players.form.config.current", url=atual["base_url"])
            if atual["base_url"]
            else t("players.form.config.none")
        )
        ctk.CTkLabel(
            dialog, text=estado, text_color=THEME_TEXT_SUB, wraplength=660, justify="left"
        ).grid(row=1, column=0, padx=16, pady=(0, 6), sticky="w")

        caixa = ctk.CTkTextbox(dialog, height=90, wrap="word")
        caixa.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        escolhido = ctk.StringVar(value="")
        menu = ctk.CTkOptionMenu(
            dialog, values=[t("players.form.config.analyze_first")], variable=escolhido, width=620
        )
        menu.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        rotulo_para_campo: dict[str, str] = {}

        def analisar() -> None:
            try:
                lido = self.export_service.parse_prefill_link(caixa.get("1.0", "end").strip())
            except Exception as exc:  # noqa: BLE001 — link colado errado é o caso comum
                self.host._show_error(exc)
                return
            rotulos = []
            rotulo_para_campo.clear()
            for identificador, valor in lido["entries"]:
                rotulo = f"{identificador} = {valor}" if valor else identificador
                rotulos.append(rotulo)
                rotulo_para_campo[rotulo] = identificador
            menu.configure(values=rotulos)
            escolhido.set(rotulos[0])

        def salvar() -> None:
            from src.services.constants import AppError

            identificador = rotulo_para_campo.get(escolhido.get(), "")
            if not identificador:
                self.host._show_error(AppError(t("players.form.config.pick_field")))
                return
            try:
                self.export_service.save_registration_form_config(
                    caixa.get("1.0", "end").strip(), identificador
                )
            except Exception as exc:  # noqa: BLE001
                self.host._show_error(exc)
                return
            dialog.close()
            self.host._show_info(t("players.form.config.saved"))

        faixa = actions_row(dialog, 4)
        ctk.CTkButton(faixa, text=t("players.form.config.analyze"), command=analisar).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(faixa, text=t("players.form.config.save"), command=salvar).pack(
            side="left", padx=(0, 8)
        )
        close_button(faixa, t("dialog.cancel"), dialog)

    # ---- Gerar ------------------------------------------------------------ #

    @guarded
    def generate(self) -> None:
        """Cria no Google Forms; sem API disponível, oferece o script manual."""
        tournament_id = self.tournament_id
        if not self.google_forms_service.is_configured():
            if self.host._confirm_action(
                t("players.form.create.title"),
                t(
                    "players.form.create.unavailable",
                    motivo=self.google_forms_service.unavailable_reason(),
                ),
            ):
                self.generate_script(tournament_id)
            return

        titulo = self._form_title(tournament_id)

        def trabalho() -> dict[str, Any]:
            try:
                return {"mode": "live", **self.google_forms_service.create_registration_form(titulo)}
            except Exception as exc:  # noqa: BLE001 — rede/credencial/autorizacao
                # Falha aqui não é excepcional: vira a oferta do caminho manual,
                # com o motivo à mostra em vez de um "erro inesperado".
                return {"mode": "error", "reason": str(exc)}

        def concluir(resultado: dict[str, Any]) -> None:
            if resultado.get("mode") == "live":
                self._show_form_created_dialog(resultado)
                return
            if self.host._confirm_action(
                t("players.form.create.title"),
                t("players.form.create.failed", motivo=resultado.get("reason", "")),
            ):
                self.generate_script(tournament_id)

        self.background(trabalho, concluir, t("players.form.create.working"))

    def _form_title(self, tournament_id: int) -> str:
        torneio = self.host.db.get_tournament(tournament_id)
        if torneio and torneio.get("name"):
            return t("players.form.title_named", torneio=torneio["name"])
        return t("players.form.title_generic")

    def generate_script(self, tournament_id: int) -> None:
        """Gera o `.gs` para colar em script.google.com."""
        caminho = filedialog.asksaveasfilename(
            title=t("players.form.script.title"),
            initialdir=str(self.host._default_export_dir()),
            initialfile=SCRIPT_FILENAME,
            defaultextension=".gs",
            filetypes=file_types.apps_script(),
        )
        if not caminho:
            return

        def concluir(resultado: dict[str, Any]) -> None:
            self.host._show_info(
                t(
                    "players.form.script.done",
                    script=resultado["script_path"],
                    definicao=resultado["definition_path"],
                )
            )

        self.background(
            lambda: self.export_service.export_registration_form(caminho, tournament_id),
            concluir,
            t("players.form.script.working"),
        )

    def _show_form_created_dialog(self, result: dict[str, str]) -> None:
        responder = result.get("responder_url", "")
        edicao = result.get("edit_url", "")
        dialog = modal(self.host, t("players.form.created.title"), "640x300")

        ctk.CTkLabel(
            dialog,
            text=t("players.form.created.help"),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
            wraplength=600,
            justify="left",
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self._readonly_box(
            dialog,
            1,
            t("players.form.created.links", jogadores=responder, edicao=edicao),
            height=70,
        )

        ctk.CTkLabel(
            dialog,
            text=t("players.form.created.next"),
            text_color=THEME_TEXT_SUB,
            wraplength=600,
            justify="left",
        ).grid(row=2, column=0, padx=16, pady=(0, 8), sticky="w")

        faixa = actions_row(dialog, 3)
        ctk.CTkButton(
            faixa, text=t("players.form.copy_link"), command=lambda: self._copy(responder)
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            faixa,
            text=t("players.form.open_form"),
            command=lambda: responder and webbrowser.open(responder),
        ).pack(side="left", padx=(0, 8))
        close_button(faixa, t("dialog.close"), dialog)

    # ---- Utilitários ------------------------------------------------------ #

    @staticmethod
    def _readonly_box(dialog: ctk.CTkToplevel, row: int, text: str, height: int) -> ctk.CTkTextbox:
        """Caixa de texto só para leitura — o operador copia, não edita."""
        caixa = ctk.CTkTextbox(dialog, height=height, wrap="word")
        caixa.grid(row=row, column=0, padx=16, pady=(0, 8), sticky="ew")
        caixa.insert("1.0", text)
        caixa.configure(state="disabled")
        return caixa

    def _copy(self, text: str) -> None:
        self.host.clipboard_clear()
        self.host.clipboard_append(text)
