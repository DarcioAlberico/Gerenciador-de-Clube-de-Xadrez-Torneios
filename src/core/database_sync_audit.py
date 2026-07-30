"""Mixin de sincronizacao, auditoria e dados de apoio da Database.

Logs de auditoria, dispositivos, fila de sync (outbox), eventos de relogio,
snapshots de pareamento/classificacao, componentes de tiebreak, tokens
publicos e submissoes de resultado. Extraido de ``src.core.database`` na
decomposicao da God Class. Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from ._database_base import _DatabaseInfra


class SyncAuditMixin(_DatabaseInfra):
    def create_audit_log(
        self,
        action: str,
        actor: str = "",
        role: str = "",
        entity_type: str = "",
        entity_id: int | None = None,
        description: str = "",
        metadata_json: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_log (
                    actor, role, action, entity_type, entity_id, description,
                    metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor.strip(),
                    role.strip(),
                    action.strip(),
                    entity_type.strip(),
                    entity_id,
                    description.strip(),
                    metadata_json.strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_audit_logs(
        self,
        limit: int = 200,
        action: str = "",
        entity_type: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if action:
            conditions.append("action = ?")
            params.append(action.strip())
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type.strip())
        if start_date:
            conditions.append("created_at >= ?")
            params.append(f"{start_date.strip()} 00:00:00")
        if end_date:
            conditions.append("created_at <= ?")
            params.append(f"{end_date.strip()} 23:59:59")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM audit_log
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    @staticmethod
    def _canonical_json(data: Mapping[str, Any] | list[Any] | None) -> str:
        return json.dumps(data or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash_payload(cls, data: Mapping[str, Any] | list[Any] | str | None) -> str:
        if isinstance(data, str):
            payload = data
        else:
            payload = cls._canonical_json(data)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _operator_context(self) -> tuple[str, str]:
        settings = self.get_app_settings()
        actor = str(settings.get("operator_name") or "").strip()
        role = str(settings.get("operator_role") or "").strip()
        return actor, role

    def ensure_local_device(self, name: str = "") -> dict[str, Any]:
        settings = self.get_app_settings()
        device_id = str(settings.get("local_device_id") or "").strip()
        if not device_id:
            seed = f"{self.db_path.resolve()}:{self.now()}:{datetime.now().timestamp()}"
            device_id = "dev_" + self._hash_payload(seed)[:24]
            self.save_app_settings({"local_device_id": device_id})
        device_name = name.strip() or str(settings.get("operator_name") or "").strip() or "Desktop local"
        return self.register_device(device_id=device_id, name=device_name, role="desktop", status="authorized")

    def register_device(
        self,
        device_id: str,
        name: str,
        role: str = "assistant",
        status: str = "authorized",
        secret: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_device_id = device_id.strip()
        if not safe_device_id:
            raise ValueError("device_id obrigatorio")
        safe_status = status.strip() or "authorized"
        safe_role = role.strip() or "assistant"
        now = self.now()
        secret_hash = self._hash_payload(secret) if secret else ""
        metadata_json = self._canonical_json(metadata)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO devices (
                    device_id, name, role, status, secret_hash, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
                    status = excluded.status,
                    secret_hash = CASE
                        WHEN excluded.secret_hash != '' THEN excluded.secret_hash
                        ELSE devices.secret_hash
                    END,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    safe_device_id,
                    name.strip() or safe_device_id,
                    safe_role,
                    safe_status,
                    secret_hash,
                    metadata_json,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM devices WHERE device_id = ?", (safe_device_id,)).fetchone()
            return dict(row)

    def list_devices(self, status: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if status:
            where = "WHERE status = ?"
            params.append(status.strip())
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM devices
                {where}
                ORDER BY status, name
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_device_status(self, device_id: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE devices
                SET status = ?, updated_at = ?
                WHERE device_id = ?
                """,
                (status.strip(), self.now(), device_id.strip()),
            )

    def create_sync_outbox_event(
        self,
        action: str,
        payload: Mapping[str, Any] | list[Any],
        tournament_id: int | None = None,
        round_id: int | None = None,
        entity_type: str = "",
        entity_id: int | None = None,
        device_id: str = "",
        conflict_policy: str = "server_authoritative",
        status: str = "pending",
    ) -> int:
        local_device = self.ensure_local_device()
        resolved_device_id = device_id.strip() or str(local_device["device_id"])
        payload_json = self._canonical_json(payload)
        now = self.now()
        event_seed = self._canonical_json(
            {
                "device_id": resolved_device_id,
                "action": action,
                "tournament_id": tournament_id,
                "round_id": round_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload_hash": self._hash_payload(payload_json),
                "created_at": now,
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sync_outbox (
                    event_id, device_id, tournament_id, round_id, entity_type,
                    entity_id, action, payload_json, payload_hash, conflict_policy,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    resolved_device_id,
                    tournament_id,
                    round_id,
                    entity_type.strip(),
                    entity_id,
                    action.strip(),
                    payload_json,
                    self._hash_payload(payload_json),
                    conflict_policy.strip() or "server_authoritative",
                    status.strip() or "pending",
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_sync_outbox(self, status: str = "pending", limit: int = 200) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM sync_outbox
                {where}
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def mark_sync_outbox_synced(self, event_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET status = 'synced', synced_at = ?, updated_at = ?, last_error = ''
                WHERE event_id = ?
                """,
                (self.now(), self.now(), event_id),
            )

    def mark_sync_outbox_failed(self, event_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET attempts = attempts + 1, last_error = ?, updated_at = ?, next_attempt_at = ?
                WHERE event_id = ?
                """,
                (error[:500], self.now(), self.now(), event_id),
            )

    def mark_sync_outbox_rejected(self, event_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET status = 'rejected', attempts = attempts + 1, last_error = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (error[:500], self.now(), event_id),
            )

    def create_clock_event(
        self,
        tournament_id: int,
        event_type: str,
        round_id: int | None = None,
        pairing_id: int | None = None,
        board_number: int = 0,
        player_id: int | None = None,
        device_id: str = "",
        source: str = "manual",
        side: str = "",
        seconds_remaining: int | None = None,
        note: str = "",
        payload: Mapping[str, Any] | None = None,
        status: str = "logged",
        occurred_at: str = "",
    ) -> int:
        payload_json = self._canonical_json(payload)
        now = self.now()
        event_seed = self._canonical_json(
            {
                "tournament_id": tournament_id,
                "round_id": round_id,
                "pairing_id": pairing_id,
                "event_type": event_type,
                "device_id": device_id,
                "source": source,
                "occurred_at": occurred_at or now,
                "payload_hash": self._hash_payload(payload_json),
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO clock_events (
                    event_id, tournament_id, round_id, pairing_id, board_number,
                    player_id, device_id, source, event_type, side,
                    seconds_remaining, note, payload_json, status, occurred_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tournament_id,
                    round_id,
                    pairing_id,
                    int(board_number or 0),
                    player_id,
                    device_id.strip(),
                    source.strip() or "manual",
                    event_type.strip(),
                    side.strip(),
                    seconds_remaining,
                    note.strip(),
                    payload_json,
                    status.strip() or "logged",
                    occurred_at.strip() or now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_clock_events(
        self,
        tournament_id: int | None = None,
        round_id: int | None = None,
        pairing_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("tournament_id = ?")
            params.append(int(tournament_id))
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        if pairing_id is not None:
            conditions.append("pairing_id = ?")
            params.append(int(pairing_id))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM clock_events
                {where}
                ORDER BY occurred_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_audit_event(
        self,
        action: str,
        tournament_id: int | None = None,
        round_id: int | None = None,
        entity_type: str = "",
        entity_id: int | None = None,
        reason: str = "",
        before: Mapping[str, Any] | list[Any] | None = None,
        after: Mapping[str, Any] | list[Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "",
        role: str = "",
    ) -> int:
        before_json = self._canonical_json(before)
        after_json = self._canonical_json(after)
        metadata_json = self._canonical_json(metadata)
        resolved_actor, resolved_role = (actor.strip(), role.strip())
        if not resolved_actor and not resolved_role:
            resolved_actor, resolved_role = self._operator_context()
        event_seed = self._canonical_json(
            {
                "action": action,
                "tournament_id": tournament_id,
                "round_id": round_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before": before,
                "after": after,
                "metadata": metadata,
                "created_at": self.now(),
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, tournament_id, round_id, entity_type, entity_id,
                    action, actor, role, reason, before_hash, after_hash,
                    before_json, after_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tournament_id,
                    round_id,
                    entity_type.strip(),
                    entity_id,
                    action.strip(),
                    resolved_actor,
                    resolved_role,
                    reason.strip(),
                    self._hash_payload(before_json),
                    self._hash_payload(after_json),
                    before_json,
                    after_json,
                    metadata_json,
                    self.now(),
                ),
            )
            audit_row_id = int(cursor.lastrowid)
        if not action.startswith("sync_"):
            self.create_sync_outbox_event(
                action=action,
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type=entity_type,
                entity_id=entity_id,
                payload={
                    "audit_event_id": event_id,
                    "action": action,
                    "actor": resolved_actor,
                    "role": resolved_role,
                    "reason": reason,
                    "before": before,
                    "after": after,
                    "metadata": metadata,
                },
            )
        return audit_row_id

    def list_audit_events(
        self,
        tournament_id: int | None = None,
        limit: int = 200,
        action: str = "",
        entity_type: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("tournament_id = ?")
            params.append(int(tournament_id))
        if action:
            conditions.append("action = ?")
            params.append(action.strip())
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM audit_events
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_pairing_snapshot(
        self,
        tournament_id: int,
        round_number: int,
        stage: str,
        snapshot: Mapping[str, Any] | list[Any],
        round_id: int | None = None,
        pairing_system: str = "",
        pairing_engine_version: str = "",
        ruleset_version: str = "",
    ) -> int:
        snapshot_json = self._canonical_json(snapshot)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO pairing_snapshots (
                    tournament_id, round_id, round_number, stage, pairing_system,
                    pairing_engine_version, ruleset_version, snapshot_json,
                    snapshot_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    round_id,
                    int(round_number),
                    stage.strip(),
                    pairing_system.strip(),
                    pairing_engine_version.strip(),
                    ruleset_version.strip(),
                    snapshot_json,
                    self._hash_payload(snapshot_json),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_pairing_snapshots(
        self,
        tournament_id: int,
        round_id: int | None = None,
        round_number: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        if round_number is not None:
            conditions.append("round_number = ?")
            params.append(int(round_number))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM pairing_snapshots
                WHERE {' AND '.join(conditions)}
                ORDER BY round_number ASC, stage ASC, id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_standings_snapshot(
        self,
        tournament_id: int,
        round_id: int,
        round_number: int,
        standings: list[dict[str, Any]],
    ) -> int:
        standings_json = self._canonical_json(standings)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO standings_snapshots (
                    tournament_id, round_id, round_number, standings_json,
                    snapshot_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament_id, round_id) DO UPDATE SET
                    standings_json = excluded.standings_json,
                    snapshot_hash = excluded.snapshot_hash,
                    created_at = excluded.created_at
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(round_number),
                    standings_json,
                    self._hash_payload(standings_json),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_standings_snapshots(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM standings_snapshots
                WHERE tournament_id = ?
                ORDER BY round_number ASC, id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def supersede_standings_snapshot(
        self,
        tournament_id: int,
        round_id: int,
        reason: str,
    ) -> str:
        """Move o retrato vigente da rodada para o historico (ARB-01).

        Devolve o hash do retrato arquivado, ou ``""`` quando nao havia retrato.
        Quem chama grava o novo em seguida — e o hash devolvido e o que entra no
        `before` do evento de auditoria, para a comparacao ficar registrada.
        """
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM standings_snapshots
                WHERE tournament_id = ? AND round_id = ?
                """,
                (int(tournament_id), int(round_id)),
            ).fetchone()
            if not row:
                return ""
            connection.execute(
                """
                INSERT INTO standings_snapshot_history (
                    tournament_id, round_id, round_number, standings_json,
                    snapshot_hash, created_at, superseded_at, superseded_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["tournament_id"]),
                    int(row["round_id"]),
                    int(row["round_number"]),
                    str(row["standings_json"]),
                    str(row["snapshot_hash"]),
                    str(row["created_at"]),
                    self.now(),
                    str(reason or "").strip(),
                ),
            )
            return str(row["snapshot_hash"])

    def list_superseded_standings_snapshots(
        self, tournament_id: int
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM standings_snapshot_history
                WHERE tournament_id = ?
                ORDER BY round_number ASC, superseded_at ASC, id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    # ---- Desbloqueio pontual de correcao (ARB-01) ----------------------- #

    def create_correction_unlock(
        self,
        tournament_id: int,
        round_id: int,
        *,
        reason: str,
        expires_at: str,
        actor: str = "",
        role: str = "",
    ) -> int:
        resolved_actor, resolved_role = (actor.strip(), role.strip())
        if not resolved_actor and not resolved_role:
            resolved_actor, resolved_role = self._operator_context()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO correction_unlocks (
                    tournament_id, round_id, reason, actor, role,
                    granted_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '')
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    str(reason or "").strip(),
                    resolved_actor,
                    resolved_role,
                    self.now(),
                    str(expires_at),
                ),
            )
            return int(cursor.lastrowid)

    def list_correction_unlocks(
        self,
        tournament_id: int,
        round_id: int | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM correction_unlocks
            WHERE tournament_id = ?
        """
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            query += " AND round_id = ?"
            params.append(int(round_id))
        query += " ORDER BY granted_at DESC, id DESC"
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
            return self.rows_to_dicts(rows)

    def revoke_correction_unlocks(self, tournament_id: int, round_id: int) -> int:
        """Revoga os desbloqueios vigentes da rodada. Devolve quantos caíram."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE correction_unlocks
                SET revoked_at = ?
                WHERE tournament_id = ? AND round_id = ? AND revoked_at = ''
                """,
                (self.now(), int(tournament_id), int(round_id)),
            )
            return int(cursor.rowcount or 0)

    def replace_tiebreak_components(
        self,
        tournament_id: int,
        round_id: int | None,
        round_number: int,
        components: list[dict[str, Any]],
    ) -> None:
        with self.connect() as connection:
            if round_id is None:
                connection.execute(
                    "DELETE FROM tiebreak_components WHERE tournament_id = ? AND round_id IS NULL",
                    (int(tournament_id),),
                )
            else:
                connection.execute(
                    "DELETE FROM tiebreak_components WHERE tournament_id = ? AND round_id = ?",
                    (int(tournament_id), int(round_id)),
                )
            rows = [
                (
                    int(tournament_id),
                    int(round_id) if round_id is not None else None,
                    int(round_number),
                    int(item["player_id"]),
                    str(item.get("player_name", "")),
                    str(item["criterion"]),
                    item.get("value"),
                    self._canonical_json(item.get("components", {})),
                    self.now(),
                )
                for item in components
            ]
            if rows:
                connection.executemany(
                    """
                    INSERT INTO tiebreak_components (
                        tournament_id, round_id, round_number, player_id, player_name,
                        criterion, value, components_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def list_tiebreak_components(
        self,
        tournament_id: int,
        player_id: int | None = None,
        round_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if player_id is not None:
            conditions.append("player_id = ?")
            params.append(int(player_id))
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM tiebreak_components
                WHERE {' AND '.join(conditions)}
                ORDER BY round_number DESC, player_name COLLATE NOCASE ASC, criterion ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_public_token(
        self,
        token_hash: str,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        board_number: int,
        expires_at: str,
        purpose: str = "result_submission",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO public_tokens (
                    token_hash, tournament_id, round_id, pairing_id, board_number,
                    purpose, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    token_hash,
                    int(tournament_id),
                    int(round_id),
                    int(pairing_id),
                    int(board_number),
                    purpose.strip() or "result_submission",
                    expires_at,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def create_public_tokens_batch(
        self,
        tokens: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not tokens:
            return []
        now = self.now()
        created = []
        with self.connect() as connection:
            for token in tokens:
                previous = connection.execute(
                    """
                    SELECT id
                    FROM public_tokens
                    WHERE pairing_id = ? AND status = 'active' AND expires_at > ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(token["pairing_id"]), now),
                ).fetchone()
                if previous:
                    connection.execute(
                        "UPDATE public_tokens SET status = 'revoked', used_at = '' WHERE id = ?",
                        (int(previous["id"]),),
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO public_tokens (
                        token_hash, tournament_id, round_id, pairing_id, board_number,
                        purpose, status, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        str(token["token_hash"]),
                        int(token["tournament_id"]),
                        int(token["round_id"]),
                        int(token["pairing_id"]),
                        int(token["board_number"]),
                        str(token.get("purpose") or "result_submission"),
                        str(token["expires_at"]),
                        now,
                    ),
                )
                created.append(
                    {
                        **token,
                        "id": int(cursor.lastrowid),
                        "revoked_previous_token_id": int(previous["id"]) if previous else None,
                    }
                )
        return created

    def get_public_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM public_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            return dict(row) if row else None

    def get_active_public_token_for_pairing(self, pairing_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM public_tokens
                WHERE pairing_id = ? AND status = 'active' AND expires_at > ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(pairing_id), self.now()),
            ).fetchone()
            return dict(row) if row else None

    def update_public_token_status(self, token_id: int, status: str, used_at: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE public_tokens
                SET status = ?, used_at = ?
                WHERE id = ?
                """,
                (status.strip(), used_at, int(token_id)),
            )

    def create_result_submission(
        self,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        token_id: int | None,
        board_number: int,
        submitted_result: str,
        submitter: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO result_submissions (
                    tournament_id, round_id, pairing_id, token_id, board_number,
                    submitted_result, submitter, status, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(pairing_id),
                    token_id,
                    int(board_number),
                    submitted_result.strip(),
                    submitter.strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def get_result_submission(self, submission_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.*,
                    r.status AS round_status,
                    p.result AS current_result
                FROM result_submissions s
                JOIN rounds r ON r.id = s.round_id
                JOIN pairings p ON p.id = s.pairing_id
                WHERE s.id = ?
                """,
                (int(submission_id),),
            ).fetchone()
            return dict(row) if row else None

    def list_result_submissions(
        self,
        tournament_id: int | None = None,
        status: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("s.tournament_id = ?")
            params.append(int(tournament_id))
        if status:
            conditions.append("s.status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    s.*,
                    t.name AS tournament_name,
                    r.number AS round_number,
                    r.status AS round_status,
                    p.result AS current_result
                FROM result_submissions s
                JOIN tournaments t ON t.id = s.tournament_id
                JOIN rounds r ON r.id = s.round_id
                JOIN pairings p ON p.id = s.pairing_id
                {where}
                ORDER BY s.submitted_at DESC, s.id DESC
                LIMIT ?
                """,
                [*params, max(1, min(int(limit or 500), 5000))],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_result_submission_status(
        self,
        submission_id: int,
        status: str,
        reviewer: str = "",
        reason: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE result_submissions
                SET status = ?, reviewer = ?, reason = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status.strip(), reviewer.strip(), reason.strip(), self.now(), int(submission_id)),
            )
