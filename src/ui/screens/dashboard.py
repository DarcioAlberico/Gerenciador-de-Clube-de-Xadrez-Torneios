from __future__ import annotations

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Any

from ..support import AppError


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

    def _draw_members_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        summary = dashboard.get("summary", {})
        active = summary.get("active_members", 0)
        inactive = summary.get("total_members", 0) - active
        defaulters = dashboard.get("defaulters_count", 0)
        
        fig, ax = plt.subplots(figsize=(5, 3), facecolor="#ffffff")
        if summary.get("total_members", 0) > 0:
            ax.pie([active, inactive], labels=["Ativos", "Inativos"], autopct='%1.1f%%', colors=["#3b82f6", "#94a3b8"])
        else:
            ax.text(0.5, 0.5, 'Sem dados', horizontalalignment='center', verticalalignment='center')
        
        title = "Status dos Membros"
        if defaulters > 0:
            title += f"\n(Atenção: {defaulters} inadimplentes)"
        ax.set_title(title)
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _draw_finance_chart(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        finance = dashboard.get("finance_summary", {})
        
        fig, ax = plt.subplots(figsize=(5, 3), facecolor="#ffffff")
        labels = ["Recebido", "Pendente", "Atrasado"]
        values = [finance.get("paid_amount", 0), finance.get("pending_amount", 0), finance.get("late_amount", 0)]
        
        ax.bar(labels, values, color=["#10b981", "#f59e0b", "#ef4444"])
        ax.set_title("Status Financeiro")
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _draw_announcements(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        ctk.CTkLabel(parent, text="Mural de Avisos", font=("Inter", 16, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        announcements = dashboard.get("active_announcements", [])
        if not announcements:
            ctk.CTkLabel(parent, text="Nenhum aviso ativo no momento.", text_color="gray").pack(pady=10, padx=10, anchor="w")
            return
            
        for a in announcements[:3]:
            cat = f"[{a.get('category', 'Geral').upper()}]"
            ctk.CTkLabel(parent, text=f"{cat} {a.get('title', '')}", font=("Inter", 12, "bold")).pack(padx=10, anchor="w")
            ctk.CTkLabel(parent, text=a.get('content', ''), font=("Inter", 12), justify="left", wraplength=400).pack(padx=10, pady=(0, 10), anchor="w")

    def _draw_upcoming_events(self, parent: ctk.CTkFrame, dashboard: dict[str, Any]) -> None:
        ctk.CTkLabel(parent, text="Próximos Eventos", font=("Inter", 16, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        events = dashboard.get("upcoming_events", [])
        if not events:
            ctk.CTkLabel(parent, text="Nenhum evento agendado.", text_color="gray").pack(pady=10, padx=10, anchor="w")
            return
            
        for e in events:
            date_str = e.get("date_start", "")
            title = e.get("title", "")
            ctk.CTkLabel(parent, text=f"­ƒôà {date_str} - {title}", font=("Inter", 12)).pack(padx=10, pady=2, anchor="w")
