from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from src.core.services import (
    AppError,
)
from src.services.result_server import LocalResultServer
from tests.support.core_service_base import CoreServiceTestCase


class QrPortalTest(CoreServiceTestCase):
    def test_phase2_arbitration_issues_aggregate_qr_sync_and_clock_alerts(self) -> None:
        self._create_players(2)
        remote_device = self.sync_service.register_device("Mesa 1", role="assistant", device_id="device-board-1")
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        self.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")
        self.sync_service.apply_remote_event(
            {
                "event_id": "remote-invalid-result",
                "device_id": remote_device["device_id"],
                "tournament_id": self.tournament_id,
                "round_id": int(round_data["id"]),
                "entity_type": "pairing",
                "entity_id": int(pairing["id"]),
                "action": "result_updated",
                "payload": {"result": "BYE"},
                "payload_hash": self.db._hash_payload({"result": "BYE"}),
            }
        )
        self.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="white",
            seconds_remaining=0,
            note="Conferir mesa.",
        )

        issues = self.service.arbitration_issues(self.tournament_id)
        sources = {item["source"] for item in issues["issues"]}

        self.assertEqual(3, issues["metrics"]["total"])
        self.assertEqual(1, issues["metrics"]["qr_pending"])
        self.assertEqual(1, issues["metrics"]["sync_conflicts"])
        self.assertEqual(1, issues["metrics"]["clock_alerts"])
        self.assertEqual({"qr", "sync", "clock"}, sources)
        self.assertTrue(all(item.get("payload") for item in issues["issues"]))
        self.assertTrue(all(item.get("issue_key") for item in issues["issues"]))

    def test_phase2_arbitration_issue_acknowledgement_hides_non_qr_issue(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="black",
            seconds_remaining=0,
            note="Mesa conferida.",
        )

        issues = self.service.arbitration_issues(self.tournament_id)
        clock_issue = next(item for item in issues["issues"] if item["source"] == "clock")
        self.service.acknowledge_arbitration_issue(self.tournament_id, str(clock_issue["issue_key"]))

        refreshed = self.service.arbitration_issues(self.tournament_id)
        audit_events = self.db.list_audit_events(
            self.tournament_id,
            action="arbitration_issue_acknowledged",
            entity_type="arbitration_issue",
        )

        self.assertEqual(0, refreshed["metrics"]["total"])
        self.assertEqual(1, len(audit_events))
        self.assertIn(str(clock_issue["issue_key"]), audit_events[0]["after_json"])

    def test_phase2_arbitration_issue_acknowledgement_rejects_qr_issue(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        self.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")

        issues = self.service.arbitration_issues(self.tournament_id)
        qr_issue = next(item for item in issues["issues"] if item["source"] == "qr")

        with self.assertRaisesRegex(AppError, "Use Aprovar QR ou Rejeitar QR"):
            self.service.acknowledge_arbitration_issue(self.tournament_id, str(qr_issue["issue_key"]))

    def test_phase4_qr_result_submission_requires_approval_and_audits_review(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        token_payload = self.qr_result_service.result_url_for_pairing(
            self.tournament_id,
            int(pairing["id"]),
            base_url="http://localhost:8765",
        )
        submission = self.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")

        self.assertEqual("submitted", submission["status"])
        self.assertEqual("", self.db.get_pairing(int(pairing["id"]))["result"])
        self.assertEqual(1, len(self.qr_result_service.pending_submissions(self.tournament_id)))

        self.qr_result_service.approve_submission(int(submission["id"]), reviewer="Arbitro")

        self.assertEqual("1-0", self.db.get_pairing(int(pairing["id"]))["result"])
        self.assertEqual([], self.qr_result_service.pending_submissions(self.tournament_id))
        actions = {event["action"] for event in self.db.list_audit_events(self.tournament_id, limit=20)}
        self.assertIn("result_submitted", actions)
        self.assertIn("result_submission_approved", actions)

    def test_phase4_qr_result_rejects_duplicate_pending_submission(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))

        first = self.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")

        with self.assertRaisesRegex(AppError, "envio pendente"):
            self.qr_result_service.submit_result(token_payload["token"], "0-1", submitter="Mesa 1")
        self.assertEqual(1, len(self.qr_result_service.pending_submissions(self.tournament_id)))

        self.qr_result_service.reject_submission(int(first["id"]), reviewer="Arbitro", reason="Conferir novamente")
        second = self.qr_result_service.submit_result(token_payload["token"], "0-1", submitter="Mesa 1")

        self.assertEqual("submitted", second["status"])
        self.assertEqual(1, len(self.qr_result_service.pending_submissions(self.tournament_id)))

    def test_phase4_qr_new_link_revokes_previous_active_token_for_pairing(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        first = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        second = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))

        first_row = self.db.get_public_token_by_hash(self.qr_result_service._token_hash(first["token"]))
        second_row = self.db.get_public_token_by_hash(self.qr_result_service._token_hash(second["token"]))
        with self.assertRaisesRegex(AppError, "utilizado ou cancelado"):
            self.qr_result_service.submit_result(first["token"], "1-0")
        submission = self.qr_result_service.submit_result(second["token"], "1-0")

        self.assertEqual("revoked", first_row["status"])
        self.assertEqual("active", second_row["status"])
        self.assertEqual("submitted", submission["status"])

    def test_phase4_qr_batch_links_revoke_previous_token_and_audit_round(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        first_pairing = pairings[0]
        previous = self.qr_result_service.result_url_for_pairing(
            self.tournament_id,
            int(first_pairing["id"]),
        )

        urls = self.qr_result_service.result_urls_for_pairings(
            self.tournament_id,
            [{**pairing, "tournament_id": self.tournament_id} for pairing in pairings],
        )

        previous_row = self.db.get_public_token_by_hash(self.qr_result_service._token_hash(previous["token"]))
        active_tokens = []
        for pairing_id, url in urls.items():
            token = parse_qs(urlparse(url).query)["token"][0]
            active_tokens.append(self.qr_result_service._validate_token(token))
            self.assertEqual(pairing_id, int(active_tokens[-1]["pairing_id"]))
        audit_events = self.db.list_audit_events(self.tournament_id, limit=20)
        batch_event = next(event for event in audit_events if event["action"] == "public_result_tokens_created")

        self.assertEqual("revoked", previous_row["status"])
        self.assertEqual(2, len(active_tokens))
        self.assertIn('"tokens_count":2', batch_event["after_json"])

    def test_phase4_qr_does_not_override_desktop_result(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))

        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        with self.assertRaisesRegex(AppError, "resultado registrado no desktop"):
            self.qr_result_service.submit_result(token_payload["token"], "0-1")

        self.service.update_result(self.tournament_id, int(pairing["id"]), "")
        submission = self.qr_result_service.submit_result(token_payload["token"], "0-1")
        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

        with self.assertRaisesRegex(AppError, "outro resultado registrado"):
            self.qr_result_service.approve_submission(int(submission["id"]), reviewer="Arbitro")
        self.assertEqual("1-0", self.db.get_pairing(int(pairing["id"]))["result"])

    def test_phase4_qr_token_rejects_tampering_expiration_closed_round_and_rejection(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))

        with self.assertRaisesRegex(AppError, "Assinatura"):
            self.qr_result_service.submit_result(token_payload["token"][:-1] + "x", "1-0")

        submission = self.qr_result_service.submit_result(token_payload["token"], "0-1")
        self.qr_result_service.reject_submission(int(submission["id"]), reviewer="Arbitro", reason="Conferido na mesa")
        self.assertEqual("", self.db.get_pairing(int(pairing["id"]))["result"])
        rejected = self.db.get_result_submission(int(submission["id"]))
        self.assertEqual("rejected", rejected["status"])

        expired = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]), expires_minutes=1)
        token_row = self.db.get_public_token_by_hash(self.qr_result_service._token_hash(expired["token"]))
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE public_tokens SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
                (int(token_row["id"]),),
            )
        with self.assertRaisesRegex(AppError, "expirado"):
            self.qr_result_service.submit_result(expired["token"], "1-0")

        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        closed_token = self.qr_result_service.result_url_for_pairing
        with self.assertRaisesRegex(AppError, "rodada fechada"):
            closed_token(self.tournament_id, int(pairing["id"]))

    def test_phase4_local_result_server_escapes_mobile_html(self) -> None:
        form_html = LocalResultServer._result_form_html("abc'><script>alert(1)</script>")
        response_html = LocalResultServer._result_response_html("Erro <script>alert(1)</script>")

        self.assertNotIn("<script>", form_html)
        self.assertIn("abc&#x27;&gt;&lt;script&gt;alert(1)&lt;/script&gt;", form_html)
        self.assertNotIn("<script>", response_html)
        self.assertIn("Erro &lt;script&gt;alert(1)&lt;/script&gt;", response_html)

    def test_phase5_public_portal_payload_json_and_html_hide_sensitive_data(self) -> None:
        first_player = self.db.create_player(
            self.tournament_id,
            name="Jogador Publico",
            rating=1800,
            club="Clube",
            category="ABS",
            birth_date="2010-01-02",
            fide_id="123456",
        )
        self.db.create_player(
            self.tournament_id,
            name="Jogador Visitante",
            rating=1700,
            club="Clube",
            category="ABS",
        )
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(round_data["id"])[0]
        self.db.update_pairing_result(pairing["id"], "1-0")
        self.service.close_round(self.tournament_id, round_data["id"])
        self.db.save_app_settings({"live_portal_notice": "Resultados sujeitos a homologacao."})
        self.db.save_tournament_settings(
            self.tournament_id,
            {"contact_email": "arbitro@example.com", "comments": "Comentario interno"},
        )

        payload = self.export_service.public_tournament_payload(self.tournament_id, mode="publico")
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual("publico", payload["mode"])
        self.assertEqual("Resultados sujeitos a homologacao.", payload["notice"])
        self.assertEqual("Jogador Publico", payload["players"][0]["name"])
        self.assertNotIn("arbitro@example.com", serialized)
        self.assertNotIn("Comentario interno", serialized)
        self.assertNotIn("2010-01-02", serialized)
        self.assertNotIn("123456", serialized)
        self.assertEqual(first_player, payload["players"][0]["id"])

        output_path = Path(self.temp_dir.name) / "publico.json"
        self.export_service.export_public_json(self.tournament_id, output_path)
        exported = output_path.read_text(encoding="utf-8")
        self.assertIn("Jogador Publico", exported)
        self.assertNotIn("arbitro@example.com", exported)

        html = self.export_service.live_portal_html(self.tournament_id, mode="publico")
        self.assertIn("Albericus Live", html)
        self.assertIn("Rodada atual", html)
        self.assertIn("Fichas publicas", html)
        self.assertNotIn("arbitro@example.com", html)

    def test_pairings_wall_pdf_includes_valid_qr_only_for_open_round(self) -> None:
        self.db.create_player(self.tournament_id, name="Ana Silva", rating=1810)
        self.db.create_player(self.tournament_id, name="Bruno Souza", rating=1720)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        open_path = Path(self.temp_dir.name) / "mural_aberto.pdf"
        captured_urls: list[str] = []

        original_qr_urls = self.export_service._qr_result_urls

        def capture_qr_urls(tournament_id: int, pairings: list[dict[str, object]]) -> dict[int, str]:
            urls = original_qr_urls(tournament_id, pairings)
            captured_urls.extend(urls.values())
            return urls

        with mock.patch.object(self.export_service, "_qr_result_urls", side_effect=capture_qr_urls):
            self.export_service.export_pairings(int(round_data["id"]), open_path)

        from urllib.parse import parse_qs, urlparse

        from pypdf import PdfReader

        open_text = "\n".join(page.extract_text() or "" for page in PdfReader(open_path).pages)
        token = parse_qs(urlparse(captured_urls[0]).query)["token"][0]
        token_row = self.qr_result_service._validate_token(token)
        self.assertEqual(1, len(captured_urls))
        self.assertEqual(int(pairing["id"]), int(token_row["pairing_id"]))
        self.assertIn("Rodada aberta - QR para envio de resultado", open_text)
        self.assertIn("Ana Silva", open_text)
        self.assertIn("Bruno Souza", open_text)

        self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        closed_path = Path(self.temp_dir.name) / "mural_fechado.pdf"
        with mock.patch.object(self.export_service, "_qr_result_urls") as qr_urls:
            self.export_service.export_pairings(int(round_data["id"]), closed_path)

        closed_text = "\n".join(page.extract_text() or "" for page in PdfReader(closed_path).pages)
        qr_urls.assert_called_once_with(self.tournament_id, [])
        self.assertIn("Rodada fechada - QR desativado", closed_text)

    def test_table_cards_pdf_exports_configured_range_with_optional_qr(self) -> None:
        for index in range(6):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index,
            )
        round_data = self.service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "cartoes.pdf"
        captured_pairing_ids: list[int] = []
        original_qr_urls = self.export_service._qr_result_urls

        def capture_qr_urls(tournament_id: int, pairings: list[dict[str, object]]) -> dict[int, str]:
            captured_pairing_ids.extend(int(pairing["id"]) for pairing in pairings)
            return original_qr_urls(tournament_id, pairings)

        with mock.patch.object(self.export_service, "_qr_result_urls", side_effect=capture_qr_urls):
            self.export_service.export_table_cards(
                output_path,
                1,
                6,
                round_id=int(round_data["id"]),
                include_qr=True,
            )

        from pypdf import PdfReader

        reader = PdfReader(output_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        self.assertEqual(2, len(reader.pages))
        self.assertEqual([int(pairing["id"]) for pairing in pairings], captured_pairing_ids)
        self.assertIn("MESA", text)
        self.assertIn("1", text)
        self.assertIn("6", text)
        self.assertIn("Rodada 1", text)
        self.assertIn("QR para enviar resultado", text)

        for pairing in pairings:
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        closed_path = Path(self.temp_dir.name) / "cartoes_fechados.pdf"
        with mock.patch.object(self.export_service, "_qr_result_urls") as qr_urls:
            self.export_service.export_table_cards(
                closed_path,
                1,
                2,
                round_id=int(round_data["id"]),
                include_qr=True,
            )
        closed_text = "\n".join(page.extract_text() or "" for page in PdfReader(closed_path).pages)
        qr_urls.assert_called_once_with(self.tournament_id, [])
        self.assertIn("QR indisponivel para esta mesa", closed_text)

if __name__ == "__main__":
    unittest.main()
