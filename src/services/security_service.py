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

class SecurityService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._current_user: dict[str, str] | None = None

    def login(self, username: str, password_raw: str) -> bool:
        import hashlib
        pw_hash = hashlib.sha256(password_raw.encode()).hexdigest()
        with self.db.connect() as conn:
            cursor = conn.execute(
                "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?",
                (username, pw_hash)
            )
            row = cursor.fetchone()
            if row:
                self._current_user = {
                    "id": str(row["id"]),
                    "username": row["username"],
                    "role": row["role"]
                }
                self.audit("login", description=f"Usuário {username} fez login.")
                return True
        return False

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
            return [dict(row) for row in cursor.fetchall()]

    def create_user(self, username: str, password_raw: str, role: str) -> None:
        self.require_permission("settings_write")
        import hashlib
        pw_hash = hashlib.sha256(password_raw.encode()).hexdigest()
        try:
            with self.db.connect() as conn:
                conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, pw_hash, role))
            self.audit("user_created", description=f"Usuário {username} criado.")
        except sqlite3.IntegrityError:
            raise AppError("Nome de usuário já existe.")

    def update_user_password(self, user_id: int, new_password_raw: str) -> None:
        self.require_permission("settings_write")
        import hashlib
        pw_hash = hashlib.sha256(new_password_raw.encode()).hexdigest()
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
        self.audit("password_updated", entity_id=user_id, description="Senha do usuário atualizada.")

    def delete_user(self, user_id: int) -> None:
        self.require_permission("settings_write")
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["role"] == "admin":
                count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
                if count <= 1:
                    raise AppError("Não é possível deletar o último administrador.")
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.audit("user_deleted", entity_id=user_id, description="Usuário deletado.")

    def current_operator(self) -> dict[str, str]:
        if self._current_user:
            role = self._current_user["role"]
            name = self._current_user["username"]
            return {"name": name, "role": role, "role_label": OPERATOR_ROLES.get(role, role)}
            
        settings = self.db.get_app_settings()
        role = str(settings.get("operator_role") or "admin")
        if role not in OPERATOR_ROLES:
            role = "admin"
        name = str(settings.get("operator_name") or "").strip() or OPERATOR_ROLES[role]
        return {"name": name, "role": role, "role_label": OPERATOR_ROLES[role]}

    def has_permission(self, action: str) -> bool:
        """Verifica se o operador atual tem a permissão solicitada."""
        from src.config.permissions import get_permissions_for_role
        operator = self.current_operator()
        role = operator["role"]
        # admin has everything
        if role == "admin":
            return True
        perms = get_permissions_for_role(role)
        return action in perms

    def require_permission(self, action: str) -> None:
        """Lança erro e audita caso o usuário não tenha permissão."""
        if not self.has_permission(action):
            self.audit(
                action="permission_denied", 
                description=f"Acesso negado para ação: {action}"
            )
            raise AppError("Permissão negada para realizar esta ação.")

    def save_security_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        self.require_permission("settings_write")
        try:
            retention_count = int(data.get("backup_retention_count") or 10)
        except ValueError as exc:
            raise AppError("Retencao de backups invalida.") from exc
        if retention_count < 1 or retention_count > 999:
            raise AppError("Retencao de backups deve ficar entre 1 e 999.")
        payload = {
            "backup_retention_count": str(retention_count),
        }
        self.db.save_app_settings(payload)
        self.audit(
            "settings_saved",
            entity_type="app_settings",
            description="Configuracoes de seguranca operacional atualizadas.",
            metadata=payload,
        )
        return payload

    def audit(
        self,
        action: str,
        entity_type: str = "",
        entity_id: int | None = None,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> int:
        operator = self.current_operator()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        return self.db.create_audit_log(
            action=action,
            actor=operator["name"],
            role=operator["role"],
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            metadata_json=metadata_json,
        )

    def list_audit_logs(
        self,
        limit: int = 200,
        action: str = "",
        entity_type: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        self._validate_optional_date(start_date, "Data inicial da auditoria invalida.")
        self._validate_optional_date(end_date, "Data final da auditoria invalida.")
        return self.db.list_audit_logs(
            limit=limit,
            action=action,
            entity_type=entity_type,
            start_date=start_date.strip(),
            end_date=end_date.strip(),
        )

    def create_backup(self, reason: str = "manual") -> dict[str, Any]:
        self.require_permission("settings_write")
        path = self.db.backup(reason)
        deleted = self.enforce_backup_retention()
        
        cloud_sync_dir = self.db.get_app_settings().get("cloud_sync_dir", "").strip()
        cloud_status = "not_configured"
        cloud_path = ""
        
        if cloud_sync_dir:
            cloud_dir_path = Path(cloud_sync_dir)
            if cloud_dir_path.exists() and cloud_dir_path.is_dir():
                try:
                    cloud_target = cloud_dir_path / path.name
                    shutil.copy2(path, cloud_target)
                    cloud_status = "success"
                    cloud_path = str(cloud_target)
                except Exception as exc:
                    logger.error("Falha ao copiar backup para nuvem %s: %s", cloud_sync_dir, exc)
                    cloud_status = f"error: {exc}"
            else:
                cloud_status = "invalid_directory"
        
        self.audit(
            "backup_created",
            entity_type="backup",
            description=f"Backup criado: {path.name}",
            metadata={
                "path": str(path),
                "reason": reason,
                "deleted_by_retention": [str(item) for item in deleted],
                "cloud_sync_status": cloud_status,
                "cloud_path": cloud_path,
            },
        )
        logger.info("Backup criado por SecurityService: %s (Cloud: %s)", path, cloud_status)
        return {"path": path, "deleted": deleted, "cloud_status": cloud_status}

    def restore_backup(self, backup_path: Path | str) -> Path:
        self.require_permission("settings_write")
        source = Path(backup_path)
        safety_backup = self.db.restore_backup(source)
        self.audit(
            "backup_restored",
            entity_type="backup",
            description=f"Backup restaurado: {source.name}",
            metadata={"source": str(source), "safety_backup": str(safety_backup)},
        )
        logger.info("Backup restaurado por SecurityService: %s", source)
        return safety_backup

    def enforce_backup_retention(self, keep_count: int | None = None) -> list[Path]:
        if keep_count is None:
            settings = self.db.get_app_settings()
            try:
                keep_count = int(settings.get("backup_retention_count") or 10)
            except ValueError:
                keep_count = 10
        deleted = self.db.prune_backups(keep_count)
        if deleted:
            self.audit(
                "backup_retention_applied",
                entity_type="backup",
                description=f"Retencao aplicada: {len(deleted)} backup(s) removido(s).",
                metadata={"keep_count": keep_count, "deleted": [str(item) for item in deleted]},
            )
        return deleted

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        try:
            date.fromisoformat(cleaned)
        except ValueError as exc:
            raise AppError(message) from exc