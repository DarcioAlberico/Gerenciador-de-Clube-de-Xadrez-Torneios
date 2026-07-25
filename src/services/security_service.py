from __future__ import annotations
import csv
import hashlib
import hmac
import html
import json
import logging
import math
import os
import secrets
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
    _PASSWORD_ALGORITHM = "pbkdf2_sha256"
    _PASSWORD_ITERATIONS = 210_000

    def __init__(self, db: Database) -> None:
        self.db = db
        self._current_user: dict[str, str] | None = None

    def login(self, username: str, password_raw: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT id, username, role, password_hash FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if not row or not self._verify_password(password_raw, str(row["password_hash"] or "")):
                return False
            if self._needs_password_rehash(str(row["password_hash"] or "")):
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (self._hash_password(password_raw), self.db.now(), row["id"]),
                )
            self._current_user = {
                "id": str(row["id"]),
                "username": row["username"],
                "role": row["role"]
            }
        self.audit("login", description=f"Usuário {username} fez login.")
        return True

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
            return [dict(row) for row in cursor.fetchall()]

    def create_user(self, username: str, password_raw: str, role: str) -> None:
        self.require_permission("settings_write")
        if not username.strip():
            raise AppError("Informe o nome de usuario.")
        if not password_raw:
            raise AppError("Informe a senha.")
        pw_hash = self._hash_password(password_raw)
        now = self.db.now()
        try:
            with self.db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (username.strip(), pw_hash, role, now, now),
                )
            self.audit("user_created", description=f"Usuário {username} criado.")
        except sqlite3.IntegrityError:
            raise AppError("Nome de usuário já existe.")

    def update_user_password(self, user_id: int, new_password_raw: str) -> None:
        self.require_permission("settings_write")
        if not new_password_raw:
            raise AppError("Informe a nova senha.")
        pw_hash = self._hash_password(new_password_raw)
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (pw_hash, self.db.now(), user_id))
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

    def current_user_id(self) -> int:
        """Id do usuário logado, ou 0 para o operador padrão (sem login).

        Zero é um id de verdade aqui, não "ausente": é a identidade de quem usa
        o app sem sessão iniciada, e é sob ele que preferências de interface
        (largura de coluna, por exemplo) ficam guardadas.
        """
        if not self._current_user:
            return 0
        try:
            return int(self._current_user["id"])
        except (KeyError, TypeError, ValueError):
            return 0

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

    @classmethod
    def _hash_password(cls, password_raw: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password_raw.encode("utf-8"),
            salt,
            cls._PASSWORD_ITERATIONS,
        )
        return (
            f"{cls._PASSWORD_ALGORITHM}${cls._PASSWORD_ITERATIONS}$"
            f"{salt.hex()}${digest.hex()}"
        )

    @classmethod
    def _verify_password(cls, password_raw: str, stored_hash: str) -> bool:
        parts = stored_hash.split("$")
        if len(parts) == 4 and parts[0] == cls._PASSWORD_ALGORITHM:
            try:
                iterations = int(parts[1])
                salt = bytes.fromhex(parts[2])
                expected = bytes.fromhex(parts[3])
            except ValueError:
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password_raw.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(digest, expected)

        legacy_digest = hashlib.sha256(password_raw.encode()).hexdigest()
        return hmac.compare_digest(legacy_digest, stored_hash)

    @classmethod
    def _needs_password_rehash(cls, stored_hash: str) -> bool:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != cls._PASSWORD_ALGORITHM:
            return True
        try:
            return int(parts[1]) < cls._PASSWORD_ITERATIONS
        except ValueError:
            return True

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

        # db.backup() ja copiou para a nuvem (caminho unico, sem duplicar). Aqui
        # so lemos o resultado para auditar e reportar.
        cloud_result = self.db.last_cloud_backup or {"status": "not_configured", "path": ""}
        cloud_status = cloud_result.get("status", "not_configured")
        cloud_path = cloud_result.get("path", "")

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
