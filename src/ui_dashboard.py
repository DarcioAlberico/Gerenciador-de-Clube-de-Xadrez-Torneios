from __future__ import annotations

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Any

from .ui_support import AppError


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
        
        try:
            dashboard = self.dashboard_service.overview()
        except Exception as e:
            self._show_error(AppError(f"Erro ao carregar dados do dashboard: {e}"))
            return

        chart1_frame = self._make_panel(body)
        chart1_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        chart2_frame = self._make_panel(body)
        chart2_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._draw_members_chart(chart1_frame, dashboard)
        self._draw_finance_chart(chart2_frame, dashboard)

    def _draw_members_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        summary = dashboard["summary"]
        active = summary["active_members"]
        inactive = summary["total_members"] - active
        
        fig, ax = plt.subplots(figsize=(5, 4), facecolor="#ffffff")
        if summary["total_members"] > 0:
            ax.pie([active, inactive], labels=["Ativos", "Inativos"], autopct='%1.1f%%', colors=["#3b82f6", "#94a3b8"])
        else:
            ax.text(0.5, 0.5, 'Sem dados', horizontalalignment='center', verticalalignment='center')
        ax.set_title("Status dos Membros")
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _draw_finance_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        finance = dashboard["finance_summary"]
        
        fig, ax = plt.subplots(figsize=(5, 4), facecolor="#ffffff")
        labels = ["Recebido", "Pendente", "Atrasado"]
        values = [finance["paid_amount"], finance["pending_amount"], finance["late_amount"]]
        
        ax.bar(labels, values, color=["#10b981", "#f59e0b", "#ef4444"])
        ax.set_title("Status Financeiro")
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
