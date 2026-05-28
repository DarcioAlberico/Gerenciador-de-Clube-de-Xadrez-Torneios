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

class PairingService:
    MAX_EXHAUSTIVE_PAIRING_PLAYERS = 16
    MAX_EXHAUSTIVE_PAIRING_TEAMS = 16
    REPEAT_PAIRING_PENALTY = 1_000_000
    SCORE_GROUP_FLOAT_PENALTY = 10_000
    SCORE_DIFF_PENALTY = 1_000
    PAIRING_ENGINE_VERSION = "albericus-swiss-1"
    TEAM_PAIRING_ENGINE_VERSION = "albericus-team-swiss-1"
    RULESET_VERSION = "albericus-2026-phase0"

    def __init__(self, db: Database) -> None:
        self.db = db

    def preview_next_round(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            plan = self._team_next_round_plan(tournament_id, tournament)
            return self._team_preview_payload(tournament_id, tournament, plan)
        plan = self._individual_next_round_plan(tournament_id, tournament)
        return self._individual_preview_payload(tournament_id, tournament, plan)

    def arbitration_dashboard(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        rounds = sorted(self.db.list_rounds(tournament_id), key=lambda item: int(item["number"]))
        latest_round = rounds[-1] if rounds else None
        players = self.db.list_players(tournament_id, active_only=False)
        absent_players = [player for player in players if player.get("player_status") == "absent"]
        corrections = self.db.list_audit_events(tournament_id, limit=5000)
        correction_count = sum(1 for event in corrections if "corrected" in str(event.get("action", "")))
        submitted_results = len(self.db.list_result_submissions(tournament_id=tournament_id, status="submitted"))
        generated_rounds = len(rounds)
        closed_rounds = sum(1 for item in rounds if item.get("status") == "closed")
        metrics: dict[str, Any] = {
            "tournament_name": tournament.get("name", ""),
            "competition_type": tournament.get("competition_type", "individual"),
            "rounds_count": int(tournament.get("rounds_count") or 0),
            "generated_rounds": generated_rounds,
            "closed_rounds": closed_rounds,
            "absent_players": len(absent_players),
            "corrections": correction_count,
            "latest_round_number": int(latest_round["number"]) if latest_round else 0,
            "latest_round_status": latest_round.get("status", "") if latest_round else "sem_rodadas",
            "pending_results": 0,
            "submitted_results": submitted_results,
            "byes": 0,
            "blocking_issues": 0,
            "ready_to_close": False,
            "can_preview_next_round": False,
            "preview_alerts": 0,
        }
        alerts: list[str] = []
        if latest_round:
            if tournament.get("competition_type") == "team":
                metrics.update(self._team_round_dashboard_metrics(int(latest_round["id"])))
            else:
                metrics.update(self._individual_round_dashboard_metrics(int(latest_round["id"])))
            if latest_round.get("status") != "closed":
                if metrics["pending_results"]:
                    alerts.append(f"Rodada {latest_round['number']} tem {metrics['pending_results']} resultado(s) pendente(s).")
                else:
                    blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, int(latest_round["id"]))
                    metrics["blocking_issues"] = len(blocking_issues)
                    if blocking_issues:
                        metrics["ready_to_close"] = False
                        alerts.append(
                            f"Rodada {latest_round['number']} tem {len(blocking_issues)} pendencia(s) de arbitragem bloqueante(s)."
                        )
                    else:
                        alerts.append(f"Rodada {latest_round['number']} esta pronta para fechamento.")
        else:
            alerts.append("Nenhuma rodada gerada. Use a chamada inicial antes da primeira rodada.")
        if absent_players:
            alerts.append(f"{len(absent_players)} jogador(es) marcado(s) como ausente(s).")
        if correction_count:
            alerts.append(f"{correction_count} correcao(oes) auditada(s) no torneio.")
        if submitted_results:
            alerts.append(f"{submitted_results} resultado(s) enviado(s) por QR aguardando aprovacao.")

        if not latest_round or latest_round.get("status") == "closed":
            try:
                preview = self.preview_next_round(tournament_id)
                metrics["can_preview_next_round"] = True
                metrics["preview_alerts"] = int(preview.get("alerts_count") or 0)
                if metrics["preview_alerts"]:
                    alerts.append(f"Previa da proxima rodada tem {metrics['preview_alerts']} alerta(s).")
            except AppError as exc:
                alerts.append(str(exc))

        return {"metrics": metrics, "alerts": alerts}

    def arbitration_issues(self, tournament_id: int, limit: int = 200) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        issues: list[dict[str, Any]] = []
        safe_limit = max(1, min(int(limit or 200), 1000))
        acknowledged_keys = self._acknowledged_arbitration_issue_keys(tournament_id)

        for submission in self.db.list_result_submissions(tournament_id=tournament_id, status="submitted", limit=safe_limit):
            issues.append(
                {
                    "issue_key": f"qr:result_submission:{submission.get('id')}",
                    "severity": "decision",
                    "source": "qr",
                    "kind": "result_submission",
                    "title": f"Resultado QR pendente - mesa {submission.get('board_number') or ''}",
                    "detail": f"Resultado enviado: {submission.get('submitted_result') or ''}",
                    "round_id": submission.get("round_id"),
                    "entity_id": submission.get("id"),
                    "created_at": submission.get("submitted_at") or "",
                    "payload": submission,
                }
            )

        for event in self.db.list_audit_events(tournament_id, action="sync_remote_rejected", limit=safe_limit):
            issues.append(self._audit_issue(event, "sync", "remote_rejected", "Evento remoto rejeitado"))
        for event in self.db.list_audit_events(tournament_id, action="sync_event_rejected", limit=safe_limit):
            issues.append(self._audit_issue(event, "sync", "outbox_rejected", "Evento local rejeitado pelo servidor"))

        for event in self.db.list_clock_events(tournament_id=tournament_id, limit=safe_limit):
            event_type = str(event.get("event_type") or "")
            seconds = int(event.get("seconds_remaining") or 999999)
            if event_type == "flag_fall":
                issues.append(self._clock_issue(event, "Queda de seta registrada"))
            elif event_type == "absence":
                issues.append(self._clock_issue(event, "Ausencia registrada"))
            elif event_type == "time_warning" and seconds <= 60:
                issues.append(self._clock_issue(event, "Alerta de tempo critico"))

        issues = [issue for issue in issues if str(issue.get("issue_key") or "") not in acknowledged_keys]
        issues.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        issues = issues[:safe_limit]
        metrics = {
            "total": len(issues),
            "qr_pending": sum(1 for item in issues if item["source"] == "qr"),
            "sync_conflicts": sum(1 for item in issues if item["source"] == "sync"),
            "clock_alerts": sum(1 for item in issues if item["source"] == "clock"),
            "decision_required": sum(1 for item in issues if item["severity"] == "decision"),
        }
        return {"metrics": metrics, "issues": issues}

    def acknowledge_arbitration_issue(self, tournament_id: int, issue_key: str, note: str = "") -> int:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        normalized_key = str(issue_key or "").strip()
        if not normalized_key:
            raise AppError("Selecione uma pendencia.")

        issues = self.arbitration_issues(tournament_id, limit=1000)["issues"]
        issue = next((item for item in issues if str(item.get("issue_key") or "") == normalized_key), None)
        if not issue:
            raise AppError("Pendencia nao encontrada ou ja tratada.")
        if issue.get("source") == "qr":
            raise AppError("Use Aprovar QR ou Rejeitar QR para pendencia QR.")

        return self.db.create_audit_event(
            action="arbitration_issue_acknowledged",
            tournament_id=tournament_id,
            round_id=issue.get("round_id"),
            entity_type="arbitration_issue",
            entity_id=None,
            reason=note.strip() or "Pendencia marcada como ciente.",
            after={"issue_key": normalized_key, "issue": issue},
            metadata={"source": issue.get("source"), "kind": issue.get("kind")},
        )

    def _acknowledged_arbitration_issue_keys(self, tournament_id: int) -> set[str]:
        acknowledged: set[str] = set()
        for event in self.db.list_audit_events(
            tournament_id,
            action="arbitration_issue_acknowledged",
            entity_type="arbitration_issue",
            limit=5000,
        ):
            try:
                payload = json.loads(event.get("after_json") or "{}")
            except json.JSONDecodeError:
                payload = {}
            issue_key = str(payload.get("issue_key") or "").strip()
            if issue_key:
                acknowledged.add(issue_key)
        return acknowledged

    def _blocking_arbitration_issues_for_round(self, tournament_id: int, round_id: int) -> list[dict[str, Any]]:
        issues = self.arbitration_issues(tournament_id, limit=1000)["issues"]
        return [
            issue
            for issue in issues
            if issue.get("severity") == "decision" and self._issue_matches_round(issue, round_id)
        ]

    @staticmethod
    def _issue_matches_round(issue: dict[str, Any], round_id: int) -> bool:
        raw_round_id = issue.get("round_id")
        if raw_round_id in (None, ""):
            return True
        try:
            return int(raw_round_id) == int(round_id)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _blocking_issues_message(issues: list[dict[str, Any]]) -> str:
        if not issues:
            return ""
        summaries = [
            f"{issue.get('source') or ''}/{issue.get('kind') or ''}".strip("/")
            for issue in issues[:3]
        ]
        suffix = f" ({', '.join(summaries)})" if summaries else ""
        return f"Resolva as pendencias de arbitragem bloqueantes antes de fechar a rodada{suffix}."

    @staticmethod
    def _audit_issue(event: dict[str, Any], source: str, kind: str, title: str) -> dict[str, Any]:
        event_identifier = event.get("event_id") or event.get("id") or event.get("entity_id") or ""
        return {
            "issue_key": f"{source}:{kind}:{event_identifier}",
            "severity": "decision",
            "source": source,
            "kind": kind,
            "title": title,
            "detail": event.get("reason") or event.get("action") or "",
            "round_id": event.get("round_id"),
            "entity_id": event.get("entity_id"),
            "created_at": event.get("created_at") or "",
            "payload": event,
        }

    @staticmethod
    def _clock_issue(event: dict[str, Any], title: str) -> dict[str, Any]:
        event_identifier = event.get("event_id") or event.get("id") or ""
        return {
            "issue_key": f"clock:{event.get('event_type') or ''}:{event_identifier}",
            "severity": "attention",
            "source": "clock",
            "kind": str(event.get("event_type") or ""),
            "title": title,
            "detail": event.get("note") or "Apenas alerta; o arbitro deve decidir manualmente.",
            "round_id": event.get("round_id"),
            "entity_id": event.get("id"),
            "created_at": event.get("occurred_at") or event.get("created_at") or "",
            "payload": event,
        }

    def _individual_round_dashboard_metrics(self, round_id: int) -> dict[str, Any]:
        pairings = self.db.get_pairings_for_round(round_id)
        pending = [item for item in pairings if not item.get("result") or item.get("result") not in FINAL_RESULTS]
        byes = [item for item in pairings if item.get("is_bye")]
        return {
            "pending_results": len(pending),
            "byes": len(byes),
            "ready_to_close": bool(pairings) and not pending,
        }

    def _team_round_dashboard_metrics(self, round_id: int) -> dict[str, Any]:
        matches = self.db.list_team_matches_for_round(round_id)
        pending = 0
        byes = 0
        for match in matches:
            if match.get("is_bye"):
                byes += 1
                continue
            boards = self.db.list_team_boards(int(match["id"]))
            pending += sum(1 for board in boards if not board.get("result") or board.get("result") not in FINAL_RESULTS)
        return {
            "pending_results": pending,
            "byes": byes,
            "ready_to_close": bool(matches) and pending == 0,
        }

    def generate_next_round(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            return self._generate_next_team_round(tournament_id, tournament)

        plan = self._individual_next_round_plan(tournament_id, tournament)
        players = plan["players"]
        settings = plan["settings"]
        next_number = int(plan["round_number"])
        pairings = plan["pairings"]

        input_snapshot = self._pairing_input_snapshot(
            tournament_id=tournament_id,
            tournament=tournament,
            settings=settings,
            round_number=next_number,
            participants=players,
        )
        self.db.create_pairing_snapshot(
            tournament_id,
            next_number,
            "input",
            input_snapshot,
            pairing_system=str(settings.get("pairing_system") or "custom_authorized"),
            pairing_engine_version=self.PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.backup_before("generate_round", tournament_id=tournament_id)
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            next_number,
            pairings,
            pairing_engine_version=self.PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.create_pairing_snapshot(
            tournament_id,
            next_number,
            "output",
            {"round_number": next_number, "pairings": pairings},
            round_id=round_id,
            pairing_system=str(settings.get("pairing_system") or "custom_authorized"),
            pairing_engine_version=self.PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.create_audit_event(
            action="round_generated",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            after={"round_number": next_number, "pairings_count": len(pairings)},
            metadata={
                "pairing_engine_version": self.PAIRING_ENGINE_VERSION,
                "ruleset_version": self.RULESET_VERSION,
            },
        )
        logger.info("Rodada %s gerada para o torneio %s", next_number, tournament_id)
        if tournament["status"] == "draft":
            self.db.update_tournament_status(tournament_id, "running")

        generated = self.db.get_round_by_number(tournament_id, next_number)
        if not generated:
            raise AppError("A rodada foi gerada, mas nao pode ser reaberta.")
        generated["id"] = round_id
        return generated

    def _individual_next_round_plan(self, tournament_id: int, tournament: dict[str, Any]) -> dict[str, Any]:
        players = self.db.list_players(tournament_id, active_only=True)
        if len(players) < 2:
            raise AppError("Cadastre pelo menos 2 jogadores ativos.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        if settings.get("disable_bye") and len(players) % 2 == 1:
            raise AppError("O bye esta desativado. Use numero par de jogadores ativos.")

        latest_round = self.db.get_latest_round(tournament_id)
        if latest_round and latest_round["status"] != "closed":
            raise AppError("Feche ou exclua a rodada gerada antes de criar outra.")

        next_number = 1 if not latest_round else int(latest_round["number"]) + 1
        if next_number > int(tournament["rounds_count"]):
            raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")

        pairing_method = settings.get("pairing_method", "swiss")
        if pairing_method == "round_robin":
            pairings = self._round_robin_pairings(tournament_id, players, next_number, settings)
        elif pairing_method == "knockout":
            pairings = self._knockout_pairings(tournament_id, players, next_number, settings)
        else:
            if next_number == 1:
                pairings = self._first_round_pairings(players)
            else:
                pairings = self._swiss_pairings(tournament_id, players)
        return {
            "players": players,
            "settings": settings,
            "round_number": next_number,
            "pairings": pairings,
        }

    def _pairing_input_snapshot(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        round_number: int,
        participants: list[dict[str, Any]],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_rounds = self.db.list_rounds(tournament_id)
        previous_pairings = self.db.get_pairings_for_tournament(tournament_id)
        return {
            "tournament": {
                "id": int(tournament["id"]),
                "name": tournament.get("name", ""),
                "competition_type": tournament.get("competition_type", "individual"),
                "rounds_count": int(tournament.get("rounds_count") or 0),
                "bye_points": float(tournament.get("bye_points") or 0.0),
            },
            "settings": {
                "pairing_method": settings.get("pairing_method", "swiss"),
                "pairing_system": settings.get("pairing_system", "custom_authorized"),
                "acceleration_method": settings.get("acceleration_method", "none"),
                "disable_bye": int(settings.get("disable_bye", 0) or 0),
                "initial_order": settings.get("initial_order", "rating"),
            },
            "round_number": int(round_number),
            "participants": [
                {
                    "id": int(item["id"]),
                    "name": str(item.get("name") or ""),
                    "rating": int(item.get("rating") or item.get("seed_rating") or 0),
                    "active": int(item.get("active", 1) or 0),
                    "status": str(item.get("player_status") or item.get("status") or ""),
                }
                for item in participants
            ],
            "previous_rounds": [
                {
                    "id": int(item["id"]),
                    "number": int(item["number"]),
                    "status": item.get("status", ""),
                }
                for item in sorted(previous_rounds, key=lambda row: int(row["number"]))
            ],
            "previous_pairings": [
                {
                    "round_number": int(item["round_number"]),
                    "board_number": int(item["board_number"]),
                    "white_player_id": int(item["white_player_id"]),
                    "black_player_id": int(item["black_player_id"]) if item.get("black_player_id") else None,
                    "result": item.get("result", ""),
                    "is_bye": int(item.get("is_bye") or 0),
                }
                for item in previous_pairings
            ],
            "extra": extra or {},
        }

    def _individual_preview_payload(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        players_by_id = {int(player["id"]): player for player in plan["players"]}
        histories = self._color_histories(tournament_id)
        played_pairs = self._played_pairs(tournament_id)
        standings = {int(item["player_id"]): item for item in self.standings(tournament_id)}
        preview_pairings = []
        alert_count = 0
        for pairing in plan["pairings"]:
            white_id = int(pairing["white_player_id"])
            black_id = int(pairing["black_player_id"]) if pairing.get("black_player_id") else None
            alerts = []
            explanation = []
            if pairing.get("is_bye"):
                alerts.append("Bye")
                explanation.append("Jogador recebeu bye por numero impar de participantes ativos.")
            elif black_id is not None:
                if frozenset((white_id, black_id)) in played_pairs:
                    alerts.append("Confronto repetido")
                white_score = float(standings.get(white_id, {}).get("points", 0.0) or 0.0)
                black_score = float(standings.get(black_id, {}).get("points", 0.0) or 0.0)
                if abs(white_score - black_score) > 1.0:
                    alerts.append("Scoregroup distante")
                explanation.append(
                    "Pareado por pontuacao e criterios do metodo configurado; "
                    f"placares atuais {white_score:g} x {black_score:g}."
                )
                if self._would_make_three_colors(white_id, "W", histories):
                    alerts.append("Brancas pela terceira vez seguida")
                if self._would_make_three_colors(black_id, "B", histories):
                    alerts.append("Pretas pela terceira vez seguida")

            alert_count += len(alerts)
            white = players_by_id.get(white_id, {})
            black = players_by_id.get(black_id or 0, {})
            preview_pairings.append(
                {
                    "board_number": int(pairing["board_number"]),
                    "white_player_id": white_id,
                    "white_name": player_pairing_name(white) if white else str(white_id),
                    "white_rating": int(white.get("rating") or 0) if white else 0,
                    "black_player_id": black_id,
                    "black_name": "BYE" if pairing.get("is_bye") else player_pairing_name(black) if black else "",
                    "black_rating": int(black.get("rating") or 0) if black else 0,
                    "is_bye": 1 if pairing.get("is_bye") else 0,
                    "alerts": alerts,
                    "explanation": " ".join(explanation),
                }
            )
        return {
            "competition_type": "individual",
            "tournament_id": tournament_id,
            "tournament_name": tournament.get("name", ""),
            "round_number": int(plan["round_number"]),
            "pairing_system": str(plan["settings"].get("pairing_system") or "custom_authorized"),
            "pairing_engine_version": self.PAIRING_ENGINE_VERSION,
            "ruleset_version": self.RULESET_VERSION,
            "pairings": preview_pairings,
            "alerts_count": alert_count,
        }

    @staticmethod
    def _would_make_three_colors(player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
        history = histories.get(int(player_id), [])
        return len(history) >= 2 and history[-2:] == [color, color]

    def _generate_next_team_round(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
    ) -> dict[str, Any]:
        plan = self._team_next_round_plan(tournament_id, tournament)
        settings = plan["settings"]
        teams = plan["teams"]
        boards_count = int(plan["boards_count"])
        seed_ratings = plan["seed_ratings"]
        next_number = int(plan["round_number"])
        matches = plan["matches"]

        input_snapshot = self._pairing_input_snapshot(
            tournament_id=tournament_id,
            tournament=tournament,
            settings=settings,
            round_number=next_number,
            participants=teams,
            extra={"boards_count": boards_count, "seed_ratings": seed_ratings},
        )
        self.db.create_pairing_snapshot(
            tournament_id,
            next_number,
            "input",
            input_snapshot,
            pairing_system=str(settings.get("pairing_system") or "team_swiss"),
            pairing_engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.backup_before("generate_team_round", tournament_id=tournament_id)
        round_id = self.db.create_round_with_team_matches(
            tournament_id,
            next_number,
            matches,
            pairing_engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.create_team_lineups_from_round(round_id)
        self.db.create_pairing_snapshot(
            tournament_id,
            next_number,
            "output",
            {"round_number": next_number, "matches": matches},
            round_id=round_id,
            pairing_system=str(settings.get("pairing_system") or "team_swiss"),
            pairing_engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self.db.create_audit_event(
            action="team_round_generated",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            after={"round_number": next_number, "matches_count": len(matches)},
            metadata={
                "pairing_engine_version": self.TEAM_PAIRING_ENGINE_VERSION,
                "ruleset_version": self.RULESET_VERSION,
                "lineups_created": True,
            },
        )
        logger.info("Rodada por equipes %s gerada para o torneio %s", next_number, tournament_id)
        if tournament["status"] == "draft":
            self.db.update_tournament_status(tournament_id, "running")

        generated = self.db.get_round_by_number(tournament_id, next_number)
        if not generated:
            raise AppError("A rodada foi gerada, mas nao pode ser reaberta.")
        generated["id"] = round_id
        return generated

    def _team_next_round_plan(self, tournament_id: int, tournament: dict[str, Any]) -> dict[str, Any]:
        settings = self.db.get_tournament_settings(tournament_id) or {}
        teams = self.db.list_teams(tournament_id, active_only=True)
        if len(teams) < 2:
            raise AppError("Cadastre pelo menos 2 equipes ativas.")
        if settings.get("disable_bye") and len(teams) % 2 == 1:
            raise AppError("O bye esta desativado. Use numero par de equipes ativas.")

        boards_count = int(settings.get("team_boards_count") or 4)
        rosters, seed_ratings = self._team_starter_rosters(teams, boards_count)

        latest_round = self.db.get_latest_round(tournament_id)
        if latest_round and latest_round["status"] != "closed":
            raise AppError("Feche ou exclua a rodada gerada antes de criar outra.")

        next_number = 1 if not latest_round else int(latest_round["number"]) + 1
        if next_number > int(tournament["rounds_count"]):
            raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")

        if next_number == 1:
            matches = self._first_round_team_matches(teams, rosters, seed_ratings, boards_count, settings)
        else:
            matches = self._swiss_team_matches(tournament_id, teams, rosters, seed_ratings, boards_count, settings)

        return {
            "settings": settings,
            "teams": teams,
            "boards_count": boards_count,
            "seed_ratings": seed_ratings,
            "round_number": next_number,
            "matches": matches,
        }

    def _team_preview_payload(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        teams_by_id = {int(team["id"]): team for team in plan["teams"]}
        played_pairs = self._team_played_pairs(tournament_id)
        preview_matches = []
        alert_count = 0
        for match in plan["matches"]:
            white_team_id = int(match["white_team_id"])
            black_team_id = int(match["black_team_id"]) if match.get("black_team_id") else None
            alerts = []
            explanation = []
            if match.get("is_bye"):
                alerts.append("Bye da equipe")
                explanation.append("Equipe recebeu bye por numero impar de equipes ativas.")
            elif black_team_id is not None:
                if frozenset((white_team_id, black_team_id)) in played_pairs:
                    alerts.append("Confronto repetido")
                explanation.append("Match gerado pelo metodo de emparceiramento por equipes configurado.")
            alert_count += len(alerts)
            white_team = teams_by_id.get(white_team_id, {})
            black_team = teams_by_id.get(black_team_id or 0, {})
            preview_matches.append(
                {
                    "match_number": int(match["match_number"]),
                    "white_team_id": white_team_id,
                    "white_team_name": str(white_team.get("name") or white_team_id),
                    "black_team_id": black_team_id,
                    "black_team_name": "BYE" if match.get("is_bye") else str(black_team.get("name") or ""),
                    "boards_count": len(match.get("boards") or []),
                    "is_bye": 1 if match.get("is_bye") else 0,
                    "alerts": alerts,
                    "explanation": " ".join(explanation),
                }
            )
        return {
            "competition_type": "team",
            "tournament_id": tournament_id,
            "tournament_name": tournament.get("name", ""),
            "round_number": int(plan["round_number"]),
            "pairing_system": str(plan["settings"].get("pairing_system") or "team_swiss"),
            "pairing_engine_version": self.TEAM_PAIRING_ENGINE_VERSION,
            "ruleset_version": self.RULESET_VERSION,
            "matches": preview_matches,
            "alerts_count": alert_count,
        }

    def _team_starter_rosters(
        self,
        teams: list[dict[str, Any]],
        boards_count: int,
    ) -> tuple[dict[int, dict[int, int]], dict[int, int]]:
        rosters: dict[int, dict[int, int]] = {}
        seed_ratings: dict[int, int] = {}
        for team in teams:
            team_id = int(team["id"])
            starters: dict[int, int] = {}
            ratings: dict[int, int] = {}
            for assignment in self.db.list_team_players(team_id, active_only=True):
                if assignment.get("role") != "starter" or not assignment.get("board_number"):
                    continue
                if assignment.get("player_status") != "active":
                    continue
                board_number = int(assignment["board_number"])
                if 1 <= board_number <= boards_count:
                    starters[board_number] = int(assignment["player_id"])
                    ratings[board_number] = int(assignment.get("player_rating") or 0)

            missing = [board for board in range(1, boards_count + 1) if board not in starters]
            if missing:
                missing_text = ", ".join(str(board) for board in missing)
                raise AppError(f"Equipe {team['name']} sem titular ativo no tabuleiro {missing_text}.")

            rosters[team_id] = starters
            seed_ratings[team_id] = round(sum(ratings.values()) / max(boards_count, 1))
        return rosters, seed_ratings

    def _first_round_team_matches(
        self,
        teams: list[dict[str, Any]],
        rosters: dict[int, dict[int, int]],
        seed_ratings: dict[int, int],
        boards_count: int,
        settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        ordered = sorted(
            teams,
            key=lambda team: (-seed_ratings[int(team["id"])], str(team["name"]).casefold()),
        )
        pairable = ordered[:]
        bye_team = None
        if len(pairable) % 2 == 1:
            bye_team = min(
                pairable,
                key=lambda team: (seed_ratings[int(team["id"])], str(team["name"]).casefold()),
            )
            pairable.remove(bye_team)

        half = len(pairable) // 2
        upper = pairable[:half]
        lower = pairable[half:]
        matches: list[dict[str, Any]] = []
        for index, team in enumerate(upper, start=1):
            opponent = lower[index - 1]
            if index % 2 == 1:
                white_team_id = int(team["id"])
                black_team_id = int(opponent["id"])
            else:
                white_team_id = int(opponent["id"])
                black_team_id = int(team["id"])
            matches.append(
                self._team_match_payload(
                    index,
                    white_team_id,
                    black_team_id,
                    rosters,
                    boards_count,
                )
            )

        if bye_team:
            matches.append(self._team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
        return matches

    def _search_dutch_team_pairing(
        self,
        pairable: list[dict[str, Any]],
        histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        strict_colors: bool,
        seed_ratings: dict[int, int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
        if not pairable:
            return []
            
        n = len(pairable)
        half = n // 2
        S1 = pairable[:half]
        S2 = pairable[half:]
        
        def solve(s1_idx: int, available_s2: list[dict[str, Any]], current_pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
            if s1_idx == len(S1):
                return current_pairs
                
            p1 = S1[s1_idx]
            for i, p2 in enumerate(available_s2):
                if frozenset((int(p1["id"]), int(p2["id"]))) in played_pairs:
                    continue
                    
                if strict_colors:
                    white_id, black_id = self._choose_team_colors(p1, p2, histories, seed_ratings)
                    p1_color = "W" if white_id == int(p1["id"]) else "B"
                    p2_color = "W" if white_id == int(p2["id"]) else "B"
                    
                    if not self._is_color_valid_fide(int(p1["id"]), p1_color, histories) or not self._is_color_valid_fide(int(p2["id"]), p2_color, histories):
                        p1_color_rev = "B" if p1_color == "W" else "W"
                        p2_color_rev = "B" if p2_color == "W" else "W"
                        if not self._is_color_valid_fide(int(p1["id"]), p1_color_rev, histories) or not self._is_color_valid_fide(int(p2["id"]), p2_color_rev, histories):
                            continue
                            
                next_pairs = solve(s1_idx + 1, available_s2[:i] + available_s2[i+1:], current_pairs + [(p1, p2)])
                if next_pairs is not None:
                    return next_pairs
            return None
            
        return solve(0, S2, [])

    def _dutch_team_bracket_pairing(
        self,
        group: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        rank_by_team_id: dict[int, int],
        seed_ratings: dict[int, int],
    ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
        n = len(group)
        
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            best_pairs = self._search_dutch_team_pairing(pairable, histories, played_pairs, strict_colors=True, seed_ratings=seed_ratings)
            if best_pairs is not None:
                return best_pairs, floaters
                
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            best_pairs = self._search_dutch_team_pairing(pairable, histories, played_pairs, strict_colors=False, seed_ratings=seed_ratings)
            if best_pairs is not None:
                return best_pairs, floaters
                
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            if len(pairable) <= self.MAX_EXHAUSTIVE_PAIRING_TEAMS:
                best_pairs = self._optimal_team_pairs(pairable, standings, played_pairs, rank_by_team_id)
            else:
                best_pairs = self._greedy_team_pairs(pairable, standings, played_pairs, rank_by_team_id)
            
            if all(frozenset((int(p1["id"]), int(p2["id"]))) not in played_pairs for p1, p2 in best_pairs):
                return best_pairs, floaters
                
        return [], group

    def _swiss_team_matches(
        self,
        tournament_id: int,
        teams: list[dict[str, Any]],
        rosters: dict[int, dict[int, int]],
        seed_ratings: dict[int, int],
        boards_count: int,
        settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        standings = {int(item["team_id"]): item for item in self.team_standings(tournament_id)}
        played_pairs = self._team_played_pairs(tournament_id)
        bye_team_ids = self._team_bye_ids(tournament_id)
        histories = self._team_color_histories(tournament_id)
        rank_by_team_id = {
            int(team_id): int(item.get("position", 0) or 0)
            for team_id, item in standings.items()
        }
        pending = sorted(
            teams,
            key=lambda team: self._team_pairing_order_key(team, standings, seed_ratings),
        )

        bye_team = None
        if len(pending) % 2 == 1:
            bye_team = self._choose_team_bye(pending, standings, bye_team_ids, seed_ratings)
            pending.remove(bye_team)

        score_groups: dict[float, list[dict[str, Any]]] = {}
        for team in pending:
            score = float(standings.get(int(team["id"]), {}).get("match_points", 0.0) or 0.0)
            score_groups.setdefault(score, []).append(team)

        sorted_scores = sorted(score_groups.keys(), reverse=True)
        team_pairs = []
        floaters = []

        for score in sorted_scores:
            group = score_groups[score]
            group.extend(floaters)
            floaters = []
            
            group = sorted(group, key=lambda t: self._team_pairing_order_key(t, standings, seed_ratings))
            
            group_pairs, group_floaters = self._dutch_team_bracket_pairing(
                group, standings, histories, played_pairs, rank_by_team_id, seed_ratings
            )
            team_pairs.extend(group_pairs)
            floaters.extend(group_floaters)
            
        if floaters:
            if len(floaters) <= self.MAX_EXHAUSTIVE_PAIRING_TEAMS:
                leftover_pairs = self._optimal_team_pairs(floaters, standings, played_pairs, rank_by_team_id)
            else:
                leftover_pairs = self._greedy_team_pairs(floaters, standings, played_pairs, rank_by_team_id)
            team_pairs.extend(leftover_pairs)

        team_pairs = sorted(
            team_pairs,
            key=lambda pair: min(
                rank_by_team_id.get(int(pair[0]["id"]), 0),
                rank_by_team_id.get(int(pair[1]["id"]), 0),
            ),
        )

        matches = []
        for match_number, (team, opponent) in enumerate(team_pairs, start=1):
            white_team_id, black_team_id = self._choose_team_colors(team, opponent, histories, seed_ratings)
            matches.append(
                self._team_match_payload(
                    match_number,
                    white_team_id,
                    black_team_id,
                    rosters,
                    boards_count,
                )
            )
        if bye_team:
            matches.append(self._team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
        return matches

    @staticmethod
    def _team_match_payload(
        match_number: int,
        white_team_id: int,
        black_team_id: int,
        rosters: dict[int, dict[int, int]],
        boards_count: int,
    ) -> dict[str, Any]:
        boards = []
        for board_number in range(1, boards_count + 1):
            if board_number % 2 == 1:
                white_player_id = rosters[white_team_id][board_number]
                black_player_id = rosters[black_team_id][board_number]
            else:
                white_player_id = rosters[black_team_id][board_number]
                black_player_id = rosters[white_team_id][board_number]
            boards.append(
                {
                    "board_number": board_number,
                    "white_player_id": white_player_id,
                    "black_player_id": black_player_id,
                    "result": "",
                }
            )
        return {
            "match_number": match_number,
            "white_team_id": white_team_id,
            "black_team_id": black_team_id,
            "result": "",
            "is_bye": 0,
            "boards": boards,
        }

    @staticmethod
    def _team_bye_payload(
        match_number: int,
        team_id: int,
        settings: dict[str, Any],
        boards_count: int,
    ) -> dict[str, Any]:
        return {
            "match_number": match_number,
            "white_team_id": team_id,
            "black_team_id": None,
            "result": "BYE",
            "white_match_points": float(settings.get("team_match_win_points", 2.0) or 2.0),
            "black_match_points": 0.0,
            "white_game_points": float(boards_count),
            "black_game_points": 0.0,
            "is_bye": 1,
            "boards": [],
        }

    def update_result(
        self,
        tournament_id: int,
        pairing_id: int,
        result: str,
    ) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            self._update_team_board_result(tournament_id, pairing_id, result)
            return

        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")
        if result not in RESULTS:
            raise AppError("Resultado invalido.")
        before = {
            "pairing_id": int(pairing_id),
            "result": pairing.get("result", ""),
            "round_status": pairing.get("round_status", ""),
        }
        if pairing["round_status"] == "closed":
            settings = self.db.get_tournament_settings(tournament_id) or {}
            if not settings.get("allow_dangerous_changes"):
                raise AppError("Resultado de rodada fechada so pode ser alterado com mudancas perigosas habilitadas.")
        self.db.update_pairing_result(pairing_id, result)
        action = "result_corrected" if pairing["round_status"] == "closed" else "result_updated"
        self.db.create_audit_event(
            action=action,
            tournament_id=tournament_id,
            round_id=int(pairing["round_id"]),
            entity_type="pairing",
            entity_id=int(pairing_id),
            reason="Correcao em rodada fechada." if action == "result_corrected" else "",
            before=before,
            after={"pairing_id": int(pairing_id), "result": result, "round_status": pairing.get("round_status", "")},
        )
        logger.info("Resultado da mesa %s atualizado para %s", pairing_id, result or "pendente")

    def close_round(self, tournament_id: int, round_id: int) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            self._close_team_round(tournament_id, round_id, tournament)
            return

        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")

        pairings = self.db.get_pairings_for_round(round_id)
        pending = [
            pairing
            for pairing in pairings
            if not pairing["result"] or pairing["result"] not in FINAL_RESULTS
        ]
        if pending:
            raise AppError("Preencha todos os resultados antes de fechar a rodada.")

        blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, round_id)
        if blocking_issues:
            raise AppError(self._blocking_issues_message(blocking_issues))

        backup_path = self.db.backup_before("close_round", tournament_id=tournament_id, round_id=round_id)
        logger.info("Backup criado antes de fechar rodada %s: %s", round_id, backup_path)

        self.db.close_round(round_id)
        standings = self.standings(tournament_id)
        self.db.create_standings_snapshot(
            tournament_id=tournament_id,
            round_id=round_id,
            round_number=int(round_data["number"]),
            standings=standings,
        )
        self._persist_tiebreak_components(
            tournament_id=tournament_id,
            round_id=round_id,
            round_number=int(round_data["number"]),
            standings=standings,
        )
        self.db.create_audit_event(
            action="round_closed",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            before={"status": round_data.get("status", "")},
            after={"status": "closed", "standings_count": len(standings)},
        )
        logger.info("Rodada %s fechada no torneio %s", round_id, tournament_id)

        latest = self.db.get_latest_round(tournament_id)
        if latest and int(latest["number"]) >= int(tournament["rounds_count"]):
            self.db.update_tournament_status(tournament_id, "finished")
        else:
            self.db.update_tournament_status(tournament_id, "running")

    def _update_team_board_result(self, tournament_id: int, team_board_id: int, result: str) -> None:
        board = self.db.get_team_board(team_board_id)
        if not board or int(board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro nao encontrado para o torneio selecionado.")
        if result not in RESULTS:
            raise AppError("Resultado invalido.")
        before = {
            "team_board_id": int(team_board_id),
            "result": board.get("result", ""),
            "round_status": board.get("round_status", ""),
        }
        if board["round_status"] == "closed":
            settings = self.db.get_tournament_settings(tournament_id) or {}
            if not settings.get("allow_dangerous_changes"):
                raise AppError("Resultado de rodada fechada so pode ser alterado com mudancas perigosas habilitadas.")
        self.db.update_team_board_result(team_board_id, result)
        action = "team_result_corrected" if board["round_status"] == "closed" else "team_result_updated"
        self.db.create_audit_event(
            action=action,
            tournament_id=tournament_id,
            round_id=int(board["round_id"]),
            entity_type="team_board",
            entity_id=int(team_board_id),
            reason="Correcao em rodada fechada." if action == "team_result_corrected" else "",
            before=before,
            after={"team_board_id": int(team_board_id), "result": result, "round_status": board.get("round_status", "")},
        )
        logger.info("Resultado do tabuleiro de equipe %s atualizado para %s", team_board_id, result or "pendente")

    def _close_team_round(
        self,
        tournament_id: int,
        round_id: int,
        tournament: dict[str, Any],
    ) -> None:
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")

        matches = self.db.list_team_matches_for_round(round_id)
        if not matches:
            raise AppError("A rodada nao possui confrontos por equipes.")

        pending: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        for match in matches:
            if match["is_bye"]:
                summaries.append(
                    {
                        "team_match_id": int(match["id"]),
                        "result": "BYE",
                        "white_match_points": float(settings.get("team_match_win_points", 2.0) or 2.0),
                        "black_match_points": 0.0,
                        "white_game_points": float(settings.get("team_boards_count", 4) or 4),
                        "black_game_points": 0.0,
                    }
                )
                continue

            boards = self.db.list_team_boards(int(match["id"]))
            for board in boards:
                if not board["result"] or board["result"] not in RESULT_POINTS:
                    pending.append(board)
            if pending:
                continue

            white_game_points = 0.0
            black_game_points = 0.0
            white_team_player_ids = {
                int(player["player_id"])
                for player in self.db.list_team_players(int(match["white_team_id"]), active_only=False)
            }
            black_team_player_ids = {
                int(player["player_id"])
                for player in self.db.list_team_players(int(match["black_team_id"]), active_only=False)
            }
            for board in boards:
                white_points, black_points = RESULT_POINTS[str(board["result"])]
                if board.get("white_player_id") in white_team_player_ids:
                    white_game_points += white_points
                elif board.get("white_player_id") in black_team_player_ids:
                    black_game_points += white_points

                if board.get("black_player_id") in white_team_player_ids:
                    white_game_points += black_points
                elif board.get("black_player_id") in black_team_player_ids:
                    black_game_points += black_points

            if white_game_points > black_game_points:
                match_result = "1-0"
                white_match_points = float(settings.get("team_match_win_points", 2.0) or 2.0)
                black_match_points = float(settings.get("team_match_loss_points", 0.0) or 0.0)
            elif black_game_points > white_game_points:
                match_result = "0-1"
                white_match_points = float(settings.get("team_match_loss_points", 0.0) or 0.0)
                black_match_points = float(settings.get("team_match_win_points", 2.0) or 2.0)
            else:
                match_result = "1/2-1/2"
                white_match_points = float(settings.get("team_match_draw_points", 1.0) or 1.0)
                black_match_points = float(settings.get("team_match_draw_points", 1.0) or 1.0)

            summaries.append(
                {
                    "team_match_id": int(match["id"]),
                    "result": match_result,
                    "white_match_points": white_match_points,
                    "black_match_points": black_match_points,
                    "white_game_points": round(white_game_points, 2),
                    "black_game_points": round(black_game_points, 2),
                }
            )

        if pending:
            raise AppError("Preencha todos os resultados dos tabuleiros antes de fechar a rodada.")

        blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, round_id)
        if blocking_issues:
            raise AppError(self._blocking_issues_message(blocking_issues))

        backup_path = self.db.backup_before("close_team_round", tournament_id=tournament_id, round_id=round_id)
        logger.info("Backup criado antes de fechar rodada por equipes %s: %s", round_id, backup_path)

        for summary in summaries:
            self.db.update_team_match_summary(
                int(summary["team_match_id"]),
                str(summary["result"]),
                float(summary["white_match_points"]),
                float(summary["black_match_points"]),
                float(summary["white_game_points"]),
                float(summary["black_game_points"]),
            )

        self.db.close_round(round_id)
        standings = self.team_standings(tournament_id)
        self.db.create_standings_snapshot(
            tournament_id=tournament_id,
            round_id=round_id,
            round_number=int(round_data["number"]),
            standings=standings,
        )
        self.db.create_audit_event(
            action="team_round_closed",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            before={"status": round_data.get("status", "")},
            after={"status": "closed", "standings_count": len(standings)},
        )
        logger.info("Rodada por equipes %s fechada no torneio %s", round_id, tournament_id)

        latest = self.db.get_latest_round(tournament_id)
        if latest and int(latest["number"]) >= int(tournament["rounds_count"]):
            self.db.update_tournament_status(tournament_id, "finished")
        else:
            self.db.update_tournament_status(tournament_id, "running")

    def delete_generated_round(self, round_id: int) -> None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT tournament_id, number, status FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
        if row and row["status"] == "closed":
            raise AppError("Rodada fechada nao pode ser excluida.")
        if row:
            self.db.backup_before("delete_generated_round", tournament_id=int(row["tournament_id"]), round_id=round_id)
        self.db.delete_round(round_id)
        if row:
            self.db.create_audit_event(
                action="round_deleted",
                tournament_id=int(row["tournament_id"]),
                round_id=None,
                entity_type="round",
                entity_id=round_id,
                before={"round_id": round_id, "number": int(row["number"]), "status": row["status"]},
                reason="Exclusao de rodada gerada ainda nao fechada.",
            )
        logger.info("Rodada gerada %s excluida", round_id)

    def delete_player_if_unpaired(self, tournament_id: int, player_id: int) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        player = self.db.get_player(player_id)
        if not player or int(player["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador nao encontrado para o torneio selecionado.")
        pairings_count = self.db.count_player_pairings(player_id)
        if pairings_count:
            raise AppError(
                "Nao e possivel excluir jogador que ja aparece em rodada. "
                "Use o status Desistente ou Nao emparceirado para preservar o historico."
            )
        self.db.delete_player(player_id)
        logger.info("Jogador %s excluido do torneio %s antes de entrar em rodadas", player_id, tournament_id)

    def adjust_pairing_player(
        self,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        color: str,
        replacement_player_id: int,
    ) -> None:
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada nao pode ser ajustada.")
        if color not in {"white", "black"}:
            raise AppError("Cor invalida para ajuste.")

        replacement = self.db.get_player(replacement_player_id)
        if not replacement or int(replacement["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador substituto nao pertence ao torneio.")
        if not replacement["active"]:
            raise AppError("Jogador substituto precisa estar ativo.")

        pairings = self.db.get_pairings_for_round(round_id)
        if not pairings:
            raise AppError("A rodada nao possui mesas para ajustar.")

        pairing_by_id = {int(pairing["id"]): pairing for pairing in pairings}
        source_pairing = pairing_by_id.get(int(pairing_id))
        if not source_pairing:
            raise AppError("Mesa selecionada nao encontrada.")
        if color == "black" and (source_pairing["is_bye"] or not source_pairing["black_player_id"]):
            raise AppError("Bye nao possui jogador de pretas para trocar.")

        affected_pairings = [source_pairing]
        target_slot = self._find_player_slot(pairings, replacement_player_id)
        if target_slot and target_slot["pairing"]["id"] != source_pairing["id"]:
            affected_pairings.append(target_slot["pairing"])

        for affected in affected_pairings:
            if affected["result"] and affected["result"] != "BYE":
                raise AppError("Limpe os resultados das mesas afetadas antes de trocar jogadores.")

        source_player_id = (
            source_pairing["white_player_id"]
            if color == "white"
            else source_pairing["black_player_id"]
        )
        if source_player_id is None:
            raise AppError("Jogador de origem invalido.")
        if int(source_player_id) == int(replacement_player_id):
            return

        updates: dict[int, dict[str, int | None]] = {
            int(pairing["id"]): {
                "white": int(pairing["white_player_id"]),
                "black": int(pairing["black_player_id"]) if pairing["black_player_id"] else None,
            }
            for pairing in pairings
        }

        updates[int(source_pairing["id"])][color] = int(replacement_player_id)
        if target_slot:
            updates[int(target_slot["pairing"]["id"])][target_slot["color"]] = int(source_player_id)

        for pairing_id_to_update, values in updates.items():
            black_player_id = values["black"]
            if black_player_id is not None and values["white"] == black_player_id:
                raise AppError("Uma mesa nao pode ter o mesmo jogador dos dois lados.")

        pairing_updates = []
        for pairing_id_to_update, values in updates.items():
            if pairing_id_to_update not in {int(source_pairing["id"])} and not (
                target_slot and pairing_id_to_update == int(target_slot["pairing"]["id"])
            ):
                continue
            white_player_id = values["white"]
            if white_player_id is None:
                raise AppError("Uma mesa precisa ter jogador de brancas.")
            pairing_updates.append((pairing_id_to_update, white_player_id, values["black"]))
        self.db.update_pairing_players(pairing_updates)
        logger.info(
            "Ajuste manual na rodada %s: mesa %s, cor %s, jogador %s",
            round_id,
            pairing_id,
            color,
            replacement_player_id,
        )

    def swap_team_board_colors(self, tournament_id: int, round_id: int, team_board_id: int) -> None:
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada nao pode ser ajustada.")
        board = self.db.get_team_board(team_board_id)
        if not board or int(board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro nao encontrado para o torneio selecionado.")
        if board["result"]:
            raise AppError("Limpe o resultado do tabuleiro antes de trocar cores.")
        self.db.swap_team_board_colors(team_board_id)
        logger.info("Cores trocadas no tabuleiro por equipes %s", team_board_id)

    def adjust_team_board_player(
        self,
        tournament_id: int,
        round_id: int,
        team_board_id: int,
        color: str,
        replacement_player_id: int,
        reason: str = "",
    ) -> None:
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada nao pode ser ajustada.")
        if color not in {"white", "black"}:
            raise AppError("Cor invalida para ajuste.")

        source_board = self.db.get_team_board(team_board_id)
        if not source_board or int(source_board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro selecionado nao encontrado.")

        replacement = self.db.get_player(replacement_player_id)
        if not replacement or int(replacement["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador substituto nao pertence ao torneio.")
        if not replacement["active"]:
            raise AppError("Jogador substituto precisa estar ativo.")

        source_player_id = source_board["white_player_id"] if color == "white" else source_board["black_player_id"]
        if source_player_id is None:
            raise AppError("Jogador de origem invalido.")
        if int(source_player_id) == int(replacement_player_id):
            return

        source_team = self.db.get_team_player_by_player(int(source_player_id))
        replacement_team = self.db.get_team_player_by_player(replacement_player_id)
        if not source_team or not replacement_team or int(source_team["team_id"]) != int(replacement_team["team_id"]):
            raise AppError("Em torneios por equipes, troque apenas por jogador da mesma equipe.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        max_substitutions = int(settings.get("team_max_substitutions") or 0)
        if max_substitutions > 0:
            existing_substitutions = [
                item
                for item in self.db.list_team_substitution_events(tournament_id, round_id=round_id)
                if int(item["team_id"]) == int(source_team["team_id"])
            ]
            if len(existing_substitutions) >= max_substitutions:
                raise AppError("Limite de substituicoes da equipe nesta rodada foi atingido.")

        active_team_player_ids = {
            int(player["player_id"])
            for player in self.db.list_team_players(int(source_team["team_id"]), active_only=True)
        }
        if replacement_player_id not in active_team_player_ids:
            raise AppError("Jogador substituto precisa estar ativo na equipe.")

        matches = self.db.list_team_matches_for_round(round_id)
        boards = [
            board
            for match in matches
            for board in self.db.list_team_boards(int(match["id"]))
        ]
        if not boards:
            raise AppError("A rodada nao possui tabuleiros para ajustar.")

        board_by_id = {int(board["id"]): board for board in boards}
        selected_board = board_by_id.get(int(team_board_id))
        if not selected_board:
            raise AppError("Tabuleiro selecionado nao encontrado.")

        target_slot = self._find_team_board_player_slot(boards, replacement_player_id)
        affected_board_ids = {int(team_board_id)}
        if target_slot:
            affected_board_ids.add(int(target_slot["board"]["id"]))

        for board_id in affected_board_ids:
            board = board_by_id[board_id]
            if board["result"]:
                raise AppError("Substituicao depois de resultado exige correcao formal: limpe o resultado antes.")

        updates: dict[int, dict[str, int | None]] = {
            int(board["id"]): {
                "white": int(board["white_player_id"]) if board["white_player_id"] else None,
                "black": int(board["black_player_id"]) if board["black_player_id"] else None,
            }
            for board in boards
        }
        updates[int(team_board_id)][color] = int(replacement_player_id)
        if target_slot:
            updates[int(target_slot["board"]["id"])][target_slot["color"]] = int(source_player_id)

        for board_id in affected_board_ids:
            values = updates[board_id]
            if values["white"] is not None and values["white"] == values["black"]:
                raise AppError("Um tabuleiro nao pode ter o mesmo jogador dos dois lados.")

        self.db.update_team_board_players(
            [
                (board_id, updates[board_id]["white"], updates[board_id]["black"])
                for board_id in affected_board_ids
            ]
        )
        self.db.create_team_lineups_from_round(round_id)
        substitution_id = self.db.create_team_substitution_event(
            tournament_id=tournament_id,
            round_id=round_id,
            team_match_id=int(source_board["team_match_id"]),
            team_board_id=team_board_id,
            team_id=int(source_team["team_id"]),
            board_number=int(source_board["board_number"]),
            color=color,
            out_player_id=int(source_player_id),
            in_player_id=int(replacement_player_id),
            reason=reason,
            requires_correction=False,
        )
        self.db.create_audit_event(
            action="team_substitution_recorded",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="team_substitution_event",
            entity_id=substitution_id,
            reason=reason,
            before={
                "team_board_id": int(team_board_id),
                "color": color,
                "out_player_id": int(source_player_id),
            },
            after={
                "team_board_id": int(team_board_id),
                "color": color,
                "in_player_id": int(replacement_player_id),
            },
        )
        logger.info(
            "Ajuste manual por equipes na rodada %s: tabuleiro %s, cor %s, jogador %s",
            round_id,
            team_board_id,
            color,
            replacement_player_id,
        )

    @staticmethod
    def _find_team_board_player_slot(
        boards: list[dict[str, Any]],
        player_id: int,
    ) -> dict[str, Any] | None:
        for board in boards:
            if board.get("white_player_id") and int(board["white_player_id"]) == int(player_id):
                return {"board": board, "color": "white"}
            if board.get("black_player_id") and int(board["black_player_id"]) == int(player_id):
                return {"board": board, "color": "black"}
        return None

    def standings(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []

        players = self.db.list_players(tournament_id, active_only=False)
        stats: dict[int, dict[str, Any]] = {}
        for player in players:
            stats[player["id"]] = {
                "player_id": player["id"],
                "name": player_full_name(player),
                "club": player["club"],
                "rating": int(player["rating"] or 0),
                "category": player["category"],
                "age_category": player.get("age_category", ""),
                "rating_category": player.get("rating_category", ""),
                "prize_tags": player.get("prize_tags", ""),
                "active": int(player["active"]),
                "player_status": player.get("player_status", "active"),
                "starting_points": float(player.get("starting_points", 0.0) or 0.0),
                "points": float(player.get("starting_points", 0.0) or 0.0),
                "wins": 0,
                "buchholz": 0.0,
                "buchholz_median": 0.0,
                "sonneborn_berger": 0.0,
                "white_count": 0,
                "black_count": 0,
                "byes": 0,
                "opponents": [],
                "earned_against": [],
                "games": [],
                "performance": "",
            }

        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        for pairing in closed_pairings:
            white_id = pairing["white_player_id"]
            black_id = pairing["black_player_id"]
            result = pairing["result"]

            if white_id not in stats:
                continue

            if pairing["is_bye"]:
                stats[white_id]["points"] += float(tournament["bye_points"])
                stats[white_id]["byes"] += 1
                stats[white_id]["games"].append(
                    {
                        "round": int(pairing.get("round_number") or 0),
                        "color": "bye",
                        "opponent_id": None,
                        "opponent_name": "BYE",
                        "result": result,
                        "earned": float(tournament["bye_points"]),
                    }
                )
                continue

            if not black_id or black_id not in stats or result not in RESULT_POINTS:
                continue

            white_points, black_points = RESULT_POINTS[result]
            stats[white_id]["points"] += white_points
            stats[black_id]["points"] += black_points
            stats[white_id]["white_count"] += 1
            stats[black_id]["black_count"] += 1
            stats[white_id]["opponents"].append(black_id)
            stats[black_id]["opponents"].append(white_id)
            stats[white_id]["earned_against"].append((black_id, white_points))
            stats[black_id]["earned_against"].append((white_id, black_points))
            stats[white_id]["games"].append(
                {
                    "round": int(pairing.get("round_number") or 0),
                    "color": "white",
                    "opponent_id": int(black_id),
                    "opponent_name": stats[black_id]["name"],
                    "result": result,
                    "earned": white_points,
                }
            )
            stats[black_id]["games"].append(
                {
                    "round": int(pairing.get("round_number") or 0),
                    "color": "black",
                    "opponent_id": int(white_id),
                    "opponent_name": stats[white_id]["name"],
                    "result": result,
                    "earned": black_points,
                }
            )
            if white_points == 1.0 and black_points == 0.0:
                stats[white_id]["wins"] += 1
            if black_points == 1.0 and white_points == 0.0:
                stats[black_id]["wins"] += 1

        for player_stat in stats.values():
            opponent_scores = [
                stats[opponent_id]["points"]
                for opponent_id in player_stat["opponents"]
                if opponent_id in stats
            ]
            player_stat["buchholz"] = round(sum(opponent_scores), 2)
            if len(opponent_scores) >= 3:
                ordered = sorted(opponent_scores)
                player_stat["buchholz_median"] = round(sum(ordered[1:-1]), 2)
            else:
                player_stat["buchholz_median"] = player_stat["buchholz"]

            sb = 0.0
            for opponent_id, earned in player_stat["earned_against"]:
                sb += stats[opponent_id]["points"] * earned
            player_stat["sonneborn_berger"] = round(sb, 2)
            player_stat["performance"] = self._performance_rating(player_stat, stats)
            player_stat["tiebreak_components"] = self._player_tiebreak_components(player_stat, stats)

        ordered_stats = sorted(
            stats.values(),
            key=lambda item: (
                -item["points"],
                -item["buchholz"],
                -item["buchholz_median"],
                -item["sonneborn_berger"],
                -item["wins"],
                -item["rating"],
                item["name"].casefold(),
            ),
        )

        for index, item in enumerate(ordered_stats, start=1):
            item["position"] = index
        return ordered_stats

    def tiebreak_report(self, tournament_id: int, player_id: int | None = None) -> list[dict[str, Any]]:
        standings = self.standings(tournament_id)
        closed_rounds = [
            round_data
            for round_data in self.db.list_rounds(tournament_id)
            if round_data.get("status") == "closed"
        ]
        latest_round = max(closed_rounds, key=lambda item: int(item["number"])) if closed_rounds else None
        if latest_round:
            self.db.replace_tiebreak_components(
                tournament_id=tournament_id,
                round_id=int(latest_round["id"]),
                round_number=int(latest_round["number"]),
                components=self._flatten_tiebreak_components(standings),
            )
        if player_id is not None:
            standings = [item for item in standings if int(item["player_id"]) == int(player_id)]
        return standings

    def _persist_tiebreak_components(
        self,
        tournament_id: int,
        round_id: int,
        round_number: int,
        standings: list[dict[str, Any]],
    ) -> None:
        self.db.replace_tiebreak_components(
            tournament_id=tournament_id,
            round_id=round_id,
            round_number=round_number,
            components=self._flatten_tiebreak_components(standings),
        )

    @staticmethod
    def _flatten_tiebreak_components(standings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in standings:
            for criterion, components in dict(item.get("tiebreak_components") or {}).items():
                rows.append(
                    {
                        "player_id": int(item["player_id"]),
                        "player_name": item.get("name", ""),
                        "criterion": criterion,
                        "value": components.get("value"),
                        "components": components,
                    }
                )
        return rows

    def _player_tiebreak_components(
        self,
        player_stat: dict[str, Any],
        stats: dict[int, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        opponent_rows = []
        opponent_scores = []
        for opponent_id in player_stat["opponents"]:
            if opponent_id not in stats:
                continue
            score = float(stats[opponent_id]["points"])
            opponent_scores.append(score)
            opponent_rows.append(
                {
                    "opponent_id": int(opponent_id),
                    "opponent_name": stats[opponent_id]["name"],
                    "points": round(score, 2),
                }
            )

        ordered_scores = sorted(opponent_scores)
        if len(ordered_scores) >= 3:
            median_used = ordered_scores[1:-1]
            cut_low = ordered_scores[0]
            cut_high = ordered_scores[-1]
        else:
            median_used = ordered_scores
            cut_low = None
            cut_high = None

        sb_rows = []
        for opponent_id, earned in player_stat["earned_against"]:
            if opponent_id not in stats:
                continue
            opponent_points = float(stats[opponent_id]["points"])
            sb_rows.append(
                {
                    "opponent_id": int(opponent_id),
                    "opponent_name": stats[opponent_id]["name"],
                    "opponent_points": round(opponent_points, 2),
                    "earned": round(float(earned), 2),
                    "contribution": round(opponent_points * float(earned), 2),
                }
            )

        tied_opponents = [
            game
            for game in player_stat["games"]
            if game.get("opponent_id") in stats
            and float(stats[int(game["opponent_id"])]["points"]) == float(player_stat["points"])
        ]
        direct_score = round(sum(float(game.get("earned") or 0.0) for game in tied_opponents), 2)
        performance = self._performance_components(player_stat, stats)

        return {
            "buchholz": {
                "label": "Buchholz",
                "value": player_stat["buchholz"],
                "formula": "Soma dos pontos finais dos adversarios enfrentados.",
                "opponents": opponent_rows,
                "total": player_stat["buchholz"],
            },
            "buchholz_median": {
                "label": "Buchholz mediano",
                "value": player_stat["buchholz_median"],
                "formula": "Soma dos pontos dos adversarios com corte do menor e maior valor quando ha 3 ou mais jogos.",
                "used_scores": [round(value, 2) for value in median_used],
                "cut_low": cut_low,
                "cut_high": cut_high,
                "total": player_stat["buchholz_median"],
            },
            "sonneborn_berger": {
                "label": "Sonneborn-Berger",
                "value": player_stat["sonneborn_berger"],
                "formula": "Pontos do adversario multiplicados pelo resultado obtido contra ele.",
                "opponents": sb_rows,
                "total": player_stat["sonneborn_berger"],
            },
            "direct_encounter": {
                "label": "Confronto direto",
                "value": direct_score,
                "formula": "Pontos marcados contra adversarios que terminaram empatados em pontos.",
                "games": tied_opponents,
                "total": direct_score,
            },
            "wins": {
                "label": "Vitorias",
                "value": int(player_stat["wins"]),
                "formula": "Quantidade de partidas vencidas no tabuleiro.",
                "games": [game for game in player_stat["games"] if float(game.get("earned") or 0.0) == 1.0],
                "total": int(player_stat["wins"]),
            },
            "performance": performance,
        }

    @staticmethod
    def _performance_components(
        player_stat: dict[str, Any],
        stats: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        rated_games = [
            {
                "opponent_id": int(opponent_id),
                "opponent_name": stats[opponent_id]["name"],
                "opponent_rating": int(stats[opponent_id]["rating"] or 0),
                "earned": round(float(earned), 2),
            }
            for opponent_id, earned in player_stat["earned_against"]
            if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
        ]
        score = round(sum(float(item["earned"]) for item in rated_games), 2)
        games = len(rated_games)
        average_rating = round(
            sum(int(item["opponent_rating"]) for item in rated_games) / games,
            2,
        ) if games else 0.0
        return {
            "label": "Performance",
            "value": player_stat["performance"] if player_stat["performance"] != "" else None,
            "formula": "Media de rating dos adversarios ajustada pelo percentual de score.",
            "games": rated_games,
            "score": score,
            "average_rating": average_rating,
            "total": player_stat["performance"],
        }

    def team_standings(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        teams = self.db.list_teams(tournament_id, active_only=False)
        stats: dict[int, dict[str, Any]] = {}
        for team in teams:
            team_id = int(team["id"])
            stats[team_id] = {
                "team_id": team_id,
                "name": team["name"],
                "club": team.get("club", ""),
                "captain": team.get("captain", ""),
                "active": int(team.get("active", 0) or 0),
                "match_points": 0.0,
                "game_points": 0.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "byes": 0,
                "matches": 0,
                "buchholz": 0.0,
                "opponents": [],
            }

        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            white_team_id = int(match["white_team_id"])
            black_team_id = int(match["black_team_id"]) if match.get("black_team_id") else None
            if white_team_id not in stats:
                continue
            if match.get("is_bye"):
                stats[white_team_id]["match_points"] += float(match.get("white_match_points", 0.0) or 0.0)
                stats[white_team_id]["game_points"] += float(match.get("white_game_points", 0.0) or 0.0)
                stats[white_team_id]["wins"] += 1
                stats[white_team_id]["byes"] += 1
                continue
            if black_team_id is None or black_team_id not in stats:
                continue

            white_match_points = float(match.get("white_match_points", 0.0) or 0.0)
            black_match_points = float(match.get("black_match_points", 0.0) or 0.0)
            stats[white_team_id]["match_points"] += white_match_points
            stats[black_team_id]["match_points"] += black_match_points
            stats[white_team_id]["game_points"] += float(match.get("white_game_points", 0.0) or 0.0)
            stats[black_team_id]["game_points"] += float(match.get("black_game_points", 0.0) or 0.0)
            stats[white_team_id]["matches"] += 1
            stats[black_team_id]["matches"] += 1
            stats[white_team_id]["opponents"].append(black_team_id)
            stats[black_team_id]["opponents"].append(white_team_id)

            if white_match_points > black_match_points:
                stats[white_team_id]["wins"] += 1
                stats[black_team_id]["losses"] += 1
            elif black_match_points > white_match_points:
                stats[black_team_id]["wins"] += 1
                stats[white_team_id]["losses"] += 1
            else:
                stats[white_team_id]["draws"] += 1
                stats[black_team_id]["draws"] += 1

        for team_stat in stats.values():
            team_stat["match_points"] = round(float(team_stat["match_points"]), 2)
            team_stat["game_points"] = round(float(team_stat["game_points"]), 2)
            team_stat["buchholz"] = round(
                sum(
                    float(stats[opponent_id]["match_points"])
                    for opponent_id in team_stat["opponents"]
                    if opponent_id in stats
                ),
                2,
            )

        primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
        secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
        ordered_stats = sorted(
            stats.values(),
            key=lambda item: (
                -self._team_standing_value(item, primary),
                -self._team_standing_value(item, secondary),
                -float(item["buchholz"]),
                -int(item["wins"]),
                str(item["name"]).casefold(),
            ),
        )
        for index, item in enumerate(ordered_stats, start=1):
            item["position"] = index
        return ordered_stats

    @staticmethod
    def _team_standing_value(item: dict[str, Any], criterion: str) -> float:
        if criterion == "wins":
            return float(item.get("wins", 0) or 0)
        if criterion == "game_points":
            return float(item.get("game_points", 0.0) or 0.0)
        return float(item.get("match_points", 0.0) or 0.0)

    @staticmethod
    def _performance_rating(
        player_stat: dict[str, Any],
        stats: dict[int, dict[str, Any]],
    ) -> int | str:
        games = len(player_stat["earned_against"])
        if not games:
            return ""

        opponent_ratings = [
            int(stats[opponent_id]["rating"] or 0)
            for opponent_id, _earned in player_stat["earned_against"]
            if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
        ]
        if not opponent_ratings:
            return ""

        score = sum(float(earned) for _opponent_id, earned in player_stat["earned_against"])
        average_rating = sum(opponent_ratings) / len(opponent_ratings)
        diff: float
        if score <= 0:
            diff = -800
        elif score >= games:
            diff = 800
        else:
            diff = 400 * math.log10(score / (games - score))
            diff = max(min(diff, 800), -800)
        return int(round(average_rating + diff))

    def _round_robin_pairings(self, tournament_id: int, players: list[dict[str, Any]], next_number: int, settings: dict[str, Any]) -> list[dict[str, Any]]:
        ordered = sorted(
            players,
            key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
        )
        if len(ordered) % 2 == 1:
            ordered.append({"id": -1, "name": "BYE", "is_dummy": True})
        
        N = len(ordered)
        if next_number > N - 1:
            raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")
            
        r = next_number
        P = [ordered[0]]
        for i in range(1, N):
            shift = r - 1
            idx = ((i - 1 - shift) % (N - 1)) + 1
            P.append(ordered[idx])
            
        upper = P[: N // 2]
        lower = P[N // 2 :]
        lower.reverse()
        
        pairings: list[dict[str, Any]] = []
        board = 1
        for k in range(N // 2):
            if (r % 2 == 1 and k == 0) or (r % 2 == 0 and k > 0):
                white, black = upper[k], lower[k]
            else:
                white, black = lower[k], upper[k]
                
            if white["id"] == -1 or black["id"] == -1:
                real_player = black if white["id"] == -1 else white
                pairings.append(
                    {
                        "board_number": board,
                        "white_player_id": real_player["id"],
                        "black_player_id": None,
                        "result": "1-0" if not settings.get("disable_bye") else "",
                        "is_bye": 1,
                    }
                )
            else:
                pairings.append(
                    {
                        "board_number": board,
                        "white_player_id": white["id"],
                        "black_player_id": black["id"],
                        "result": "",
                        "is_bye": 0,
                    }
                )
            board += 1
            
        return pairings

    def _knockout_pairings(self, tournament_id: int, players: list[dict[str, Any]], next_number: int, settings: dict[str, Any]) -> list[dict[str, Any]]:
        ordered = sorted(
            players,
            key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
        )
        
        if next_number == 1:
            active_players = ordered[:]
        else:
            prev_round = self.db.get_round_by_number(tournament_id, next_number - 1)
            if not prev_round:
                raise AppError("Rodada anterior não encontrada.")
                
            pairings = self.db.list_pairings(prev_round["id"])
            active_players_set = set()
            seed_map = {int(p["id"]): i for i, p in enumerate(ordered)}
            
            for p in pairings:
                if p["is_bye"]:
                    active_players_set.add(int(p["white_player_id"]))
                    continue
                    
                w_id = int(p["white_player_id"])
                b_id = int(p["black_player_id"])
                
                if p["result"] == "1-0":
                    active_players_set.add(w_id)
                elif p["result"] == "0-1":
                    active_players_set.add(b_id)
                else: 
                    w_idx = seed_map.get(w_id, 9999)
                    b_idx = seed_map.get(b_id, 9999)
                    if w_idx < b_idx:
                        active_players_set.add(w_id)
                    else:
                        active_players_set.add(b_id)
                        
            active_players = [pl for pl in ordered if int(pl["id"]) in active_players_set]
            
        if len(active_players) == 1:
            raise AppError("O torneio já tem um vencedor. Não é possível gerar mais rodadas.")
            
        N = len(active_players)
        pow2 = 1
        while pow2 < N:
            pow2 *= 2
            
        if pow2 != N:
            num_byes = pow2 - N
            bye_players = active_players[:num_byes]
            playing_players = active_players[num_byes:]
        else:
            bye_players = []
            playing_players = active_players[:]
            
        pairings: list[dict[str, Any]] = []
        board = 1
        
        half = len(playing_players) // 2
        for i in range(half):
            p1 = playing_players[i]
            p2 = playing_players[len(playing_players) - 1 - i]
            if i % 2 == 0:
                w, b = p1, p2
            else:
                w, b = p2, p1
                
            pairings.append({
                "board_number": board,
                "white_player_id": w["id"],
                "black_player_id": b["id"],
                "result": "",
                "is_bye": 0,
            })
            board += 1
            
        for p in bye_players:
            pairings.append({
                "board_number": board,
                "white_player_id": p["id"],
                "black_player_id": None,
                "result": "1-0" if not settings.get("disable_bye") else "",
                "is_bye": 1,
            })
            board += 1
            
        return pairings

    def _first_round_pairings(self, players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            players,
            key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
        )
        pairable = ordered[:]
        bye_player = None
        if len(pairable) % 2 == 1:
            bye_player = min(
                pairable,
                key=lambda player: (int(player["rating"] or 0), player["name"].casefold()),
            )
            pairable.remove(bye_player)

        half = len(pairable) // 2
        upper = pairable[:half]
        lower = pairable[half:]
        pairings: list[dict[str, Any]] = []

        board = 1
        for index, player in enumerate(upper):
            opponent = lower[index]
            if index % 2 == 0:
                white_id = player["id"]
                black_id = opponent["id"]
            else:
                white_id = opponent["id"]
                black_id = player["id"]
            pairings.append(
                {
                    "board_number": board,
                    "white_player_id": white_id,
                    "black_player_id": black_id,
                    "result": "",
                    "is_bye": 0,
                }
            )
            board += 1

        if bye_player:
            pairings.append(
                {
                    "board_number": board,
                    "white_player_id": bye_player["id"],
                    "black_player_id": None,
                    "result": "BYE",
                    "is_bye": 1,
                }
            )
        return pairings

    @staticmethod
    def _find_player_slot(
        pairings: list[dict[str, Any]],
        player_id: int,
    ) -> dict[str, Any] | None:
        for pairing in pairings:
            if int(pairing["white_player_id"]) == int(player_id):
                return {"pairing": pairing, "color": "white"}
            if pairing["black_player_id"] and int(pairing["black_player_id"]) == int(player_id):
                return {"pairing": pairing, "color": "black"}
        return None

    def _is_color_valid_fide(self, player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
        history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
        white_count = history.count("W")
        black_count = history.count("B")
        next_white = white_count + (1 if color == "W" else 0)
        next_black = black_count + (1 if color == "B" else 0)
        if abs(next_white - next_black) > 2:
            return False
        if len(history) >= 2 and history[-2:] == [color, color]:
            return False
        return True

    def _search_dutch_pairing(
        self,
        pairable: list[dict[str, Any]],
        histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        strict_colors: bool,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
        if not pairable:
            return []
            
        n = len(pairable)
        half = n // 2
        S1 = pairable[:half]
        S2 = pairable[half:]
        
        def solve(s1_idx: int, available_s2: list[dict[str, Any]], current_pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
            if s1_idx == len(S1):
                return current_pairs
                
            p1 = S1[s1_idx]
            for i, p2 in enumerate(available_s2):
                if frozenset((p1["id"], p2["id"])) in played_pairs:
                    continue
                    
                if strict_colors:
                    white_id, black_id = self._choose_colors(p1, p2, histories)
                    p1_color = "W" if white_id == p1["id"] else "B"
                    p2_color = "W" if white_id == p2["id"] else "B"
                    
                    if not self._is_color_valid_fide(p1["id"], p1_color, histories) or not self._is_color_valid_fide(p2["id"], p2_color, histories):
                        p1_color_rev = "B" if p1_color == "W" else "W"
                        p2_color_rev = "B" if p2_color == "W" else "W"
                        if not self._is_color_valid_fide(p1["id"], p1_color_rev, histories) or not self._is_color_valid_fide(p2["id"], p2_color_rev, histories):
                            continue
                            
                next_pairs = solve(s1_idx + 1, available_s2[:i] + available_s2[i+1:], current_pairs + [(p1, p2)])
                if next_pairs is not None:
                    return next_pairs
            return None
            
        return solve(0, S2, [])

    def _dutch_bracket_pairing(
        self,
        group: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        histories: dict[int, list[str]],
        float_histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        rank_by_player_id: dict[int, int],
    ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
        n = len(group)
        
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            best_pairs = self._search_dutch_pairing(pairable, histories, played_pairs, strict_colors=True)
            if best_pairs is not None:
                return best_pairs, floaters
                
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            best_pairs = self._search_dutch_pairing(pairable, histories, played_pairs, strict_colors=False)
            if best_pairs is not None:
                return best_pairs, floaters
                
        for num_floaters in range(n % 2, n + 1, 2):
            if num_floaters == n:
                break
            pairable = group[:-num_floaters] if num_floaters else group
            floaters = group[-num_floaters:] if num_floaters else []
            if len(pairable) <= self.MAX_EXHAUSTIVE_PAIRING_PLAYERS:
                best_pairs = self._optimal_player_pairs(pairable, standings, histories, float_histories, played_pairs, rank_by_player_id)
            else:
                best_pairs = self._greedy_player_pairs(pairable, standings, histories, float_histories, played_pairs, rank_by_player_id)
            
            if all(frozenset((p1["id"], p2["id"])) not in played_pairs for p1, p2 in best_pairs):
                return best_pairs, floaters
                
        return [], group

    def _swiss_pairings(
        self,
        tournament_id: int,
        players: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        standings = {item["player_id"]: item for item in self.standings(tournament_id)}
        histories = self._color_histories(tournament_id)
        float_histories = self._float_histories(tournament_id)
        played_pairs = self._played_pairs(tournament_id)
        bye_player_ids = self._bye_player_ids(tournament_id)
        rank_by_player_id = self._rank_by_player_id(standings)

        pending = sorted(
            players,
            key=lambda player: self._pairing_order_key(player, standings),
        )

        pairings: list[dict[str, Any]] = []
        board = 1

        if len(pending) % 2 == 1:
            bye_player = self._choose_bye_player(pending, standings, bye_player_ids)
            pending.remove(bye_player)
            pairings.append(
                {
                    "board_number": 9999,
                    "white_player_id": bye_player["id"],
                    "black_player_id": None,
                    "result": "BYE",
                    "is_bye": 1,
                }
            )

        score_groups: dict[float, list[dict[str, Any]]] = {}
        for player in pending:
            score = float(standings.get(player["id"], {}).get("points", 0.0) or 0.0)
            score_groups.setdefault(score, []).append(player)

        sorted_scores = sorted(score_groups.keys(), reverse=True)
        player_pairs = []
        floaters = []

        for score in sorted_scores:
            group = score_groups[score]
            group.extend(floaters)
            floaters = []
            
            group = sorted(group, key=lambda p: self._pairing_order_key(p, standings))
            
            group_pairs, group_floaters = self._dutch_bracket_pairing(
                group, standings, histories, float_histories, played_pairs, rank_by_player_id
            )
            player_pairs.extend(group_pairs)
            floaters.extend(group_floaters)
            
        if floaters:
            if len(floaters) <= self.MAX_EXHAUSTIVE_PAIRING_PLAYERS:
                leftover_pairs = self._optimal_player_pairs(floaters, standings, histories, float_histories, played_pairs, rank_by_player_id)
            else:
                leftover_pairs = self._greedy_player_pairs(floaters, standings, histories, float_histories, played_pairs, rank_by_player_id)
            player_pairs.extend(leftover_pairs)

        player_pairs = sorted(
            player_pairs,
            key=lambda pair: min(
                rank_by_player_id.get(pair[0]["id"], 0),
                rank_by_player_id.get(pair[1]["id"], 0),
            ),
        )
        for player, opponent in player_pairs:
            white_id, black_id = self._choose_colors(player, opponent, histories)
            pairings.append(
                {
                    "board_number": board,
                    "white_player_id": white_id,
                    "black_player_id": black_id,
                    "result": "",
                    "is_bye": 0,
                }
            )
            board += 1

        normal_pairings = [pairing for pairing in pairings if not pairing["is_bye"]]
        bye_pairings = [pairing for pairing in pairings if pairing["is_bye"]]
        for index, pairing in enumerate(normal_pairings + bye_pairings, start=1):
            pairing["board_number"] = index
        return normal_pairings + bye_pairings

    def _greedy_player_pairs(
        self,
        players: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        histories: dict[int, list[str]],
        float_histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        rank_by_player_id: dict[int, int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        pending = players[:]
        pairs = []
        while pending:
            player = pending.pop(0)
            opponent = min(
                pending,
                key=lambda candidate: self._pair_penalty(
                    player,
                    candidate,
                    standings,
                    histories,
                    float_histories,
                    played_pairs,
                    rank_by_player_id,
                ),
            )
            pending.remove(opponent)
            pairs.append((player, opponent))
        return pairs

    def _optimal_player_pairs(
        self,
        players: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        histories: dict[int, list[str]],
        float_histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        rank_by_player_id: dict[int, int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        player_by_id = {int(player["id"]): player for player in players}
        penalty_cache: dict[tuple[int, int], float] = {}

        def penalty(player_id: int, opponent_id: int) -> float:
            key = (player_id, opponent_id)
            if key not in penalty_cache:
                penalty_cache[key] = self._pair_penalty(
                    player_by_id[player_id],
                    player_by_id[opponent_id],
                    standings,
                    histories,
                    float_histories,
                    played_pairs,
                    rank_by_player_id,
                )
            return penalty_cache[key]

        best_cost = float("inf")
        best_pairs: list[tuple[int, int]] = []
        seen_costs: dict[tuple[int, ...], float] = {}

        def search(
            remaining: tuple[int, ...],
            selected_pairs: list[tuple[int, int]],
            current_cost: float,
        ) -> None:
            nonlocal best_cost, best_pairs
            if current_cost >= best_cost:
                return
            if current_cost >= seen_costs.get(remaining, float("inf")):
                return
            seen_costs[remaining] = current_cost
            if not remaining:
                best_cost = current_cost
                best_pairs = selected_pairs[:]
                return

            player_id = remaining[0]
            candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(player_id, candidate_id))
            for opponent_id in candidates:
                next_remaining = tuple(
                    item_id for item_id in remaining[1:] if item_id != opponent_id
                )
                search(
                    next_remaining,
                    selected_pairs + [(player_id, opponent_id)],
                    current_cost + penalty(player_id, opponent_id),
                )

        search(tuple(player_by_id), [], 0.0)
        if not best_pairs:
            return self._greedy_player_pairs(
                players,
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
            )
        return [(player_by_id[player_id], player_by_id[opponent_id]) for player_id, opponent_id in best_pairs]

    @staticmethod
    def _rank_by_player_id(standings: dict[int, dict[str, Any]]) -> dict[int, int]:
        return {
            int(player_id): int(item.get("position", 0) or 0)
            for player_id, item in standings.items()
        }

    @staticmethod
    def _pairing_order_key(
        player: dict[str, Any],
        standings: dict[int, dict[str, Any]],
    ) -> tuple[float, float, float, float, int, int, str]:
        standing = standings.get(player["id"], {})
        return (
            -float(standing.get("points", 0.0) or 0.0),
            -float(standing.get("buchholz", 0.0) or 0.0),
            -float(standing.get("buchholz_median", 0.0) or 0.0),
            -float(standing.get("sonneborn_berger", 0.0) or 0.0),
            -int(standing.get("wins", 0) or 0),
            -int(player["rating"] or 0),
            player["name"].casefold(),
        )

    def _choose_bye_player(
        self,
        players: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        bye_player_ids: set[int],
    ) -> dict[str, Any]:
        candidates = [player for player in players if player["id"] not in bye_player_ids]
        if not candidates:
            candidates = players
        return min(
            candidates,
            key=lambda player: (
                standings.get(player["id"], {}).get("points", 0.0),
                int(player["rating"] or 0),
                player["name"].casefold(),
            ),
        )

    @staticmethod
    def _team_pairing_order_key(
        team: dict[str, Any],
        standings: dict[int, dict[str, Any]],
        seed_ratings: dict[int, int],
    ) -> tuple[float, float, int, str]:
        team_id = int(team["id"])
        standing = standings.get(team_id, {})
        return (
            -float(standing.get("match_points", 0.0) or 0.0),
            -float(standing.get("game_points", 0.0) or 0.0),
            -int(seed_ratings.get(team_id, 0)),
            str(team["name"]).casefold(),
        )

    def _choose_team_bye(
        self,
        teams: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        bye_team_ids: set[int],
        seed_ratings: dict[int, int],
    ) -> dict[str, Any]:
        candidates = [team for team in teams if int(team["id"]) not in bye_team_ids]
        if not candidates:
            candidates = teams
        return min(
            candidates,
            key=lambda team: (
                float(standings.get(int(team["id"]), {}).get("match_points", 0.0) or 0.0),
                float(standings.get(int(team["id"]), {}).get("game_points", 0.0) or 0.0),
                seed_ratings.get(int(team["id"]), 0),
                str(team["name"]).casefold(),
            ),
        )

    def _greedy_team_pairs(
        self,
        teams: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        played_pairs: set[frozenset[int]],
        rank_by_team_id: dict[int, int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        pending = teams[:]
        pairs = []
        while pending:
            team = pending.pop(0)
            opponent = min(
                pending,
                key=lambda candidate: self._team_pair_penalty(
                    team,
                    candidate,
                    standings,
                    played_pairs,
                    rank_by_team_id,
                ),
            )
            pending.remove(opponent)
            pairs.append((team, opponent))
        return pairs

    def _optimal_team_pairs(
        self,
        teams: list[dict[str, Any]],
        standings: dict[int, dict[str, Any]],
        played_pairs: set[frozenset[int]],
        rank_by_team_id: dict[int, int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        team_by_id = {int(team["id"]): team for team in teams}
        penalty_cache: dict[tuple[int, int], float] = {}

        def penalty(team_id: int, opponent_id: int) -> float:
            key = (team_id, opponent_id)
            if key not in penalty_cache:
                penalty_cache[key] = self._team_pair_penalty(
                    team_by_id[team_id],
                    team_by_id[opponent_id],
                    standings,
                    played_pairs,
                    rank_by_team_id,
                )
            return penalty_cache[key]

        best_cost = float("inf")
        best_pairs: list[tuple[int, int]] = []
        seen_costs: dict[tuple[int, ...], float] = {}

        def search(
            remaining: tuple[int, ...],
            selected_pairs: list[tuple[int, int]],
            current_cost: float,
        ) -> None:
            nonlocal best_cost, best_pairs
            if current_cost >= best_cost:
                return
            if current_cost >= seen_costs.get(remaining, float("inf")):
                return
            seen_costs[remaining] = current_cost
            if not remaining:
                best_cost = current_cost
                best_pairs = selected_pairs[:]
                return

            team_id = remaining[0]
            candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(team_id, candidate_id))
            for opponent_id in candidates:
                next_remaining = tuple(item_id for item_id in remaining[1:] if item_id != opponent_id)
                search(
                    next_remaining,
                    selected_pairs + [(team_id, opponent_id)],
                    current_cost + penalty(team_id, opponent_id),
                )

        search(tuple(team_by_id), [], 0.0)
        if not best_pairs:
            return self._greedy_team_pairs(teams, standings, played_pairs, rank_by_team_id)
        return [(team_by_id[team_id], team_by_id[opponent_id]) for team_id, opponent_id in best_pairs]

    def _team_pair_penalty(
        self,
        team: dict[str, Any],
        opponent: dict[str, Any],
        standings: dict[int, dict[str, Any]],
        played_pairs: set[frozenset[int]],
        rank_by_team_id: dict[int, int],
    ) -> float:
        team_id = int(team["id"])
        opponent_id = int(opponent["id"])
        team_score = float(standings.get(team_id, {}).get("match_points", 0.0) or 0.0)
        opponent_score = float(standings.get(opponent_id, {}).get("match_points", 0.0) or 0.0)
        score_diff = abs(team_score - opponent_score)
        penalty = score_diff * self.SCORE_DIFF_PENALTY
        if score_diff:
            penalty += self.SCORE_GROUP_FLOAT_PENALTY

        rank_distance = abs(rank_by_team_id.get(team_id, 0) - rank_by_team_id.get(opponent_id, 0))
        penalty += rank_distance * (4 if not score_diff else 1)

        if frozenset((team_id, opponent_id)) in played_pairs:
            penalty += self.REPEAT_PAIRING_PENALTY
        return penalty

    def _choose_team_colors(
        self,
        team: dict[str, Any],
        opponent: dict[str, Any],
        histories: dict[int, list[str]],
        seed_ratings: dict[int, int],
    ) -> tuple[int, int]:
        team_id = int(team["id"])
        opponent_id = int(opponent["id"])
        first_penalty = self._assignment_color_penalty(team_id, "W", histories)
        first_penalty += self._assignment_color_penalty(opponent_id, "B", histories)

        second_penalty = self._assignment_color_penalty(team_id, "B", histories)
        second_penalty += self._assignment_color_penalty(opponent_id, "W", histories)

        if first_penalty < second_penalty:
            return team_id, opponent_id
        if second_penalty < first_penalty:
            return opponent_id, team_id
        if seed_ratings.get(team_id, 0) >= seed_ratings.get(opponent_id, 0):
            return team_id, opponent_id
        return opponent_id, team_id

    def _team_played_pairs(self, tournament_id: int) -> set[frozenset[int]]:
        played: set[frozenset[int]] = set()
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            if match["is_bye"] or not match["black_team_id"]:
                continue
            played.add(frozenset((int(match["white_team_id"]), int(match["black_team_id"]))))
        return played

    def _team_bye_ids(self, tournament_id: int) -> set[int]:
        return {
            int(match["white_team_id"])
            for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
            if match["is_bye"]
        }

    def _team_color_histories(self, tournament_id: int) -> dict[int, list[str]]:
        histories: dict[int, list[str]] = {}
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            white_team_id = int(match["white_team_id"])
            black_team_id = int(match["black_team_id"]) if match["black_team_id"] else None
            histories.setdefault(white_team_id, [])
            if match["is_bye"]:
                histories[white_team_id].append("BYE")
                continue
            histories[white_team_id].append("W")
            if black_team_id:
                histories.setdefault(black_team_id, [])
                histories[black_team_id].append("B")
        return histories

    def _played_pairs(self, tournament_id: int) -> set[frozenset[int]]:
        played: set[frozenset[int]] = set()
        for pairing in self.db.get_pairings_for_tournament(tournament_id, closed_only=True):
            if pairing["is_bye"] or not pairing["black_player_id"]:
                continue
            played.add(frozenset((pairing["white_player_id"], pairing["black_player_id"])))
        return played

    def _bye_player_ids(self, tournament_id: int) -> set[int]:
        return {
            pairing["white_player_id"]
            for pairing in self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
            if pairing["is_bye"]
        }

    def _color_histories(self, tournament_id: int) -> dict[int, list[str]]:
        histories: dict[int, list[str]] = {}
        for pairing in self.db.get_pairings_for_tournament(tournament_id, closed_only=True):
            white_id = pairing["white_player_id"]
            black_id = pairing["black_player_id"]
            histories.setdefault(white_id, [])
            if pairing["is_bye"]:
                histories[white_id].append("BYE")
                continue
            if black_id:
                histories.setdefault(black_id, [])
                histories[white_id].append("W")
                histories[black_id].append("B")
        return histories

    def _float_histories(self, tournament_id: int) -> dict[int, list[str]]:
        tournament = self.db.get_tournament(tournament_id)
        bye_points = float(tournament["bye_points"] if tournament else 0.0)
        players = self.db.list_players(tournament_id, active_only=False)
        scores = {
            int(player["id"]): float(player.get("starting_points", 0.0) or 0.0)
            for player in players
        }
        histories: dict[int, list[str]] = {player_id: [] for player_id in scores}

        for pairing in self.db.get_pairings_for_tournament(tournament_id, closed_only=True):
            white_id = int(pairing["white_player_id"])
            black_id = int(pairing["black_player_id"]) if pairing["black_player_id"] else None
            histories.setdefault(white_id, [])
            scores.setdefault(white_id, 0.0)

            if pairing["is_bye"]:
                histories[white_id].append("bye")
                scores[white_id] += bye_points
                continue

            if black_id is None:
                continue
            histories.setdefault(black_id, [])
            scores.setdefault(black_id, 0.0)

            white_score = scores[white_id]
            black_score = scores[black_id]
            if white_score < black_score:
                histories[white_id].append("up")
                histories[black_id].append("down")
            elif white_score > black_score:
                histories[white_id].append("down")
                histories[black_id].append("up")
            else:
                histories[white_id].append("=")
                histories[black_id].append("=")

            result = pairing["result"]
            if result in RESULT_POINTS:
                white_points, black_points = RESULT_POINTS[result]
                scores[white_id] += white_points
                scores[black_id] += black_points
        return histories

    def _pair_penalty(
        self,
        player: dict[str, Any],
        opponent: dict[str, Any],
        standings: dict[int, dict[str, Any]],
        histories: dict[int, list[str]],
        float_histories: dict[int, list[str]],
        played_pairs: set[frozenset[int]],
        rank_by_player_id: dict[int, int],
    ) -> float:
        player_id = player["id"]
        opponent_id = opponent["id"]
        player_score = float(standings.get(player_id, {}).get("points", 0.0) or 0.0)
        opponent_score = float(standings.get(opponent_id, {}).get("points", 0.0) or 0.0)
        score_diff = abs(player_score - opponent_score)
        penalty = score_diff * self.SCORE_DIFF_PENALTY

        if score_diff:
            penalty += self.SCORE_GROUP_FLOAT_PENALTY
            if player_score < opponent_score:
                penalty += self._float_penalty(player_id, "up", float_histories)
                penalty += self._float_penalty(opponent_id, "down", float_histories)
            else:
                penalty += self._float_penalty(player_id, "down", float_histories)
                penalty += self._float_penalty(opponent_id, "up", float_histories)

        rank_distance = abs(
            rank_by_player_id.get(player_id, 0)
            - rank_by_player_id.get(opponent_id, 0)
        )
        penalty += rank_distance * (4 if not score_diff else 1)

        if frozenset((player_id, opponent_id)) in played_pairs:
            penalty += self.REPEAT_PAIRING_PENALTY

        white_a, black_a = self._choose_colors(player, opponent, histories)
        color_penalty = self._assignment_color_penalty(player_id, "W", histories)
        color_penalty += self._assignment_color_penalty(opponent_id, "B", histories)
        if white_a == opponent_id and black_a == player_id:
            color_penalty = self._assignment_color_penalty(player_id, "B", histories)
            color_penalty += self._assignment_color_penalty(opponent_id, "W", histories)

        return penalty + color_penalty

    @staticmethod
    def _float_penalty(
        player_id: int,
        direction: str,
        float_histories: dict[int, list[str]],
    ) -> int:
        history = float_histories.get(player_id, [])
        penalty = history.count(direction) * 25
        if history[-2:] == [direction, direction]:
            penalty += 300
        elif history[-1:] == [direction]:
            penalty += 120
        return penalty

    def _choose_colors(
        self,
        player: dict[str, Any],
        opponent: dict[str, Any],
        histories: dict[int, list[str]],
    ) -> tuple[int, int]:
        player_id = player["id"]
        opponent_id = opponent["id"]
        first_penalty = self._assignment_color_penalty(player_id, "W", histories)
        first_penalty += self._assignment_color_penalty(opponent_id, "B", histories)

        second_penalty = self._assignment_color_penalty(player_id, "B", histories)
        second_penalty += self._assignment_color_penalty(opponent_id, "W", histories)

        if first_penalty < second_penalty:
            return player_id, opponent_id
        if second_penalty < first_penalty:
            return opponent_id, player_id

        if int(player["rating"] or 0) >= int(opponent["rating"] or 0):
            return player_id, opponent_id
        return opponent_id, player_id

    def _assignment_color_penalty(
        self,
        player_id: int,
        color: str,
        histories: dict[int, list[str]],
    ) -> int:
        history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
        white_count = history.count("W")
        black_count = history.count("B")
        next_white = white_count + (1 if color == "W" else 0)
        next_black = black_count + (1 if color == "B" else 0)
        penalty = abs(next_white - next_black) * 12

        if history[-2:] == [color, color]:
            penalty += 250
        elif history[-1:] == [color]:
            penalty += 20

        if white_count - black_count >= 2 and color == "W":
            penalty += 120
        if black_count - white_count >= 2 and color == "B":
            penalty += 120

        return penalty
