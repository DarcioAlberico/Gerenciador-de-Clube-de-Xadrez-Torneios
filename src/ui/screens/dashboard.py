from __future__ import annotations

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Any

from ..charts import FigureCache, finance_chart_key, members_chart_key
from ..components import EmptyState
from ..support import AppError
from ..theme import (
    SIZE_BODY,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    font_section,
    on_theme_change,
)
from .dashboard_figures import build_finance_figure, build_members_figure, current_palette

# Cache das figuras (P2-14). Vive no módulo, e não na instância, porque a tela é
# um mixin recriado a cada navegação — guardá-lo na instância seria guardá-lo em
# quem morre justamente na hora em que o cache serviria.
DASHBOARD_FIGURES = FigureCache()

# Trocar de tema não invalida chave nenhuma (a paleta faz parte dela), mas deixa
# no cache figuras de um tema que ninguém mais vai ver: solta a memória.
on_theme_change(DASHBOARD_FIGURES.clear)


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
    def _embed_chart(fig: Any, parent: ctk.CTkFrame) -> None:
        """Embute a figura num canvas novo — a figura pode vir do cache.

        Cada visita destrói o conteúdo antigo, então o canvas é sempre novo; a
        figura é que sobrevive. Reaproveitá-la é seguro porque o
        ``FigureCanvasTkAgg`` assume a figura ao nascer (``fig.canvas`` passa a
        apontar para o canvas atual). Por isso a figura **não** é fechada aqui:
        fechá-la esvaziaria o cache no primeiro uso.
        """
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _draw_members_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        palette = current_palette()
        figure = DASHBOARD_FIGURES.get_or_build(
            members_chart_key(dashboard, palette),
            lambda: build_members_figure(dashboard, palette),
        )
        self._embed_chart(figure, parent)

    def _draw_finance_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        palette = current_palette()
        figure = DASHBOARD_FIGURES.get_or_build(
            finance_chart_key(dashboard, palette),
            lambda: build_finance_figure(dashboard, palette),
        )
        self._embed_chart(figure, parent)

    def _draw_announcements(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        ctk.CTkLabel(
            parent, text="Mural de Avisos", font=font_section(), text_color=THEME_TEXT_MAIN
        ).pack(pady=(10, 5), padx=10, anchor="w")
        announcements = dashboard.get("active_announcements", [])
        if not announcements:
            EmptyState(
                parent,
                title="Sem avisos ativos",
                description="Os comunicados do clube aparecerao aqui.",
                cta_text="Ir para Comunicacao",
                cta_command=self.show_communication,
            ).pack(fill="both", expand=True, padx=10, pady=10)
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
            EmptyState(
                parent,
                title="Nenhum evento agendado",
                description="Agende eventos no calendario para ve-los aqui.",
                cta_text="Ir para Calendario",
                cta_command=self.show_calendar,
            ).pack(fill="both", expand=True, padx=10, pady=10)
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
