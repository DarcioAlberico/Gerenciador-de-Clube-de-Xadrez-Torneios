from __future__ import annotations
import json
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable

from src.core.database import Database
from src.core.database_tournament_core import default_tiebreak_engine
from src.services.constants import (
    AppError,
    FINAL_RESULTS,
    RESULTS,
    RESULT_POINTS,
    RESULT_STATES,
    is_played_result as _is_played_result,
    pairing_player_name,
    player_full_name,
)
from src.services.pairing import (
    BAKU_NOT_IMPLEMENTED as _BAKU_NOT_IMPLEMENTED,
    DEFAULT_PLAYER_TIEBREAKS as _DEFAULT_PLAYER_TIEBREAKS,
    acceleration_spec as _acceleration_spec,
    accelerated_player_ids as _accelerated_player_ids,
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
    pairing_diagnostics as _pairing_diagnostics,
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
    rating_for_initial_order as _rating_for_initial_order,
    result_submission_issue as _result_submission_issue,
    result_states_summary as _result_states_summary,
    round_robin_team_matches as _round_robin_team_matches,
    scheme_applies_bonus as _scheme_applies_bonus,
    scheme_is_baku as _scheme_is_baku,
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
from src.services.pairing.point_adjustments import (
    aggregate_player_adjustments as _aggregate_player_adjustments,
    aggregate_team_adjustments as _aggregate_team_adjustments,
)
from src.services.pairing.gacrux_tiebreak_map import (
    sequence_signature as _sequence_signature,
)
from src.services.pairing.gacrux_trf import (
    acceleration_ignored_warning as _acceleration_ignored_warning,
    bonus_is_expressible as _bonus_is_expressible,
)
from src.services.pairing.knockout import (
    ADVANCEMENT_CRITERIA as _KNOCKOUT_CRITERIA,
    advancing_player_ids as _knockout_advancing_ids,
    bracket as _knockout_bracket,
    clean_notes as _knockout_clean_notes,
    decision_error as _knockout_decision_error,
    pending_decision_message as _knockout_pending_message,
    third_place_pairing as _knockout_third_place_pairing,
    undecided_boards as _knockout_undecided_boards,
)
from src.services.pairing.scheveningen import (
    assign_scale as _assign_scheveningen_scale,
    calendar_rounds as _scheveningen_calendar_rounds,
    late_entry_warning as _scheveningen_late_entry_warning,
    missing_from_scale as _missing_from_scale,
    rounds_mismatch_warning as _scheveningen_rounds_mismatch_warning,
    scheveningen_pairings_from_scale as _scheveningen_pairings_from_scale,
    withdrawn_on_board_warning as _scheveningen_withdrawn_warning,
)
from src.services.pairing.round_robin import (
    annulment_candidates as _annulment_candidates,
    annulment_warning as _annulment_warning,
    assign_numbers as _assign_round_robin_numbers,
    calendar_rounds as _calendar_rounds,
    late_entry_warning as _late_entry_warning,
    missing_from_calendar as _missing_from_calendar,
    round_robin_pairings_from_numbers as _round_robin_pairings_from_numbers,
    rounds_mismatch_warning as _rounds_mismatch_warning,
    withdrawn_on_board_warning as _withdrawn_on_board_warning,
)
from src.services.pairing.participation import STATUS_WITHDRAWN as _STATUS_WITHDRAWN
from src.services.pairing.incidents import (
    DECISION_NEEDS_PAIRING as _INCIDENT_DECISION_NEEDS_PAIRING,
    DECISION_NEEDS_POINTS as _INCIDENT_DECISION_NEEDS_POINTS,
    clean_notes as _incident_clean_notes,
    clock_event_needs_decision as _clock_event_needs_decision,
    decided_clock_event_ids as _decided_clock_event_ids,
    describe as _incident_describe,
    forfeit_result as _incident_forfeit_result,
    infraction_label as _incident_infraction_label,
    register_error as _incident_register_error,
    repeat_offenders as _incident_repeat_offenders,
)
from src.services.pairing.participation import (
    absence_rounds as _participation_absence_rounds,
    change_error as _participation_change_error,
    clean_reason as _participation_clean_reason,
    effective_round as _participation_effective_round,
    status_at_round as _participation_status_at,
    summarize as _participation_summarize,
)
from src.services.pairing.bye_policy import (
    ByePolicy as _ByePolicy,
    discarded_warning as _bye_discarded_warning,
    request_error as _bye_request_error,
)
from src.services.pairing.postponement import (
    blocking_message as _postponed_blocking_message,
    clean_note as _clean_postpone_note,
    issue_from_pairing as _postponed_issue,
    postpone_error as _postpone_error,
    postponed_label as _postponed_label,
    resume_error as _resume_error,
)
from src.services.pairing.corrections import (
    DEFAULT_UNLOCK_MINUTES,
    UnlockState,
    cascade_message as _cascade_message,
    cascade_rounds as _cascade_rounds,
    clean_reason as _clean_reason,
    correction_reason_error as _correction_reason_error,
    expiry_from as _expiry_from,
    reconcilable_rounds as _reconcilable_rounds,
    unlock_minutes as _unlock_minutes,
    unlock_reason_error as _unlock_reason_error,
    unlock_state as _unlock_state,
)
from src.services.pairing.tiebreak_engine import (
    ENGINE_GACRUX,
    EngineOutcome,
    EngineReport,
    engine_badge as _engine_badge,
    fallback_audit_reason as _fallback_audit_reason,
    report_engine_blocked as _report_engine_blocked,
    report_engine_fallback as _report_engine_fallback,
    report_engine_ok as _report_engine_ok,
    strict_block_message as _strict_block_message,
)

logger = logging.getLogger(__name__)

# Cache (nivel de modulo, pois PairingService e instanciado ad-hoc em varios
# servicos) dos desempates calculados pelo motor FIDE (Gacrux). standings() e
# chamado com frequencia e cada calculo dispara um subprocesso; a chave embute a
# assinatura do estado (resultados + jogadores + criterios), invalidando-se
# naturalmente quando algo muda.
_GACRUX_TIEBREAK_CACHE: "OrderedDict[tuple, EngineOutcome]" = OrderedDict()
_GACRUX_TIEBREAK_CACHE_MAX = 64
# Ultimo motor que efetivamente assinou a classificacao de cada torneio (TBK-02).
# Alimenta a faixa permanente da tela: quem pergunta nao roda o motor de novo.
_LAST_TIEBREAK_ENGINE: dict[int, EngineReport] = {}
# Guarda de reentrancia: o calculo do Gacrux exporta o TRF e o export chama
# standings() de novo. Nessa chamada aninhada usamos o motor proprio (as colunas
# de rank/pontos do TRF nao alimentam o desempate FIDE — o Gacrux recalcula a
# partir dos resultados), evitando recursao infinita.
_GACRUX_TIEBREAK_INFLIGHT: set[int] = set()


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
            # `context` carrega o adiamento (ARB-02): a coluna existia vazia no
            # individual, e e exatamente onde o arbitro precisa ler "Adiada —
            # sabado 14h" em vez de confundir a mesa com uma esquecida.
            def item_de(pairing: dict[str, Any]) -> dict[str, Any]:
                return {
                    "pairing_id": int(pairing["id"]),
                    "board": int(pairing.get("board_number") or 0),
                    "white": pairing_player_name(pairing, "white"),
                    "black": (
                        "BYE" if pairing.get("is_bye") else pairing_player_name(pairing, "black")
                    ),
                    "context": _postponed_label(pairing) if pairing.get("postponed") else "",
                    "postponed": bool(pairing.get("postponed")),
                }

            return [
                item
                for item in (
                    item_de(pairing)
                    for pairing in self.db.get_pairings_for_round(int(latest_round["id"]))
                    if not pairing.get("result") or pairing.get("result") not in FINAL_RESULTS
                )
                if matches_query(item)
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

        # Queda de seta e ausencia BLOQUEIAM ate a decisao ser registrada
        # (ARB-03): sao os dois eventos que a FIDE nao deixa passar sem o
        # arbitro decidir — quem ganha a partida? houve reclamacao? perdeu por
        # 6.7? Antes eram `attention`, e a rodada fechava com a pergunta em
        # aberto. Registrado o incidente que aponta para o evento, o alerta volta
        # a ser informativo: a decisao existe e esta na ata.
        decididos = _decided_clock_event_ids(self.db.list_incidents(tournament_id))
        for event in self.db.list_clock_events(tournament_id=tournament_id, limit=safe_limit):
            issue = _clock_event_issue(event)
            if issue is None:
                continue
            if (
                _clock_event_needs_decision(event.get("event_type"))
                and int(event.get("id") or 0) not in decididos
            ):
                issue["severity"] = "decision"
                issue["detail"] = (
                    "Registre a decisao no painel disciplinar: a rodada nao fecha "
                    "com queda de seta ou ausencia sem decisao do arbitro."
                )
            issues.append(issue)

        # Incidentes registrados viram pendencia informativa: o painel e onde o
        # arbitro reve o que decidiu, e a ata sai dali.
        for incident in self.db.list_incidents(tournament_id)[-safe_limit:]:
            issues.append(
                {
                    "issue_key": f"incident:registered:{int(incident['id'])}",
                    "severity": "attention",
                    "source": "incident",
                    "kind": str(incident.get("infraction") or ""),
                    "title": _incident_describe(incident),
                    "detail": str(incident.get("notes") or ""),
                    "round_id": None,
                    "round_number": int(incident.get("round_number") or 0),
                    "entity_id": int(incident.get("player_id") or 0),
                    "created_at": str(incident.get("created_at") or ""),
                }
            )

        # Troca de motor de desempate (TBK-02). Reusa a mesma porta dos eventos de
        # sync: o fallback ja virou evento de auditoria, e o painel so o le.
        #
        # Severidade "attention", nao "decision": decision BLOQUEIA o fechamento
        # da rodada, e um problema de relatorio nao pode parar o torneio. Quem
        # segura a publicacao e o modo estrito, dentro de standings().
        for event in self.db.list_audit_events(
            tournament_id, action="tiebreak_engine_fallback", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "tiebreak", "engine_fallback",
                    "Motor de desempate substituido", severity="attention",
                )
            )
        for event in self.db.list_audit_events(
            tournament_id, action="tiebreak_engine_blocked", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "tiebreak", "engine_blocked",
                    "Classificacao bloqueada (modo estrito)", severity="attention",
                )
            )

        # Cascata de correcao (ARB-01): corrigiu uma rodada que ja alimentou o
        # pareamento das seguintes. `attention` — quem decide se repareia e o
        # arbitro, e travar o fechamento nao ajudaria em nada.
        for event in self.db.list_audit_events(
            tournament_id, action="result_correction_cascade", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "correction", "cascade",
                    "Correcao afeta rodada ja pareada", severity="attention",
                )
            )

        # Bye solicitado descartado por jogador inativo (ARB-04). `attention`: o
        # pedido ja ficou para tras, e travar o fechamento nao o traria de volta
        # — o que faltava era o arbitro FICAR SABENDO.
        for event in self.db.list_audit_events(
            tournament_id, action="requested_bye_discarded", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "bye", "discarded",
                    "Bye solicitado descartado (jogador inativo)", severity="attention",
                )
            )

        issues.extend(self._pairing_arbitration_issues(tournament_id, tournament))
        issues.extend(self._postponed_arbitration_issues(tournament_id))

        issues = _finalize_issues(issues, acknowledged_keys, safe_limit)
        metrics = _issue_metrics(issues)
        return {"metrics": metrics, "issues": issues}

    def _postponed_arbitration_issues(self, tournament_id: int) -> list[dict[str, Any]]:
        """Uma pendencia por mesa adiada da rodada em andamento (ARB-02).

        So a rodada corrente: mesa adiada de rodada fechada nao existe — lancar
        o resultado desfaz o adiamento, e fechar a rodada exige o resultado.
        """
        latest_round = self.db.get_latest_round(tournament_id)
        if not latest_round or latest_round.get("status") != "generated":
            return []
        round_id = int(latest_round["id"])
        return [
            _postponed_issue(pairing, round_id, int(latest_round.get("number") or 0))
            for pairing in self.db.list_postponed_pairings(round_id)
        ]

    # ------------------------------------------------------------------ #
    # Registro disciplinar (ARB-03)
    # ------------------------------------------------------------------ #

    def register_incident(
        self,
        tournament_id: int,
        *,
        player_id: int,
        infraction: str,
        decision: str,
        round_number: int = 0,
        pairing_id: int | None = None,
        notes: str = "",
        deduction_points: float = 0.0,
        clock_event_id: int | None = None,
        actor: str = "",
    ) -> dict[str, Any]:
        """Registra o incidente E aplica a decisao (ARB-03).

        Uma decisao disciplinar que nao chega na classificacao e um bilhete: o
        `point_adjustments` ja existia (TBK-01 o faz mover a ordem), mas sem
        catalogo de infracoes e sem vinculo — a deducao era um numero com texto
        livre ao lado. Aqui os dois viram um registro so.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        player = self.db.get_player(int(player_id)) if player_id else None
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador nao encontrado para o torneio selecionado.")

        pairing = self.db.get_pairing(int(pairing_id)) if pairing_id else None
        if pairing_id and (
            not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id)
        ):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")

        erro = _incident_register_error(
            infraction=infraction,
            decision=decision,
            player_id=int(player_id),
            pairing_id=int(pairing_id) if pairing_id else None,
            deduction_points=float(deduction_points or 0.0),
            notes=notes,
        )
        if erro:
            raise AppError(erro)

        rodada = int(round_number or (pairing or {}).get("round_number") or 0)
        mesa = int((pairing or {}).get("board_number") or 0)
        limpo = _incident_clean_notes(notes)

        adjustment_id: int | None = None
        if str(decision).strip() in _INCIDENT_DECISION_NEEDS_POINTS:
            adjustment_id = self.db.add_point_adjustment(
                int(tournament_id),
                round_number=rodada,
                player_id=int(player_id),
                game_points=-abs(float(deduction_points)),
                reason=f"{_incident_infraction_label(infraction)}: {limpo}".strip(": "),
            )

        incident_id = self.db.add_incident(
            int(tournament_id),
            player_id=int(player_id),
            infraction=str(infraction).strip(),
            decision=str(decision).strip(),
            round_number=rodada,
            board_number=mesa,
            pairing_id=int(pairing_id) if pairing_id else None,
            notes=limpo,
            adjustment_id=adjustment_id,
            clock_event_id=int(clock_event_id) if clock_event_id else None,
            actor=actor,
        )

        if str(decision).strip() in _INCIDENT_DECISION_NEEDS_PAIRING and pairing:
            # W.O., e nao o resultado por decisao do arbitro (`1U-0U`, ARB-02):
            # quem perde por regulamento NAO JOGOU a partida aos olhos da FIDE.
            resultado = _incident_forfeit_result(
                int(pairing["white_player_id"]) == int(player_id)
            )
            self.update_result(int(tournament_id), int(pairing_id or 0), resultado)

        self.db.create_audit_event(
            action="incident_registered",
            tournament_id=int(tournament_id),
            entity_type="player",
            entity_id=int(player_id),
            after={
                "incident_id": incident_id,
                "infraction": str(infraction).strip(),
                "decision": str(decision).strip(),
                "round_number": rodada,
                "board_number": mesa,
                "notes": limpo,
                "adjustment_id": adjustment_id,
            },
        )
        return {
            "incident_id": incident_id,
            "adjustment_id": adjustment_id,
            "round_number": rodada,
        }

    def incidents(self, tournament_id: int, player_id: int | None = None) -> list[dict[str, Any]]:
        return list(self.db.list_incidents(int(tournament_id), player_id))

    def incident_repeat_offenders(self, tournament_id: int) -> dict[int, int]:
        """``{player_id: total}`` de quem tem mais de um incidente (ARB-03)."""
        return _incident_repeat_offenders(self.db.list_incidents(int(tournament_id)))

    # ------------------------------------------------------------------ #
    # Participacao: retirada e reentrada (ARB-05)
    # ------------------------------------------------------------------ #

    def set_player_participation(
        self,
        tournament_id: int,
        player_id: int,
        status: str,
        reason: str = "",
        actor: str = "",
    ) -> int:
        """Muda o estado de participacao E registra no historico (ARB-05).

        `players.player_status` guarda so o estado de agora; sem o evento nao
        sobra rastro de "saiu na rodada 3, voltou na 5" — nem para a ata, nem
        para explicar por que um jogador some do pareamento.

        Devolve a rodada A PARTIR da qual a mudanca vale.
        """
        player = self.db.get_player(int(player_id))
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador nao encontrado para o torneio selecionado.")
        erro = _participation_change_error(
            new_status=str(status or "").strip(),
            current_status=str(player.get("player_status") or "active"),
            reason=reason,
        )
        if erro:
            raise AppError(erro)

        rodada = _participation_effective_round(self.db.get_latest_round(tournament_id))
        limpo = _participation_clean_reason(reason)
        self.db.set_player_status(int(player_id), str(status).strip())
        self.db.add_player_status_event(
            int(tournament_id),
            int(player_id),
            rodada,
            str(status).strip(),
            reason=limpo,
            actor=actor,
        )
        self.db.create_audit_event(
            action="player_participation_changed",
            tournament_id=int(tournament_id),
            entity_type="player",
            entity_id=int(player_id),
            before={"player_status": str(player.get("player_status") or "active")},
            after={
                "player_status": str(status).strip(),
                "round_number": rodada,
                "reason": limpo,
            },
        )
        return rodada

    def participation_history(
        self,
        tournament_id: int,
        player_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return list(self.db.list_player_status_events(int(tournament_id), player_id))

    def participation_summary(self, tournament_id: int) -> list[dict[str, Any]]:
        """Um resumo por jogador que teve mudanca — a secao da ata (ARB-05)."""
        tournament = self.db.get_tournament(tournament_id) or {}
        rodadas = int(tournament.get("rounds_count") or 0)
        eventos = self.db.list_player_status_events(int(tournament_id))
        por_jogador: dict[int, list[dict[str, Any]]] = {}
        for evento in eventos:
            por_jogador.setdefault(int(evento["player_id"]), []).append(evento)
        resumo = []
        for player_id, historico in por_jogador.items():
            resumo.append(
                {
                    "player_id": player_id,
                    "player_name": player_full_name(
                        {
                            "name": historico[0].get("player_name"),
                            "surname": historico[0].get("player_surname"),
                            "given_name": historico[0].get("player_given_name"),
                        }
                    ),
                    "summary": _participation_summarize(historico, rodadas),
                    "absence_rounds": _participation_absence_rounds(historico, rodadas),
                    "final_status": _participation_status_at(historico, rodadas or 10**6),
                }
            )
        return sorted(resumo, key=lambda item: str(item["player_name"]).casefold())

    # ------------------------------------------------------------------ #
    # Byes solicitados (ARB-04)
    # ------------------------------------------------------------------ #

    def request_bye(
        self,
        tournament_id: int,
        player_id: int,
        round_number: int,
        bye_type: str = "H",
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado, aplicando a politica do torneio (ARB-04).

        Era gravado direto da tela no banco, sem servico nenhum — e por isso um
        pedido para rodada ja gerada era aceito e nunca aplicado, um pedido de
        jogador inativo sumia na hora de parear, e nao havia limite nenhum.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        player = self.db.get_player(int(player_id))
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador nao encontrado para o torneio selecionado.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        existing = self.db.get_round_by_number(tournament_id, int(round_number))
        ja_pedidos = [
            item
            for item in self.db.list_requested_byes(tournament_id)
            if int(item.get("player_id") or 0) == int(player_id)
        ]
        erro = _bye_request_error(
            _ByePolicy.from_settings(settings),
            bye_type=bye_type,
            round_number=int(round_number),
            rounds_count=int(tournament.get("rounds_count") or 0),
            round_status=str(existing["status"]) if existing else None,
            player_active=bool(int(player.get("active") or 0)),
            existing_byes=ja_pedidos,
            editing_existing=any(
                int(item.get("round_number") or 0) == int(round_number) for item in ja_pedidos
            ),
        )
        if erro:
            raise AppError(erro)

        bye_id = self.db.add_requested_bye(
            tournament_id, int(player_id), int(round_number), bye_type, reason=reason
        )
        self.db.create_audit_event(
            action="requested_bye_registered",
            tournament_id=int(tournament_id),
            entity_type="player",
            entity_id=int(player_id),
            after={
                "round_number": int(round_number),
                "bye_type": str(bye_type or "H").strip().upper(),
                "reason": str(reason or "").strip(),
            },
        )
        return bye_id

    def _warn_discarded_byes(
        self,
        tournament_id: int,
        round_number: int,
        discarded: list[dict[str, Any]],
    ) -> None:
        """Registra os byes que a geracao teve de descartar (ARB-04)."""
        if not discarded:
            return
        aviso = _bye_discarded_warning(discarded)
        logger.warning("Rodada %s do torneio %s: %s", round_number, tournament_id, aviso)
        self.db.create_audit_event(
            action="requested_bye_discarded",
            tournament_id=int(tournament_id),
            entity_type="round",
            entity_id=int(round_number),
            after={
                "round_number": int(round_number),
                "message": aviso,
                "player_ids": [int(item.get("player_id") or 0) for item in discarded],
            },
        )

    def _warn_pairing_notes(
        self,
        tournament_id: int,
        round_number: int,
        avisos: list[str],
    ) -> None:
        """Deixa na trilha o que o pareamento avisou ao arbitro (PAR-02).

        A previa mostra os mesmos avisos ANTES de gerar; este registro e para
        depois: quem conferir a rodada no futuro precisa achar por que ela foi
        pareada assim (aceleracao que trocou de motor, pontuacao que o motor FIDE
        nao recebeu) sem depender de quem estava na sala.
        """
        if not avisos:
            return
        for aviso in avisos:
            logger.warning("Rodada %s do torneio %s: %s", round_number, tournament_id, aviso)
        self.db.create_audit_event(
            action="pairing_warning",
            tournament_id=int(tournament_id),
            entity_type="round",
            entity_id=int(round_number),
            after={"round_number": int(round_number), "messages": list(avisos)},
        )

    def bye_policy_summary(self, tournament_id: int) -> str:
        """Uma linha com os limites configurados. ``""`` quando nao ha."""
        settings = self.db.get_tournament_settings(tournament_id) or {}
        return _ByePolicy.from_settings(settings).describe()

    def postpone_pairing(self, tournament_id: int, pairing_id: int, note: str = "") -> None:
        """Marca a mesa como adiada, com o combinado como nota (ARB-02)."""
        pairing = self.db.get_pairing(int(pairing_id))
        if not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")
        erro = _postpone_error(pairing)
        if erro:
            raise AppError(erro)
        limpa = _clean_postpone_note(note)
        self.db.set_pairing_postponed(int(pairing_id), True, limpa)
        self.db.create_audit_event(
            action="pairing_postponed",
            tournament_id=int(tournament_id),
            round_id=int(pairing["round_id"]),
            entity_type="pairing",
            entity_id=int(pairing_id),
            before={"postponed": 0},
            after={"postponed": 1, "postponed_note": limpa},
        )

    def resume_pairing(self, tournament_id: int, pairing_id: int) -> None:
        """Desfaz o adiamento da mesa (ARB-02)."""
        pairing = self.db.get_pairing(int(pairing_id))
        if not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")
        erro = _resume_error(pairing)
        if erro:
            raise AppError(erro)
        self.db.set_pairing_postponed(int(pairing_id), False)
        self.db.create_audit_event(
            action="pairing_resumed",
            tournament_id=int(tournament_id),
            round_id=int(pairing["round_id"]),
            entity_type="pairing",
            entity_id=int(pairing_id),
            before={"postponed": 1, "postponed_note": str(pairing.get("postponed_note") or "")},
            after={"postponed": 0},
        )

    def _pairing_arbitration_issues(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if tournament.get("competition_type") == "team":
            return []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        if str(settings.get("pairing_method") or "swiss") != "swiss":
            return []
        latest_round = self.db.get_latest_round(tournament_id)
        if not latest_round or latest_round.get("status") != "generated":
            return []

        round_id = int(latest_round["id"])
        current_pairings = self.db.get_pairings_for_round(round_id)
        if not current_pairings:
            return []

        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        diagnostics = _pairing_diagnostics(
            current_pairings,
            _color_histories(closed_pairings),
            _played_pairs(closed_pairings),
            _bye_player_ids(closed_pairings),
            players=self.db.list_players(tournament_id, active_only=True),
            standings={int(item["player_id"]): item for item in self._standings(tournament_id)},
            float_histories=self._float_histories(tournament_id),
        )

        issues = []
        for diagnostic in diagnostics:
            player_suffix = "-".join(str(player_id) for player_id in diagnostic.get("player_ids") or [])
            board_number = int(diagnostic.get("board_number") or 0)
            kind = str(diagnostic.get("kind") or "diagnostic")
            issues.append(
                {
                    "issue_key": f"pairing:{kind}:{round_id}:{board_number}:{player_suffix}",
                    "severity": diagnostic.get("severity") or "attention",
                    "source": "pairing",
                    "kind": kind,
                    "title": diagnostic.get("title") or "Alerta de pareamento",
                    "detail": diagnostic.get("detail") or "",
                    "round_id": round_id,
                    "entity_id": diagnostic.get("pairing_id"),
                    "created_at": latest_round.get("created_at") or "",
                    "payload": {
                        **diagnostic,
                        "round_number": latest_round.get("number"),
                    },
                }
            )
        return issues

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

        plan = self._individual_next_round_plan(tournament_id, tournament, persist=True)
        players = plan["players"]
        settings = plan["settings"]
        next_number = int(plan["round_number"])
        pairings = plan["pairings"]
        self._warn_pairing_notes(tournament_id, next_number, plan.get("warnings") or [])

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

    def _individual_next_round_plan(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        *,
        persist: bool = False,
    ) -> dict[str, Any]:
        """Plano da proxima rodada. `persist` autoriza gravar o que o plano decide.

        A previa chama com `persist=False` e a geracao com `True`: o unico plano
        que decide algo PERSISTENTE e o do rodizio, que sorteia os numeros de
        Berger na primeira rodada (PAR-01) — e uma previa que grava o sorteio
        seria uma previa que muda o torneio.
        """
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

        # Avisos do que o pareamento decidiu e o arbitro precisa saber — o que
        # nao coube no arquivo do motor FIDE, a aceleracao que trocou de motor
        # (PAR-02). Vao para a previa, para o log e para a auditoria.
        avisos: list[str] = []
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
            # todos os jogadores ativos (comportamento historico). No rodizio a
            # paridade e a do CALENDARIO, nao a da chamada de hoje: quem desistiu
            # continua tendo mesa (ver _round_robin_round).
            if (
                settings.get("disable_bye")
                and pairing_method != "round_robin"
                and len(players) % 2 == 1
            ):
                raise AppError("O bye esta desativado. Use numero par de jogadores ativos.")
            if pairing_method == "round_robin":
                pairings = self._round_robin_round(
                    tournament_id, tournament, settings, next_number, avisos, persist=persist
                )
            elif pairing_method == "scheveningen":
                pairings = self._scheveningen_round(
                    tournament_id, tournament, settings, next_number, avisos, persist=persist
                )
            else:
                pairings = self._knockout_pairings(tournament_id, players, next_number, settings)
        else:
            active_ids = {int(player["id"]) for player in players}
            pedidos = self.db.list_requested_byes_for_round(tournament_id, next_number)
            bye_by_player = {
                int(item["player_id"]): str(item["bye_type"])
                for item in pedidos
                if int(item["player_id"]) in active_ids
            }
            # Bye de jogador inativo era descartado EM SILENCIO (ARB-04): o
            # jogador avisou que faltaria, o arbitro registrou, e na hora de
            # parear o pedido sumia. Agora sai aviso e fica na auditoria — quem
            # le decide se reativa o jogador ou aceita a ausencia. A geracao
            # segue: barrar a rodada por um pedido que ficou para tras seria
            # trocar um silencio ruim por uma parada pior.
            self._warn_discarded_byes(
                tournament_id,
                next_number,
                [item for item in pedidos if int(item["player_id"]) not in active_ids],
            )
            to_pair = [
                player for player in players if int(player["id"]) not in bye_by_player
            ]
            if bye_by_player and len(to_pair) < 2:
                raise AppError(
                    "Byes solicitados deixariam menos de 2 jogadores para parear."
                )
            if settings.get("disable_bye") and len(to_pair) % 2 == 1:
                raise AppError("O bye esta desativado. Use numero par de jogadores ativos.")
            use_gacrux = settings.get("pairing_system") == "gacrux_swiss"
            if use_gacrux and _prohibited_pairs_for_round(
                self.db.list_prohibited_pairings(tournament_id), next_number
            ):
                # O Gacrux (via TRF-16) nao recebe as proibicoes desta integracao;
                # nas rodadas com proibicao ativa caimos no motor proprio, que as respeita.
                logger.info(
                    "Rodada %s tem proibicao ativa; usando o motor proprio em vez do Gacrux.",
                    next_number,
                )
                use_gacrux = False
            acelerados, bonus, use_gacrux = self._acceleration_plan(
                to_pair, settings, next_number, use_gacrux, avisos
            )
            if use_gacrux:
                from src.services.pairing.gacrux_engine import GacruxEngine
                engine = GacruxEngine(self.db)
                pairings = engine.pair_round(
                    tournament_id,
                    to_pair,
                    next_number,
                    accelerated_player_ids=acelerados,
                    acceleration_bonus=bonus,
                )
                avisos.extend(engine.warnings)
            elif next_number == 1:
                pairings = _first_round_pairings(to_pair, settings)
            else:
                pairings = self._swiss_pairings(tournament_id, to_pair, next_number)
            pairings = _append_requested_bye_pairings(pairings, bye_by_player)
        return {
            "players": players,
            "settings": settings,
            "round_number": next_number,
            "pairings": pairings,
            "warnings": avisos,
        }

    def round_robin_numbers(self, tournament_id: int) -> dict[int, int]:
        """Numeros de rodizio do torneio: `{player_id: numero}` (PAR-01).

        Vazio enquanto o calendario nao foi sorteado — o que acontece na geracao
        da primeira rodada.
        """
        return self.db.list_round_robin_numbers(int(tournament_id))

    def _round_robin_round(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        round_number: int,
        avisos: list[str],
        *,
        persist: bool,
    ) -> list[dict[str, Any]]:
        """Mesas da rodada lidas do CALENDARIO do rodizio (PAR-01).

        O calendario e sorteado uma vez e guardado; daqui para a frente a rodada
        so e lida da tabela de Berger. Por isso desativar um jogador nao mexe nos
        confrontos futuros dos outros: a mesa dele continua existindo e sai por
        W.O. — que e o que a FIDE manda no rodizio, onde nao existe "tirar alguem
        da rotacao" sem desmanchar o torneio inteiro.
        """
        numeros = self._round_robin_calendar(tournament_id, settings, persist=persist)
        jogadores = {
            int(player["id"]): player
            for player in self.db.list_players(tournament_id, active_only=False)
        }
        double = bool(settings.get("round_robin_double"))

        configuradas = int(tournament.get("rounds_count") or 0)
        do_calendario = _calendar_rounds(len(numeros), double=double)
        if configuradas != do_calendario:
            avisos.append(_rounds_mismatch_warning(configuradas, do_calendario, double=double))

        ativos = [
            int(player_id)
            for player_id, player in jogadores.items()
            if int(player.get("active") or 0)
        ]
        fora = _missing_from_calendar(numeros, ativos)
        if fora:
            avisos.append(_late_entry_warning(self._player_names(jogadores, fora)))

        pairings = _round_robin_pairings_from_numbers(numeros, round_number, double=double)
        ausentes = self._inactive_on_boards(pairings, jogadores)
        if ausentes:
            avisos.append(_withdrawn_on_board_warning(self._player_names(jogadores, ausentes)))
            avisos.extend(self._round_robin_annulment_warnings(tournament_id, do_calendario, ausentes, jogadores))
        return pairings

    def _scheveningen_round(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        round_number: int,
        avisos: list[str],
        *,
        persist: bool,
    ) -> list[dict[str, Any]]:
        """Mesas da rodada a partir da ESCALA guardada (PAR-03).

        A escala era refeita a cada rodada com a lista de ativos: uma desistencia
        deslocava todos os indices seguintes — os confrontos que faltavam viravam
        outros — e ainda desigualava os grupos, o que fazia a geracao ser
        RECUSADA. Agora o grupo e o numero moram no jogador, e quem sai mantem a
        cadeira: a mesa sai por W.O.
        """
        escala = self._scheveningen_scale(tournament_id, settings, persist=persist)
        jogadores = {
            int(player["id"]): player
            for player in self.db.list_players(tournament_id, active_only=False)
        }

        configuradas = int(tournament.get("rounds_count") or 0)
        do_calendario = _scheveningen_calendar_rounds(escala)
        if configuradas != do_calendario:
            avisos.append(_scheveningen_rounds_mismatch_warning(configuradas, do_calendario))

        ativos = [
            int(player_id)
            for player_id, player in jogadores.items()
            if int(player.get("active") or 0)
        ]
        fora = _missing_from_scale(escala, ativos)
        if fora:
            avisos.append(_scheveningen_late_entry_warning(self._player_names(jogadores, fora)))

        pairings = _scheveningen_pairings_from_scale(escala, round_number)
        ausentes = self._inactive_on_boards(pairings, jogadores)
        if ausentes:
            avisos.append(_scheveningen_withdrawn_warning(self._player_names(jogadores, ausentes)))
        return pairings

    def _scheveningen_scale(
        self,
        tournament_id: int,
        settings: dict[str, Any],
        *,
        persist: bool,
    ) -> dict[int, tuple[str, int]]:
        """Escala do Scheveningen, montando-a na primeira vez.

        Respeita o grupo que o arbitro tiver atribuido a mao; sem isso, parte o
        campo pela ordem inicial. O numero dentro do grupo e o que faltava para a
        escala parar de andar quando alguem sai.
        """
        jogadores = self.db.list_players(tournament_id, active_only=False)
        guardada = {
            int(player["id"]): (
                str(player.get("scheveningen_group") or "").strip().upper(),
                int(player.get("scheveningen_number") or 0),
            )
            for player in jogadores
            if int(player.get("scheveningen_number") or 0) > 0
        }
        if guardada:
            return guardada

        ativos = [player for player in jogadores if int(player.get("active") or 0)]
        escala = _assign_scheveningen_scale(
            self._seeding(ativos, settings),
            {int(player["id"]): player.get("scheveningen_group") for player in ativos},
        )
        if persist:
            self.db.save_scheveningen_scale(tournament_id, escala)
            self.db.create_audit_event(
                action="scheveningen_scale_assigned",
                tournament_id=int(tournament_id),
                entity_type="tournament",
                entity_id=int(tournament_id),
                after={
                    "scale": {
                        str(player_id): f"{grupo}{numero}"
                        for player_id, (grupo, numero) in escala.items()
                    }
                },
            )
        return escala

    @staticmethod
    def _inactive_on_boards(
        pairings: list[dict[str, Any]],
        players_by_id: dict[int, dict[str, Any]],
    ) -> list[int]:
        """Quem esta fora do torneio e mesmo assim tem mesa no calendario fixo."""
        return sorted(
            {
                int(player_id)
                for pairing in pairings
                for player_id in (pairing["white_player_id"], pairing["black_player_id"])
                if player_id and not int(players_by_id.get(int(player_id), {}).get("active") or 0)
            }
        )

    def _round_robin_calendar(
        self,
        tournament_id: int,
        settings: dict[str, Any],
        *,
        persist: bool,
    ) -> dict[int, int]:
        """Numeros de rodizio, sorteando-os na primeira vez.

        A ordem do sorteio e a ORDEM INICIAL do torneio — a mesma que o arbitro ja
        configurou e ve na lista. Um sorteio aleatorio de verdade (a alternativa
        do regulamento) precisaria de uma tela para o arbitro conduzi-lo em
        publico; enquanto ela nao existe, um numero previsivel e conferivel e
        melhor do que um numero que ninguem viu sair.
        """
        numeros = self.db.list_round_robin_numbers(tournament_id)
        if numeros:
            return numeros
        jogadores = self.db.list_players(tournament_id, active_only=True)
        numeros = _assign_round_robin_numbers(self._seeding(jogadores, settings))
        if persist:
            self.db.save_round_robin_numbers(tournament_id, numeros)
            self.db.create_audit_event(
                action="round_robin_table_assigned",
                tournament_id=int(tournament_id),
                entity_type="tournament",
                entity_id=int(tournament_id),
                after={
                    "numbers": {str(player_id): int(numero) for player_id, numero in numeros.items()},
                    "initial_order": str(settings.get("initial_order") or "rating"),
                },
            )
        return numeros

    def _round_robin_annulment_warnings(
        self,
        tournament_id: int,
        calendar_rounds: int,
        candidate_ids: list[int],
        players_by_id: dict[int, dict[str, Any]],
    ) -> list[str]:
        """Aviso da regra dos 50% (FIDE C.05) para quem desistiu cedo."""
        desistentes = [
            player_id
            for player_id in candidate_ids
            if str(players_by_id.get(player_id, {}).get("player_status") or "") == _STATUS_WITHDRAWN
        ]
        if not desistentes:
            return []
        jogadas: dict[int, int] = {}
        for pairing in self.db.get_pairings_for_tournament(tournament_id, closed_only=True):
            if pairing.get("is_bye") or not _is_played_result(str(pairing.get("result") or "")):
                continue
            for player_id in (pairing.get("white_player_id"), pairing.get("black_player_id")):
                if player_id:
                    jogadas[int(player_id)] = jogadas.get(int(player_id), 0) + 1
        anular = _annulment_candidates(jogadas, calendar_rounds, desistentes)
        if not anular:
            return []
        return [_annulment_warning(self._player_names(players_by_id, anular), calendar_rounds)]

    @staticmethod
    def _player_names(
        players_by_id: dict[int, dict[str, Any]],
        player_ids: list[int],
    ) -> list[str]:
        return [
            player_full_name(players_by_id.get(int(player_id), {})) or f"#{player_id}"
            for player_id in player_ids
        ]

    def _acceleration_plan(
        self,
        to_pair: list[dict[str, Any]],
        settings: dict[str, Any],
        round_number: int,
        use_gacrux: bool,
        avisos: list[str],
    ) -> tuple[list[int], float, bool]:
        """Quem acelera nesta rodada, com quanto, e por qual motor (PAR-02).

        A aceleracao so existia no motor proprio: com o Gacrux — que e o padrao —
        ela era ignorada em silencio. Agora ela viaja no TRF (registro 250) e,
        quando o bonus configurado nao cabe nesse registro, a rodada cai no motor
        proprio COM AVISO. O que nao pode e o arbitro configurar aceleracao e nao
        receber nem o efeito nem a noticia de que ele nao veio.
        """
        method = str(settings.get("acceleration_method") or "none")
        if _scheme_is_baku(method):
            avisos.append(_BAKU_NOT_IMPLEMENTED)
            return [], 0.0, use_gacrux
        if not _scheme_applies_bonus(method):
            return [], 0.0, use_gacrux

        acelerados = _accelerated_player_ids(
            self._seeding(to_pair, settings), round_number, method
        )
        bonus = float(_acceleration_spec(method).get("bonus", 0.0) or 0.0)
        if not acelerados:
            # Fora das rodadas aceleradas: nada a fazer em nenhum dos motores.
            return [], 0.0, use_gacrux
        if use_gacrux and not _bonus_is_expressible(bonus):
            avisos.append(_acceleration_ignored_warning(bonus))
            return acelerados, bonus, False
        if not use_gacrux and round_number == 1:
            # `first_round_pairings` divide o campo pela ordem inicial e nao olha
            # pontuacao — fictícia inclusive. Quem quer a rodada 1 acelerada de
            # fato usa o motor FIDE; aqui o arbitro ao menos sabe.
            avisos.append(
                "Aceleracao configurada, mas o motor proprio pareia a rodada 1 pela "
                "ordem inicial, sem os pontos ficticios. Use o motor Suico (Gacrux) "
                "para acelerar a primeira rodada."
            )
        return acelerados, bonus, use_gacrux

    def _seeding(
        self,
        players: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> list[int]:
        """IDs na ordem de ranking inicial do torneio (1 = cabeca de chave)."""
        initial_order = str(settings.get("initial_order") or "rating")
        return [
            int(player["id"])
            for player in sorted(
                players,
                key=lambda p: (
                    -_rating_for_initial_order(p, initial_order),
                    str(p.get("name") or "").casefold(),
                ),
            )
        ]

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
        float_histories = self._float_histories(tournament_id)
        played_pairs = self._played_pairs(tournament_id)
        bye_player_ids = self._bye_player_ids(tournament_id)
        standings = {int(item["player_id"]): item for item in self._standings(tournament_id)}
        return _individual_preview_payload(
            tournament_id=tournament_id,
            tournament=tournament,
            plan=plan,
            histories=histories,
            played_pairs=played_pairs,
            bye_player_ids=bye_player_ids,
            standings=standings,
            float_histories=float_histories,
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

        # O metodo de pareamento por equipes era lido pela exportacao e pelo
        # motor de desempate, mas NAO pela geracao de rodada — que era sempre
        # Suico (PAR-04). Com a constante duplicada consertada, `round_robin`
        # voltou a ser selecionavel, e agora ele de fato pareia.
        team_method = str(settings.get("team_pairing_method") or "swiss")
        if team_method == "round_robin":
            if bye_by_team:
                # O calendario do todos-contra-todos e fixo: tirar uma equipe da
                # rotacao desloca todo mundo e faz pares se repetirem. Num
                # torneio assim, quem nao comparece perde por W.O. — nao "folga".
                raise AppError(
                    "Bye solicitado nao se aplica a todos contra todos por equipes: "
                    "o calendario e fixo. Registre W.O. no confronto da rodada."
                )
            matches = _round_robin_team_matches(
                to_pair, rosters, seed_ratings, boards_count, settings, next_number
            )
        elif next_number == 1:
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
        standings = {int(item["team_id"]): item for item in self._team_standings(tournament_id)}
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
        reason: str = "",
    ) -> None:
        """Lanca ou corrige o resultado de uma mesa.

        `reason` e OBRIGATORIO quando a rodada esta fechada (ARB-01): antes o
        motivo era uma constante no codigo, e a trilha registrava que houve
        correcao sem nunca dizer por que — inutil na hora de sustentar a decisao
        numa apelacao.
        """
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            self._update_team_board_result(tournament_id, pairing_id, result, reason)
            return

        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")
        allowed = set(RESULTS)
        if pairing.get("is_bye"):
            allowed.update({"BYE", "F", "H", "Z"})
        if result not in allowed:
            raise AppError("Resultado invalido.")
        before = {
            "pairing_id": int(pairing_id),
            "result": pairing.get("result", ""),
            "round_status": pairing.get("round_status", ""),
        }
        is_correction = pairing["round_status"] == "closed"
        round_id = int(pairing["round_id"])
        if is_correction:
            reason = self._authorize_correction(tournament_id, round_id, reason)
        self.db.update_pairing_result(pairing_id, result)
        action = "result_corrected" if is_correction else "result_updated"
        self.db.create_audit_event(
            action=action,
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="pairing",
            entity_id=int(pairing_id),
            reason=reason if is_correction else "",
            before=before,
            after={"pairing_id": int(pairing_id), "result": result, "round_status": pairing.get("round_status", "")},
        )
        logger.info("Resultado da mesa %s atualizado para %s", pairing_id, result or "pendente")
        if is_correction:
            self._after_correction(tournament_id, round_id, reason)

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
            # Mesa adiada primeiro, com recado proprio (ARB-02): mandar o arbitro
            # "preencher todos os resultados" quando ele SABE que aquela mesa esta
            # em aberto e o manda procurar o que ele mesmo combinou.
            adiadas = self.db.list_postponed_pairings(round_id)
            if adiadas:
                raise AppError(_postponed_blocking_message(adiadas))
            raise AppError("Preencha todos os resultados antes de fechar a rodada.")

        blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, round_id)
        if blocking_issues:
            raise AppError(_blocking_issues_message(blocking_issues))

        backup_path = self.db.backup_before("close_round", tournament_id=tournament_id, round_id=round_id)
        logger.info("Backup criado antes de fechar rodada %s: %s", round_id, backup_path)

        self.db.close_round(round_id)
        standings = self._standings(tournament_id)
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

    def _update_team_board_result(
        self,
        tournament_id: int,
        team_board_id: int,
        result: str,
        reason: str = "",
    ) -> None:
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
        is_correction = board["round_status"] == "closed"
        round_id = int(board["round_id"])
        if is_correction:
            reason = self._authorize_correction(tournament_id, round_id, reason)
        self.db.update_team_board_result(team_board_id, result)
        action = "team_result_corrected" if is_correction else "team_result_updated"
        self.db.create_audit_event(
            action=action,
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="team_board",
            entity_id=int(team_board_id),
            reason=reason if is_correction else "",
            before=before,
            after={"team_board_id": int(team_board_id), "result": result, "round_status": board.get("round_status", "")},
        )
        logger.info("Resultado do tabuleiro de equipe %s atualizado para %s", team_board_id, result or "pendente")
        if is_correction:
            self._after_correction(tournament_id, round_id, reason, is_team=True)

    # ------------------------------------------------------------------ #
    # Correcao em rodada fechada: motivo, desbloqueio, cascata, retratos
    # (ARB-01)
    # ------------------------------------------------------------------ #

    def correction_unlock_state(self, tournament_id: int, round_id: int) -> UnlockState:
        """Pode corrigir esta rodada agora? De onde vem a permissao?"""
        settings = self.db.get_tournament_settings(tournament_id) or {}
        return _unlock_state(
            self.db.list_correction_unlocks(tournament_id, round_id),
            self.db.now(),
            dangerous_changes=bool(settings.get("allow_dangerous_changes")),
        )

    def unlock_round_for_correction(
        self,
        tournament_id: int,
        round_id: int,
        reason: str,
        minutes: int = DEFAULT_UNLOCK_MINUTES,
    ) -> dict[str, Any]:
        """Abre a rodada fechada para correcao, com justificativa e prazo.

        Substitui o habito de ligar `allow_dangerous_changes` e esquecer: aqui a
        permissao e de UMA rodada e morre sozinha. Devolve o retrato para a tela.
        """
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")
        erro = _unlock_reason_error(reason)
        if erro:
            raise AppError(erro)
        cleaned = _clean_reason(reason)
        janela = _unlock_minutes(minutes)
        expires_at = _expiry_from(self.db.now(), janela)
        unlock_id = self.db.create_correction_unlock(
            tournament_id,
            round_id,
            reason=cleaned,
            expires_at=expires_at,
        )
        self.db.create_audit_event(
            action="round_correction_unlocked",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            reason=cleaned,
            after={"unlock_id": unlock_id, "expires_at": expires_at, "minutes": janela},
        )
        logger.info(
            "Rodada %s desbloqueada para correcao por %s min (torneio %s)",
            round_id,
            janela,
            tournament_id,
        )
        return {
            "unlock_id": unlock_id,
            "expires_at": expires_at,
            "minutes": janela,
            "reason": cleaned,
        }

    def revoke_round_correction_unlock(self, tournament_id: int, round_id: int) -> int:
        """Fecha a rodada de novo antes do prazo. Devolve quantos desbloqueios caíram."""
        revogados = self.db.revoke_correction_unlocks(tournament_id, round_id)
        if revogados:
            self.db.create_audit_event(
                action="round_correction_relocked",
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type="round",
                entity_id=round_id,
                reason="Desbloqueio de correcao revogado pelo arbitro.",
                after={"revoked": revogados},
            )
        return revogados

    def _authorize_correction(self, tournament_id: int, round_id: int, reason: str) -> str:
        """Motivo valido + permissao vigente, ou `AppError`. Devolve o motivo limpo.

        A ordem importa: o motivo e checado ANTES da permissao. Quem chegou sem
        motivo precisa saber disso mesmo que a rodada esteja desbloqueada, senao
        desbloqueia, tenta nao nomear a razao e leva um recado sobre outra coisa.
        """
        erro = _correction_reason_error(reason)
        if erro:
            raise AppError(erro)
        estado = self.correction_unlock_state(tournament_id, round_id)
        if not estado.allowed:
            raise AppError(
                "Rodada fechada. Desbloqueie a rodada para correcao (com motivo e "
                "prazo) ou habilite mudancas perigosas nas configuracoes do torneio."
            )
        return _clean_reason(reason)

    def _after_correction(
        self,
        tournament_id: int,
        round_id: int,
        reason: str,
        *,
        is_team: bool = False,
    ) -> None:
        """O que a correcao contamina: pareamento posterior e retratos publicados."""
        round_data = self.db.get_round(round_id)
        corrected_number = int((round_data or {}).get("number") or 0)
        rounds = self.db.list_rounds(tournament_id)
        self._register_correction_cascade(tournament_id, round_id, corrected_number, rounds)
        self._reconcile_standings_snapshots(
            tournament_id, corrected_number, rounds, reason, is_team=is_team
        )

    def _register_correction_cascade(
        self,
        tournament_id: int,
        round_id: int,
        corrected_number: int,
        rounds: list[dict[str, Any]],
    ) -> None:
        """Evento de cascata quando ja existe rodada posterior pareada.

        Sem isto, corrigir a rodada 3 com a rodada 4 ja pareada nao dizia nada: o
        pareamento da 4 nasceu do placar antigo, e quem tinha de decidir se
        repareia nunca era avisado.
        """
        afetadas = _cascade_rounds(rounds, corrected_number)
        if not afetadas:
            return
        self.db.create_audit_event(
            action="result_correction_cascade",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            reason=_cascade_message(corrected_number, afetadas),
            after={"corrected_round": corrected_number, "affected_rounds": afetadas},
        )
        logger.warning(
            "Correcao na rodada %s do torneio %s afeta rodadas ja pareadas: %s",
            corrected_number,
            tournament_id,
            afetadas,
        )

    def _reconcile_standings_snapshots(
        self,
        tournament_id: int,
        corrected_number: int,
        rounds: list[dict[str, Any]],
        reason: str,
        *,
        is_team: bool,
    ) -> None:
        """Regrava os retratos de classificacao que a correcao invalidou.

        O retrato antigo NAO e apagado: vai para `standings_snapshot_history` com
        data e motivo, porque e ele que foi publicado e e ele que uma apelacao
        vai querer ver. A linha viva passa a ser a reconciliada.

        Cada rodada e recalculada com os pareamentos ATE ela — nao com o torneio
        inteiro. Sem esse corte, o retrato da rodada 3 receberia a classificacao
        de hoje, o que seria uma segunda informacao errada no lugar da primeira.
        """
        for round_data in _reconcilable_rounds(rounds, corrected_number):
            round_id = int(round_data["id"])
            round_number = int(round_data["number"])
            antes = self.db.supersede_standings_snapshot(
                tournament_id,
                round_id,
                f"Correcao na rodada {corrected_number}: {reason}",
            )
            standings = (
                self._team_standings(tournament_id, up_to_round=round_number)
                if is_team
                else self._standings(tournament_id, up_to_round=round_number)
            )
            self.db.create_standings_snapshot(
                tournament_id=tournament_id,
                round_id=round_id,
                round_number=round_number,
                standings=standings,
            )
            if not is_team:
                self._persist_tiebreak_components(
                    tournament_id=tournament_id,
                    round_id=round_id,
                    round_number=round_number,
                    standings=standings,
                )
            depois = next(
                (
                    str(item.get("snapshot_hash") or "")
                    for item in self.db.list_standings_snapshots(tournament_id)
                    if int(item.get("round_id") or 0) == round_id
                ),
                "",
            )
            self.db.create_audit_event(
                action="standings_snapshot_reconciled",
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type="standings_snapshot",
                entity_id=round_id,
                reason=f"Retrato da rodada {round_number} regravado apos correcao: {reason}",
                before={"snapshot_hash": antes},
                after={"snapshot_hash": depois, "superseded": bool(antes)},
            )
        logger.info(
            "Retratos de classificacao reconciliados no torneio %s a partir da rodada %s",
            tournament_id,
            corrected_number,
        )

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
            # Pendencia DESTE confronto, e nao da lista acumulada (PAR-04): com o
            # `pending` global, um tabuleiro em branco no primeiro confronto fazia
            # todos os seguintes pularem o sumario, mesmo os completos.
            faltando = [
                board
                for board in boards
                if not board["result"] or board["result"] not in RESULT_POINTS
            ]
            pending.extend(faltando)
            if faltando:
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
        standings = self._team_standings(tournament_id)
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

    def swap_pairing_colors(self, tournament_id: int, round_id: int, pairing_id: int) -> None:
        """Inverte as cores de uma mesa, com auditoria (PAR-04).

        A tela chamava `db.swap_pairing_colors` direto: era a UNICA mutacao de
        rodada que nao passava pelo servico e, por isso, a unica sem evento de
        auditoria. Cor decidida pelo arbitro entra no TRF e no historico de
        cores — precisa de trilha como qualquer outra decisao.
        """
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada nao encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada nao pode ser ajustada.")
        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa nao encontrada para o torneio selecionado.")
        if pairing.get("is_bye"):
            raise AppError("Mesa de bye nao tem cores para inverter.")
        if pairing["result"]:
            raise AppError("Limpe o resultado da mesa antes de trocar cores.")

        before = {
            "pairing_id": int(pairing_id),
            "white_player_id": pairing.get("white_player_id"),
            "black_player_id": pairing.get("black_player_id"),
        }
        self.db.swap_pairing_colors(pairing_id)
        self.db.create_audit_event(
            action="pairing_colors_swapped",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="pairing",
            entity_id=int(pairing_id),
            reason="Cores invertidas pelo arbitro.",
            before=before,
            after={
                "pairing_id": int(pairing_id),
                "white_player_id": before["black_player_id"],
                "black_player_id": before["white_player_id"],
            },
        )
        logger.info("Cores trocadas na mesa %s", pairing_id)

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
        before = {
            "team_board_id": int(team_board_id),
            "white_player_id": board.get("white_player_id"),
            "black_player_id": board.get("black_player_id"),
        }
        self.db.swap_team_board_colors(team_board_id)
        # Passava pelo servico, mas sem trilha — mesma lacuna do individual.
        self.db.create_audit_event(
            action="team_board_colors_swapped",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="team_board",
            entity_id=int(team_board_id),
            reason="Cores invertidas pelo arbitro.",
            before=before,
            after={
                "team_board_id": int(team_board_id),
                "white_player_id": before["black_player_id"],
                "black_player_id": before["white_player_id"],
            },
        )
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
        """Classificacao para PUBLICAR — tela, exportacao, premio, podio, ata.

        Em modo estrito (TBK-02), motor FIDE caido levanta `AppError` aqui: e o
        "bloquear a publicacao" do criterio de aceite.
        """
        return self._standings(tournament_id, honor_strict=True)

    def _standings(
        self,
        tournament_id: int,
        *,
        honor_strict: bool = False,
        up_to_round: int | None = None,
    ) -> list[dict[str, Any]]:
        """Motor da classificacao individual. `honor_strict` diz para que serve.

        Com `honor_strict=False` — pareamento, previa, snapshot de rodada,
        diagnostico do painel — a falha do motor FIDE degrada para o motor
        proprio mesmo em modo estrito, e de proposito: esses usos so precisam da
        ORDEM POR PONTOS, que os dois motores calculam igual. Barrar aqui pararia
        o torneio (nao se fecharia rodada nem se gerariam pares) por causa de um
        problema de RELATORIO — trocaria um risco de publicacao por um risco de
        operacao, que e maior. O registro e o alerta acontecem de qualquer forma.

        `up_to_round` recorta a classificacao "como estava depois da rodada N",
        que e o que um retrato de rodada guarda (ARB-01). Sem o corte, reconciliar
        o retrato da rodada 3 gravaria nele a classificacao de hoje.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []

        players = self.db.list_players(tournament_id, active_only=False)
        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        if up_to_round is not None:
            closed_pairings = [
                pairing
                for pairing in closed_pairings
                if int(pairing.get("round_number") or 0) <= int(up_to_round)
            ]
        settings = self.db.get_tournament_settings(tournament_id) or {}
        sequence = _parse_player_tiebreak_sequence(settings.get("tiebreak_sequence"))
        gacrux_tiebreaks = self._gacrux_player_tiebreaks(
            tournament_id, tournament, settings, sequence, players, closed_pairings,
            honor_strict=honor_strict, current_round=up_to_round,
        )
        return _calculate_player_standings(
            tournament,
            players,
            closed_pairings,
            sequence=sequence,
            gacrux_tiebreaks=gacrux_tiebreaks,
            adjustments=_aggregate_player_adjustments(
                self.db.list_point_adjustments(tournament_id)
            ),
        )

    def _gacrux_player_tiebreaks(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        sequence: list[dict[str, Any]] | None,
        players: list[dict[str, Any]],
        closed_pairings: list[dict[str, Any]],
        *,
        honor_strict: bool = False,
        current_round: int | None = None,
    ) -> dict[int, dict[str, Any]] | None:
        """Desempates pelo motor FIDE (Gacrux), ou None para usar o motor proprio.

        Retorna None quando: o motor configurado nao e o Gacrux; e torneio por
        equipes (Fase 5); nao ha rodada fechada; ou o motor falhou (fallback ao
        Albericus, hoje registrado e visivel — ver `_run_tiebreak_engine`). O
        resultado e cacheado por assinatura do estado.
        """
        engine_name = str(settings.get("tiebreak_engine") or default_tiebreak_engine())
        if engine_name != ENGINE_GACRUX:
            self._remember_engine(tournament_id, _report_engine_ok(engine_name))
            return None
        if tournament.get("competition_type") == "team":
            return None
        if not closed_pairings:
            # Nada calculado ainda: o motor configurado segue valendo.
            self._remember_engine(tournament_id, _report_engine_ok(engine_name))
            return None
        # Chamada aninhada vinda do export do TRF: usa o motor proprio (evita
        # recursao standings -> Gacrux -> export -> standings). NAO e fallback —
        # nao registra nada, nao alerta e nao vale o modo estrito, senao o export
        # que o proprio motor pediu ficaria impossivel.
        if int(tournament_id) in _GACRUX_TIEBREAK_INFLIGHT:
            return None

        # A sequencia vai INTEIRA (codigo + parametros) para o motor: era so a
        # lista de codigos, entao o corte que o arbitro configurou na TBK-04
        # chegava ao registro 212 do arquivo FIDE mas nao ao calculo em execucao
        # — o motor rodava com os padroes e a tela mostrava outro numero.
        codes: list[Any] = (
            [dict(item) for item in sequence]
            if sequence
            else list(_DEFAULT_PLAYER_TIEBREAKS)
        )
        results_sig = tuple(sorted(
            (int(pairing["id"]), str(pairing.get("result") or "")) for pairing in closed_pairings
        ))
        players_sig = tuple(sorted(
            (
                int(player["id"]),
                int(player.get("rating") or 0),
                int(player.get("international_rating") or 0),
                int(player.get("national_rating") or 0),
            )
            for player in players
        ))
        # `current_round` entra na chave: a classificacao "ate a rodada N" e outro
        # calculo, e sem isso o retrato de uma rodada leria o cache de outra.
        cache_key = (
            int(tournament_id), _sequence_signature(codes), results_sig, players_sig,
            int(current_round or 0),
        )

        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
        return self._run_tiebreak_engine(
            tournament_id,
            engine_name,
            settings,
            cache_key,
            lambda: GacruxTiebreakEngine(self.db).compute(
                tournament_id, codes, current_round=current_round
            ),
            honor_strict=honor_strict,
        )

    # ------------------------------------------------------------------ #
    # Motor de desempate: qual foi, e o que dizer quando trocou (TBK-02)
    # ------------------------------------------------------------------ #

    def _run_tiebreak_engine(
        self,
        tournament_id: int,
        engine_name: str,
        settings: dict[str, Any],
        cache_key: tuple,
        compute: Callable[[], dict[int, dict[str, Any]]],
        *,
        honor_strict: bool,
    ) -> dict[int, dict[str, Any]] | None:
        """Roda o motor FIDE e responde pelo que aconteceu.

        Antes da TBK-02 esta falha era um `logger.warning` e um `return None`: o
        mesmo torneio podia publicar duas classificacoes diferentes entre rodadas
        sem nenhum aviso ao arbitro. Agora ela deixa retrato (para a faixa da
        tela), evento de auditoria (para o relatorio e para o painel) e, em modo
        estrito, barra a publicacao em vez de degradar.

        O retrato e o registro NAO dependem de `honor_strict`: a falha e a mesma,
        e o modo estrito do torneio e que diz se ela bloqueia. `honor_strict` so
        decide se ESTE chamador recebe a excecao — quem so precisa da ordem por
        pontos (pareamento, snapshot) segue pelo motor proprio.
        """
        strict = bool(settings.get("tiebreak_strict"))
        cached = _GACRUX_TIEBREAK_CACHE.get(cache_key)
        if cached is not None:
            _GACRUX_TIEBREAK_CACHE.move_to_end(cache_key)
            self._remember_engine(tournament_id, cached.report)
            if cached.report.blocked and honor_strict:
                raise AppError(_strict_block_message(engine_name, cached.report.error))
            return cached.tiebreaks

        _GACRUX_TIEBREAK_INFLIGHT.add(int(tournament_id))
        try:
            tiebreaks = compute()
        except AppError as exc:
            report = (
                _report_engine_blocked(engine_name, str(exc))
                if strict
                else _report_engine_fallback(engine_name, str(exc))
            )
            self._store_engine_outcome(tournament_id, cache_key, report, None)
            self._audit_engine_failure(tournament_id, report)
            if report.blocked:
                logger.error(
                    "Motor %s de desempate falhou no torneio %s e o modo estrito barra a "
                    "publicacao da classificacao. (%s)",
                    engine_name,
                    tournament_id,
                    exc,
                )
                if honor_strict:
                    raise AppError(_strict_block_message(engine_name, str(exc))) from exc
                return None
            logger.warning(
                "Motor %s de desempate falhou no torneio %s; usando o motor proprio. (%s)",
                engine_name,
                tournament_id,
                exc,
            )
            return None
        finally:
            _GACRUX_TIEBREAK_INFLIGHT.discard(int(tournament_id))

        self._store_engine_outcome(
            tournament_id, cache_key, _report_engine_ok(engine_name), tiebreaks
        )
        return tiebreaks

    def _store_engine_outcome(
        self,
        tournament_id: int,
        cache_key: tuple,
        report: EngineReport,
        tiebreaks: dict[int, dict[str, Any]] | None,
    ) -> None:
        _GACRUX_TIEBREAK_CACHE[cache_key] = EngineOutcome(report=report, tiebreaks=tiebreaks)
        _GACRUX_TIEBREAK_CACHE.move_to_end(cache_key)
        while len(_GACRUX_TIEBREAK_CACHE) > _GACRUX_TIEBREAK_CACHE_MAX:
            _GACRUX_TIEBREAK_CACHE.popitem(last=False)
        self._remember_engine(tournament_id, report)

    @staticmethod
    def _remember_engine(tournament_id: int, report: EngineReport) -> EngineReport:
        _LAST_TIEBREAK_ENGINE[int(tournament_id)] = report
        return report

    def _audit_engine_failure(self, tournament_id: int, report: EngineReport) -> None:
        """Evento na trilha do torneio — mesma porta do `export_tournament_audit`.

        Uma falha por ESTADO do torneio, nao por chamada: o cache guarda o
        fracasso junto com o sucesso, entao fechar uma rodada nova gera um evento
        novo (o arbitro precisa saber que aconteceu de novo) e repintar a tela
        nao gera nenhum.
        """
        try:
            self.db.create_audit_event(
                action="tiebreak_engine_blocked" if report.blocked else "tiebreak_engine_fallback",
                tournament_id=int(tournament_id),
                entity_type="tiebreak_engine",
                reason=_fallback_audit_reason(report)
                if report.fallback
                else f"Motor {report.configured} falhou em modo estrito: {report.error}",
                metadata={
                    "configured": report.configured,
                    "used": report.used,
                    "error": report.error,
                },
            )
        except Exception:  # pragma: no cover - trilha nunca bloqueia o calculo
            logger.exception("Falha ao registrar a troca de motor de desempate")

    def tiebreak_engine_report(self, tournament_id: int) -> EngineReport:
        """Retrato do ultimo calculo de desempate deste torneio.

        Sem calculo registrado, devolve o motor configurado como usado — que e a
        verdade disponivel ("nada foi calculado ainda") e permite a faixa dizer
        de saida qual motor vai assinar a tabela.
        """
        stored = _LAST_TIEBREAK_ENGINE.get(int(tournament_id))
        if stored is not None:
            return stored
        settings = self.db.get_tournament_settings(tournament_id) or {}
        return _report_engine_ok(
            str(settings.get("tiebreak_engine") or default_tiebreak_engine())
        )

    def tiebreak_engine_badge(self, tournament_id: int) -> dict[str, str]:
        """A faixa pronta para a tela: rotulo, tom e detalhe."""
        return _engine_badge(self.tiebreak_engine_report(tournament_id))

    def reset_tiebreak_engine(self, tournament_id: int) -> None:
        """Esquece o calculo cacheado deste torneio e tenta o motor de novo.

        Falha cacheada e o que evita a enxurrada de subprocessos, mas tambem
        prende o torneio numa falha que pode ter sido passageira. O "Recalcular"
        da tela de classificacao chama aqui: e o caminho explicito de volta ao
        motor configurado, sem precisar mexer em resultado nenhum.
        """
        target = int(tournament_id)
        for key in [key for key in _GACRUX_TIEBREAK_CACHE if target in key]:
            _GACRUX_TIEBREAK_CACHE.pop(key, None)
        _LAST_TIEBREAK_ENGINE.pop(target, None)

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
                round_match = matches_by_team_round.get((team_id, round_number))
                if not round_match:
                    round_cells[round_number] = {
                        "kind": "absent",
                        "label": "-",
                        "round": round_number,
                        "boards": [],
                    }
                    continue
                if round_match.get("is_bye"):
                    round_cells[round_number] = {
                        **round_match,
                        "kind": "bye",
                        "label": (
                            f"BYE MP {self._compact_number(round_match.get('white_match_points'))} "
                            f"GP {self._compact_number(round_match.get('white_game_points'))}"
                        ),
                        "boards": [],
                    }
                    continue
                is_white = team_id == int(round_match["white_team_id"])
                opponent_id = int(round_match["black_team_id"] if is_white else round_match["white_team_id"])
                opponent = standings_by_team.get(opponent_id, {})
                match_points = round_match.get("white_match_points" if is_white else "black_match_points")
                game_points = round_match.get("white_game_points" if is_white else "black_game_points")
                result = str(round_match.get("result") or "")
                round_cells[round_number] = {
                    **round_match,
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
                    "boards": boards_by_match_id[int(round_match["id"])],
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
        """Classificacao de EQUIPES para publicar. Ver `standings` (TBK-02)."""
        return self._team_standings(tournament_id, honor_strict=True)

    def _team_standings(
        self,
        tournament_id: int,
        *,
        honor_strict: bool = False,
        up_to_round: int | None = None,
    ) -> list[dict[str, Any]]:
        """Ver `_standings`: mesmos dois parametros, mesmas razoes."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        teams = self.db.list_teams(tournament_id, active_only=False)
        closed_matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        if up_to_round is not None:
            closed_matches = [
                match
                for match in closed_matches
                if int(match.get("round_number") or 0) <= int(up_to_round)
            ]
        sequence = _parse_team_tiebreak_sequence(settings.get("team_tiebreak_sequence"))
        gacrux_tiebreaks = self._gacrux_team_tiebreaks(
            tournament_id, tournament, settings, sequence, teams, closed_matches,
            honor_strict=honor_strict, current_round=up_to_round,
        )
        return _calculate_team_standings(
            settings,
            teams,
            closed_matches,
            sequence=sequence,
            gacrux_tiebreaks=gacrux_tiebreaks,
            adjustments=_aggregate_team_adjustments(
                self.db.list_point_adjustments(tournament_id)
            ),
            board_results=self._team_board_results(tournament_id, sequence, up_to_round),
        )

    def _team_board_results(
        self,
        tournament_id: int,
        sequence: list[dict[str, Any]] | None,
        up_to_round: int | None,
    ) -> list[dict[str, Any]] | None:
        """Resultados por tabuleiro — so quando algum criterio precisa (TBK-05).

        A classificacao e recalculada a cada abertura de tela e a cada secao de
        relatorio; a consulta so vale a pena quando o board count esta na
        sequencia configurada, o que nao acontece em nenhum torneio por padrao.
        """
        if not any(str(item.get("code")) == "board_count" for item in sequence or []):
            return None
        rows = self.db.list_team_board_results(tournament_id, closed_only=True)
        if up_to_round is None:
            return rows
        return [row for row in rows if int(row.get("round_number") or 0) <= int(up_to_round)]

    def _gacrux_team_tiebreaks(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        sequence: list[dict[str, Any]] | None,
        teams: list[dict[str, Any]],
        closed_matches: list[dict[str, Any]],
        *,
        honor_strict: bool = False,
        current_round: int | None = None,
    ) -> dict[int, dict[str, Any]] | None:
        """Desempates de EQUIPES pelo motor FIDE (Gacrux), ou None p/ o proprio.

        Espelha _gacrux_player_tiebreaks, inclusive no registro da troca de motor
        (TBK-02): None quando o motor nao e o Gacrux, nao ha confronto fechado, ou
        o motor falhou; cache por assinatura + guarda de reentrancia (o export
        TRF-25 chama team_standings() de novo).
        """
        engine_name = str(settings.get("tiebreak_engine") or default_tiebreak_engine())
        if engine_name != ENGINE_GACRUX:
            self._remember_engine(tournament_id, _report_engine_ok(engine_name))
            return None
        if tournament.get("competition_type") != "team":
            return None
        if not closed_matches:
            self._remember_engine(tournament_id, _report_engine_ok(engine_name))
            return None
        if int(tournament_id) in _GACRUX_TIEBREAK_INFLIGHT:
            return None

        # Sequencia inteira, com parametros — ver `_gacrux_player_tiebreaks`.
        codes: list[Any] = [dict(item) for item in (sequence or []) if item.get("code")]
        if not codes:
            primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
            secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
            codes = [primary, secondary, "buchholz", "wins"]

        results_sig = tuple(sorted(
            (
                int(match["id"]),
                str(match.get("result") or ""),
                float(match.get("white_match_points") or 0.0),
                float(match.get("black_match_points") or 0.0),
                float(match.get("white_game_points") or 0.0),
                float(match.get("black_game_points") or 0.0),
            )
            for match in closed_matches
        ))
        teams_sig = tuple(sorted(int(team["id"]) for team in teams))
        cache_key = (
            "team", int(tournament_id), _sequence_signature(codes), results_sig, teams_sig,
            int(current_round or 0),
        )

        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
        return self._run_tiebreak_engine(
            tournament_id,
            engine_name,
            settings,
            cache_key,
            lambda: GacruxTiebreakEngine(self.db).compute_teams(
                tournament_id, codes, current_round=current_round
            ),
            honor_strict=honor_strict,
        )

    def _knockout_pairings(
        self,
        tournament_id: int,
        players: list[dict[str, Any]],
        next_number: int,
        settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Proxima fase do mata-mata, com o avanco explicado (PAR-03).

        A fase so e gerada quando toda mesa da anterior tem vencedor — do
        tabuleiro ou por decisao registrada. Empate, dupla ausencia e mesa em
        branco promoviam o melhor numero inicial em silencio; agora eles PARAM a
        geracao e pedem a decisao do arbitro.
        """
        if next_number == 1:
            return _knockout_pairings(players, next_number, settings)

        anteriores = self._knockout_round_pairings(tournament_id, next_number - 1)
        decisoes = self._knockout_decisions(tournament_id)
        pendentes = _knockout_undecided_boards(anteriores, decisoes)
        if pendentes:
            raise AppError(
                _knockout_pending_message(
                    [int(mesa.get("board_number") or 0) for mesa in pendentes]
                )
            )

        avancaram = _knockout_advancing_ids(anteriores, decisoes)
        if next_number > 2:
            # Quem jogou a mesa de 3o lugar perdeu a fase anterior: vencer ali
            # nao devolve ninguem a chave principal.
            na_chave = set(
                _knockout_advancing_ids(
                    self._knockout_round_pairings(tournament_id, next_number - 2), decisoes
                )
            )
            avancaram = [player_id for player_id in avancaram if player_id in na_chave]

        pairings = _knockout_pairings(players, next_number, settings, avancaram)
        if settings.get("knockout_third_place") and len(avancaram) == 2:
            terceiro = _knockout_third_place_pairing(
                anteriores, decisoes, len(pairings) + 1
            )
            if terceiro:
                pairings.append(terceiro)
        return pairings

    def _knockout_round_pairings(self, tournament_id: int, round_number: int) -> list[dict[str, Any]]:
        round_data = self.db.get_round_by_number(tournament_id, int(round_number))
        if not round_data:
            raise AppError("Rodada anterior não encontrada.")
        return self.db.get_pairings_for_round(int(round_data["id"]))

    def _knockout_decisions(self, tournament_id: int) -> dict[int, dict[str, Any]]:
        return {
            int(item["pairing_id"]): item
            for item in self.db.list_knockout_advancements(int(tournament_id))
        }

    def knockout_advancement_criteria(self) -> dict[str, str]:
        """Criterios de desempate de mata-mata oferecidos ao arbitro (PAR-03)."""
        return dict(_KNOCKOUT_CRITERIA)

    def register_knockout_advancement(
        self,
        tournament_id: int,
        pairing_id: int,
        player_id: int,
        criterion: str,
        notes: str = "",
        actor: str = "",
    ) -> None:
        """Registra quem avancou numa mesa que a partida nao decidiu (PAR-03)."""
        pairing = self.db.get_pairing(int(pairing_id))
        if not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id):
            pairing = None
        round_data = (
            self.db.get_round(int(pairing["round_id"])) if pairing else None
        )
        erro = _knockout_decision_error(
            criterion=criterion,
            notes=notes,
            player_id=int(player_id),
            pairing=pairing,
            round_closed=bool(round_data and str(round_data.get("status")) == "closed"),
        )
        if erro:
            raise AppError(erro)
        limpo = _knockout_clean_notes(notes)
        self.db.save_knockout_advancement(
            int(tournament_id),
            int(pairing_id),
            int(player_id),
            str(criterion).strip(),
            notes=limpo,
            actor=actor,
        )
        self.db.create_audit_event(
            action="knockout_advancement_registered",
            tournament_id=int(tournament_id),
            round_id=int(pairing["round_id"]) if pairing else None,
            entity_type="pairing",
            entity_id=int(pairing_id),
            after={
                "player_id": int(player_id),
                "criterion": str(criterion).strip(),
                "notes": limpo,
            },
        )

    def knockout_bracket(self, tournament_id: int) -> dict[str, Any]:
        """A chave do mata-mata, com o motivo de cada avanco (PAR-03)."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        rounds = sorted(
            self.db.list_rounds(tournament_id), key=lambda item: int(item["number"])
        )
        pairings_by_round = {
            int(round_data["number"]): self.db.get_pairings_for_round(int(round_data["id"]))
            for round_data in rounds
        }
        nomes = {
            int(player["id"]): player_full_name(player)
            for player in self.db.list_players(tournament_id, active_only=False)
        }
        fases = _knockout_bracket(
            rounds, pairings_by_round, self._knockout_decisions(tournament_id), nomes
        )
        return {
            "tournament_id": int(tournament_id),
            "tournament_name": str(tournament.get("name") or ""),
            "rounds": fases,
            "pending": sum(int(fase["pending"]) for fase in fases),
        }

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
        standings = {item["player_id"]: item for item in self._standings(tournament_id)}
        settings = self.db.get_tournament_settings(tournament_id) or {}
        seeding = self._seeding(players, settings)
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
