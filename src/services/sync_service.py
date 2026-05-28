from __future__ import annotations

import hmac
import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.core.database import Database
from src.services.constants import AppError, FINAL_RESULTS

DEVICE_ROLES = {"assistant", "desktop", "viewer"}


class SyncService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def register_device(
        self,
        name: str,
        role: str = "assistant",
        device_id: str = "",
        secret: str = "",
    ) -> dict[str, Any]:
        name = name.strip()
        role = role.strip() or "assistant"
        device_id = device_id.strip()
        if not name:
            raise AppError("Informe o nome do dispositivo.")
        if role not in DEVICE_ROLES:
            raise AppError("Perfil de dispositivo invalido.")
        if not device_id:
            device_id = "dev_" + self.db._hash_payload(f"{name}:{self.db.now()}")[:24]
        device = self.db.register_device(
            device_id=device_id,
            name=name,
            role=role,
            status="authorized",
            secret=secret,
        )
        self.db.create_audit_event(
            action="device_authorized",
            entity_type="device",
            entity_id=int(device["id"]),
            after={"device_id": device["device_id"], "name": device["name"], "role": device["role"]},
        )
        return device

    def list_devices(self) -> list[dict[str, Any]]:
        return self.db.list_devices()

    def revoke_device(self, device_id: str) -> None:
        device_id = device_id.strip()
        if not any(item["device_id"] == device_id for item in self.db.list_devices()):
            raise AppError("Dispositivo nao encontrado.")
        self.db.update_device_status(device_id, "revoked")
        self.db.create_audit_event(
            action="device_revoked",
            entity_type="device",
            after={"device_id": device_id},
        )

    def pending_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.db.list_sync_outbox(status="pending", limit=limit)

    def sync_pending(self, server_url: str = "", limit: int = 100, timeout_seconds: int = 5) -> dict[str, int]:
        settings = self.db.get_app_settings()
        target_url = (server_url or str(settings.get("sync_server_url") or "")).strip()
        if not target_url:
            raise AppError("Configure a URL do servidor de sincronizacao.")
        parsed_url = urlparse(target_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise AppError("URL do servidor de sincronizacao invalida.")
        if int(limit or 0) <= 0:
            raise AppError("Limite de sincronizacao deve ser positivo.")
        if int(timeout_seconds or 0) <= 0:
            raise AppError("Timeout de sincronizacao deve ser positivo.")
        endpoint = target_url.rstrip("/") + "/api/sync/events"
        summary = {"sent": 0, "synced": 0, "rejected": 0, "failed": 0}
        for event in self.pending_events(limit=limit):
            summary["sent"] += 1
            try:
                payload = self._event_payload(event)
                request = Request(
                    endpoint,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Albericus"},
                    method="POST",
                )
                with urlopen(request, timeout=timeout_seconds) as response:
                    response_payload = json.loads(response.read().decode("utf-8") or "{}")
                status = str(response_payload.get("status") or "accepted")
                if status in {"accepted", "synced"}:
                    self.db.mark_sync_outbox_synced(str(event["event_id"]))
                    summary["synced"] += 1
                elif status in {"rejected", "conflict"}:
                    reason = str(response_payload.get("reason") or status)
                    self._reject_outbox_event(event, reason)
                    summary["rejected"] += 1
                else:
                    self.db.mark_sync_outbox_failed(str(event["event_id"]), f"Resposta desconhecida: {status}")
                    summary["failed"] += 1
            except Exception as exc:
                self.db.mark_sync_outbox_failed(str(event["event_id"]), str(exc))
                summary["failed"] += 1
        return summary

    def apply_remote_event(self, event: dict[str, Any]) -> dict[str, str]:
        action = str(event.get("action") or "").strip()
        device_id = str(event.get("device_id") or "").strip()
        device = next((item for item in self.db.list_devices() if item["device_id"] == device_id), None)
        if not device or device.get("status") != "authorized":
            self._audit_rejected_remote(event, "Dispositivo nao autorizado.")
            return {"status": "rejected", "reason": "Dispositivo nao autorizado."}
        if not self._payload_hash_is_valid(event):
            reason = "Hash do payload remoto nao confere."
            self._audit_rejected_remote(event, reason)
            return {"status": "rejected", "reason": reason}

        if action == "result_updated":
            return self._apply_remote_result(event)

        self._audit_rejected_remote(event, "Acao remota nao suportada neste cliente.")
        return {"status": "rejected", "reason": "Acao remota nao suportada neste cliente."}

    def _apply_remote_result(self, event: dict[str, Any]) -> dict[str, str]:
        pairing_id = self._event_int(event.get("entity_id"))
        if pairing_id is None:
            self._audit_rejected_remote(event, "Mesa remota invalida.")
            return {"status": "rejected", "reason": "Mesa remota invalida."}
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            self._audit_rejected_remote(event, "Payload remoto invalido.")
            return {"status": "rejected", "reason": "Payload remoto invalido."}
        result = str(payload.get("result") or event.get("result") or "").strip()
        pairing = self.db.get_pairing(pairing_id)
        if not pairing:
            self._audit_rejected_remote(event, "Mesa nao encontrada.")
            return {"status": "rejected", "reason": "Mesa nao encontrada."}
        remote_tournament_id = self._event_int(event.get("tournament_id"))
        if event.get("tournament_id") is not None and remote_tournament_id is None:
            self._audit_rejected_remote(event, "Torneio remoto invalido.")
            return {"status": "rejected", "reason": "Torneio remoto invalido."}
        if remote_tournament_id is not None and remote_tournament_id != int(pairing["tournament_id"]):
            self._audit_rejected_remote(
                event,
                "Evento remoto pertence a outro torneio.",
                tournament_id=int(pairing["tournament_id"]),
            )
            return {"status": "rejected", "reason": "Evento remoto pertence a outro torneio."}
        remote_round_id = self._event_int(event.get("round_id"))
        if event.get("round_id") is not None and remote_round_id is None:
            self._audit_rejected_remote(event, "Rodada remota invalida.", tournament_id=int(pairing["tournament_id"]))
            return {"status": "rejected", "reason": "Rodada remota invalida."}
        if remote_round_id is not None and remote_round_id != int(pairing["round_id"]):
            self._audit_rejected_remote(
                event,
                "Evento remoto pertence a outra rodada.",
                tournament_id=int(pairing["tournament_id"]),
                round_id=int(pairing["round_id"]),
            )
            return {"status": "rejected", "reason": "Evento remoto pertence a outra rodada."}
        if result not in FINAL_RESULTS or result == "BYE":
            self._audit_rejected_remote(event, "Resultado remoto invalido.")
            return {"status": "rejected", "reason": "Resultado remoto invalido."}
        if pairing.get("round_status") == "closed":
            reason = "Rodada fechada: conflito exige aprovacao do arbitro."
            self._audit_rejected_remote(event, reason, tournament_id=int(pairing["tournament_id"]))
            return {"status": "conflict", "reason": reason}
        current_result = str(pairing.get("result") or "")
        if current_result and current_result != result:
            reason = "Mesa ja possui outro resultado no desktop: conflito exige aprovacao do arbitro."
            self._audit_rejected_remote(
                event,
                reason,
                tournament_id=int(pairing["tournament_id"]),
                round_id=int(pairing["round_id"]),
            )
            return {"status": "conflict", "reason": reason}
        self.db.update_pairing_result(pairing_id, result)
        self.db.create_audit_event(
            action="remote_result_applied",
            tournament_id=int(pairing["tournament_id"]),
            round_id=int(pairing["round_id"]),
            entity_type="pairing",
            entity_id=pairing_id,
            before={"result": pairing.get("result", "")},
            after={"result": result, "device_id": event.get("device_id", "")},
        )
        return {"status": "accepted"}

    @staticmethod
    def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(str(event.get("payload_json") or "{}"))
        return {
            "event_id": event["event_id"],
            "device_id": event["device_id"],
            "tournament_id": event.get("tournament_id"),
            "round_id": event.get("round_id"),
            "entity_type": event.get("entity_type"),
            "entity_id": event.get("entity_id"),
            "action": event["action"],
            "payload": payload,
            "payload_hash": event["payload_hash"],
            "conflict_policy": event["conflict_policy"],
            "created_at": event["created_at"],
        }

    def _payload_hash_is_valid(self, event: dict[str, Any]) -> bool:
        payload_hash = str(event.get("payload_hash") or "").strip()
        if not payload_hash:
            return True
        expected = self.db._hash_payload(event.get("payload") or {})
        return hmac.compare_digest(payload_hash, expected)

    @staticmethod
    def _event_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _reject_outbox_event(self, event: dict[str, Any], reason: str) -> None:
        self.db.mark_sync_outbox_rejected(str(event["event_id"]), reason)
        self.db.create_audit_event(
            action="sync_event_rejected",
            tournament_id=event.get("tournament_id"),
            round_id=event.get("round_id"),
            entity_type=str(event.get("entity_type") or ""),
            entity_id=event.get("entity_id"),
            reason=reason,
            after={"event_id": event["event_id"], "remote_reason": reason},
        )

    def _audit_rejected_remote(
        self,
        event: dict[str, Any],
        reason: str,
        tournament_id: int | None = None,
        round_id: int | None = None,
    ) -> None:
        resolved_tournament_id = self._valid_audit_tournament_id(
            tournament_id if tournament_id is not None else event.get("tournament_id")
        )
        resolved_round_id = self._valid_audit_round_id(
            round_id if round_id is not None else event.get("round_id"),
            resolved_tournament_id,
        )
        self.db.create_audit_event(
            action="sync_remote_rejected",
            tournament_id=resolved_tournament_id,
            round_id=resolved_round_id,
            entity_type=str(event.get("entity_type") or ""),
            entity_id=event.get("entity_id"),
            reason=reason,
            after={"event": event, "reason": reason},
        )

    def _valid_audit_tournament_id(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            tournament_id = int(value)
        except (TypeError, ValueError):
            return None
        return tournament_id if self.db.get_tournament(tournament_id) else None

    def _valid_audit_round_id(self, value: Any, tournament_id: int | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            round_id = int(value)
        except (TypeError, ValueError):
            return None
        round_data = self.db.get_round(round_id)
        if not round_data:
            return None
        if tournament_id is not None and int(round_data["tournament_id"]) != tournament_id:
            return None
        return round_id
