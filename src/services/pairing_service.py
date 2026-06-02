from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any

from src.core.database import Database
from src.services.constants import (
    AppError,
    FINAL_RESULTS,
    RESULTS,
    RESULT_POINTS,
    RESULT_STATES,
    pairing_player_name,
)
from src.services.pairing import (
    accelerated_standings as _accelerated_standings,
    acknowledged_issue_keys as _acknowledged_issue_keys,
    append_requested_bye_pairings as _append_requested_bye_pairings,
    audit_issue as _audit_issue,
    blocking_issues_message as _blocking_issues_message,
    bye_player_ids as _bye_player_ids,
    calculate_player_standings as _calculate_player_standings,
    calculate_team_standings as _calculate_team_standings,
    clock_event_issue as _clock_event_issue,
    color_histories as _color_histories,
    derive_pairing_state as _derive_pairing_state,
    finalize_issues as _finalize_issues,
    find_player_slot as _find_player_slot,
    find_team_board_player_slot as _find_team_board_player_slot,
    flatten_tiebreak_components as _flatten_tiebreak_components,
    float_histories as _float_histories,
    first_round_pairings as _first_round_pairings,
    first_round_team_matches as _first_round_team_matches,
    individual_preview_payload as _individual_preview_payload,
    individual_round_dashboard_metrics as _individual_round_dashboard_metrics,
    issue_matches_round as _issue_matches_round,
    issue_metrics as _issue_metrics,
    knockout_pairings as _knockout_pairings,
    pairing_input_snapshot as _pairing_input_snapshot,
    parse_player_tiebreak_sequence as _parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence as _parse_team_tiebreak_sequence,
    plan_pairing_player_swap as _plan_pairing_player_swap,
    plan_team_board_player_swap as _plan_team_board_player_swap,
    played_pairs as _played_pairs,
    prohibited_pairs_for_round as _prohibited_pairs_for_round,
    result_submission_issue as _result_submission_issue,
    result_states_summary as _result_states_summary,
    round_robin_pairings as _round_robin_pairings,
    scheveningen_pairings as _scheveningen_pairings,
    team_preview_payload as _team_preview_payload,
    team_round_dashboard_metrics as _team_round_dashboard_metrics,
    tiebreak_narrative_from_standings as _tiebreak_narrative_from_standings,
    swiss_pairings as _swiss_pairings,
    swiss_team_matches as _swiss_team_matches,
    team_bye_payload as _team_bye_payload,
    team_bye_summary as _team_bye_summary,
    team_match_summary as _team_match_summary,
    team_starter_roster as _team_starter_roster,
    team_bye_ids as _team_bye_ids,
    team_color_histories as _team_color_histories,
    team_played_pairs as _team_played_pairs,
)

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

    @staticmethod
    def derive_pairing_state(
        *,
        result: str,
        round_closed: bool,
        has_pending_submission: bool = False,
        has_correction: bool = False,
    ) -> str:
        """Delegação para src.services.pairing.result_states.derive_pairing_state.

        Mantida na classe para compatibilidade da API existente.
        """
        return _derive_pairing_state(
            result=result,
            round_closed=round_closed,
            has_pending_submission=has_pending_submission,
            has_correction=has_correction,
        )

    def result_states_summary(self, tournament_id: int) -> dict[str, int]:
        """Conta mesas do torneio por estado derivado de resultado.

        Cobre apenas pairings individuais; tabuleiros de equipe ficam para
        evolução futura (semântica idêntica, fonte de dados diferente).
        """
        pairings = self.db.get_pairings_for_tournament(tournament_id)
        audit_events = self.db.list_audit_events(tournament_id, limit=10000)
        result_submissions = self.db.list_result_submissions(
            tournament_id=tournament_id, status="submitted"
        )
        return _result_states_summary(pairings, audit_events, result_submissions, RESULT_STATES)

    def arbitration_dashboard(
        self,
        tournament_id: int,
        pending_limit: int = 20,
        pending_query: str = "",
    ) -> dict[str, Any]:
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
            "total_results": 0,
            "resolved_results": 0,
            "round_progress_percent": 0,
            "result_states": self.result_states_summary(tournament_id),
            **self._round_clock_metrics(latest_round),
        }
        alerts: list[str] = []
        alerts_detailed: list[dict[str, Any]] = []

        def add_alert(text: str, severity: str, action: str = "") -> None:
            # Mantem `alerts` (strings, retrocompatibilidade) em sincronia com a
            # versao estruturada usada pelos alertas clicaveis do painel.
            alerts.append(text)
            alerts_detailed.append({"text": text, "severity": severity, "action": action})
        if latest_round:
            if tournament.get("competition_type") == "team":
                metrics.update(self._team_round_dashboard_metrics(int(latest_round["id"])))
            else:
                metrics.update(self._individual_round_dashboard_metrics(int(latest_round["id"])))
            if latest_round.get("status") != "closed":
                if metrics["pending_results"]:
                    add_alert(
                        f"Rodada {latest_round['number']} tem {metrics['pending_results']} resultado(s) pendente(s).",
                        "danger",
                        "pending_results",
                    )
                else:
                    blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, int(latest_round["id"]))
                    metrics["blocking_issues"] = len(blocking_issues)
                    if blocking_issues:
                        metrics["ready_to_close"] = False
                        add_alert(
                            f"Rodada {latest_round['number']} tem {len(blocking_issues)} pendencia(s) de arbitragem bloqueante(s).",
                            "danger",
                            "blocking_issues",
                        )
                    else:
                        add_alert(
                            f"Rodada {latest_round['number']} esta pronta para fechamento.",
                            "success",
                            "ready_to_close",
                        )
        else:
            add_alert(
                "Nenhuma rodada gerada. Use a chamada inicial antes da primeira rodada.",
                "info",
                "initial_call",
            )
        if absent_players:
            add_alert(f"{len(absent_players)} jogador(es) marcado(s) como ausente(s).", "info", "absent_players")
        if correction_count:
            add_alert(f"{correction_count} correcao(oes) auditada(s) no torneio.", "info", "corrections")
        if submitted_results:
            add_alert(
                f"{submitted_results} resultado(s) enviado(s) por QR aguardando aprovacao.",
                "danger",
                "qr_pending",
            )

        if not latest_round or latest_round.get("status") == "closed":
            try:
                preview = self.preview_next_round(tournament_id)
                metrics["can_preview_next_round"] = True
                metrics["preview_alerts"] = int(preview.get("alerts_count") or 0)
                if metrics["preview_alerts"]:
                    add_alert(
                        f"Previa da proxima rodada tem {metrics['preview_alerts']} alerta(s).",
                        "info",
                        "preview_next",
                    )
            except AppError as exc:
                add_alert(str(exc), "info", "")

        # Progresso da rodada atual (mesas resolvidas / total que precisa de resultado).
        total_results = int(metrics.get("total_results") or 0)
        resolved_results = int(metrics.get("resolved_results") or 0)
        metrics["round_progress_percent"] = round(100 * resolved_results / total_results) if total_results else 0

        pending_items = self._pending_round_items(
            latest_round,
            metrics["competition_type"],
            pending_limit,
            pending_query,
        )
        return {
            "metrics": metrics,
            "alerts": alerts,
            "alerts_detailed": alerts_detailed,
            "pending_items": pending_items,
        }

    def closing_checklist(self, tournament_id: int) -> list[dict[str, Any]]:
        """Checklist de fechamento da rodada atual, derivado do painel.

        Cada item: {label, ok, action} — `action` reaproveita o mapa de acoes dos
        alertas clicaveis do painel.
        """
        metrics = self.arbitration_dashboard(tournament_id)["metrics"]
        status = metrics.get("latest_round_status")
        if status == "sem_rodadas":
            return [{"label": "Gerar a primeira rodada", "ok": False, "action": "initial_call"}]
        if status == "closed":
            return [
                {"label": f"Rodada {metrics['latest_round_number']} fechada", "ok": True, "action": ""}
            ]
        total = int(metrics.get("total_results") or 0)
        resolved = int(metrics.get("resolved_results") or 0)
        items: list[dict[str, Any]] = [
            {
                "label": f"Resultados lancados ({resolved}/{total})",
                "ok": int(metrics.get("pending_results") or 0) == 0,
                "action": "pending_results",
            },
            {
                "label": "Sem resultados QR aguardando aprovacao",
                "ok": int(metrics.get("submitted_results") or 0) == 0,
                "action": "qr_pending",
            },
            {
                "label": "Sem pendencias de arbitragem bloqueantes",
                "ok": int(metrics.get("blocking_issues") or 0) == 0,
                "action": "blocking_issues",
            },
        ]
        # Especifico de equipes: escalacoes/ordem de tabuleiro sem avisos de policy.
        if metrics.get("competition_type") == "team":
            from src.services.tournament_service import TeamService

            rounds = sorted(self.db.list_rounds(tournament_id), key=lambda item: int(item["number"]))
            latest_round_id = int(rounds[-1]["id"]) if rounds else None
            roster_issues = TeamService(self.db).validate_roster_policy(tournament_id, round_id=latest_round_id)
            items.append(
                {
                    "label": f"Escalacoes sem pendencias ({len(roster_issues)})",
                    "ok": not roster_issues,
                    "action": "lineups",
                }
            )
        items.append(
            {
                "label": f"Rodada {metrics['latest_round_number']} pronta para fechar",
                "ok": bool(metrics.get("ready_to_close")),
                "action": "ready_to_close",
            }
        )
        return items

    def _round_clock_metrics(self, latest_round: dict[str, Any] | None) -> dict[str, Any]:
        if not latest_round:
            return {
                "round_clock_status": "sem_rodada",
                "round_started_at": "",
                "round_closed_at": "",
                "round_started_label": "--",
                "round_duration_seconds": 0,
                "round_duration_label": "--",
            }
        started_at = str(latest_round.get("created_at") or "")
        is_closed = latest_round.get("status") == "closed"
        closed_at = str(latest_round.get("closed_at") or "")
        ended_at = closed_at if is_closed and closed_at else self.db.now()
        duration_seconds = self._elapsed_seconds(started_at, ended_at)
        return {
            "round_clock_status": "fechada" if is_closed else "em_andamento",
            "round_started_at": started_at,
            "round_closed_at": closed_at,
            "round_started_label": self._timestamp_label(started_at),
            "round_duration_seconds": duration_seconds,
            "round_duration_label": self._duration_label(duration_seconds),
        }

    @staticmethod
    def _elapsed_seconds(started_at: str, ended_at: str) -> int:
        try:
            started = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
            ended = datetime.strptime(ended_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return 0
        return max(0, int((ended - started).total_seconds()))

    @staticmethod
    def _timestamp_label(value: str) -> str:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m %H:%M")
        except ValueError:
            return "--"

    @staticmethod
    def _duration_label(seconds: int) -> str:
        hours, remainder = divmod(max(0, int(seconds)), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _pending_round_items(
        self,
        latest_round: dict[str, Any] | None,
        competition_type: str,
        limit: int = 20,
        query: str = "",
    ) -> list[dict[str, Any]]:
        if not latest_round or latest_round.get("status") == "closed":
            return []
        safe_limit = max(1, min(int(limit or 20), 100))
        normalized_query = str(query or "").strip().casefold()

        def matches_query(item: dict[str, Any]) -> bool:
            if not normalized_query:
                return True
            if normalized_query.isdigit():
                return int(item.get("board") or 0) == int(normalized_query)
            searchable = " ".join(
                str(item.get(field) or "")
                for field in ("board", "context", "white", "black")
            ).casefold()
            return normalized_query in searchable

        if competition_type != "team":
            return [
                {
                    "pairing_id": int(pairing["id"]),
                    "board": int(pairing.get("board_number") or 0),
                    "white": pairing_player_name(pairing, "white"),
                    "black": "BYE" if pairing.get("is_bye") else pairing_player_name(pairing, "black"),
                    "context": "",
                }
                for pairing in self.db.get_pairings_for_round(int(latest_round["id"]))
                if not pairing.get("result") or pairing.get("result") not in FINAL_RESULTS
                if matches_query(
                    {
                        "board": int(pairing.get("board_number") or 0),
                        "white": pairing_player_name(pairing, "white"),
                        "black": "BYE" if pairing.get("is_bye") else pairing_player_name(pairing, "black"),
                        "context": "",
                    }
                )
            ][:safe_limit]

        pending_items: list[dict[str, Any]] = []
        for match in self.db.list_team_matches_for_round(int(latest_round["id"])):
            if match.get("is_bye"):
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                if board.get("result") and board.get("result") in FINAL_RESULTS:
                    continue
                pending_items.append(
                    {
                        "pairing_id": int(board["id"]),
                        "board": int(board.get("board_number") or 0),
                        "white": str(board.get("white_player_name") or ""),
                        "black": str(board.get("black_player_name") or ""),
                        "context": f"Match {match.get('match_number') or ''}",
                    }
                )
                if not matches_query(pending_items[-1]):
                    pending_items.pop()
                    continue
                if len(pending_items) >= safe_limit:
                    return pending_items
        return pending_items

    def arbitration_issues(self, tournament_id: int, limit: int = 200) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        issues: list[dict[str, Any]] = []
        safe_limit = max(1, min(int(limit or 200), 1000))
        acknowledged_keys = self._acknowledged_arbitration_issue_keys(tournament_id)

        for submission in self.db.list_result_submissions(tournament_id=tournament_id, status="submitted", limit=safe_limit):
            issues.append(_result_submission_issue(submission))

        for event in self.db.list_audit_events(tournament_id, action="sync_remote_rejected", limit=safe_limit):
            issues.append(_audit_issue(event, "sync", "remote_rejected", "Evento remoto rejeitado"))
        for event in self.db.list_audit_events(tournament_id, action="sync_event_rejected", limit=safe_limit):
            issues.append(_audit_issue(event, "sync", "outbox_rejected", "Evento local rejeitado pelo servidor"))

        for event in self.db.list_clock_events(tournament_id=tournament_id, limit=safe_limit):
            issue = _clock_event_issue(event)
            if issue is not None:
                issues.append(issue)

        issues = _finalize_issues(issues, acknowledged_keys, safe_limit)
        metrics = _issue_metrics(issues)
        return {"metrics": metrics, "issues": issues}

    @staticmethod
    def filter_arbitration_issues(
        issues: list[dict[str, Any]],
        issue_filter: str = "all",
        query: str = "",
    ) -> list[dict[str, Any]]:
        normalized_filter = str(issue_filter or "all").strip().casefold()
        normalized_query = str(query or "").strip().casefold()

        def matches_filter(issue: dict[str, Any]) -> bool:
            if normalized_filter in {"", "all"}:
                return True
            if normalized_filter == "decision":
                return issue.get("severity") == "decision"
            return str(issue.get("source") or "").casefold() == normalized_filter

        def matches_query(issue: dict[str, Any]) -> bool:
            if not normalized_query:
                return True
            payload = json.dumps(issue.get("payload") or {}, ensure_ascii=False, sort_keys=True)
            searchable = " ".join(
                [
                    str(issue.get("severity") or ""),
                    str(issue.get("source") or ""),
                    str(issue.get("kind") or ""),
                    str(issue.get("title") or ""),
                    str(issue.get("detail") or ""),
                    str(issue.get("round_id") or ""),
                    payload,
                ]
            ).casefold()
            return normalized_query in searchable

        return [issue for issue in issues if matches_filter(issue) and matches_query(issue)]

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
        events = self.db.list_audit_events(
            tournament_id,
            action="arbitration_issue_acknowledged",
            entity_type="arbitration_issue",
            limit=5000,
        )
        return _acknowledged_issue_keys(events)

    def _blocking_arbitration_issues_for_round(self, tournament_id: int, round_id: int) -> list[dict[str, Any]]:
        issues = self.arbitration_issues(tournament_id, limit=1000)["issues"]
        return [
            issue
            for issue in issues
            if issue.get("severity") == "decision" and _issue_matches_round(issue, round_id)
        ]

    def _individual_round_dashboard_metrics(self, round_id: int) -> dict[str, Any]:
        pairings = self.db.get_pairings_for_round(round_id)
        return _individual_round_dashboard_metrics(pairings, FINAL_RESULTS)

    def _team_round_dashboard_metrics(self, round_id: int) -> dict[str, Any]:
        matches = self.db.list_team_matches_for_round(round_id)
        boards_by_match_id = {
            int(match["id"]): self.db.list_team_boards(int(match["id"]))
            for match in matches
            if not match.get("is_bye")
        }
        return _team_round_dashboard_metrics(matches, boards_by_match_id, FINAL_RESULTS)

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

        pairing_system = str(settings.get("pairing_system") or "custom_authorized")
        input_snapshot = self._pairing_input_snapshot(
            tournament_id=tournament_id,
            tournament=tournament,
            settings=settings,
            round_number=next_number,
            participants=players,
        )
        self._save_pairing_snapshot(
            tournament_id, next_number, "input", input_snapshot,
            pairing_system=pairing_system,
            engine_version=self.PAIRING_ENGINE_VERSION,
        )
        self.db.backup_before("generate_round", tournament_id=tournament_id)
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            next_number,
            pairings,
            pairing_engine_version=self.PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )
        self._save_pairing_snapshot(
            tournament_id, next_number, "output",
            {"round_number": next_number, "pairings": pairings},
            pairing_system=pairing_system,
            engine_version=self.PAIRING_ENGINE_VERSION,
            round_id=round_id,
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
        return self._finalize_generated_round(tournament_id, tournament, next_number, round_id)

    def _save_pairing_snapshot(
        self,
        tournament_id: int,
        round_number: int,
        stage: str,
        payload: dict[str, Any],
        *,
        pairing_system: str,
        engine_version: str,
        round_id: int | None = None,
    ) -> None:
        self.db.create_pairing_snapshot(
            tournament_id,
            round_number,
            stage,
            payload,
            round_id=round_id,
            pairing_system=pairing_system,
            pairing_engine_version=engine_version,
            ruleset_version=self.RULESET_VERSION,
        )

    def _finalize_generated_round(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        round_number: int,
        round_id: int,
    ) -> dict[str, Any]:
        if tournament["status"] == "draft":
            self.db.update_tournament_status(tournament_id, "running")
        generated = self.db.get_round_by_number(tournament_id, round_number)
        if not generated:
            raise AppError("A rodada foi gerada, mas nao pode ser reaberta.")
        generated["id"] = round_id
        return generated

    def _individual_next_round_plan(self, tournament_id: int, tournament: dict[str, Any]) -> dict[str, Any]:
        players = self.db.list_players(tournament_id, active_only=True)
        if len(players) < 2:
            raise AppError("Cadastre pelo menos 2 jogadores ativos.")
        settings = self.db.get_tournament_settings(tournament_id) or {}

        latest_round = self.db.get_latest_round(tournament_id)
        if latest_round and latest_round["status"] != "closed":
            raise AppError("Feche ou exclua a rodada gerada antes de criar outra.")

        next_number = 1 if not latest_round else int(latest_round["number"]) + 1
        if next_number > int(tournament["rounds_count"]):
            raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")

        pairing_method = settings.get("pairing_method", "swiss")
        if pairing_method in ("round_robin", "knockout", "scheveningen"):
            # Byes solicitados sao um conceito do Suico: nestes formatos o
            # calendario e predeterminado (rotacao todos-contra-todos / chave de
            # eliminacao), entao remover um jogador corromperia o esquema. Em vez
            # de gerar pareamentos enganosos, rejeitamos com mensagem clara.
            active_ids = {int(player["id"]) for player in players}
            if any(
                int(item["player_id"]) in active_ids
                for item in self.db.list_requested_byes_for_round(tournament_id, next_number)
            ):
                raise AppError(
                    "Byes solicitados sao exclusivos do sistema Suico. Remova o bye "
                    "solicitado desta rodada ou troque o metodo de pareamento para gera-la."
                )
            # Estes metodos nao descontam byes solicitados: a paridade vale sobre
            # todos os jogadores ativos (comportamento historico).
            if settings.get("disable_bye") and len(players) % 2 == 1:
                raise AppError("O bye esta desativado. Use numero par de jogadores ativos.")
            if pairing_method == "round_robin":
                pairings = _round_robin_pairings(players, next_number, settings)
            elif pairing_method == "scheveningen":
                pairings = _scheveningen_pairings(players, next_number, settings)
            else:
                pairings = self._knockout_pairings(tournament_id, players, next_number, settings)
        else:
            active_ids = {int(player["id"]) for player in players}
            bye_by_player = {
                int(item["player_id"]): str(item["bye_type"])
                for item in self.db.list_requested_byes_for_round(tournament_id, next_number)
                if int(item["player_id"]) in active_ids
            }
            to_pair = [
                player for player in players if int(player["id"]) not in bye_by_player
            ]
            if bye_by_player and len(to_pair) < 2:
                raise AppError(
                    "Byes solicitados deixariam menos de 2 jogadores para parear."
                )
            if settings.get("disable_bye") and len(to_pair) % 2 == 1:
                raise AppError("O bye esta desativado. Use numero par de jogadores ativos.")
            if next_number == 1:
                pairings = _first_round_pairings(to_pair)
            else:
                pairings = self._swiss_pairings(tournament_id, to_pair, next_number)
            pairings = _append_requested_bye_pairings(pairings, bye_by_player)
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
        return _pairing_input_snapshot(
            tournament,
            settings,
            round_number,
            participants,
            previous_rounds,
            previous_pairings,
            extra,
        )

    def _individual_preview_payload(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        histories = self._color_histories(tournament_id)
        played_pairs = self._played_pairs(tournament_id)
        standings = {int(item["player_id"]): item for item in self.standings(tournament_id)}
        return _individual_preview_payload(
            tournament_id=tournament_id,
            tournament=tournament,
            plan=plan,
            histories=histories,
            played_pairs=played_pairs,
            standings=standings,
            pairing_engine_version=self.PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )

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

        pairing_system = str(settings.get("pairing_system") or "team_swiss")
        input_snapshot = self._pairing_input_snapshot(
            tournament_id=tournament_id,
            tournament=tournament,
            settings=settings,
            round_number=next_number,
            participants=teams,
            extra={"boards_count": boards_count, "seed_ratings": seed_ratings},
        )
        self._save_pairing_snapshot(
            tournament_id, next_number, "input", input_snapshot,
            pairing_system=pairing_system,
            engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
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
        self._save_pairing_snapshot(
            tournament_id, next_number, "output",
            {"round_number": next_number, "matches": matches},
            pairing_system=pairing_system,
            engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
            round_id=round_id,
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
        return self._finalize_generated_round(tournament_id, tournament, next_number, round_id)

    def _team_next_round_plan(self, tournament_id: int, tournament: dict[str, Any]) -> dict[str, Any]:
        settings = self.db.get_tournament_settings(tournament_id) or {}
        teams = self.db.list_teams(tournament_id, active_only=True)
        if len(teams) < 2:
            raise AppError("Cadastre pelo menos 2 equipes ativas.")

        boards_count = int(settings.get("team_boards_count") or 4)

        latest_round = self.db.get_latest_round(tournament_id)
        if latest_round and latest_round["status"] != "closed":
            raise AppError("Feche ou exclua a rodada gerada antes de criar outra.")

        next_number = 1 if not latest_round else int(latest_round["number"]) + 1
        if next_number > int(tournament["rounds_count"]):
            raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")

        active_team_ids = {int(team["id"]) for team in teams}
        bye_by_team = {
            int(item["team_id"]): str(item["bye_type"])
            for item in self.db.list_requested_team_byes_for_round(tournament_id, next_number)
            if int(item["team_id"]) in active_team_ids
        }
        to_pair = [team for team in teams if int(team["id"]) not in bye_by_team]
        if bye_by_team and len(to_pair) < 2:
            raise AppError("Byes solicitados deixariam menos de 2 equipes para parear.")
        if settings.get("disable_bye") and len(to_pair) % 2 == 1:
            raise AppError("O bye esta desativado. Use numero par de equipes ativas.")

        rosters, seed_ratings = self._team_starter_rosters(to_pair, boards_count)

        if next_number == 1:
            matches = _first_round_team_matches(to_pair, rosters, seed_ratings, boards_count, settings)
        else:
            matches = self._swiss_team_matches(
                tournament_id, to_pair, rosters, seed_ratings, boards_count, settings, next_number
            )
        matches = self._append_requested_team_byes(matches, bye_by_team, settings, boards_count)

        return {
            "settings": settings,
            "teams": teams,
            "boards_count": boards_count,
            "seed_ratings": seed_ratings,
            "round_number": next_number,
            "matches": matches,
        }

    @staticmethod
    def _append_requested_team_byes(
        matches: list[dict[str, Any]],
        bye_by_team: dict[int, str],
        settings: dict[str, Any],
        boards_count: int,
    ) -> list[dict[str, Any]]:
        """Anexa confrontos de bye solicitado (F/H/Z) ao final da rodada por equipes.

        O tipo vai no `result` do confronto; pontuacao e 240 derivam dele,
        distinguindo do bye alocado pelo pareamento (`BYE`)."""
        if not bye_by_team:
            return matches
        result = list(matches)
        next_number = max((int(m.get("match_number") or 0) for m in result), default=0) + 1
        for team_id in sorted(bye_by_team):
            result.append(
                _team_bye_payload(
                    next_number, int(team_id), settings, boards_count, bye_by_team[team_id]
                )
            )
            next_number += 1
        return result

    def _team_preview_payload(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        played_pairs = self._team_played_pairs(tournament_id)
        return _team_preview_payload(
            tournament_id=tournament_id,
            tournament=tournament,
            plan=plan,
            played_pairs=played_pairs,
            pairing_engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
            ruleset_version=self.RULESET_VERSION,
        )

    def _team_starter_rosters(
        self,
        teams: list[dict[str, Any]],
        boards_count: int,
    ) -> tuple[dict[int, dict[int, int]], dict[int, int]]:
        rosters: dict[int, dict[int, int]] = {}
        seed_ratings: dict[int, int] = {}
        for team in teams:
            team_id = int(team["id"])
            assignments = self.db.list_team_players(team_id, active_only=True)
            starters, seed_rating = _team_starter_roster(team["name"], assignments, boards_count)
            rosters[team_id] = starters
            seed_ratings[team_id] = seed_rating
        return rosters, seed_ratings

    def _swiss_team_matches(
        self,
        tournament_id: int,
        teams: list[dict[str, Any]],
        rosters: dict[int, dict[int, int]],
        seed_ratings: dict[int, int],
        boards_count: int,
        settings: dict[str, Any],
        round_number: int,
    ) -> list[dict[str, Any]]:
        standings = {int(item["team_id"]): item for item in self.team_standings(tournament_id)}
        played_pairs = self._team_played_pairs(tournament_id)
        prohibited = _prohibited_pairs_for_round(
            self.db.list_prohibited_team_pairings(tournament_id),
            round_number,
            "team_a_id",
            "team_b_id",
        )
        if prohibited:
            played_pairs = played_pairs | prohibited
        bye_team_ids = self._team_bye_ids(tournament_id)
        histories = self._team_color_histories(tournament_id)
        return _swiss_team_matches(
            teams,
            rosters,
            seed_ratings,
            boards_count,
            settings,
            standings,
            histories,
            played_pairs,
            bye_team_ids,
            max_exhaustive_pairing_teams=self.MAX_EXHAUSTIVE_PAIRING_TEAMS,
            repeat_pairing_penalty=self.REPEAT_PAIRING_PENALTY,
            score_group_float_penalty=self.SCORE_GROUP_FLOAT_PENALTY,
            score_diff_penalty=self.SCORE_DIFF_PENALTY,
        )

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
            raise AppError(_blocking_issues_message(blocking_issues))

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
                    _team_bye_summary(
                        match,
                        win_points=float(settings.get("team_match_win_points", 2.0) or 2.0),
                        boards_count=int(settings.get("team_boards_count", 4) or 4),
                        draw_points=float(settings.get("team_match_draw_points", 1.0) or 1.0),
                        loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
                    )
                )
                continue

            boards = self.db.list_team_boards(int(match["id"]))
            for board in boards:
                if not board["result"] or board["result"] not in RESULT_POINTS:
                    pending.append(board)
            if pending:
                continue

            white_team_player_ids = {
                int(player["player_id"])
                for player in self.db.list_team_players(int(match["white_team_id"]), active_only=False)
            }
            black_team_player_ids = {
                int(player["player_id"])
                for player in self.db.list_team_players(int(match["black_team_id"]), active_only=False)
            }
            summaries.append(
                _team_match_summary(
                    match,
                    boards,
                    white_team_player_ids,
                    black_team_player_ids,
                    RESULT_POINTS,
                    win_points=float(settings.get("team_match_win_points", 2.0) or 2.0),
                    loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
                    draw_points=float(settings.get("team_match_draw_points", 1.0) or 1.0),
                )
            )

        if pending:
            raise AppError("Preencha todos os resultados dos tabuleiros antes de fechar a rodada.")

        blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, round_id)
        if blocking_issues:
            raise AppError(_blocking_issues_message(blocking_issues))

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

        pairing_updates = _plan_pairing_player_swap(
            pairings,
            source_pairing,
            target_slot,
            color,
            int(source_player_id),
            int(replacement_player_id),
        )
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

        board_updates = _plan_team_board_player_swap(
            boards,
            affected_board_ids,
            int(team_board_id),
            target_slot,
            color,
            int(source_player_id),
            int(replacement_player_id),
        )
        self.db.update_team_board_players(board_updates)
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
        return _find_team_board_player_slot(boards, player_id)

    def standings(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []

        players = self.db.list_players(tournament_id, active_only=False)
        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        sequence = _parse_player_tiebreak_sequence(settings.get("tiebreak_sequence"))
        return _calculate_player_standings(tournament, players, closed_pairings, sequence=sequence)

    def crosstable(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            return self.team_crosstable(tournament_id)
        standings = self.standings(tournament_id)
        standings_by_player = {int(item["player_id"]): item for item in standings}
        rounds = sorted(
            int(round_data["number"])
            for round_data in self.db.list_rounds(tournament_id)
            if round_data.get("status") == "closed"
        )
        rows = []
        for standing in standings:
            games_by_round = {int(game["round"]): game for game in standing.get("games", [])}
            round_cells: dict[int, dict[str, Any]] = {}
            for round_number in rounds:
                game = games_by_round.get(round_number)
                if not game:
                    round_cells[round_number] = {
                        "kind": "absent",
                        "label": "-",
                        "round": round_number,
                    }
                    continue
                if game.get("color") == "bye":
                    round_cells[round_number] = {
                        **game,
                        "kind": "bye",
                        "label": f"BYE {game.get('result') or ''}".strip(),
                    }
                    continue
                opponent = standings_by_player.get(int(game.get("opponent_id") or 0), {})
                color = "B" if game.get("color") == "white" else "P"
                result = str(game.get("result") or "")
                opponent_position = int(opponent.get("position") or 0)
                round_cells[round_number] = {
                    **game,
                    "kind": "game",
                    "color_label": color,
                    "opponent_position": opponent_position,
                    "label": f"{opponent_position}{color} {result}".strip(),
                }
            rows.append(
                {
                    **standing,
                    "rounds": round_cells,
                }
            )
        return {
            "tournament_id": int(tournament_id),
            "tournament_name": tournament["name"],
            "competition_type": "individual",
            "rounds": rounds,
            "rows": rows,
        }

    def team_crosstable(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Tabela cruzada por equipes disponivel apenas para torneios por equipes.")
        standings = self.team_standings(tournament_id)
        standings_by_team = {int(item["team_id"]): item for item in standings}
        rounds = sorted(
            int(round_data["number"])
            for round_data in self.db.list_rounds(tournament_id)
            if round_data.get("status") == "closed"
        )
        matches_by_team_round: dict[tuple[int, int], dict[str, Any]] = {}
        boards_by_match_id: dict[int, list[dict[str, Any]]] = {}
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            round_number = int(match["round_number"])
            white_team_id = int(match["white_team_id"])
            matches_by_team_round[(white_team_id, round_number)] = match
            if match.get("black_team_id"):
                matches_by_team_round[(int(match["black_team_id"]), round_number)] = match
                boards_by_match_id[int(match["id"])] = self.db.list_team_boards(int(match["id"]))

        rows = []
        for standing in standings:
            team_id = int(standing["team_id"])
            round_cells: dict[int, dict[str, Any]] = {}
            for round_number in rounds:
                match = matches_by_team_round.get((team_id, round_number))
                if not match:
                    round_cells[round_number] = {
                        "kind": "absent",
                        "label": "-",
                        "round": round_number,
                        "boards": [],
                    }
                    continue
                if match.get("is_bye"):
                    round_cells[round_number] = {
                        **match,
                        "kind": "bye",
                        "label": (
                            f"BYE MP {self._compact_number(match.get('white_match_points'))} "
                            f"GP {self._compact_number(match.get('white_game_points'))}"
                        ),
                        "boards": [],
                    }
                    continue
                is_white = team_id == int(match["white_team_id"])
                opponent_id = int(match["black_team_id"] if is_white else match["white_team_id"])
                opponent = standings_by_team.get(opponent_id, {})
                match_points = match.get("white_match_points" if is_white else "black_match_points")
                game_points = match.get("white_game_points" if is_white else "black_game_points")
                result = str(match.get("result") or "")
                round_cells[round_number] = {
                    **match,
                    "kind": "match",
                    "opponent_id": opponent_id,
                    "opponent_position": int(opponent.get("position") or 0),
                    "color_label": "B" if is_white else "P",
                    "match_points": float(match_points or 0),
                    "game_points": float(game_points or 0),
                    "label": (
                        f"{int(opponent.get('position') or 0)}{'B' if is_white else 'P'} "
                        f"{self._oriented_match_result(result, is_white)} "
                        f"MP {self._compact_number(match_points)} GP {self._compact_number(game_points)}"
                    ),
                    "boards": boards_by_match_id[int(match["id"])],
                }
            rows.append({**standing, "rounds": round_cells})
        return {
            "tournament_id": int(tournament_id),
            "tournament_name": tournament["name"],
            "competition_type": "team",
            "rounds": rounds,
            "rows": rows,
        }

    @staticmethod
    def _oriented_match_result(result: str, is_white: bool) -> str:
        if is_white or "-" not in result:
            return result
        white, black = result.split("-", maxsplit=1)
        return f"{black}-{white}"

    @staticmethod
    def _compact_number(value: Any) -> str:
        numeric = float(value or 0)
        return str(int(numeric)) if numeric.is_integer() else f"{numeric:.2f}".rstrip("0").rstrip(".")

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
                components=_flatten_tiebreak_components(standings),
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
            components=_flatten_tiebreak_components(standings),
        )

    def tiebreak_narrative(
        self,
        tournament_id: int,
        player_id: int,
    ) -> dict[str, Any]:
        full = self.tiebreak_report(tournament_id)
        return _tiebreak_narrative_from_standings(full, player_id)

    def team_standings(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        teams = self.db.list_teams(tournament_id, active_only=False)
        closed_matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        sequence = _parse_team_tiebreak_sequence(settings.get("team_tiebreak_sequence"))
        return _calculate_team_standings(settings, teams, closed_matches, sequence=sequence)

    def _knockout_pairings(self, tournament_id: int, players: list[dict[str, Any]], next_number: int, settings: dict[str, Any]) -> list[dict[str, Any]]:
        previous_pairings = None
        if next_number > 1:
            prev_round = self.db.get_round_by_number(tournament_id, next_number - 1)
            if not prev_round:
                raise AppError("Rodada anterior não encontrada.")
            previous_pairings = self.db.list_pairings(prev_round["id"])
        return _knockout_pairings(players, next_number, settings, previous_pairings)

    @staticmethod
    def _find_player_slot(
        pairings: list[dict[str, Any]],
        player_id: int,
    ) -> dict[str, Any] | None:
        return _find_player_slot(pairings, player_id)

    def _swiss_pairings(
        self,
        tournament_id: int,
        players: list[dict[str, Any]],
        round_number: int,
    ) -> list[dict[str, Any]]:
        standings = {item["player_id"]: item for item in self.standings(tournament_id)}
        settings = self.db.get_tournament_settings(tournament_id) or {}
        seeding = [
            int(player["id"])
            for player in sorted(
                players,
                key=lambda p: (-int(p.get("rating") or 0), str(p.get("name", "")).casefold()),
            )
        ]
        standings = _accelerated_standings(
            standings,
            seeding,
            round_number,
            settings.get("acceleration_method", "none"),
        )
        histories = self._color_histories(tournament_id)
        float_histories = self._float_histories(tournament_id)
        played_pairs = self._played_pairs(tournament_id)
        prohibited = _prohibited_pairs_for_round(
            self.db.list_prohibited_pairings(tournament_id), round_number
        )
        if prohibited:
            played_pairs = played_pairs | prohibited
        bye_player_ids = self._bye_player_ids(tournament_id)
        return _swiss_pairings(
            players,
            standings,
            histories,
            float_histories,
            played_pairs,
            bye_player_ids,
            max_exhaustive_pairing_players=self.MAX_EXHAUSTIVE_PAIRING_PLAYERS,
            repeat_pairing_penalty=self.REPEAT_PAIRING_PENALTY,
            score_group_float_penalty=self.SCORE_GROUP_FLOAT_PENALTY,
            score_diff_penalty=self.SCORE_DIFF_PENALTY,
        )

    def _team_played_pairs(self, tournament_id: int) -> set[frozenset[int]]:
        matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        return _team_played_pairs(matches)

    def _team_bye_ids(self, tournament_id: int) -> set[int]:
        matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        return _team_bye_ids(matches)

    def _team_color_histories(self, tournament_id: int) -> dict[int, list[str]]:
        matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        return _team_color_histories(matches)

    def _played_pairs(self, tournament_id: int) -> set[frozenset[int]]:
        pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        return _played_pairs(pairings)

    def _bye_player_ids(self, tournament_id: int) -> set[int]:
        pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        return _bye_player_ids(pairings)

    def _color_histories(self, tournament_id: int) -> dict[int, list[str]]:
        pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        return _color_histories(pairings)

    def _float_histories(self, tournament_id: int) -> dict[int, list[str]]:
        tournament = self.db.get_tournament(tournament_id)
        bye_points = float(tournament["bye_points"] if tournament else 0.0)
        players = self.db.list_players(tournament_id, active_only=False)
        pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        return _float_histories(pairings, players, bye_points, RESULT_POINTS)
