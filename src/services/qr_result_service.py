from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode

from src.core.database import Database
from src.services.constants import AppError, FINAL_RESULTS


class QRResultService:
    PURPOSE = "result_submission"

    def __init__(self, db: Database, pairing_service: Any | None = None) -> None:
        self.db = db
        self.pairing_service = pairing_service

    def result_url_for_pairing(
        self,
        tournament_id: int,
        pairing_id: int,
        base_url: str = "http://localhost:8765",
        expires_minutes: int = 480,
    ) -> dict[str, Any]:
        pairing = self._open_pairing(tournament_id, pairing_id)
        previous_token = self.db.get_active_public_token_for_pairing(pairing_id)
        if previous_token:
            self.db.update_public_token_status(int(previous_token["id"]), "revoked")
        token = self._new_signed_token(tournament_id, pairing)
        token_hash = self._token_hash(token)
        expires_at = (datetime.now() + timedelta(minutes=max(1, int(expires_minutes or 480)))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        token_id = self.db.create_public_token(
            token_hash=token_hash,
            tournament_id=tournament_id,
            round_id=int(pairing["round_id"]),
            pairing_id=pairing_id,
            board_number=int(pairing.get("board_number") or 0),
            expires_at=expires_at,
            purpose=self.PURPOSE,
        )
        token_row = self.db.get_public_token_by_hash(token_hash) or {"id": token_id, **pairing}
        token_row["token_marker"] = token
        self.db.create_audit_event(
            action="public_result_token_created",
            tournament_id=tournament_id,
            round_id=int(pairing["round_id"]),
            entity_type="pairing",
            entity_id=pairing_id,
            after={
                "board_number": int(pairing.get("board_number") or 0),
                "expires_at": expires_at,
                "revoked_previous_token_id": int(previous_token["id"]) if previous_token else None,
            },
        )
        return self._token_payload(token_row, token, base_url)

    def submit_result(self, token: str, result: str, submitter: str = "") -> dict[str, Any]:
        if result not in FINAL_RESULTS or result == "BYE":
            raise AppError("Resultado invalido para envio por QR.")
        token_row = self._validate_token(token)
        pairing = self._open_pairing(int(token_row["tournament_id"]), int(token_row["pairing_id"]))
        if int(pairing["round_id"]) != int(token_row["round_id"]):
            raise AppError("Token nao pertence a esta rodada.")
        if str(pairing.get("result") or "") in FINAL_RESULTS:
            raise AppError("Mesa ja possui resultado registrado no desktop.")
        if self._has_pending_submission(token_row):
            raise AppError("Ja existe envio pendente para esta mesa.")
        submission_id = self.db.create_result_submission(
            tournament_id=int(token_row["tournament_id"]),
            round_id=int(token_row["round_id"]),
            pairing_id=int(token_row["pairing_id"]),
            token_id=int(token_row["id"]),
            board_number=int(token_row.get("board_number") or pairing.get("board_number") or 0),
            submitted_result=result,
            submitter=submitter,
        )
        self.db.create_audit_event(
            action="result_submitted",
            tournament_id=int(token_row["tournament_id"]),
            round_id=int(token_row["round_id"]),
            entity_type="result_submission",
            entity_id=submission_id,
            after={"pairing_id": int(token_row["pairing_id"]), "result": result, "submitter": submitter},
        )
        return self.db.get_result_submission(submission_id) or {"id": submission_id}

    def pending_submissions(self, tournament_id: int) -> list[dict[str, Any]]:
        return self.db.list_result_submissions(tournament_id=tournament_id, status="submitted")

    def approve_submission(self, submission_id: int, reviewer: str = "", reason: str = "") -> None:
        submission = self._pending_submission(submission_id)
        if submission.get("round_status") == "closed":
            raise AppError("Nao e possivel aprovar envio de rodada fechada.")
        current_result = str(submission.get("current_result") or "")
        if current_result and current_result != str(submission["submitted_result"]):
            raise AppError("A mesa ja possui outro resultado registrado no desktop.")
        if self.pairing_service is None:
            raise AppError("Servico de emparceiramento indisponivel para aprovar resultado.")
        before = dict(submission)
        self.pairing_service.update_result(
            int(submission["tournament_id"]),
            int(submission["pairing_id"]),
            str(submission["submitted_result"]),
        )
        self.db.update_result_submission_status(submission_id, "approved", reviewer=reviewer, reason=reason)
        if submission.get("token_id"):
            self.db.update_public_token_status(int(submission["token_id"]), "used", used_at=self.db.now())
        self.db.create_audit_event(
            action="result_submission_approved",
            tournament_id=int(submission["tournament_id"]),
            round_id=int(submission["round_id"]),
            entity_type="result_submission",
            entity_id=submission_id,
            reason=reason,
            before=before,
            after={"status": "approved", "result": submission["submitted_result"], "reviewer": reviewer},
        )

    def reject_submission(self, submission_id: int, reviewer: str = "", reason: str = "") -> None:
        submission = self._pending_submission(submission_id)
        self.db.update_result_submission_status(submission_id, "rejected", reviewer=reviewer, reason=reason)
        self.db.create_audit_event(
            action="result_submission_rejected",
            tournament_id=int(submission["tournament_id"]),
            round_id=int(submission["round_id"]),
            entity_type="result_submission",
            entity_id=submission_id,
            reason=reason,
            before=submission,
            after={"status": "rejected", "reviewer": reviewer},
        )

    def _pending_submission(self, submission_id: int) -> dict[str, Any]:
        submission = self.db.get_result_submission(submission_id)
        if not submission:
            raise AppError("Envio de resultado nao encontrado.")
        if submission.get("status") != "submitted":
            raise AppError("Este envio ja foi revisado.")
        return submission

    def _has_pending_submission(self, token_row: dict[str, Any]) -> bool:
        pairing_id = int(token_row["pairing_id"])
        token_id = int(token_row["id"])
        for submission in self.db.list_result_submissions(
            tournament_id=int(token_row["tournament_id"]),
            status="submitted",
        ):
            if int(submission.get("pairing_id") or 0) == pairing_id or int(submission.get("token_id") or 0) == token_id:
                return True
        return False

    def _validate_token(self, token: str) -> dict[str, Any]:
        self._assert_signed_token_shape(token)
        token_hash = self._token_hash(token)
        token_row = self.db.get_public_token_by_hash(token_hash)
        if not token_row:
            raise AppError("Token de resultado invalido.")
        if token_row.get("status") != "active":
            raise AppError("Token de resultado ja utilizado ou cancelado.")
        if str(token_row.get("expires_at") or "") <= self.db.now():
            raise AppError("Token de resultado expirado.")
        if not hmac.compare_digest(token_hash, self._token_hash(token)):
            raise AppError("Assinatura do token invalida.")
        return token_row

    def _open_pairing(self, tournament_id: int, pairing_id: int) -> dict[str, Any]:
        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa nao encontrada para este torneio.")
        if pairing.get("is_bye"):
            raise AppError("Mesa com bye nao recebe resultado por QR.")
        if pairing.get("round_status") == "closed":
            raise AppError("Token nao funciona para rodada fechada.")
        return pairing

    def _new_signed_token(self, tournament_id: int, pairing: dict[str, Any]) -> str:
        nonce = secrets.token_urlsafe(18)
        payload = f"{int(tournament_id)}:{int(pairing['round_id'])}:{int(pairing['id'])}:{nonce}"
        signature = hmac.new(self._secret(), payload.encode("utf-8"), sha256).hexdigest()[:32]
        return f"{payload}:{signature}"

    def _assert_signed_token_shape(self, token: str) -> None:
        parts = token.split(":")
        if len(parts) != 5:
            raise AppError("Token de resultado invalido.")
        payload = ":".join(parts[:4])
        expected = hmac.new(self._secret(), payload.encode("utf-8"), sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected, parts[4]):
            raise AppError("Assinatura do token invalida.")

    def _secret(self) -> bytes:
        settings = self.db.get_app_settings()
        seed = str(settings.get("operator_name") or "albericus") + str(self.db.db_path)
        return sha256(seed.encode("utf-8")).digest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _token_payload(token_row: dict[str, Any], token: str, base_url: str) -> dict[str, Any]:
        clean_base = base_url.rstrip("/")
        url = f"{clean_base}/resultado?{urlencode({'token': token})}"
        return {
            "token": token,
            "url": url,
            "token_id": int(token_row.get("id") or 0),
            "expires_at": token_row.get("expires_at", ""),
            "board_number": int(token_row.get("board_number") or 0),
        }
