from __future__ import annotations

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Any

from ..support import (
    AppError,
    SIZE_BODY,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    font_section,
)


class DashboardPagesMixin:
    def show_visual_dashboard(self) -> None:
        self._clear_content()
        self._page_title(
            "Dashboard Visual",
            "Visao geral grafica do clube e finanças.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        try:
            dashboard = self.dashboard_service.overview()
        except Exception as e:
            self._show_error(AppError(f"Erro ao carregar dados do dashboard: {e}"))
            return

        chart1_frame = self._make_panel(body)
        chart1_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))

        chart2_frame = self._make_panel(body)
        chart2_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))

        info1_frame = self._make_panel(body)
        info1_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        info2_frame = self._make_panel(body)
        info2_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 0))

        self._draw_members_chart(chart1_frame, dashboard)
        self._draw_finance_chart(chart2_frame, dashboard)
        self._draw_announcements(info1_frame, dashboard)
        self._draw_upcoming_events(info2_frame, dashboard)

    @staticmethod
    def _chart_palette() -> tuple[str, str, str]:
        """(fundo, texto, texto-secundario) do tema atual, para os graficos.

        Le a face clara/escura ativa para que os graficos matplotlib acompanhem
        o tema em vez de ficarem sempre com fundo branco.
        """
        face = 1 if ctk.get_appearance_mode() == "Dark" else 0
        return THEME_PANEL_BG[face], THEME_TEXT_MAIN[face], THEME_TEXT_SUB[face]

    @staticmethod
    def _embed_chart(fig: Any, parent: ctk.CTkFrame) -> None:
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        plt.close(fig)

    def _draw_members_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        panel, text, sub = self._chart_palette()
        summary = dashboard.get("summary", {})
        active = summary.get("active_members", 0)
        inactive = summary.get("total_members", 0) - active
        defaulters = dashboard.get("defaulters_count", 0)

        fig, ax = plt.subplots(figsize=(5, 3), facecolor=panel)
        ax.set_facecolor(panel)
        if summary.get("total_members", 0) > 0:
            ax.pie(
                [active, inactive],
                labels=["Ativos", "Inativos"],
                autopct="%1.1f%%",
                colors=["#3B82F6", "#94A3B8"],
                textprops={"color": text},
            )
        else:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", color=sub)

        title = "Status dos Membros"
        if defaulters > 0:
            title += f"\n(Atenção: {defaulters} inadimplentes)"
        ax.set_title(title, color=text)

        self._embed_chart(fig, parent)

    def _draw_finance_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        panel, text, sub = self._chart_palette()
        finance = dashboard.get("finance_summary", {})

        fig, ax = plt.subplots(figsize=(5, 3), facecolor=panel)
        ax.set_facecolor(panel)
        labels = ["Recebido", "Pendente", "Atrasado"]
        values = [
            finance.get("paid_amount", 0),
            finance.get("pending_amount", 0),
            finance.get("late_amount", 0),
        ]

        ax.bar(labels, values, color=["#10B981", "#F59E0B", "#EF4444"])
        ax.set_title("Status Financeiro", color=text)
        ax.tick_params(colors=sub)
        for spine in ax.spines.values():
            spine.set_color(sub)

        self._embed_chart(fig, parent)

    def _draw_announcements(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        ctk.CTkLabel(
            parent, text="Mural de Avisos", font=font_section(), text_color=THEME_TEXT_MAIN
        ).pack(pady=(10, 5), padx=10, anchor="w")
        announcements = dashboard.get("active_announcements", [])
        if not announcements:
            ctk.CTkLabel(
                parent, text="Nenhum aviso ativo no momento.", text_color=THEME_TEXT_SUB
            ).pack(pady=10, padx=10, anchor="w")
            return

        for a in announcements[:3]:
            cat = f"[{a.get('category', 'Geral').upper()}]"
            ctk.CTkLabel(
                parent,
                text=f"{cat} {a.get('title', '')}",
                font=ctk.CTkFont(size=SIZE_BODY, weight="bold"),
                text_color=THEME_TEXT_MAIN,
            ).pack(padx=10, anchor="w")
            ctk.CTkLabel(
                parent,
                text=a.get("content", ""),
                font=ctk.CTkFont(size=SIZE_BODY),
                justify="left",
                wraplength=400,
                text_color=THEME_TEXT_SUB,
            ).pack(padx=10, pady=(0, 10), anchor="w")

    def _draw_upcoming_events(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        ctk.CTkLabel(
            parent, text="Próximos Eventos", font=font_section(), text_color=THEME_TEXT_MAIN
        ).pack(pady=(10, 5), padx=10, anchor="w")
        events = dashboard.get("upcoming_events", [])
        if not events:
            ctk.CTkLabel(
                parent, text="Nenhum evento agendado.", text_color=THEME_TEXT_SUB
            ).pack(pady=10, padx=10, anchor="w")
            return

        for e in events:
            date_str = e.get("date_start", "")
            title = e.get("title", "")
            ctk.CTkLabel(
                parent,
                text=f"{date_str}  —  {title}",
                font=ctk.CTkFont(size=SIZE_BODY),
                text_color=THEME_TEXT_MAIN,
            ).pack(padx=10, pady=2, anchor="w")
