from __future__ import annotations
import csv
import html
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.constants import *

if TYPE_CHECKING:
    from src.services.club_service import ClubService
    from src.services.member_service import MemberService, GuardianService
    from src.services.tournament_service import TournamentService, RefereeService, TeamService
    from src.services.pairing_service import PairingService
    from src.services.finance_service import FinanceService
    from src.services.event_service import EventService, CalendarService
    from src.services.education_service import TrainingService, ExerciseService, LibraryService, LearningLevelService
    from src.services.inventory_service import InventoryService
    from src.services.security_service import SecurityService
    from src.services.export_service import ExportService, ImportService, CertificateService
    from src.services.rating_service import OfficialRatingService, InternalRatingService
    from src.services.dashboard_service import DashboardService, CommunicationService

logger = logging.getLogger(__name__)

class FinanceService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_plan(self, data: dict[str, Any], plan_id: int | None = None) -> int:
        payload = self._validated_plan_payload(data)
        if plan_id:
            if not self.db.get_membership_plan(plan_id):
                raise AppError("Plano nao encontrado.")
            self.db.update_membership_plan(plan_id, **payload)
            logger.info("Plano financeiro atualizado: %s", plan_id)
            return plan_id
        saved_id = self.db.create_membership_plan(**payload)
        logger.info("Plano financeiro criado: %s", saved_id)
        return saved_id

    def toggle_plan_active(self, plan_id: int) -> int:
        plan = self.db.get_membership_plan(plan_id)
        if not plan:
            raise AppError("Plano nao encontrado.")
        next_active = 0 if plan.get("active") else 1
        self.db.set_membership_plan_active(plan_id, next_active)
        logger.info("Plano financeiro %s alterado para active=%s", plan_id, next_active)
        return next_active

    def save_payment(self, data: dict[str, Any], payment_id: int | None = None) -> int:
        payload = self._validated_payment_payload(data)
        if payment_id:
            if not self.db.get_payment(payment_id):
                raise AppError("Pagamento nao encontrado.")
            self.db.update_payment(payment_id, **payload)
            logger.info("Pagamento atualizado: %s", payment_id)
            return payment_id
        saved_id = self.db.create_payment(**payload)
        logger.info("Pagamento criado: %s", saved_id)
        return saved_id

    def mark_payment_paid(
        self,
        payment_id: int,
        payment_date: str = "",
        method: str = "",
    ) -> None:
        payment = self.db.get_payment(payment_id)
        if not payment:
            raise AppError("Pagamento nao encontrado.")
        payload = dict(payment)
        payload["status"] = "paid"
        payload["payment_date"] = payment_date.strip() or date.today().isoformat()
        if method.strip():
            payload["method"] = method
        self.save_payment(payload, payment_id)

    def generate_recurring_payments(
        self,
        plan_id: int,
        reference_period: str,
        due_date: str,
        member_ids: list[int] | None = None,
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        plan = self.db.get_membership_plan(int(plan_id or 0))
        if not plan:
            raise AppError("Plano nao encontrado.")
        if not plan.get("active"):
            raise AppError("Selecione um plano ativo para gerar mensalidades.")

        reference = self._validated_reference_period(reference_period)
        due = due_date.strip()
        self._validate_optional_date(due, "Vencimento invalido.")
        if not due:
            raise AppError("Informe o vencimento das mensalidades.")

        members = self._members_for_recurring_payments(member_ids, club_id, class_id)
        if not members:
            raise AppError("Nao ha membros ativos para gerar mensalidades.")

        created_ids: list[int] = []
        skipped = 0
        amount = float(plan.get("amount") or 0.0)
        description = f"{plan['name']} - {reference}"
        for member in members:
            member_id = int(member["id"])
            if self._has_open_payment_for_reference(member_id, int(plan["id"]), reference):
                skipped += 1
                continue
            created_ids.append(
                self.save_payment(
                    {
                        "member_id": member_id,
                        "plan_id": int(plan["id"]),
                        "description": description,
                        "reference_period": reference,
                        "due_date": due,
                        "amount": amount,
                        "status": "pending",
                    }
                )
            )

        logger.info(
            "Mensalidades geradas para plano %s referencia %s: %s criadas, %s puladas",
            plan_id,
            reference,
            len(created_ids),
            skipped,
        )
        return {
            "created": len(created_ids),
            "skipped": skipped,
            "payment_ids": created_ids,
            "reference_period": reference,
            "due_date": due,
            "plan_name": str(plan.get("name") or ""),
        }

    def payments_report(
        self,
        start_date: str = "",
        end_date: str = "",
        member_id: int | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_optional_date(start_date, "Data inicial invalida.")
        self._validate_optional_date(end_date, "Data final invalida.")
        rows = self.db.list_payments(
            start_date=start_date.strip(),
            end_date=end_date.strip(),
            member_id=member_id,
            include_canceled=False,
        )
        return [self._with_effective_status(row) for row in rows]

    def finance_summary(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        payments = self.payments_report(start_date=start_date, end_date=end_date)
        transactions = self.list_transactions(start_date=start_date, end_date=end_date)
        
        summary = {
            "total_payments": len(payments),
            "paid": 0,
            "pending": 0,
            "late": 0,
            "exempt": 0,
            "paid_amount": 0.0,
            "pending_amount": 0.0,
            "late_amount": 0.0,
            "exempt_amount": 0.0,
            "total_transactions": len(transactions),
            "income_amount": 0.0,
            "expense_amount": 0.0,
            "net_balance": 0.0,
        }
        
        # 1. Process Member Payments
        for payment in payments:
            status = payment["effective_status"]
            amount = float(payment.get("amount") or 0.0)
            if status in {"paid", "pending", "late", "exempt"}:
                summary[status] += 1
                summary[f"{status}_amount"] += amount
                
        # 2. Process Financial Transactions (Fluxo de Caixa Livre)
        for tx in transactions:
            amount = float(tx.get("amount") or 0.0)
            if tx.get("type") == "income":
                summary["income_amount"] += amount
            elif tx.get("type") == "expense":
                summary["expense_amount"] += amount
                
        # 3. Calculate Consolidated Balance
        # Net = (Paid Mensalidades + Other Income) - Other Expenses
        summary["net_balance"] = round(
            summary["paid_amount"] + summary["income_amount"] - summary["expense_amount"], 2
        )
        summary["paid_amount"] = round(summary["paid_amount"], 2)
        summary["income_amount"] = round(summary["income_amount"], 2)
        summary["expense_amount"] = round(summary["expense_amount"], 2)
        
        return summary

    def member_financial_status(self, member_id: int) -> dict[str, Any]:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")
        payments = [
            self._with_effective_status(payment)
            for payment in self.db.list_payments(member_id=member_id, include_canceled=False)
        ]
        if not payments:
            return {"status": "none", "label": "Sem lancamentos", "open_amount": 0.0, "late_amount": 0.0}

        late_amount = sum(
            float(payment.get("amount") or 0.0)
            for payment in payments
            if payment["effective_status"] == "late"
        )
        pending_amount = sum(
            float(payment.get("amount") or 0.0)
            for payment in payments
            if payment["effective_status"] == "pending"
        )
        if late_amount:
            status = "late"
        elif pending_amount:
            status = "pending"
        elif payments and all(payment["effective_status"] == "exempt" for payment in payments):
            status = "exempt"
        else:
            status = "paid"
        return {
            "status": status,
            "label": PAYMENT_STATUSES.get(status, "Sem lancamentos"),
            "open_amount": round(pending_amount + late_amount, 2),
            "late_amount": round(late_amount, 2),
        }

    def list_transactions(self, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
        self._validate_optional_date(start_date, "Data inicial inválida.")
        self._validate_optional_date(end_date, "Data final inválida.")
        return self.db.list_financial_transactions(start_date=start_date.strip(), end_date=end_date.strip())

    def save_transaction(self, data: dict[str, Any], transaction_id: int | None = None) -> int:
        payload = {
            "type": data.get("type", "income"),
            "amount": self._parse_amount(data.get("amount", 0.0), "Valor invalido"),
            "transaction_date": data.get("transaction_date", date.today().isoformat()),
            "description": data.get("description", "").strip(),
            "category": data.get("category", "").strip(),
            "payment_method": data.get("payment_method", "").strip(),
            "notes": data.get("notes", "").strip()
        }
        if not payload["description"]:
            raise AppError("A descricao da transacao e obrigatoria.")

        if transaction_id:
            self.db.update_financial_transaction(transaction_id, **payload)
            logger.info("Transacao financeira atualizada: %s", transaction_id)
            return transaction_id
        saved_id = self.db.create_financial_transaction(**payload)
        logger.info("Transacao financeira criada: %s", saved_id)
        return saved_id

    def delete_transaction(self, transaction_id: int) -> None:
        self.db.delete_financial_transaction(transaction_id)
        logger.info("Transacao financeira removida: %s", transaction_id)

    def generate_receipt(self, payment_id: int, output_path: Path) -> None:
        payment = self.db.get_payment(payment_id)
        if not payment:
            raise AppError("Pagamento nao encontrado.")
        if payment.get("status") not in ("paid", "exempt"):
            raise AppError("Nao e possivel emitir recibo para pagamentos pendentes/atrasados.")
            
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A5
        except ImportError as exc:
            raise AppError("Instale reportlab para gerar recibos (pip install reportlab).") from exc

        try:
            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")
                
            c = canvas.Canvas(str(output_path), pagesize=A5)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 550, "RECIBO DE PAGAMENTO")
            
            c.setFont("Helvetica", 12)
            c.drawString(50, 500, f"Recibo: {payment['id']}")
            member_name = self.db.get_member(int(payment["member_id"])).get("name", "Membro")
            c.drawString(50, 480, f"Recebemos de: {member_name}")
            c.drawString(50, 460, f"A quantia de: R$ {payment.get('amount', 0):.2f}")
            c.drawString(50, 440, f"Referente a: {payment.get('description', '')} / Ref: {payment.get('reference_period', '')}")
            c.drawString(50, 420, f"Plano: {payment.get('plan_name') or 'N/A'}")
            c.drawString(50, 400, f"Data do Pagamento: {payment.get('payment_date', '')}")
            c.drawString(50, 380, f"Metodo: {payment.get('method', '')}")
            
            c.line(50, 350, 350, 350)
            c.drawString(50, 330, "Albericus - Gerenciador de Clube de Xadrez")
            
            c.save()
            logger.info("Recibo gerado: %s", output_path)
        except Exception as exc:
            logger.exception("Falha ao gerar recibo")
            raise AppError("Ocorreu um erro ao gerar o recibo em PDF.") from exc

    # generate_dre_report movido para report_engine.py
    def save_sponsor(self, data: dict[str, Any], sponsor_id: int | None = None) -> int:
        payload = {
            "name": str(data.get("name", "")).strip(),
            "sponsor_type": str(data.get("sponsor_type", "company")).strip(),
            "contribution_amount": self._parse_amount(data.get("contribution_amount", 0.0), "Valor do patrocínio inválido"),
            "frequency": str(data.get("frequency", "monthly")).strip(),
            "benefits_notes": str(data.get("benefits_notes", "")).strip(),
        }
        if not payload["name"]:
            raise AppError("O nome do patrocinador é obrigatório.")
            
        if sponsor_id:
            self.db.update_sponsor(sponsor_id, **payload)
            logger.info("Patrocinador atualizado: %s", sponsor_id)
            return sponsor_id
        saved_id = self.db.create_sponsor(**payload)
        logger.info("Patrocinador criado: %s", saved_id)
        return saved_id

    def list_sponsors(self) -> list[dict[str, Any]]:
        return self.db.list_sponsors()

    def delete_sponsor(self, sponsor_id: int) -> None:
        self.db.delete_sponsor(sponsor_id)
        logger.info("Patrocinador removido: %s", sponsor_id)

    def _members_for_recurring_payments(
        self,
        member_ids: list[int] | None,
        club_id: int | None,
        class_id: int | None,
    ) -> list[dict[str, Any]]:
        if member_ids is not None:
            members = []
            for member_id in member_ids:
                member = self.db.get_member(int(member_id))
                if not member:
                    raise AppError("Membro selecionado para mensalidade nao encontrado.")
                members.append(member)
        else:
            members = self.db.list_members(active_only=True, club_id=club_id, class_id=class_id)
        billable_types = {"socio", "aluno"}
        return [
            member
            for member in members
            if str(member.get("status") or "") == "active"
            and str(member.get("member_type") or "") in billable_types
        ]

    def _has_open_payment_for_reference(self, member_id: int, plan_id: int, reference_period: str) -> bool:
        return any(
            int(payment.get("plan_id") or 0) == plan_id
            and str(payment.get("reference_period") or "").strip() == reference_period
            for payment in self.db.list_payments(member_id=member_id, include_canceled=False)
        )

    @staticmethod
    def _validated_reference_period(value: str) -> str:
        reference = value.strip()
        parts = reference.split("-")
        if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
            raise AppError("Informe a referencia no formato AAAA-MM.")
        try:
            year = int(parts[0])
            month = int(parts[1])
            date(year, month, 1)
        except ValueError as exc:
            raise AppError("Referencia financeira invalida.") from exc
        return reference

    def _validated_plan_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do plano.")
        billing_cycle = str(data.get("billing_cycle", "monthly")).strip() or "monthly"
        if billing_cycle not in BILLING_CYCLES:
            raise AppError("Ciclo de cobranca invalido.")
        amount = self._parse_amount(data.get("amount"), "Valor do plano invalido.")
        if amount < 0:
            raise AppError("Valor do plano nao pode ser negativo.")
        return {
            "name": name,
            "amount": amount,
            "billing_cycle": billing_cycle,
            "active": 1 if data.get("active", 1) else 0,
            "notes": str(data.get("notes", "")),
        }

    def _validated_payment_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            member_id = int(data.get("member_id") or 0)
        except ValueError as exc:
            raise AppError("Membro do pagamento invalido.") from exc
        if not self.db.get_member(member_id):
            raise AppError("Membro do pagamento nao encontrado.")

        try:
            plan_id = int(data.get("plan_id") or 0)
        except ValueError as exc:
            raise AppError("Plano do pagamento invalido.") from exc
        plan = self.db.get_membership_plan(plan_id) if plan_id else None
        if plan_id and not plan:
            raise AppError("Plano do pagamento nao encontrado.")

        status = str(data.get("status", "pending")).strip() or "pending"
        if status not in PAYMENT_STATUSES:
            raise AppError("Status financeiro invalido.")

        due_date = str(data.get("due_date", "")).strip()
        payment_date = str(data.get("payment_date", "")).strip()
        self._validate_optional_date(due_date, "Vencimento invalido.")
        self._validate_optional_date(payment_date, "Data de pagamento invalida.")

        amount_value = data.get("amount")
        amount = self._parse_amount(amount_value, "Valor do pagamento invalido.")
        if amount <= 0 and plan:
            amount = float(plan.get("amount") or 0.0)
        if amount < 0:
            raise AppError("Valor do pagamento nao pode ser negativo.")

        description = str(data.get("description", "")).strip()
        if not description and plan:
            description = str(plan.get("name") or "")
        if not description:
            description = "Lancamento financeiro"

        if status == "paid" and not payment_date:
            payment_date = date.today().isoformat()

        return {
            "member_id": member_id,
            "plan_id": plan_id or None,
            "description": description,
            "reference_period": str(data.get("reference_period", "")),
            "due_date": due_date,
            "payment_date": payment_date,
            "amount": amount,
            "status": status,
            "method": str(data.get("method", "")),
            "notes": str(data.get("notes", "")),
        }

    @staticmethod
    def _parse_amount(value: Any, message: str) -> float:
        try:
            return round(float(str(value or "0").replace(",", ".")), 2)
        except ValueError as exc:
            raise AppError(message) from exc

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        try:
            date.fromisoformat(cleaned)
        except ValueError as exc:
            raise AppError(message) from exc

    @classmethod
    def _with_effective_status(cls, payment: dict[str, Any]) -> dict[str, Any]:
        row = dict(payment)
        row["effective_status"] = cls._effective_payment_status(row)
        return row

    @staticmethod
    def _effective_payment_status(payment: dict[str, Any]) -> str:
        status = str(payment.get("status") or "pending")
        due_date = str(payment.get("due_date") or "").strip()
        if status == "pending" and due_date:
            try:
                if date.fromisoformat(due_date) < date.today():
                    return "late"
            except ValueError:
                return status
        return status