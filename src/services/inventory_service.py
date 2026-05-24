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

class InventoryService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_item(self, data: dict[str, Any], item_id: int | None = None) -> int:
        payload = self._validated_item_payload(data, item_id=item_id)
        if item_id:
            if not self.db.get_inventory_item(item_id):
                raise AppError("Item de inventario nao encontrado.")
            self.db.update_inventory_item(item_id, **payload)
            logger.info("Item de inventario atualizado: %s", item_id)
            return item_id
        saved_id = self.db.create_inventory_item(**payload)
        logger.info("Item de inventario criado: %s", saved_id)
        return saved_id

    def toggle_item_active(self, item_id: int) -> int:
        item = self.db.get_inventory_item(item_id)
        if not item:
            raise AppError("Item de inventario nao encontrado.")
        next_active = 0 if item.get("active") else 1
        if not next_active and int(item.get("borrowed_quantity") or 0) > 0:
            raise AppError("Nao inative item com emprestimos em aberto.")
        self.db.set_inventory_item_active(item_id, next_active)
        logger.info("Item de inventario %s alterado para active=%s", item_id, next_active)
        return next_active

    def save_loan(self, data: dict[str, Any], loan_id: int | None = None) -> int:
        payload = self._validated_loan_payload(data, loan_id=loan_id)
        if loan_id:
            if not self.db.get_inventory_loan(loan_id):
                raise AppError("Emprestimo nao encontrado.")
            self.db.update_inventory_loan(loan_id, **payload)
            logger.info("Emprestimo atualizado: %s", loan_id)
            return loan_id
        saved_id = self.db.create_inventory_loan(**payload)
        logger.info("Emprestimo criado: %s", saved_id)
        return saved_id

    def return_loan(self, loan_id: int, return_date: str = "") -> None:
        loan = self.db.get_inventory_loan(loan_id)
        if not loan:
            raise AppError("Emprestimo nao encontrado.")
        if loan.get("status") == "returned":
            return
        payload = dict(loan)
        payload["status"] = "returned"
        payload["return_date"] = return_date.strip() or date.today().isoformat()
        self.save_loan(payload, loan_id=loan_id)

    def save_maintenance(self, data: dict[str, Any], maintenance_id: int | None = None) -> int:
        payload = self._validated_maintenance_payload(data)
        if maintenance_id:
            if not self.db.get_inventory_maintenance(maintenance_id):
                raise AppError("Manutencao nao encontrada.")
            self.db.update_inventory_maintenance(maintenance_id, **payload)
            logger.info("Manutencao atualizada: %s", maintenance_id)
            return maintenance_id
        saved_id = self.db.create_inventory_maintenance(**payload)
        logger.info("Manutencao criada: %s", saved_id)
        return saved_id

    def close_maintenance(self, maintenance_id: int, resolved_date: str = "") -> None:
        maintenance = self.db.get_inventory_maintenance(maintenance_id)
        if not maintenance:
            raise AppError("Manutencao nao encontrada.")
        payload = dict(maintenance)
        payload["status"] = "done"
        payload["resolved_date"] = resolved_date.strip() or date.today().isoformat()
        self.save_maintenance(payload, maintenance_id=maintenance_id)

    def inventory_summary(self) -> dict[str, Any]:
        items = self.db.list_inventory_items(active_only=False)
        loans = self.db.list_inventory_loans()
        maintenance_rows = self.db.list_inventory_maintenance()
        total_items = sum(int(item.get("quantity_total") or 0) for item in items if item.get("active"))
        borrowed = sum(int(item.get("borrowed_quantity") or 0) for item in items)
        available = sum(int(item.get("available_quantity") or 0) for item in items if item.get("active"))
        open_loans = [loan for loan in loans if loan.get("status") == "open"]
        today = date.today().isoformat()
        overdue_loans = [
            loan
            for loan in open_loans
            if str(loan.get("due_date") or "").strip()
            and str(loan.get("due_date") or "").strip() < today
        ]
        open_maintenance = [
            row
            for row in maintenance_rows
            if str(row.get("status") or "") in {"open", "in_progress"}
        ]
        return {
            "items": len(items),
            "total_quantity": total_items,
            "available_quantity": available,
            "borrowed_quantity": borrowed,
            "open_loans": len(open_loans),
            "overdue_loans": len(overdue_loans),
            "open_maintenance": len(open_maintenance),
        }

    def _validated_item_payload(self, data: dict[str, Any], item_id: int | None = None) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do item.")

        try:
            club_id = int(data.get("club_id") or 1)
        except ValueError as exc:
            raise AppError("Clube/escola do item invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola do item nao encontrado.")

        item_type = str(data.get("item_type", "other")).strip() or "other"
        if item_type not in INVENTORY_ITEM_TYPES:
            raise AppError("Tipo de item invalido.")

        condition_status = str(data.get("condition_status", "good")).strip() or "good"
        if condition_status not in INVENTORY_CONDITIONS:
            raise AppError("Estado do item invalido.")

        try:
            quantity_total = int(data.get("quantity_total") or 1)
        except ValueError as exc:
            raise AppError("Quantidade do item invalida.") from exc
        if quantity_total <= 0:
            raise AppError("Quantidade do item deve ser maior que zero.")

        borrowed_quantity = self.db.inventory_item_open_loan_quantity(item_id) if item_id else 0
        if quantity_total < borrowed_quantity:
            raise AppError("Quantidade total nao pode ficar abaixo dos emprestimos em aberto.")

        acquisition_date = str(data.get("acquisition_date", "")).strip()
        self._validate_optional_date(acquisition_date, "Data de aquisicao invalida.")

        acquisition_value = self._parse_money(data.get("acquisition_value"), "Valor de aquisicao invalido.")
        if acquisition_value < 0:
            raise AppError("Valor de aquisicao nao pode ser negativo.")

        return {
            "club_id": club_id,
            "code": str(data.get("code", "")),
            "name": name,
            "item_type": item_type,
            "quantity_total": quantity_total,
            "condition_status": condition_status,
            "storage_location": str(data.get("storage_location", "")),
            "acquisition_date": acquisition_date,
            "acquisition_value": acquisition_value,
            "active": 1 if data.get("active", 1) else 0,
            "notes": str(data.get("notes", "")),
        }

    def _validated_loan_payload(self, data: dict[str, Any], loan_id: int | None = None) -> dict[str, Any]:
        try:
            item_id = int(data.get("item_id") or 0)
        except ValueError as exc:
            raise AppError("Item do emprestimo invalido.") from exc
        item = self.db.get_inventory_item(item_id)
        if not item:
            raise AppError("Item do emprestimo nao encontrado.")
        if not item.get("active"):
            raise AppError("Item inativo nao pode ser emprestado.")

        try:
            member_id = int(data.get("member_id") or 0)
        except ValueError as exc:
            raise AppError("Membro do emprestimo invalido.") from exc
        if not self.db.get_member(member_id):
            raise AppError("Membro do emprestimo nao encontrado.")

        try:
            quantity = int(data.get("quantity") or 1)
        except ValueError as exc:
            raise AppError("Quantidade do emprestimo invalida.") from exc
        if quantity <= 0:
            raise AppError("Quantidade do emprestimo deve ser maior que zero.")

        status = str(data.get("status", "open")).strip() or "open"
        if status not in INVENTORY_LOAN_STATUSES:
            raise AppError("Status do emprestimo invalido.")

        loan_date = str(data.get("loan_date", "")).strip() or date.today().isoformat()
        due_date = str(data.get("due_date", "")).strip()
        return_date = str(data.get("return_date", "")).strip()
        self._validate_optional_date(loan_date, "Data do emprestimo invalida.")
        self._validate_optional_date(due_date, "Data prevista de devolucao invalida.")
        self._validate_optional_date(return_date, "Data de devolucao invalida.")

        if status == "returned" and not return_date:
            return_date = date.today().isoformat()
        if status == "open":
            return_date = ""

        if status == "open":
            borrowed_other = self.db.inventory_item_open_loan_quantity(item_id, exclude_loan_id=loan_id)
            available = int(item.get("quantity_total") or 0) - borrowed_other
            if quantity > available:
                raise AppError("Quantidade indisponivel para emprestimo.")

        return {
            "item_id": item_id,
            "member_id": member_id,
            "quantity": quantity,
            "loan_date": loan_date,
            "due_date": due_date,
            "return_date": return_date,
            "status": status,
            "notes": str(data.get("notes", "")),
        }

    def _validated_maintenance_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            item_id = int(data.get("item_id") or 0)
        except ValueError as exc:
            raise AppError("Item da manutencao invalido.") from exc
        if not self.db.get_inventory_item(item_id):
            raise AppError("Item da manutencao nao encontrado.")

        description = str(data.get("description", "")).strip()
        if not description:
            raise AppError("Informe a descricao da manutencao.")

        status = str(data.get("status", "open")).strip() or "open"
        if status not in INVENTORY_MAINTENANCE_STATUSES:
            raise AppError("Status da manutencao invalido.")

        opened_date = str(data.get("opened_date", "")).strip() or date.today().isoformat()
        resolved_date = str(data.get("resolved_date", "")).strip()
        self._validate_optional_date(opened_date, "Data de abertura invalida.")
        self._validate_optional_date(resolved_date, "Data de conclusao invalida.")
        if status == "done" and not resolved_date:
            resolved_date = date.today().isoformat()
        if status in {"open", "in_progress"}:
            resolved_date = ""

        cost = self._parse_money(data.get("cost"), "Custo da manutencao invalido.")
        if cost < 0:
            raise AppError("Custo da manutencao nao pode ser negativo.")

        return {
            "item_id": item_id,
            "opened_date": opened_date,
            "resolved_date": resolved_date,
            "status": status,
            "description": description,
            "cost": cost,
            "vendor": str(data.get("vendor", "")),
            "notes": str(data.get("notes", "")),
        }

    @staticmethod
    def _parse_money(value: Any, message: str) -> float:
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