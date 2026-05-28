from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from pathlib import Path

from ..support import *

if TYPE_CHECKING:
    from src.services.report_engine import ReportEngine

logger = logging.getLogger(__name__)

class ReportPagesMixin:
    def show_reports(self) -> None:
        self._clear_content()
        self._page_title(
            "Relatórios & Estatísticas",
            "Gere o DRE Financeiro e outros relatórios gerenciais.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        
        main_panel = self._make_scrollable_panel(body)
        main_panel.grid(row=0, column=0, sticky="nsew")
        main_panel.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(main_panel, text="DRE Financeiro", font=font_section()).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        
        dre_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        dre_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")
        
        ctk.CTkLabel(dre_frame, text="Data Inicial:").grid(row=0, column=0, padx=(0, 8))
        start_date = self._make_date_entry(dre_frame, width=15)
        start_date.grid(row=0, column=1, padx=(0, 16))
        
        ctk.CTkLabel(dre_frame, text="Data Final:").grid(row=0, column=2, padx=(0, 8))
        end_date = self._make_date_entry(dre_frame, width=15)
        end_date.grid(row=0, column=3, padx=(0, 16))

        dre_results_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        dre_results_frame.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        dre_results_frame.grid_columnconfigure(0, weight=1)
        dre_results_frame.grid_columnconfigure(1, weight=1)
        dre_results_frame.grid_columnconfigure(2, weight=1)

        summary_labels: dict[str, ctk.CTkLabel] = {}
        for idx, (key, label) in enumerate([("total_income", "Receitas (+)"), ("total_expense", "Despesas (-)"), ("net_balance", "Resultado Líquido")]):
            card = ctk.CTkFrame(dre_results_frame, fg_color=THEME_APP_BG, corner_radius=8)
            card.grid(row=0, column=idx, padx=8, pady=4, sticky="ew")
            val_lbl = ctk.CTkLabel(card, text="R$ 0.00", font=font_kpi_value())
            val_lbl.pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(anchor="w", padx=12, pady=(0, 10))
            summary_labels[key] = val_lbl

        trees_frame = ctk.CTkFrame(dre_results_frame, fg_color="transparent")
        trees_frame.grid(row=1, column=0, columnspan=3, pady=(16, 0), sticky="ew")
        trees_frame.grid_columnconfigure(0, weight=1)
        trees_frame.grid_columnconfigure(1, weight=1)

        income_tree_holder = self._make_panel(trees_frame)
        income_tree_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        income_tree_holder.grid_columnconfigure(0, weight=1)
        income_tree_holder.grid_rowconfigure(0, weight=1)
        income_tree = self._make_tree(
            income_tree_holder,
            ["category", "amount"],
            {"category": "Receitas (Categorias)", "amount": "Valor"},
            {"category": 200, "amount": 100},
            height=6
        )

        expense_tree_holder = self._make_panel(trees_frame)
        expense_tree_holder.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        expense_tree_holder.grid_columnconfigure(0, weight=1)
        expense_tree_holder.grid_rowconfigure(0, weight=1)
        expense_tree = self._make_tree(
            expense_tree_holder,
            ["category", "amount"],
            {"category": "Despesas (Categorias)", "amount": "Valor"},
            {"category": 200, "amount": 100},
            height=6
        )

        def load_dre() -> None:
            try:
                data = self.report_engine.calculate_dre(start_date.get(), end_date.get())
                summary_labels["total_income"].configure(text=f"R$ {data['total_income']:,.2f}", text_color=THEME_INFO[0])
                summary_labels["total_expense"].configure(text=f"R$ {data['total_expense']:,.2f}", text_color=THEME_DANGER[0])
                net = data['net_balance']
                summary_labels["net_balance"].configure(
                    text=f"R$ {net:,.2f}",
                    text_color=THEME_INFO[0] if net >= 0 else THEME_DANGER[0]
                )
                
                income_tree.delete(*income_tree.get_children())
                for cat, amount in sorted(data["income_by_category"].items(), key=lambda x: -x[1]):
                    income_tree.insert("", "end", values=(cat, f"R$ {amount:,.2f}"))
                    
                expense_tree.delete(*expense_tree.get_children())
                for cat, amount in sorted(data["expense_by_category"].items(), key=lambda x: -x[1]):
                    expense_tree.insert("", "end", values=(cat, f"R$ {amount:,.2f}"))
            except Exception as exc:
                self._show_error(exc)

        def export_dre() -> None:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                title="Salvar DRE",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile="Relatorio_DRE.pdf"
            )
            if path:
                try:
                    self.report_engine.generate_dre_report(start_date.get(), end_date.get(), Path(path))
                    self._show_toast(f"DRE salvo em {Path(path).name}")
                    logger.info("DRE exportado.")
                except Exception as exc:
                    self._show_error(exc)

        btn_calc = ctk.CTkButton(dre_frame, text="Calcular", command=load_dre)
        btn_calc.grid(row=0, column=4, padx=(16, 8))

        btn_dre = ctk.CTkButton(dre_frame, text="Gerar PDF do DRE", command=export_dre, fg_color="transparent", border_width=1, text_color=THEME_TEXT_MAIN)
        btn_dre.grid(row=0, column=5, padx=(0, 0))
        self._disable_if_unauthorized(btn_dre, "finance_write")
        
        ctk.CTkLabel(main_panel, text="Estatísticas de Torneios (Em Breve)", font=font_section()).grid(row=3, column=0, padx=16, pady=(16, 8), sticky="w")
        ctk.CTkLabel(main_panel, text="Métricas de participação e desempenho em torneios.").grid(row=4, column=0, padx=16, pady=(0, 16), sticky="w")

        ctk.CTkLabel(main_panel, text="Crescimento de Membros (Em Breve)", font=font_section()).grid(row=5, column=0, padx=16, pady=(16, 8), sticky="w")
        ctk.CTkLabel(main_panel, text="Análise de novas associações e frequência.").grid(row=6, column=0, padx=16, pady=(0, 16), sticky="w")
