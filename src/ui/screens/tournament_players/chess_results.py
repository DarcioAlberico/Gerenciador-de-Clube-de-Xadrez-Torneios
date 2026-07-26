"""Ponte com o Chess-Results.com — B-6.

Duas mãos: **importar** as inscrições que chegaram por lá e **preparar** o
pacote TRF16 para publicar o torneio. O envio em si continua manual — o site
não tem API pública —, e é por isso que o diálogo entrega o passo a passo junto
com o arquivo: o operador vai alternar entre a janela e o navegador.

O link publicado fica guardado no torneio, então "abrir torneio publicado" é um
clique nas próximas vezes em vez de uma busca no histórico do navegador.
"""
from __future__ import annotations

import webbrowser
from typing import Any, Callable

import customtkinter as ctk

from src.services.chess_results import normalize_results_url

from ...i18n import t
from ...support import THEME_TEXT_SUB, filedialog, font_section
from . import file_types
from .actions import ScreenActions, guarded
from .dialogs import actions_row, close_button, modal


class ChessResultsActions(ScreenActions):
    def __init__(self, host: Any, on_changed: Callable[[], None] | None = None) -> None:
        super().__init__(host, on_changed)
        self.service = host.chess_results_service

    @guarded
    def import_entries(self) -> None:
        tournament_id = self.tournament_id
        caminho = filedialog.askopenfilename(
            title=t("players.chess_results.import_title"),
            filetypes=file_types.csv_only(),
        )
        if not caminho:
            return

        def concluir(resultado: dict[str, Any]) -> None:
            self.changed()
            self.host._show_info(
                self.with_errors(
                    t("players.chess_results.imported", quantidade=resultado["imported"]),
                    resultado["errors"],
                    label=t("players.import.warnings"),
                )
            )

        self.background(
            lambda: self.service.import_entries(tournament_id, caminho),
            concluir,
            t("players.chess_results.import_working"),
        )

    @guarded
    def prepare_upload(self) -> None:
        tournament_id = self.tournament_id
        pasta = filedialog.askdirectory(
            title=t("players.chess_results.folder_title"),
            initialdir=str(self.host._default_export_dir()),
        )
        if not pasta:
            return
        self.background(
            lambda: self.service.prepare_upload(tournament_id, pasta),
            self.show_package,
            t("players.chess_results.working"),
        )

    def show_package(self, result: dict[str, Any]) -> None:
        """Arquivo gerado, passo a passo do envio e o campo do link publicado."""
        tournament_id = self.tournament_id
        dialog = modal(self.host, t("players.chess_results.title"), "700x540")

        ctk.CTkLabel(
            dialog, text=t("players.chess_results.heading"), font=font_section()
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            dialog,
            text=t("players.chess_results.trf", caminho=result["trf_path"]),
            justify="left",
            anchor="w",
            wraplength=640,
            text_color=THEME_TEXT_SUB,
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        passos = ctk.CTkTextbox(dialog, height=180, wrap="word")
        passos.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
        passos.insert("1.0", "\n".join(result["steps"]))
        if result.get("warnings"):
            passos.insert(
                "end",
                "\n\n"
                + t("players.chess_results.trf_warnings")
                + "\n"
                + "\n".join(f"- {aviso}" for aviso in result["warnings"]),
            )
        passos.configure(state="disabled")

        linha = ctk.CTkFrame(dialog, fg_color="transparent")
        linha.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        linha.grid_columnconfigure(0, weight=1)
        campo_link = ctk.CTkEntry(
            linha, placeholder_text=t("players.chess_results.link_hint")
        )
        campo_link.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        if result.get("published_url"):
            campo_link.insert(0, result["published_url"])

        def salvar_link() -> None:
            try:
                salvo = self.service.set_published_url(tournament_id, campo_link.get())
            except Exception as exc:  # noqa: BLE001 — link torto é o caso comum
                self.host._show_error(exc)
                return
            self.host._show_toast(
                t("players.chess_results.link_saved")
                if salvo
                else t("players.chess_results.link_removed"),
                kind="success",
            )

        ctk.CTkButton(
            linha, text=t("players.chess_results.save_link"), command=salvar_link, width=110
        ).grid(row=0, column=1)

        def abrir_publicado() -> None:
            normalizado = normalize_results_url(campo_link.get())
            if normalizado:
                webbrowser.open(normalizado)
            else:
                self.host._show_warning(t("players.chess_results.no_valid_link"))

        faixa = actions_row(dialog, 4, pady=(4, 16))
        ctk.CTkButton(
            faixa,
            text=t("players.chess_results.open_register"),
            command=lambda: webbrowser.open(result["register_url"]),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            faixa, text=t("players.chess_results.open_published"), command=abrir_publicado
        ).pack(side="left", padx=(0, 8))
        close_button(faixa, t("dialog.close"), dialog)
