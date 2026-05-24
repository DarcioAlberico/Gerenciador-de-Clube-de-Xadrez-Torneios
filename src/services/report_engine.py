from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.database import Database
from src.services.constants import AppError

if TYPE_CHECKING:
    from src.services.finance_service import FinanceService
    from src.services.member_service import MemberService
    from src.services.tournament_service import TournamentService

logger = logging.getLogger(__name__)

class ReportEngine:
    """Motor de geração de relatórios e estatísticas da Fase 3."""
    
    def __init__(
        self, 
        db: Database, 
        finance_service: FinanceService,
        member_service: MemberService | None = None,
        tournament_service: TournamentService | None = None
    ) -> None:
        self.db = db
        self.finance_service = finance_service
        self.member_service = member_service
        self.tournament_service = tournament_service

    def calculate_dre(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Calcula os dados do Demonstrativo de Resultado do Exercício (DRE)."""
        payments = self.finance_service.payments_report(start_date=start_date, end_date=end_date)
        transactions = self.finance_service.list_transactions(start_date=start_date, end_date=end_date)
        
        income_by_cat: dict[str, float] = {}
        expense_by_cat: dict[str, float] = {}
        
        # Mensalidades pagas
        paid_mensalidades = sum(float(p.get("amount") or 0.0) for p in payments if p.get("effective_status") == "paid")
        if paid_mensalidades > 0:
            income_by_cat["Mensalidades (Pagamentos dos Sócios)"] = paid_mensalidades
            
        # Transações de Caixa
        for tx in transactions:
            cat = tx.get("category", "Geral").strip() or "Geral"
            amount = float(tx.get("amount") or 0.0)
            if tx.get("type") == "income":
                income_by_cat[cat] = income_by_cat.get(cat, 0.0) + amount
            elif tx.get("type") == "expense":
                expense_by_cat[cat] = expense_by_cat.get(cat, 0.0) + amount
                
        total_income = sum(income_by_cat.values())
        total_expense = sum(expense_by_cat.values())
        net_balance = total_income - total_expense
        
        return {
            "income_by_category": income_by_cat,
            "expense_by_category": expense_by_cat,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": net_balance
        }

    def generate_dre_report(self, start_date: str, end_date: str, output_path: Path) -> None:
        """Gera o Demonstrativo de Resultado do Exercício (DRE) em PDF."""
        dre_data = self.calculate_dre(start_date, end_date)
        income_by_cat = dre_data["income_by_category"]
        expense_by_cat = dre_data["expense_by_category"]
        total_income = dre_data["total_income"]
        total_expense = dre_data["total_expense"]
        net_balance = dre_data["net_balance"]
        
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")
                
            c = canvas.Canvas(str(output_path), pagesize=A4)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 800, "DEMONSTRATIVO DO RESULTADO DO EXERCÍCIO (DRE)")
            c.setFont("Helvetica", 12)
            c.drawString(50, 780, f"Período: {start_date or 'Início'} a {end_date or 'Hoje'}")
            
            y = 740
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "1. RECEITAS (+)")
            y -= 25
            c.setFont("Helvetica", 12)
            for cat, amount in sorted(income_by_cat.items(), key=lambda x: -x[1]):
                c.drawString(70, y, f"- {cat}")
                c.drawRightString(500, y, f"R$ {amount:,.2f}")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = 800
                    
            c.setFont("Helvetica-Bold", 12)
            c.drawString(70, y, "TOTAL DE RECEITAS")
            c.drawRightString(500, y, f"R$ {total_income:,.2f}")
            y -= 40
            
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "2. DESPESAS (-)")
            y -= 25
            c.setFont("Helvetica", 12)
            for cat, amount in sorted(expense_by_cat.items(), key=lambda x: -x[1]):
                c.drawString(70, y, f"- {cat}")
                c.drawRightString(500, y, f"R$ {amount:,.2f}")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = 800
                    
            c.setFont("Helvetica-Bold", 12)
            c.drawString(70, y, "TOTAL DE DESPESAS")
            c.drawRightString(500, y, f"R$ {total_expense:,.2f}")
            y -= 40
            
            c.line(50, y, 500, y)
            y -= 25
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "RESULTADO LÍQUIDO")
            c.drawRightString(500, y, f"R$ {net_balance:,.2f}")
            
            c.save()
            logger.info("DRE gerado: %s", output_path)
        except ImportError as exc:
            raise AppError("Instale reportlab para gerar DRE (pip install reportlab).") from exc
        except Exception as exc:
            logger.exception("Falha ao gerar DRE")
            raise AppError("Ocorreu um erro ao gerar o DRE em PDF.") from exc
