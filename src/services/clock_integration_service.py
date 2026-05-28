from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.core.database import Database
from src.services.constants import AppError


CLOCK_EVENT_TYPES = {
    "clock_started",
    "clock_paused",
    "clock_resumed",
    "clock_stopped",
    "time_warning",
    "flag_fall",
    "absence",
    "manual_note",
}
NOTIFICATION_CHANNELS = {"email", "whatsapp", "sms"}


class ClockDevicePlugin(Protocol):
    plugin_id: str
    label: str

    def normalize_event(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ManualClockPlugin:
    plugin_id: str = "manual"
    label: str = "Registro manual"

    def normalize_event(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        return dict(raw_event)


class ClockIntegrationService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._plugins: dict[str, ClockDevicePlugin] = {}
        self.register_plugin(ManualClockPlugin())

    def register_plugin(self, plugin: ClockDevicePlugin) -> None:
        self._plugins[plugin.plugin_id] = plugin

    def list_plugins(self) -> list[dict[str, str]]:
        return [
            {"plugin_id": plugin.plugin_id, "label": plugin.label}
            for plugin in sorted(self._plugins.values(), key=lambda item: item.plugin_id)
        ]

    def record_manual_event(
        self,
        tournament_id: int,
        event_type: str,
        round_id: int | None = None,
        pairing_id: int | None = None,
        player_id: int | None = None,
        board_number: int = 0,
        side: str = "",
        seconds_remaining: int | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        return self._record_event(
            tournament_id=tournament_id,
            event_type=event_type,
            round_id=round_id,
            pairing_id=pairing_id,
            player_id=player_id,
            board_number=board_number,
            side=side,
            seconds_remaining=seconds_remaining,
            note=note,
            payload={"manual": True},
            source="manual",
        )

    def record_plugin_event(self, plugin_id: str, raw_event: dict[str, Any]) -> dict[str, Any]:
        settings = self.db.get_app_settings()
        if str(settings.get("device_integrations_enabled") or "0") not in {"1", "true", "True", "sim"}:
            return {"status": "ignored", "reason": "Integracoes de dispositivos desativadas."}
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise AppError("Plugin de dispositivo nao registrado.")
        event = plugin.normalize_event(raw_event)
        return self._record_event(
            tournament_id=int(event["tournament_id"]),
            event_type=str(event["event_type"]),
            round_id=self._optional_int(event.get("round_id")),
            pairing_id=self._optional_int(event.get("pairing_id")),
            player_id=self._optional_int(event.get("player_id")),
            board_number=int(event.get("board_number") or 0),
            side=str(event.get("side") or ""),
            seconds_remaining=self._optional_int(event.get("seconds_remaining")),
            note=str(event.get("note") or ""),
            payload=event,
            source=plugin.plugin_id,
            device_id=str(event.get("device_id") or ""),
            occurred_at=str(event.get("occurred_at") or ""),
        )

    def list_clock_events(
        self,
        tournament_id: int,
        round_id: int | None = None,
        pairing_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return self.db.list_clock_events(
            tournament_id=tournament_id,
            round_id=round_id,
            pairing_id=pairing_id,
            limit=limit,
        )

    def anomaly_alerts(self, tournament_id: int) -> list[dict[str, Any]]:
        alerts = []
        events = self.db.list_clock_events(tournament_id=tournament_id, limit=5000)
        for event in events:
            event_type = str(event.get("event_type") or "")
            if event_type == "flag_fall":
                alerts.append(self._alert(event, "Queda de seta registrada. Conferir a mesa antes de lancar resultado."))
            elif event_type == "absence":
                alerts.append(self._alert(event, "Ausencia registrada. Confirmar regra de WO antes de lancar resultado."))
            elif event_type == "time_warning" and int(event.get("seconds_remaining") or 999999) <= 60:
                alerts.append(self._alert(event, "Jogador com menos de 60 segundos informado pelo relogio."))
        return alerts

    def queue_notification(
        self,
        channel: str,
        recipient: str,
        message: str,
        tournament_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        channel = channel.strip().lower()
        recipient = recipient.strip()
        message = message.strip()
        if channel not in NOTIFICATION_CHANNELS:
            raise AppError("Canal de notificacao invalido.")
        if not recipient:
            raise AppError("Informe o destinatario da notificacao.")
        if not message:
            raise AppError("Informe a mensagem da notificacao.")
        settings = self.db.get_app_settings()
        if str(settings.get("notifications_enabled") or "0") not in {"1", "true", "True", "sim"}:
            self.db.create_audit_event(
                action="notification_skipped",
                tournament_id=tournament_id,
                entity_type="notification",
                after={"channel": channel, "recipient": recipient, "reason": "disabled"},
            )
            return {"status": "skipped", "reason": "Notificacoes desativadas."}
        self.db.create_audit_event(
            action="notification_queued",
            tournament_id=tournament_id,
            entity_type="notification",
            after={
                "channel": channel,
                "recipient": recipient,
                "message": message,
                "metadata": metadata or {},
            },
        )
        return {"status": "queued"}

    def _record_event(
        self,
        tournament_id: int,
        event_type: str,
        round_id: int | None = None,
        pairing_id: int | None = None,
        player_id: int | None = None,
        board_number: int = 0,
        side: str = "",
        seconds_remaining: int | None = None,
        note: str = "",
        payload: dict[str, Any] | None = None,
        source: str = "manual",
        device_id: str = "",
        occurred_at: str = "",
    ) -> dict[str, Any]:
        if event_type not in CLOCK_EVENT_TYPES:
            raise AppError("Tipo de evento de relogio invalido.")
        if side not in {"", "white", "black"}:
            raise AppError("Lado do evento de relogio invalido.")
        if seconds_remaining is not None and int(seconds_remaining) < 0:
            raise AppError("Segundos restantes nao podem ser negativos.")
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if pairing_id:
            pairing = self.db.get_pairing(pairing_id)
            if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
                raise AppError("Mesa nao encontrada para o torneio selecionado.")
            if player_id and int(player_id) not in {
                int(pairing.get("white_player_id") or 0),
                int(pairing.get("black_player_id") or 0),
            }:
                raise AppError("Jogador nao pertence a mesa informada.")
            round_id = int(pairing["round_id"])
            board_number = int(pairing.get("board_number") or board_number or 0)
        elif player_id:
            player = self.db.get_player(player_id)
            if not player or int(player["tournament_id"]) != int(tournament_id):
                raise AppError("Jogador nao pertence ao torneio selecionado.")

        event_id = self.db.create_clock_event(
            tournament_id=tournament_id,
            round_id=round_id,
            pairing_id=pairing_id,
            player_id=player_id,
            board_number=board_number,
            device_id=device_id,
            source=source,
            event_type=event_type,
            side=side,
            seconds_remaining=seconds_remaining,
            note=note,
            payload=payload,
            occurred_at=occurred_at,
        )
        event = self.db.list_clock_events(tournament_id=tournament_id, limit=1)[0]
        self.db.create_audit_event(
            action="clock_event_logged",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="clock_event",
            entity_id=event_id,
            after={
                "event_type": event_type,
                "pairing_id": pairing_id,
                "player_id": player_id,
                "source": source,
                "note": note,
            },
        )
        return event

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @staticmethod
    def _alert(event: dict[str, Any], message: str) -> dict[str, Any]:
        return {
            "severity": "attention",
            "message": message,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "round_id": event.get("round_id"),
            "pairing_id": event.get("pairing_id"),
            "recommendation": "Apenas alerta; o arbitro deve decidir e registrar o resultado manualmente.",
        }
