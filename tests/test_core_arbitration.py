from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.core.services import (
    AppError,
)
from tests.support.core_service_base import CoreServiceTestCase


class ArbitrationPhasesTest(CoreServiceTestCase):
    def test_phase0_records_pairing_snapshots_standings_snapshot_and_audit_events(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        pairings = self.db.get_pairings_for_round(round_id)
        for pairing in pairings:
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        self.service.close_round(self.tournament_id, round_id)

        snapshots = self.db.list_pairing_snapshots(self.tournament_id, round_id=round_id)
        input_snapshots = self.db.list_pairing_snapshots(self.tournament_id, round_number=1)
        standings_snapshots = self.db.list_standings_snapshots(self.tournament_id)
        audit_events = self.db.list_audit_events(self.tournament_id, limit=20)
        current_round = self.db.get_round(round_id)

        self.assertTrue(any(item["stage"] == "input" for item in input_snapshots))
        self.assertTrue(any(item["stage"] == "output" for item in snapshots))
        self.assertEqual(1, len(standings_snapshots))
        self.assertTrue(standings_snapshots[0]["snapshot_hash"])
        self.assertEqual("albericus-swiss-1", current_round["pairing_engine_version"])
        self.assertEqual("albericus-2026-phase0", current_round["ruleset_version"])
        self.assertIn("round_generated", {item["action"] for item in audit_events})
        self.assertIn("round_closed", {item["action"] for item in audit_events})
        self.assertIn("backup_created", {item["action"] for item in audit_events})

    def test_phase1_preview_next_round_does_not_persist(self) -> None:
        self._create_players(4)

        preview = self.service.preview_next_round(self.tournament_id)

        self.assertEqual("individual", preview["competition_type"])
        self.assertEqual(1, preview["round_number"])
        self.assertEqual(2, len(preview["pairings"]))
        self.assertEqual([], self.db.list_rounds(self.tournament_id))
        self.assertEqual([], self.db.list_pairing_snapshots(self.tournament_id))
        self.assertEqual([], self.db.list_audit_events(self.tournament_id))
        self.assertEqual([], list(self.backup_dir.glob("*.db")))

    def test_phase1_preview_flags_bye_alert(self) -> None:
        self._create_players(3)

        preview = self.service.preview_next_round(self.tournament_id)

        self.assertEqual(2, len(preview["pairings"]))
        self.assertGreaterEqual(preview["alerts_count"], 1)
        self.assertTrue(any("Bye" in pairing["alerts"] for pairing in preview["pairings"]))

    def test_phase2_arbitration_dashboard_reports_pending_ready_and_corrections(self) -> None:
        self._create_players(2)
        empty_dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(0, empty_dashboard["metrics"]["generated_rounds"])
        self.assertIn("Nenhuma rodada gerada", empty_dashboard["alerts"][0])

        round_data = self.service.generate_next_round(self.tournament_id)
        pending_dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(1, pending_dashboard["metrics"]["pending_results"])
        self.assertFalse(pending_dashboard["metrics"]["ready_to_close"])
        self.assertEqual(1, len(pending_dashboard["pending_items"]))
        self.assertEqual(1, pending_dashboard["pending_items"][0]["board"])
        self.assertTrue(pending_dashboard["pending_items"][0]["pairing_id"])

        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        ready_dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(0, ready_dashboard["metrics"]["pending_results"])
        self.assertTrue(ready_dashboard["metrics"]["ready_to_close"])
        self.assertEqual([], ready_dashboard["pending_items"])

        self.service.close_round(self.tournament_id, int(round_data["id"]))
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        settings["allow_dangerous_changes"] = 1
        self.db.save_tournament_settings(self.tournament_id, settings)
        self.service.update_result(self.tournament_id, int(pairing["id"]), "0-1")

        corrected_dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(1, corrected_dashboard["metrics"]["corrections"])
        self.assertTrue(corrected_dashboard["metrics"]["can_preview_next_round"])

    def test_phase2_arbitration_dashboard_respects_pending_items_limit(self) -> None:
        self._create_players(24)
        self.service.generate_next_round(self.tournament_id)

        dashboard = self.service.arbitration_dashboard(self.tournament_id, pending_limit=10)

        self.assertEqual(12, dashboard["metrics"]["pending_results"])
        self.assertEqual(10, len(dashboard["pending_items"]))
        self.assertEqual(list(range(1, 11)), [item["board"] for item in dashboard["pending_items"]])

    def test_phase2_arbitration_dashboard_searches_exact_pending_board_before_limit(self) -> None:
        self._create_players(120)
        self.service.generate_next_round(self.tournament_id)

        dashboard = self.service.arbitration_dashboard(
            self.tournament_id,
            pending_limit=50,
            pending_query="60",
        )

        self.assertEqual(60, dashboard["metrics"]["pending_results"])
        self.assertEqual([60], [item["board"] for item in dashboard["pending_items"]])

    def test_phase2_arbitration_dashboard_round_clock_freezes_when_round_closes(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE rounds SET created_at = '2026-05-31 10:00:00' WHERE id = ?",
                (int(round_data["id"]),),
            )

        with mock.patch.object(self.db, "now", return_value="2026-05-31 11:30:00"):
            open_dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual("em_andamento", open_dashboard["metrics"]["round_clock_status"])
        self.assertEqual("31/05 10:00", open_dashboard["metrics"]["round_started_label"])
        self.assertEqual("01:30:00", open_dashboard["metrics"]["round_duration_label"])

        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        with mock.patch.object(self.db, "now", return_value="2026-05-31 12:00:00"):
            self.service.close_round(self.tournament_id, int(round_data["id"]))
        with mock.patch.object(self.db, "now", return_value="2026-05-31 14:00:00"):
            closed_dashboard = self.service.arbitration_dashboard(self.tournament_id)

        self.assertEqual("2026-05-31 12:00:00", self.db.get_round(int(round_data["id"]))["closed_at"])
        self.assertEqual("fechada", closed_dashboard["metrics"]["round_clock_status"])
        self.assertEqual("02:00:00", closed_dashboard["metrics"]["round_duration_label"])

    def test_phase2_round_close_blocks_arbitration_decision_issues(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        submission = self.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertFalse(dashboard["metrics"]["ready_to_close"])
        self.assertEqual(1, dashboard["metrics"]["blocking_issues"])
        with self.assertRaisesRegex(AppError, "pendencias de arbitragem bloqueantes"):
            self.service.close_round(self.tournament_id, int(round_data["id"]))

        self.qr_result_service.reject_submission(int(submission["id"]), reviewer="Arbitro", reason="Resultado lancado no desktop.")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        self.assertEqual("closed", self.db.get_round(int(round_data["id"]))["status"])

    def test_phase2_round_close_allows_attention_only_clock_issue(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="white",
            seconds_remaining=0,
            note="Apenas alerta conferido em mesa.",
        )

        dashboard = self.service.arbitration_dashboard(self.tournament_id)
        self.assertTrue(dashboard["metrics"]["ready_to_close"])
        self.assertEqual(0, dashboard["metrics"]["blocking_issues"])

        self.service.close_round(self.tournament_id, int(round_data["id"]))
        self.assertEqual("closed", self.db.get_round(int(round_data["id"]))["status"])

    def test_phase2_arbitration_issue_filters_are_pure_and_search_payload_board(self) -> None:
        issues = [
            {
                "severity": "decision",
                "source": "qr",
                "kind": "result_submission",
                "title": "Resultado QR pendente - mesa 17",
                "detail": "Resultado enviado: 1-0",
                "payload": {"board_number": 17},
            },
            {
                "severity": "decision",
                "source": "sync",
                "kind": "remote_rejected",
                "title": "Evento remoto rejeitado",
                "detail": "Conferir conflito",
                "payload": {"board_number": 42},
            },
            {
                "severity": "attention",
                "source": "clock",
                "kind": "flag_fall",
                "title": "Queda de seta registrada",
                "detail": "Mesa decisiva",
                "payload": {"board_number": 3},
            },
        ]

        self.assertEqual(issues, self.service.filter_arbitration_issues(issues))
        self.assertEqual([issues[0], issues[1]], self.service.filter_arbitration_issues(issues, "decision"))
        self.assertEqual([issues[0]], self.service.filter_arbitration_issues(issues, "qr"))
        self.assertEqual([issues[1]], self.service.filter_arbitration_issues(issues, query="42"))
        self.assertEqual([issues[2]], self.service.filter_arbitration_issues(issues, query="mesa decisiva"))
        self.assertEqual(3, len(issues))

    def test_phase0_audits_dangerous_result_correction(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        settings["allow_dangerous_changes"] = 1
        self.db.save_tournament_settings(self.tournament_id, settings)

        self.service.update_result(self.tournament_id, int(pairing["id"]), "0-1")

        corrections = self.db.list_audit_events(
            self.tournament_id,
            action="result_corrected",
            entity_type="pairing",
        )
        self.assertEqual(1, len(corrections))
        self.assertIn("1-0", corrections[0]["before_json"])
        self.assertIn("0-1", corrections[0]["after_json"])
        self.assertTrue(corrections[0]["before_hash"])
        self.assertTrue(corrections[0]["after_hash"])

    def test_phase8_audit_events_enqueue_sync_outbox_and_network_failure_keeps_pending(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        outbox = self.db.list_sync_outbox(status="pending", limit=20)
        round_generated = next(item for item in outbox if item["action"] == "round_generated")

        with mock.patch("src.services.sync_service.urlopen", side_effect=OSError("offline")):
            summary = self.sync_service.sync_pending("https://sync.example.test", limit=1)

        pending = self.db.list_sync_outbox(status="pending", limit=20)
        failed_event = next(item for item in pending if int(item["attempts"]) == 1)
        self.assertEqual(int(round_data["id"]), int(round_generated["round_id"]))
        self.assertEqual({"sent": 1, "synced": 0, "rejected": 0, "failed": 1}, summary)
        self.assertEqual("pending", failed_event["status"])
        self.assertEqual(1, failed_event["attempts"])
        self.assertIn("offline", failed_event["last_error"])

    def test_phase8_device_registration_validates_role_name_and_revoke_target(self) -> None:
        with self.assertRaisesRegex(AppError, "nome do dispositivo"):
            self.sync_service.register_device("   ", role="assistant")
        with self.assertRaisesRegex(AppError, "Perfil"):
            self.sync_service.register_device("Mesa 1", role="admin")

        device = self.sync_service.register_device(" Mesa 1 ", role="assistant", device_id=" device-board-1 ")
        self.sync_service.revoke_device("device-board-1")

        revoked = next(item for item in self.sync_service.list_devices() if item["device_id"] == "device-board-1")
        self.assertEqual("Mesa 1", device["name"])
        self.assertEqual("revoked", revoked["status"])
        with self.assertRaisesRegex(AppError, "nao encontrado"):
            self.sync_service.revoke_device("missing-device")

    def test_phase8_sync_pending_validates_target_url_limit_and_timeout(self) -> None:
        with self.assertRaisesRegex(AppError, "URL"):
            self.sync_service.sync_pending("sync.example.test")
        with self.assertRaisesRegex(AppError, "Limite"):
            self.sync_service.sync_pending("https://sync.example.test", limit=0)
        with self.assertRaisesRegex(AppError, "Timeout"):
            self.sync_service.sync_pending("https://sync.example.test", timeout_seconds=0)

        self.assertEqual([], self.db.list_sync_outbox(status="rejected", limit=20))

    def test_phase8_remote_rejection_ignores_invalid_audit_scope(self) -> None:
        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-invalid-scope",
                "device_id": "unknown-device",
                "tournament_id": 999999,
                "round_id": 999999,
                "entity_type": "pairing",
                "entity_id": 999999,
                "action": "result_updated",
                "payload": {"result": "1-0"},
            }
        )

        rejected = self.db.list_audit_events(action="sync_remote_rejected")
        self.assertEqual("rejected", response["status"])
        self.assertTrue(rejected)
        self.assertIsNone(rejected[0]["tournament_id"])
        self.assertIsNone(rejected[0]["round_id"])

    def test_phase8_remote_result_rejects_malformed_ids_without_exception(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        bad_pairing = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-bad-pairing",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": "abc",
                "action": "result_updated",
                "payload": {"result": "1-0"},
            }
        )
        bad_tournament = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-bad-tournament",
                "device_id": remote_device["device_id"],
                "tournament_id": "abc",
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "1-0"},
            }
        )
        bad_round = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-bad-round",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": "abc",
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "1-0"},
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        self.assertEqual("rejected", bad_pairing["status"])
        self.assertEqual("rejected", bad_tournament["status"])
        self.assertEqual("rejected", bad_round["status"])
        self.assertEqual("", unchanged["result"])

    def test_phase8_remote_result_rejects_malformed_payload_without_exception(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-bad-payload",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": ["1-0"],
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("rejected", response["status"])
        self.assertEqual("", unchanged["result"])
        self.assertTrue(any("Payload remoto invalido" in item["reason"] for item in rejected))

    def test_phase8_remote_result_conflict_does_not_change_closed_round(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))

        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-event-1",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "0-1"},
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("conflict", response["status"])
        self.assertEqual("1-0", unchanged["result"])
        self.assertTrue(rejected)
        self.assertIn("Rodada fechada", rejected[0]["reason"])

    def test_phase8_remote_result_rejects_payload_hash_mismatch(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-event-tampered",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "0-1"},
                "payload_hash": self.db._hash_payload({"result": "1-0"}),
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("rejected", response["status"])
        self.assertEqual("", unchanged["result"])
        self.assertTrue(rejected)
        self.assertIn("Hash do payload", rejected[0]["reason"])

    def test_phase8_remote_result_cannot_clear_pairing_result(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-event-clear",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": ""},
                "payload_hash": self.db._hash_payload({"result": ""}),
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("rejected", response["status"])
        self.assertEqual("1-0", unchanged["result"])
        self.assertTrue(rejected)
        self.assertIn("Resultado remoto invalido", rejected[0]["reason"])

    def test_phase8_remote_result_conflict_does_not_override_open_desktop_result(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        response = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-open-conflict",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "0-1"},
                "payload_hash": self.db._hash_payload({"result": "0-1"}),
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("conflict", response["status"])
        self.assertEqual("1-0", unchanged["result"])
        self.assertTrue(any("outro resultado" in item["reason"] for item in rejected))

    def test_phase8_remote_result_rejects_tournament_or_round_mismatch(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        wrong_tournament = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-event-wrong-tournament",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id + 999,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "1-0"},
                "payload_hash": self.db._hash_payload({"result": "1-0"}),
            }
        )
        wrong_round = self.sync_service.apply_remote_event(
            {
                "event_id": "remote-event-wrong-round",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]) + 999,
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "0-1"},
                "payload_hash": self.db._hash_payload({"result": "0-1"}),
            }
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        rejected = self.db.list_audit_events(self.tournament_id, action="sync_remote_rejected")
        self.assertEqual("rejected", wrong_tournament["status"])
        self.assertEqual("rejected", wrong_round["status"])
        self.assertEqual("", unchanged["result"])
        self.assertTrue(any("outra rodada" in item["reason"] for item in rejected))

    def test_phase8_pending_event_syncs_when_server_returns(self) -> None:
        event_id = self.db.create_sync_outbox_event(
            action="heartbeat",
            tournament_id=self.tournament_id,
            entity_type="tournament",
            entity_id=self.tournament_id,
            payload={"status": "local_ok"},
        )
        event = self.db.list_sync_outbox(status="pending", limit=1)[0]

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            @staticmethod
            def read() -> bytes:
                return b'{"status": "accepted"}'

        with mock.patch("src.services.sync_service.urlopen", return_value=FakeResponse()):
            summary = self.sync_service.sync_pending("https://sync.example.test", limit=1)

        synced = self.db.list_sync_outbox(status="synced", limit=20)
        self.assertEqual({"sent": 1, "synced": 1, "rejected": 0, "failed": 0}, summary)
        self.assertEqual(event["event_id"], next(item["event_id"] for item in synced if item["id"] == event_id))

    def test_phase9_manual_clock_event_is_audited_without_changing_result(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        event = self.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="white",
            seconds_remaining=0,
            note="Seta caiu, aguardando decisao do arbitro.",
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        audit_events = self.db.list_audit_events(self.tournament_id, action="clock_event_logged")
        alerts = self.clock_integration_service.anomaly_alerts(self.tournament_id)
        self.assertEqual("flag_fall", event["event_type"])
        self.assertEqual("", unchanged["result"])
        self.assertTrue(audit_events)
        self.assertTrue(any("Apenas alerta" in alert["recommendation"] for alert in alerts))

    def test_phase9_clock_event_rejects_invalid_side_and_negative_time(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        with self.assertRaisesRegex(AppError, "Lado"):
            self.clock_integration_service.record_manual_event(
                self.tournament_id,
                "time_warning",
                pairing_id=int(pairing["id"]),
                side="red",
                seconds_remaining=30,
            )
        with self.assertRaisesRegex(AppError, "Segundos"):
            self.clock_integration_service.record_manual_event(
                self.tournament_id,
                "time_warning",
                pairing_id=int(pairing["id"]),
                side="white",
                seconds_remaining=-1,
            )

        self.assertEqual([], self.clock_integration_service.list_clock_events(self.tournament_id))

    def test_phase9_clock_event_validates_player_tournament_and_pairing(self) -> None:
        player_ids = self._create_players(2)
        outside_tournament_id = self.db.create_tournament("Outro torneio", rounds_count=1)
        outside_player_id = self.db.create_player(outside_tournament_id, name="Jogador externo", rating=1500)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        with self.assertRaisesRegex(AppError, "torneio selecionado"):
            self.clock_integration_service.record_manual_event(
                self.tournament_id,
                "manual_note",
                player_id=outside_player_id,
            )
        with self.assertRaisesRegex(AppError, "mesa informada"):
            self.clock_integration_service.record_manual_event(
                self.tournament_id,
                "manual_note",
                pairing_id=int(pairing["id"]),
                player_id=outside_player_id,
            )

        event = self.clock_integration_service.record_manual_event(
            self.tournament_id,
            "manual_note",
            pairing_id=int(pairing["id"]),
            player_id=player_ids[0],
        )

        self.assertEqual(player_ids[0], event["player_id"])
        self.assertEqual(1, len(self.clock_integration_service.list_clock_events(self.tournament_id)))

    def test_phase9_plugin_events_are_optional_and_never_apply_result(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        class FakeClockPlugin:
            plugin_id = "fake_clock"
            label = "Relogio falso"

            def normalize_event(self, raw_event: dict[str, object]) -> dict[str, object]:
                return {**raw_event, "event_type": "absence", "note": "Ausencia detectada pelo dispositivo."}

        self.clock_integration_service.register_plugin(FakeClockPlugin())
        disabled = self.clock_integration_service.record_plugin_event(
            "fake_clock",
            {
                "tournament_id": self.tournament_id,
                "pairing_id": int(pairing["id"]),
                "device_id": "clock-1",
                "result": "0-1",
            },
        )
        self.db.save_app_settings({"device_integrations_enabled": "1"})
        accepted = self.clock_integration_service.record_plugin_event(
            "fake_clock",
            {
                "tournament_id": self.tournament_id,
                "pairing_id": int(pairing["id"]),
                "device_id": "clock-1",
                "result": "0-1",
            },
        )

        unchanged = self.db.get_pairing(int(pairing["id"]))
        self.assertEqual("ignored", disabled["status"])
        self.assertEqual("absence", accepted["event_type"])
        self.assertEqual("", unchanged["result"])

    def test_phase9_notifications_are_optional_audited_queue_only(self) -> None:
        skipped = self.clock_integration_service.queue_notification(
            "EMAIL",
            " arbitro@example.com ",
            " Rodada publicada. ",
            tournament_id=self.tournament_id,
        )
        self.db.save_app_settings({"notifications_enabled": "1"})
        queued = self.clock_integration_service.queue_notification(
            "sms",
            "+5500000000000",
            "Mesa 1 requer atencao.",
            tournament_id=self.tournament_id,
        )

        skipped_events = self.db.list_audit_events(self.tournament_id, action="notification_skipped")
        queued_events = self.db.list_audit_events(self.tournament_id, action="notification_queued")
        self.assertEqual("skipped", skipped["status"])
        self.assertEqual("queued", queued["status"])
        self.assertTrue(skipped_events)
        self.assertTrue(queued_events)

    def test_phase9_notification_queue_validates_channel_recipient_and_message(self) -> None:
        self.db.save_app_settings({"notifications_enabled": "1"})

        with self.assertRaisesRegex(AppError, "Canal"):
            self.clock_integration_service.queue_notification("telegram", "arbitro@example.com", "Rodada publicada")
        with self.assertRaisesRegex(AppError, "destinatario"):
            self.clock_integration_service.queue_notification("email", "", "Rodada publicada")
        with self.assertRaisesRegex(AppError, "mensagem"):
            self.clock_integration_service.queue_notification("email", "arbitro@example.com", " ")

        self.assertEqual([], self.db.list_audit_events(self.tournament_id, action="notification_queued"))

    def test_phase0_exports_tournament_audit_report(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))

        output_path = Path(self.temp_dir.name) / "auditoria.csv"
        self.export_service.export_tournament_audit(self.tournament_id, output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertIn("Data/hora;Acao;Entidade", content)
        self.assertIn("round_generated", content)
        self.assertIn("round_closed", content)

if __name__ == "__main__":
    unittest.main()
