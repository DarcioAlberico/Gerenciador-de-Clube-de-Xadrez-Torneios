from __future__ import annotations
import json
import logging
import threading
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from src.core.database import Database
from src.core.database_tournament_core import default_tiebreak_engine
from src.domain.numbers import setting_number
from src.core.operator import SYSTEM_ACTOR
from src.services.transactions import atomic
from src.services.constants import (
    ACCELERATION_METHODS as _ACCELERATION_METHODS,
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
    DEFAULT_PLAYER_TIEBREAKS as _DEFAULT_PLAYER_TIEBREAKS,
    acceleration_spec as _acceleration_spec,
    accelerated_player_ids as _accelerated_player_ids,
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
    topscorer_ids as _topscorer_ids,
    result_submission_issue as _result_submission_issue,
    result_states_summary as _result_states_summary,
    round_robin_team_matches as _round_robin_team_matches,
    scheme_applies_bonus as _scheme_applies_bonus,
    scheme_is_baku as _scheme_is_baku,
    standings_with_virtual_points as _standings_with_virtual_points,
    team_preview_payload as _team_preview_payload,
    team_round_dashboard_metrics as _team_round_dashboard_metrics,
    tiebreak_narrative_from_standings as _tiebreak_narrative_from_standings,
    swiss_pairings as _swiss_pairings,
    swiss_team_matches as _swiss_team_matches,
    team_bye_payload as _team_bye_payload,
    team_bye_summary as _team_bye_summary,
    team_match_summary as _team_match_summary,
    TeamWithoutPlayersError as _TeamWithoutPlayersError,
    assign_team_pairing_numbers as _assign_team_pairing_numbers,
    pairing_strengths as _team_pairing_strengths,
    team_lineup as _team_lineup,
    team_lineup_warnings as _team_lineup_warnings,
    team_seed as _team_seed,
    team_bye_ids as _team_bye_ids,
    team_color_histories as _team_color_histories,
    team_float_histories as _team_float_histories,
    team_played_pairs as _team_played_pairs,
)
from src.services.pairing.constraints import seeding_order as _seeding_order
from src.services.pairing.initial_color import resolve_initial_color
from src.services.permissions import requires
from src.services.pairing.pairing_check import (
    PairingCheck,
    manual_adjustment_reason_error as _manual_adjustment_reason_error,
    paired_player_ids as _paired_player_ids,
    reserve_round_notice as _reserve_round_notice,
    stored_pairs as _stored_pairs,
    unchecked as _unchecked_round,
)
from src.services.pairing.point_adjustments import (
    aggregate_player_adjustments as _aggregate_player_adjustments,
    aggregate_team_adjustments as _aggregate_team_adjustments,
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
from src.services.pairing.fixed_calendar import (
    late_entry_warning as _fixed_calendar_late_entry_warning,
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
from src.services.pairing.player_round import (
    LateEntryPlan as _LateEntryPlan,
    bye_balance as _bye_balance,
    late_entry_plan as _late_entry_plan,
    walkover_result as _walkover_result,
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
    deleted_results_message as _deleted_results_message,
    expiry_from as _expiry_from,
    round_deletion_reason_error as _round_deletion_reason_error,
    shared_reason_error as _shared_reason_error,
    unlock_minutes as _unlock_minutes,
    unlock_reason_error as _unlock_reason_error,
    unlock_state as _unlock_state,
)
from src.services.pairing.team_swiss import (
    baku_first_round_team_matches as _baku_first_round_team_matches,
    team_round_violations as _team_round_violations,
)
from src.services.pairing.acceleration import (
    baku_accelerated_player_ids as _baku_accelerated_player_ids,
    baku_team_accelerated_ids as _baku_team_accelerated_ids,
    team_acceleration_not_applied_warning as _team_acceleration_not_applied_warning,
)
from src.services.pairing.standings_cut import (
    adjustments_up_to_round as _adjustments_up_to_round,
    players_as_of_round as _players_as_of_round,
    teams_as_of_round as _teams_as_of_round,
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

if TYPE_CHECKING:
    from src.services.pairing.gacrux_engine import GacruxRefusal
    from src.services.pairing.gacrux_tiebreak_engine import TiebreakJob

logger = logging.getLogger(__name__)

# Cache (nível de módulo, pois PairingService e instanciado ad-hoc em vários
# serviços) dos desempates calculados pelo motor FIDE (Gacrux). standings() e
# chamado com frequência e cada cálculo dispara um subprocesso; a chave e
# (torneio, hash do TRF + linha de comando) — ver `TiebreakJob.fingerprint`
# (RGS-36) —, invalidando-se quando qualquer dado que o motor recebe muda.
# Lido e gravado por mais de uma thread (RGS-10): todo acesso passa pelo lock.
_GACRUX_TIEBREAK_CACHE: "OrderedDict[tuple, EngineOutcome]" = OrderedDict()
_GACRUX_TIEBREAK_CACHE_MAX = 64
_GACRUX_TIEBREAK_CACHE_LOCK = threading.Lock()
# Ultimo motor que efetivamente assinou a classificação de cada torneio (TBK-02).
# Alimenta a faixa permanente da tela: quem pergunta não roda o motor de novo.
_LAST_TIEBREAK_ENGINE: dict[int, EngineReport] = {}
# Guarda de reentrância: o cálculo do Gacrux exporta o TRF e o export chama
# standings() de novo. Nessa chamada aninhada usamos o motor próprio (as colunas
# de rank/pontos do TRF não alimentam o desempate FIDE — o Gacrux recalcula a
# partir dos resultados), evitando recursao infinita. A guarda e POR THREAD
# (RGS-10, item 4): global, a classificação pedida por outra thread enquanto
# esta calcula sairia em silêncio pelo motor próprio.
_GACRUX_TIEBREAK_INFLIGHT = threading.local()


def _tiebreak_inflight() -> set[int]:
    """Torneios cujo desempate Gacrux esta sendo calculado NESTA thread."""
    tournaments = getattr(_GACRUX_TIEBREAK_INFLIGHT, "tournaments", None)
    if tournaments is None:
        tournaments = _GACRUX_TIEBREAK_INFLIGHT.tournaments = set()
    return tournaments


def _json_or_empty(raw: Any) -> dict[str, Any]:
    """``before_json``/``after_json`` de um evento como dicionario (vazio se nao for)."""
    try:
        valor = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return valor if isinstance(valor, dict) else {}


def _repair_reason(reason: str, pending: int) -> str:
    """O motivo do re-emparceiramento: exigido com resultado ou QR pendente (RGS-34)."""
    erro = _round_deletion_reason_error(reason, pending)
    if erro:
        raise AppError(
            erro,
            suggestion="Diga por que a rodada vai ser refeita, por exemplo “metade da turma faltou”.",
        )
    return _clean_reason(reason) or "Re-emparceiramento do modo amistoso."


def _is_open_round(rodada: Mapping[str, Any]) -> bool:
    """Há rodada e ela ainda não foi fechada."""
    return bool(rodada) and str(rodada.get("status")) != "closed"


def _late_entry_fields(data: Mapping[str, Any], allowed: Sequence[str], nome: str) -> dict[str, Any]:
    """Os campos do jogador que a entrada tardia grava, com nome limpo e ratings inteiros."""
    campos = {chave: data[chave] for chave in allowed if data.get(chave) is not None}
    campos["name"] = nome
    for chave in ("rating", "national_rating", "international_rating"):
        if chave in campos:
            campos[chave] = int(campos[chave] or 0)
    return campos


def _round_ref(rodada: Mapping[str, Any] | None) -> dict[str, int]:
    """``{"round_id", "number"}`` da rodada, zeros se não houver."""
    rodada = rodada or {}
    return {"round_id": int(rodada.get("id") or 0), "number": int(rodada.get("number") or 0)}


class PairingService:
    MAX_EXHAUSTIVE_PAIRING_PLAYERS = 16
    MAX_EXHAUSTIVE_PAIRING_TEAMS = 16
    REPEAT_PAIRING_PENALTY = 1_000_000
    SCORE_GROUP_FLOAT_PENALTY = 10_000
    SCORE_DIFF_PENALTY = 1_000
    PAIRING_ENGINE_VERSION = "albericus-swiss-1"
    TEAM_PAIRING_ENGINE_VERSION = "albericus-team-swiss-1"
    RULESET_VERSION = "albericus-2026-phase0"
    RECONCILE_MAX_PASSES = 10

    def __init__(self, db: Database) -> None:
        self.db = db
        # RGS-10: quem quer saber que há retrato a reconciliar (o trabalhador
        # que a tela liga). Chamado com o id do torneio DEPOIS do commit da
        # correção, na thread que corrigiu. Sem ninguém ouvindo, a pendência
        # fica no banco e e terminada na próxima abertura do app.
        self.on_snapshots_pending: Callable[[int], None] | None = None

    def preview_next_round(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
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
            raise AppError("Selecione um torneio válido.")
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
            # Tolerância de atraso (ORG-03). O árbitro precisa dela na mão no
            # momento de declarar ausência, e ela vivia só na cabeça de quem leu
            # o edital. `0` = perde a hora marcada, que é o default da FIDE.
            "late_tolerance_minutes": int(
                (self.db.get_tournament_settings(tournament_id) or {}).get(
                    "late_tolerance_minutes"
                )
                or 0
            ),
            **self._round_clock_metrics(latest_round),
        }
        alerts: list[str] = []
        alerts_detailed: list[dict[str, Any]] = []

        def add_alert(text: str, severity: str, action: str = "") -> None:
            # Mantém `alerts` (strings, retrocompatibilidade) em sincronia com a
            # versão estruturada usada pelos alertas clicáveis do painel.
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
                            f"Rodada {latest_round['number']} tem {len(blocking_issues)} pendência(s) de arbitragem bloqueante(s).",
                            "danger",
                            "blocking_issues",
                        )
                    else:
                        add_alert(
                            f"Rodada {latest_round['number']} está pronta para fechamento.",
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
            add_alert(f"{correction_count} correção(ões) auditada(s) no torneio.", "info", "corrections")
        if submitted_results:
            add_alert(
                f"{submitted_results} resultado(s) enviado(s) por QR aguardando aprovação.",
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
                        f"Prévia da próxima rodada tem {metrics['preview_alerts']} alerta(s).",
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

        Cada item: {label, ok, action} — `action` reaproveita o mapa de ações dos
        alertas clicáveis do painel.
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
                "label": f"Resultados lançados ({resolved}/{total})",
                "ok": int(metrics.get("pending_results") or 0) == 0,
                "action": "pending_results",
            },
            {
                "label": "Sem resultados QR aguardando aprovação",
                "ok": int(metrics.get("submitted_results") or 0) == 0,
                "action": "qr_pending",
            },
            {
                "label": "Sem pendências de arbitragem bloqueantes",
                "ok": int(metrics.get("blocking_issues") or 0) == 0,
                "action": "blocking_issues",
            },
        ]
        # Específico de equipes: escalacoes/ordem de tabuleiro sem avisos de policy.
        if metrics.get("competition_type") == "team":
            from src.services.tournament_service import TeamService

            rounds = sorted(self.db.list_rounds(tournament_id), key=lambda item: int(item["number"]))
            latest_round_id = int(rounds[-1]["id"]) if rounds else None
            roster_issues = TeamService(self.db).validate_roster_policy(tournament_id, round_id=latest_round_id)
            items.append(
                {
                    "label": f"Escalações sem pendências ({len(roster_issues)})",
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
            # individual, e é exatamente onde o árbitro precisa ler "Adiada —
            # sábado 14h" em vez de confundir a mesa com uma esquecida.
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
            raise AppError("Selecione um torneio válido.")
        issues: list[dict[str, Any]] = []
        safe_limit = max(1, min(int(limit or 200), 1000))
        acknowledged_keys = self._acknowledged_arbitration_issue_keys(tournament_id)

        for submission in self.db.list_result_submissions(tournament_id=tournament_id, status="submitted", limit=safe_limit):
            issues.append(_result_submission_issue(submission))

        # Queda de seta e ausência BLOQUEIAM até a decisão ser registrada
        # (ARB-03): são os dois eventos que a FIDE não deixa passar sem o
        # árbitro decidir — quem ganha a partida? houve reclamação? perdeu por
        # 6.7? Antes eram `attention`, e a rodada fechava com a pergunta em
        # aberto. Registrado o incidente que aponta para o evento, o alerta volta
        # a ser informativo: a decisão existe e é na ata.
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
                    "Registre a decisão no painel disciplinar: a rodada não fecha "
                    "com queda de seta ou ausência sem decisão do árbitro."
                )
            issues.append(issue)

        # Incidentes registrados viram pendência informativa: o painel e onde o
        # árbitro revê o que decidiu, e a ata sai dali.
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
        # sync: o fallback já virou evento de auditoria, e o painel só o lê.
        #
        # Severidade "attention", não "decision": decision BLOQUEIA o fechamento
        # da rodada, e um problema de relatório não pode parar o torneio. Quem
        # segura a publicação e o modo estrito, dentro de standings().
        for event in self.db.list_audit_events(
            tournament_id, action="tiebreak_engine_fallback", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "tiebreak", "engine_fallback",
                    "Motor de desempate substituído", severity="attention",
                )
            )
        for event in self.db.list_audit_events(
            tournament_id, action="tiebreak_engine_blocked", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "tiebreak", "engine_blocked",
                    "Classificação bloqueada (modo estrito)", severity="attention",
                )
            )

        # Cascata de correção (ARB-01): corrigiu uma rodada que já alimentou o
        # pareamento das seguintes. `attention` — quem decide se repareia e o
        # árbitro, e travar o fechamento não ajudaria em nada.
        for event in self.db.list_audit_events(
            tournament_id, action="result_correction_cascade", limit=safe_limit
        ):
            issue = _audit_issue(
                event, "correction", "cascade",
                "Correção afeta rodada já pareada", severity="attention",
            )
            # RGS-20: o `reason` do evento e o motivo do árbitro; o que fazer
            # (reparear, conferir desempates) mora no `after`. O painel mostra
            # os dois — eventos antigos tinham o recado no próprio motivo.
            recado = str(_json_or_empty(event.get("after_json")).get("message") or "")
            motivo = str(event.get("reason") or "")
            if recado and recado != motivo:
                issue["detail"] = f"{recado} Motivo: {motivo}" if motivo else recado
            issues.append(issue)

        # Bye solicitado descartado por jogador inativo (ARB-04). `attention`: o
        # pedido já ficou para trás, e travar o fechamento não o traria de volta
        # — o que faltava era o árbitro FICAR SABENDO.
        for event in self.db.list_audit_events(
            tournament_id, action="requested_bye_discarded", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "bye", "discarded",
                    "Bye solicitado descartado (jogador inativo)", severity="attention",
                )
            )

        # Rodada GERADA pelo Gacrux que difere do holandês em modo verificação
        # (RGS-16): e defeito, não decisão do árbitro — `decision` BLOQUEIA o
        # fechamento até ele registrar que viu (pendência "ciente"). Rodada não
        # verificada (motor ausente, arquivo sem representação) so avisa.
        for event in self.db.list_audit_events(
            tournament_id, action="pairing_check_divergence", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "pairing", "check_divergence",
                    "Rodada gerada difere do holandês (Gacrux)", severity="decision",
                )
            )
        for event in self.db.list_audit_events(
            tournament_id, action="pairing_check_unverified", limit=safe_limit
        ):
            issues.append(
                _audit_issue(
                    event, "pairing", "check_unverified",
                    "Rodada não verificada pelo holandês (Gacrux)", severity="attention",
                )
            )

        issues.extend(self._pairing_arbitration_issues(tournament_id, tournament))
        issues.extend(self._postponed_arbitration_issues(tournament_id))

        issues = _finalize_issues(issues, acknowledged_keys, safe_limit)
        metrics = _issue_metrics(issues)
        return {"metrics": metrics, "issues": issues}

    def _postponed_arbitration_issues(self, tournament_id: int) -> list[dict[str, Any]]:
        """Uma pendência por mesa adiada da rodada em andamento (ARB-02).

        Só a rodada corrente: mesa adiada de rodada fechada não existe — lançar
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

    @requires("tournament_write")
    @atomic
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
        """Registra o incidente E aplica a decisão (ARB-03).

        Uma decisão disciplinar que não chega na classificação e um bilhete: o
        `point_adjustments` já existia (TBK-01 o faz mover a ordem), mas sem
        catálogo de infrações e sem vínculo — a dedução era um número com texto
        livre ao lado. Aqui os dois viram um registro só.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        player = self.db.get_player(int(player_id)) if player_id else None
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador não encontrado para o torneio selecionado.")

        pairing = self.db.get_pairing(int(pairing_id)) if pairing_id else None
        if pairing_id and (
            not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id)
        ):
            raise AppError("Mesa não encontrada para o torneio selecionado.")

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
            # W.O., e não o resultado por decisão do árbitro (`1U-0U`, ARB-02):
            # quem perde por regulamento NÃO JOGOU a partida aos olhos da FIDE.
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
    # Participação: retirada e reentrada (ARB-05)
    # ------------------------------------------------------------------ #

    @requires("tournament_write")
    @atomic
    def set_player_participation(
        self,
        tournament_id: int,
        player_id: int,
        status: str,
        reason: str = "",
        actor: str = "",
    ) -> int:
        """Muda o estado de participação E registra no histórico (ARB-05).

        `players.player_status` guarda só o estado de agora; sem o evento não
        sobra rastro de "saiu na rodada 3, voltou na 5" — nem para a ata, nem
        para explicar por que um jogador some do pareamento.

        Devolve a rodada A PARTIR da qual a mudança vale.
        """
        player = self.db.get_player(int(player_id))
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador não encontrado para o torneio selecionado.")
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

    @requires("tournament_write")
    @atomic
    def set_players_participation(
        self,
        tournament_id: int,
        player_ids: list[int],
        status: str,
        *,
        skip_withdrawn: bool = False,
    ) -> dict[str, int]:
        """Muda a participação de vários jogadores numa transação só (RG2-25).

        "Todos presentes" parava no primeiro desistente e deixava metade
        aplicada. Com ``skip_withdrawn``, quem desistiu fica como está e entra
        na contagem; sem ele, a recusa de um desfaz todos.
        """
        changed = skipped = 0
        for player_id in player_ids:
            player = self.db.get_player(int(player_id))
            if skip_withdrawn and player and str(player.get("player_status") or "") == "withdrawn":
                skipped += 1
                continue
            self.set_player_participation(tournament_id, int(player_id), status)
            changed += 1
        return {"changed": changed, "skipped_withdrawn": skipped}

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

    @requires("tournament_write")
    @atomic
    def request_bye(
        self,
        tournament_id: int,
        player_id: int,
        round_number: int,
        bye_type: str = "H",
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado, aplicando a política do torneio (ARB-04).

        Era gravado direto da tela no banco, sem serviço nenhum — e por isso um
        pedido para rodada já gerada era aceito e nunca aplicado, um pedido de
        jogador inativo sumia na hora de parear, e não havia limite nenhum.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        player = self.db.get_player(int(player_id))
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador não encontrado para o torneio selecionado.")

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

    @requires("tournament_write")
    @atomic
    def cancel_requested_bye(self, tournament_id: int, bye_id: int, reason: str) -> None:
        """Exclui um bye solicitado com regra e rastro (RG2-05).

        A tela apagava direto no banco: o bye já aplicado numa rodada gerada
        sumia do cadastro, a mesa continuava "H" e o saldo zerava — com limite
        no regulamento, um bye a mais. Agora: rodada do bye já gerada (ou
        fechada) recusa, porque o bye já está na mesa; sem rodada, exige motivo
        e audita.
        """
        bye = next(
            (
                item
                for item in self.db.list_requested_byes(tournament_id)
                if int(item["id"]) == int(bye_id)
            ),
            None,
        )
        if bye is None:
            raise AppError("Bye solicitado não encontrado neste torneio.")
        round_number = int(bye.get("round_number") or 0)
        if self.db.get_round_by_number(tournament_id, round_number):
            raise AppError(
                f"O bye da rodada {round_number} já está na rodada gerada e conta no saldo "
                "do jogador. Para desfazê-lo, exclua a rodada ainda não fechada ou corrija "
                "o resultado da mesa."
            )
        motivo = str(reason or "").strip()
        if not motivo:
            raise AppError("Informe o motivo da exclusão do bye.")
        self.db.delete_requested_bye(int(bye_id))
        self.db.create_audit_event(
            action="requested_bye_removed",
            tournament_id=int(tournament_id),
            entity_type="player",
            entity_id=int(bye["player_id"]),
            reason=motivo,
            before={
                "round_number": round_number,
                "bye_type": str(bye.get("bye_type") or "").strip().upper(),
                "reason": str(bye.get("reason") or "").strip(),
            },
        )

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
        """Deixa na trilha o que o pareamento avisou ao árbitro (PAR-02).

        A prévia mostra os mesmos avisos ANTES de gerar; este registro e para
        depois: quem conferir a rodada no futuro precisa achar por que ela foi
        pareada assim (aceleração que trocou de motor, pontuação que o motor FIDE
        não recebeu) sem depender de quem estava na sala.
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

    # ------------------------------------------------------------------ #
    # Ações na linha do jogador (RGS-22, RGS-23, RGS-24)
    # ------------------------------------------------------------------ #

    def _player_of(self, tournament_id: int, player_id: int) -> dict[str, Any]:
        player = self.db.get_player(int(player_id))
        if not player or int(player.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Jogador não encontrado para o torneio selecionado.")
        return player

    def next_round_number(self, tournament_id: int) -> int:
        """A próxima rodada a ser gerada — de onde vale uma mudança de agora."""
        return _participation_effective_round(self.db.get_latest_round(int(tournament_id)))

    def bye_balance(self, tournament_id: int, player_id: int) -> str:
        """Saldo do jogador na política de bye: "1 de 2 byes usados; …" (RGS-23)."""
        settings = self.db.get_tournament_settings(tournament_id) or {}
        byes = [
            item
            for item in self.db.list_requested_byes(int(tournament_id))
            if int(item.get("player_id") or 0) == int(player_id)
        ]
        return _bye_balance(_ByePolicy.from_settings(settings), byes)

    def player_round_situation(
        self, tournament_id: int, player_id: int, round_number: int
    ) -> dict[str, Any]:
        """Onde o jogador está na rodada pedida — para o diálogo saber o que oferecer.

        ``round_status`` é ``None`` quando a rodada ainda não existe (cabe bye
        solicitado); com a rodada gerada e o jogador numa mesa sem resultado, o
        diálogo oferece o W.O. (``walkover_result``) em vez de um bye que seria
        aceito e nunca aplicado.
        """
        self._player_of(tournament_id, player_id)
        situacao: dict[str, Any] = {
            "round_number": int(round_number),
            "round_status": None,
            "pairing_id": None,
            "board_number": 0,
            "is_bye": False,
            "has_result": False,
            "walkover_result": "",
        }
        rodada = self.db.get_round_by_number(int(tournament_id), int(round_number))
        if not rodada:
            return situacao
        situacao["round_status"] = str(rodada.get("status") or "generated")
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            jogadores = {int(mesa.get("white_player_id") or 0), int(mesa.get("black_player_id") or 0)}
            if int(player_id) not in jogadores:
                continue
            situacao.update(
                pairing_id=int(mesa["id"]),
                board_number=int(mesa.get("board_number") or 0),
                is_bye=bool(mesa.get("is_bye")),
                has_result=bool(str(mesa.get("result") or "").strip()),
                walkover_result="" if mesa.get("is_bye") else _walkover_result(mesa, int(player_id)),
            )
            break
        return situacao

    def miss_round(
        self, tournament_id: int, player_id: int, round_number: int, reason: str = ""
    ) -> int:
        """"Faltar só à rodada N" (RGS-22): bye Z solicitado; o status NÃO muda.

        O Z não conta no limite da política (`count_limited`), e o jogador
        volta sozinho na rodada seguinte — não há "retorno automático" a
        lembrar, porque ele nunca saiu. Rodada já gerada é recusada aqui com o
        caminho certo (W.O. na mesa), antes de a política dizer o mesmo sem acento.
        """
        situacao = self.player_round_situation(tournament_id, player_id, round_number)
        if situacao["round_status"] == "closed":
            raise AppError(
                f"A rodada {int(round_number)} já foi fechada. Para mudar o que já "
                "aconteceu, use a correção de resultado com motivo."
            )
        if situacao["round_status"] is not None:
            mesa = (
                f" e o jogador está na mesa {situacao['board_number']}"
                if situacao["board_number"] and not situacao["is_bye"]
                else ""
            )
            raise AppError(
                f"A rodada {int(round_number)} já foi gerada{mesa}. Bye só vale antes "
                "da geração; para a ausência nesta rodada, lance o W.O. na mesa."
            )
        return self.request_bye(tournament_id, player_id, int(round_number), "Z", reason=reason)

    @requires("tournament_write")
    def forfeit_absent_player(
        self, tournament_id: int, player_id: int, round_number: int, reason: str = ""
    ) -> dict[str, Any]:
        """W.O. contra quem faltou a uma rodada JÁ GERADA (RGS-22/RGS-23).

        É o que o bye não consegue mais fazer: a mesa existe. Só vale para mesa
        sem resultado — mudar um resultado lançado é correção, com outro fluxo.
        """
        situacao = self.player_round_situation(tournament_id, player_id, round_number)
        numero = int(round_number)
        if situacao["round_status"] is None:
            raise AppError(
                f"A rodada {numero} ainda não foi gerada: registre a ausência como "
                "bye Z (Faltar só à rodada)."
            )
        if situacao["round_status"] == "closed":
            raise AppError(
                f"A rodada {numero} já foi fechada: use a correção de resultado com motivo."
            )
        if not situacao["pairing_id"]:
            raise AppError(f"O jogador não tem mesa na rodada {numero}.")
        if situacao["is_bye"]:
            raise AppError(f"O jogador está de bye na rodada {numero}: não há W.O. a lançar.")
        if situacao["has_result"]:
            raise AppError(
                f"A mesa {situacao['board_number']} já tem resultado. Para mudá-lo, "
                "corrija o resultado pela mesa."
            )
        self.update_result(int(tournament_id), int(situacao["pairing_id"]), situacao["walkover_result"])
        self.db.create_audit_event(
            action="absence_walkover",
            tournament_id=int(tournament_id),
            entity_type="player",
            entity_id=int(player_id),
            reason=_participation_clean_reason(reason),
            after={
                "round_number": numero,
                "board_number": situacao["board_number"],
                "result": situacao["walkover_result"],
            },
        )
        return {"board_number": situacao["board_number"], "result": situacao["walkover_result"]}

    def late_entry_plan(
        self,
        tournament_id: int,
        per_round_points: float | None = None,
        *,
        join_open_round: bool = False,
    ) -> _LateEntryPlan:
        """Em que rodada entra quem se inscreve agora, e com quantos pontos (RGS-24)."""
        tournament = self.db.get_tournament(int(tournament_id))
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if per_round_points is None:
            settings = self.db.get_tournament_settings(int(tournament_id)) or {}
            per_round_points = float(settings.get("late_entry_points") or 0.0)
        ultima = self.db.get_latest_round(int(tournament_id)) or {}
        return _late_entry_plan(
            latest_round_number=int(ultima.get("number") or 0),
            rounds_count=int(tournament.get("rounds_count") or 0),
            per_round_points=float(per_round_points),
            join_open_round=join_open_round,
            latest_round_open=_is_open_round(ultima),
        )

    _LATE_ENTRY_FIELDS = (
        "name", "surname", "given_name", "title", "sex", "club", "category",
        "fide_id", "cbx_id", "lbx_id", "birth_date", "rating", "national_rating",
        "international_rating",
    )

    @requires("tournament_write")
    def register_late_entry(
        self,
        tournament_id: int,
        data: Mapping[str, Any],
        per_round_points: float | None = None,
        actor: str = "",
        *,
        join_open_round: bool = False,
    ) -> dict[str, Any]:
        """Inscreve um entrante tardio (RGS-24) — uma linha em `players`, só.

        As rodadas 1…N−1 dele são CÉLULAS DERIVADAS: o TRF as escreve como Z/H/F
        a partir dos ``starting_points`` (`reconcile_scores`). Nada é gravado em
        `pairings`, em rodada fechada ou em `requested_byes` — o limite de bye
        não é consumido e a `bye_policy` não muda.
        """
        nome = " ".join(str(data.get("name") or "").split())
        if not nome:
            raise AppError("Informe o nome do jogador.")
        plano = self.late_entry_plan(
            tournament_id, per_round_points, join_open_round=join_open_round
        )
        if plano.error:
            raise AppError(plano.error)
        campos = _late_entry_fields(data, self._LATE_ENTRY_FIELDS, nome)
        with self.db.transaction():
            player_id = int(
                self.db.create_player(
                    int(tournament_id),
                    **campos,
                    starting_points=plano.starting_points,
                    entry_round=plano.entry_round,
                )
            )
            self.db.create_audit_event(
                action="late_entry_registered",
                tournament_id=int(tournament_id),
                entity_type="player",
                entity_id=player_id,
                actor=actor,
                after={
                    "name": nome,
                    "entry_round": plano.entry_round,
                    "missed_rounds": plano.missed_rounds,
                    "per_round_points": plano.per_round_points,
                    "starting_points": plano.starting_points,
                },
            )
        return {
            "player_id": player_id,
            "entry_round": plano.entry_round,
            "starting_points": plano.starting_points,
        }

    @requires("tournament_write")
    @atomic
    def postpone_pairing(self, tournament_id: int, pairing_id: int, note: str = "") -> None:
        """Marca a mesa como adiada, com o combinado como nota (ARB-02)."""
        pairing = self.db.get_pairing(int(pairing_id))
        if not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
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

    @requires("tournament_write")
    @atomic
    def resume_pairing(self, tournament_id: int, pairing_id: int) -> None:
        """Desfaz o adiamento da mesa (ARB-02)."""
        pairing = self.db.get_pairing(int(pairing_id))
        if not pairing or int(pairing.get("tournament_id") or 0) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
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

    @requires("tournament_write")
    def acknowledge_arbitration_issue(self, tournament_id: int, issue_key: str, note: str = "") -> int:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        normalized_key = str(issue_key or "").strip()
        if not normalized_key:
            raise AppError("Selecione uma pendência.")

        issues = self.arbitration_issues(tournament_id, limit=1000)["issues"]
        issue = next((item for item in issues if str(item.get("issue_key") or "") == normalized_key), None)
        if not issue:
            raise AppError("Pendência não encontrada ou já tratada.")
        if issue.get("source") == "qr":
            raise AppError("Use Aprovar QR ou Rejeitar QR para pendência QR.")

        return self.db.create_audit_event(
            action="arbitration_issue_acknowledged",
            tournament_id=tournament_id,
            round_id=issue.get("round_id"),
            entity_type="arbitration_issue",
            entity_id=None,
            reason=note.strip() or "Pendência marcada como ciente.",
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

    @requires("tournament_write")
    def generate_next_round(
        self,
        tournament_id: int,
        *,
        reserve_engine: bool = False,
        forfeit_empty_teams: bool = False,
    ) -> dict[str, Any]:
        """Gera e grava a próxima rodada.

        ``reserve_engine=True`` e a resposta do árbitro a recusa do Gacrux
        (``GacruxRefusal``: pontuação que o TRF não diz, RGS-03, ou saída que
        não confere, RGS-19): a rodada sai pelo motor próprio e o fato fica na
        auditoria (``pairing_engine_fallback``).

        ``forfeit_empty_teams=True`` e a resposta do árbitro ao
        ``TeamWithoutPlayersError`` (EQ-02.4): a equipe sem ninguém presente e
        pareada e todos os tabuleiros dela saem por W.O.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            return self._generate_next_team_round(
                tournament_id, tournament, forfeit_empty_teams=forfeit_empty_teams
            )

        plan = self._individual_next_round_plan(
            tournament_id, tournament, persist=True, reserve_engine=reserve_engine
        )
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
        # RG2-25: rodada, retratos do motor, auditoria, marca do motor reserva e status
        # do torneio entram juntos. O backup fica antes, e o motor já rodou: a
        # transação (BEGIN IMMEDIATE) não segura a escrita durante o cálculo.
        with self.db.transaction():
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
            if plan.get("engine_fallback") is not None:
                self.db.create_audit_event(
                    action="pairing_engine_fallback",
                    tournament_id=tournament_id,
                    round_id=round_id,
                    entity_type="round",
                    entity_id=round_id,
                    reason=f"Motor reserva escolhido pelo árbitro: {plan['engine_fallback'].refusal}.",
                    metadata={"round_number": next_number, "details": plan["engine_fallback"].details},
                )
            if plan.get("engine") == "reserve":
                self._record_reserve_engine_round(tournament_id, round_id, next_number)
            generated = self._finalize_generated_round(tournament_id, tournament, next_number, round_id)
        logger.info("Rodada %s gerada para o torneio %s", next_number, tournament_id)
        # A conferência contra o holandês roda o pareamento de novo (segundos):
        # fica fora da transação e só registra o que achou (RGS-16).
        check = self._verify_generated_round(tournament_id, round_id, next_number, settings, plan)
        if check is not None:
            generated["pairing_check"] = check.as_dict()
        return generated

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
            raise AppError("A rodada foi gerada, mas não pode ser reaberta.")
        generated["id"] = round_id
        return generated

    # ------------------------------------------------------------------ #
    # Verificação da rodada (RGS-16) e motor reserva (RGS-18)
    # ------------------------------------------------------------------ #

    def _pairing_checker_applies(self, settings: dict[str, Any]) -> bool:
        """O verificador holandês (Gacrux) roda neste torneio?

        Só quando o motor de pareamento configurado e o Gacrux: e ele quem diz
        o que o holandês produziria. Com o motor reserva configurado a rodada já
        nasce marcada como não homologada (RGS-18), e rodar um subprocesso a
        cada geração não mudaria esse aviso.
        """
        return (
            str(settings.get("pairing_system") or "") == "gacrux_swiss"
            and str(settings.get("pairing_method") or "swiss") == "swiss"
        )

    def _check_round_against_dutch(
        self,
        tournament_id: int,
        round_number: int,
        acceleration: dict[str, Any] | None = None,
    ) -> PairingCheck:
        """`pairingchecker -c` sobre a rodada GRAVADA (nunca levanta)."""
        from src.services.pairing.gacrux_engine import GacruxEngine

        if acceleration is None:
            acceleration = self._round_acceleration(tournament_id, round_number)
        return GacruxEngine(self.db).check_round(
            tournament_id,
            round_number,
            accelerated_player_ids=acceleration.get("player_ids") or (),
            acceleration_bonus=float(acceleration.get("bonus") or 0.0),
        )

    def _round_acceleration(self, tournament_id: int, round_number: int) -> dict[str, Any]:
        """A aceleracao da rodada, refeita sobre quem esta pareado nela."""
        settings = self.db.get_tournament_settings(tournament_id) or {}
        round_data = self.db.get_round_by_number(tournament_id, round_number)
        pairings = self.db.get_pairings_for_round(int(round_data["id"])) if round_data else []
        paired = _paired_player_ids(pairings)
        to_pair = [
            player
            for player in self.db.list_players(tournament_id, active_only=False)
            if int(player["id"]) in paired
        ]
        acelerados, bonus, _motor = self._acceleration_plan(
            tournament_id, to_pair, settings, round_number, True, []
        )
        return {"player_ids": list(acelerados), "bonus": float(bonus)}

    def _verify_generated_round(
        self,
        tournament_id: int,
        round_id: int,
        round_number: int,
        settings: dict[str, Any],
        plan: dict[str, Any],
    ) -> PairingCheck | None:
        """Depois de toda geração, a rodada gravada contra o holandês (RGS-16).

        Rodada gerada pelo Gacrux que difere do que o próprio holandês produz e
        defeito: evento `pairing_check_divergence`, que vira pendência que
        BLOQUEIA o fechamento até o árbitro decidir (C.04.2: o pareamento
        publicado e o do sistema; desvio precisa de decisão registrada). Rodada
        do motor reserva (recusa do Gacrux, aceleração fora do registro 250)
        só registra: ela já carrega o aviso de não homologada (RGS-18).
        """
        engine = plan.get("engine")
        if engine is None or not self._pairing_checker_applies(settings):
            return None
        check = self._check_round_against_dutch(
            tournament_id, round_number, plan.get("acceleration") or {}
        )
        blocking = engine == "gacrux" and check.diverges
        self.db.create_audit_event(
            action="pairing_check",
            tournament_id=int(tournament_id),
            round_id=int(round_id),
            entity_type="round",
            entity_id=int(round_id),
            reason=check.summary(),
            after=check.as_dict(),
            metadata={"engine": engine, "blocking": blocking},
        )
        if blocking:
            logger.error("Torneio %s: %s", tournament_id, check.summary())
            self.db.create_audit_event(
                action="pairing_check_divergence",
                tournament_id=int(tournament_id),
                round_id=int(round_id),
                entity_type="round",
                entity_id=int(round_id),
                reason=check.summary(),
                after=check.as_dict(),
            )
        elif engine == "gacrux" and not check.checked:
            logger.warning("Torneio %s: %s", tournament_id, check.summary())
            self.db.create_audit_event(
                action="pairing_check_unverified",
                tournament_id=int(tournament_id),
                round_id=int(round_id),
                entity_type="round",
                entity_id=int(round_id),
                reason=check.summary(),
                after=check.as_dict(),
            )
        return check

    def _record_reserve_engine_round(
        self, tournament_id: int, round_id: int, round_number: int
    ) -> None:
        """Marca a rodada pareada pelo motor reserva (RGS-18).

        E o que sustenta o aviso PERSISTENTE da tela (`round_engine_notice`):
        ele vale para a rodada, e não some quando o árbitro marca uma pendência
        como ciente.
        """
        self.db.create_audit_event(
            action="pairing_reserve_engine",
            tournament_id=int(tournament_id),
            round_id=int(round_id),
            entity_type="round",
            entity_id=int(round_id),
            reason=_reserve_round_notice(round_number),
            after={"round_number": int(round_number)},
        )

    def round_engine_notice(self, tournament_id: int, round_id: int) -> str:
        """Aviso permanente da rodada pareada pelo motor reserva ("" se nao foi)."""
        for event in self.db.list_audit_events(
            tournament_id, action="pairing_reserve_engine", limit=1000
        ):
            if int(event.get("round_id") or 0) == int(round_id):
                return str(event.get("reason") or "")
        return ""

    def round_pairing_notices(self, tournament_id: int, round_id: int) -> list[str]:
        """Avisos permanentes da rodada para a tela de Rodadas (RGS-16/RGS-18).

        Motor reserva e divergência do verificador holandês valem para a
        RODADA: continuam na tela mesmo depois de a pendência ser marcada como
        ciente — o "ciente" libera o fechamento, não apaga o fato.
        """
        avisos = []
        reserva = self.round_engine_notice(tournament_id, round_id)
        if reserva:
            avisos.append(reserva)
        for event in self.db.list_audit_events(
            tournament_id, action="pairing_check_divergence", limit=1000
        ):
            if int(event.get("round_id") or 0) == int(round_id):
                avisos.append(str(event.get("reason") or ""))
                break
        return avisos

    def _individual_next_round_plan(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        *,
        persist: bool = False,
        reserve_engine: bool = False,
    ) -> dict[str, Any]:
        """Plano da próxima rodada. `persist` autoriza gravar o que o plano decide.

        A prévia chama com `persist=False` e a geração com `True`: o único plano
        que decide algo PERSISTENTE e o do rodízio, que sorteia os números de
        Berger na primeira rodada (PAR-01) — e uma prévia que grava o sorteio
        seria uma prévia que muda o torneio.
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
            raise AppError("O número máximo de rodadas do torneio já foi atingido.")

        # Avisos do que o pareamento decidiu e o árbitro precisa saber — o que
        # não coube no arquivo do motor FIDE, a aceleração que trocou de motor
        # (PAR-02). Vão para a prévia, para o log e para a auditoria.
        avisos: list[str] = []
        # A recusa do Gacrux quando o árbitro pediu o motor reserva.
        engine_fallback: GacruxRefusal | None = None
        # Quem pareou o Suíço individual (RGS-16/RGS-18): "gacrux" ou "reserve";
        # None nos formatos de calendário (rodízio, Scheveningen, eliminatória).
        pairing_engine: str | None = None
        acelerados: list[int] = []
        bonus = 0.0
        pairing_method = settings.get("pairing_method", "swiss")
        if pairing_method in ("round_robin", "knockout", "scheveningen"):
            # Byes solicitados são um conceito do Suíço: nestes formatos o
            # calendário e predeterminado (rotação todos-contra-todos / chave de
            # eliminação), então remover um jogador corromperia o esquema. Em vez
            # de gerar pareamentos enganosos, rejeitamos com mensagem clara.
            active_ids = {int(player["id"]) for player in players}
            if any(
                int(item["player_id"]) in active_ids
                for item in self.db.list_requested_byes_for_round(tournament_id, next_number)
            ):
                raise AppError(
                    "Byes solicitados são exclusivos do sistema Suíço. Remova o bye "
                    "solicitado desta rodada ou troque o método de pareamento para gerá-lá."
                )
            # Estes métodos não descontam byes solicitados: a paridade vale sobre
            # todos os jogadores ativos (comportamento histórico). No rodízio a
            # paridade e a do CALENDÁRIO, não a da chamada de hoje: quem desistiu
            # continua tendo mesa (ver _round_robin_round).
            if (
                settings.get("disable_bye")
                and pairing_method != "round_robin"
                and len(players) % 2 == 1
            ):
                raise AppError("O bye está desativado. Use número par de jogadores ativos.")
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
            # Bye de jogador inativo era descartado EM SILÊNCIO (ARB-04): o
            # jogador avisou que faltaria, o árbitro registrou, e na hora de
            # parear o pedido sumia. Agora sai aviso e fica na auditoria — quem
            # lê decide se reativa o jogador ou aceita a ausência. A geração
            # segue: barrar a rodada por um pedido que ficou para trás seria
            # trocar um silêncio ruim por uma parada pior.
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
                raise AppError("O bye está desativado. Use número par de jogadores ativos.")
            # Proibição de pareamento NÃO tira a rodada do Gacrux (RGS-15): ela
            # viaja no TRF como registro 260 (ver GacruxEngine.write_pairing_trf).
            use_gacrux = settings.get("pairing_system") == "gacrux_swiss"
            acelerados, bonus, use_gacrux = self._acceleration_plan(
                tournament_id, to_pair, settings, next_number, use_gacrux, avisos
            )
            pairings = None
            if use_gacrux:
                from src.services.pairing.gacrux_engine import (
                    RESERVE_ENGINE_LABEL,
                    GacruxEngine,
                    GacruxRefusal,
                )
                engine = GacruxEngine(self.db)
                try:
                    pairings = engine.pair_round(
                        tournament_id,
                        to_pair,
                        next_number,
                        accelerated_player_ids=acelerados,
                        acceleration_bonus=bonus,
                    )
                    avisos.extend(engine.warnings)
                except GacruxRefusal as recusa:
                    if not reserve_engine:
                        raise
                    avisos.append(
                        f"Rodada {next_number} pareada pelo {RESERVE_ENGINE_LABEL}, "
                        f"a pedido do árbitro: {recusa.refusal}."
                    )
                    # A auditoria e gravada por generate_next_round DEPOIS
                    # de a rodada existir; o plano só relata o fato.
                    engine_fallback = recusa
            pairing_engine = "gacrux" if pairings is not None else "reserve"
            if pairings is None and next_number == 1:
                # Mesma cor inicial da prévia, da geração e do 152 do Gacrux (RGS-14).
                pairings = _first_round_pairings(
                    to_pair,
                    {**settings, "initial_color": resolve_initial_color(self.db, tournament_id, settings)},
                )
            elif pairings is None:
                pairings = self._swiss_pairings(
                    tournament_id, to_pair, next_number, (acelerados, bonus)
                )
            pairings = _append_requested_bye_pairings(pairings, bye_by_player)
        return {
            "players": players,
            "settings": settings,
            "round_number": next_number,
            "pairings": pairings,
            "warnings": avisos,
            "engine_fallback": engine_fallback,
            "engine": pairing_engine,
            "acceleration": {"player_ids": list(acelerados), "bonus": float(bonus)},
        }

    def round_robin_numbers(self, tournament_id: int) -> dict[int, int]:
        """Números de rodízio do torneio: `{player_id: numero}` (PAR-01).

        Vazio enquanto o calendário não foi sorteado — o que acontece na geração
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
        """Mesas da rodada lidas do CALENDÁRIO do rodízio (PAR-01).

        O calendário e sorteado uma vez e guardado; daqui para a frente a rodada
        só é lida da tabela de Berger. Por isso desativar um jogador não mexe nos
        confrontos futuros dos outros: a mesa dele continua existindo e sai por
        W.O. — que é o que a FIDE manda no rodízio, onde não existe "tirar alguém
        da rotação" sem desmanchar o torneio inteiro.
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

        A escala era refeita a cada rodada com a lista de ativos: uma desistência
        deslocava todos os índices seguintes — os confrontos que faltavam viravam
        outros — e ainda desigualava os grupos, o que fazia a geração ser
        RECUSADA. Agora o grupo e o número moram no jogador, e quem sai mantém a
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

        Respeita o grupo que o árbitro tiver atribuído à mão; sem isso, parte o
        campo pela ordem inicial. O número dentro do grupo e o que faltava para a
        escala parar de andar quando alguém sai.
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
        """Números de rodízio, sorteando-os na primeira vez.

        A ordem do sorteio e a ORDEM INICIAL do torneio — a mesma que o árbitro já
        configurou e vê na lista. Um sorteio aleatório de verdade (a alternativa
        do regulamento) precisaria de uma tela para o árbitro conduzi-lo em
        publico; enquanto ela não existe, um número previsível e conferível e
        melhor do que um número que ninguém viu sair.
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
        tournament_id: int,
        to_pair: list[dict[str, Any]],
        settings: dict[str, Any],
        round_number: int,
        use_gacrux: bool,
        avisos: list[str],
    ) -> tuple[list[int], float, bool]:
        """Quem acelera nesta rodada, com quanto, e por qual motor (PAR-02).

        A aceleração só existia no motor próprio: com o Gacrux — que é o padrão —
        ela era ignorada em silêncio. Agora ela viaja no TRF (registro 250) e,
        quando o bônus configurado não cabe nesse registro, a rodada cai no motor
        próprio COM AVISO. O que não pode e o árbitro configurar aceleração e não
        receber nem o efeito nem a noticia de que ele não veio.
        """
        method = str(settings.get("acceleration_method") or "none")
        if _scheme_is_baku(method):
            acelerados, bonus = self._baku_acceleration(tournament_id, to_pair, settings, round_number)
        elif not _scheme_applies_bonus(method):
            return [], 0.0, use_gacrux
        else:
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
            # `first_round_pairings` divide o campo pela ordem inicial e não olha
            # pontuação — fictícia inclusive. Quem quer a rodada 1 acelerada de
            # fato usa o motor FIDE; aqui o árbitro ao menos sabe.
            avisos.append(
                "Aceleração configurada, mas o motor próprio pareia a rodada 1 pela "
                "ordem inicial, sem os pontos fictícios. Use o motor Suíço (Gacrux) "
                "para acelerar a primeira rodada."
            )
        return acelerados, bonus, use_gacrux

    def _baku_acceleration(
        self,
        tournament_id: int,
        to_pair: list[dict[str, Any]],
        settings: dict[str, Any],
        round_number: int,
    ) -> tuple[list[int], float]:
        """GA e VP de Baku nesta rodada, só entre quem é sendo pareado (RGS-30).

        O GA sai da lista de ANTES da R1 (FIDE C.04.7 1.2), não de quem e
        pareado agora: quem pediu bye continua contando, e o entrante tardio só
        entra no GA se ficou acima do ultimo dele (1.3). Inscrito até a R1 e o
        mesmo corte do retrato da R1 (`players_as_of_round`).
        """
        tournament = self.db.get_tournament(tournament_id) or {}
        todos = self.db.list_players(tournament_id, active_only=False)
        iniciais = _players_as_of_round(
            todos, [], self.db.get_pairings_for_tournament(tournament_id), 1
        )
        acelerados, bonus = _baku_accelerated_player_ids(
            self._seeding(todos, settings),
            [int(player["id"]) for player in iniciais],
            int(tournament.get("rounds_count") or 0),
            round_number,
        )
        pareados = {int(player["id"]) for player in to_pair}
        return [player_id for player_id in acelerados if player_id in pareados], bonus

    def _seeding(
        self,
        players: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> list[int]:
        """IDs na ordem de ranking inicial do torneio (1 = cabeça de chave).

        A ordem e a `seeding_key` (RGS-13): a mesma do TRF, logo do Gacrux, e
        a mesma que a aceleração usa para escolher a metade acelerada.
        """
        return [int(player["id"]) for player in _seeding_order(players, settings)]

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
        *,
        forfeit_empty_teams: bool = False,
    ) -> dict[str, Any]:
        # A guarda da C.04.1 (RG2-07a) só vale ao gravar: a prévia mostra a
        # repetição como alerta, que é o que o árbitro precisa ver antes.
        plan = self._team_next_round_plan(tournament_id, tournament, enforce_absolute=True)
        sem_ninguem = [aviso["team_name"] for aviso in plan["lineup_warnings"] if aviso["empty"]]
        if sem_ninguem and not forfeit_empty_teams:
            # EQ-02.4: antes de qualquer gravação — cancelar não deixa rastro.
            raise _TeamWithoutPlayersError(sem_ninguem)
        settings = plan["settings"]
        self._warn_pairing_notes(tournament_id, int(plan["round_number"]), plan.get("warnings") or [])
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
            extra={
                "boards_count": boards_count,
                "seed_ratings": seed_ratings,
                "pairing_numbers": plan["pairing_numbers"],
                "acceleration": plan["acceleration"],
            },
        )
        self._save_pairing_snapshot(
            tournament_id, next_number, "input", input_snapshot,
            pairing_system=pairing_system,
            engine_version=self.TEAM_PAIRING_ENGINE_VERSION,
        )
        self.db.backup_before("generate_team_round", tournament_id=tournament_id)
        with self.db.transaction():
            # EQ-01: o TPN nasce junto com a rodada que o usou (só grava o novo).
            self.db.save_team_pairing_numbers(plan["pairing_numbers"], seed_ratings)
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

    def _team_next_round_plan(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        *,
        enforce_absolute: bool = False,
    ) -> dict[str, Any]:
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
            raise AppError("O número máximo de rodadas do torneio já foi atingido.")

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
            raise AppError("O bye está desativado. Use número par de equipes ativas.")

        team_method = str(settings.get("team_pairing_method") or "swiss")
        avisos: list[str] = []
        rosters, seed_ratings = self._team_starter_rosters(teams, boards_count)
        # EQ-01: a ordem e o TPN gravado (o da R1), não a semente de hoje. Quem
        # ainda não tem número recebe o seguinte; a geração grava (a prévia não).
        numbered = [
            team
            for team in self.db.list_teams(tournament_id, active_only=False)
            if team.get("pairing_number") or int(team["id"]) in active_team_ids
        ]
        if team_method == "round_robin" and next_number > 1:
            # EQ-06: o calendário saiu dos TPN da R1. Equipe sem TPN entrou
            # depois: fica fora (sem número), como o entrante tardio do rodízio
            # individual — incluí-la mudaria os confrontos de todo mundo.
            fora = [team for team in numbered if not team.get("pairing_number")]
            if fora:
                numbered = [team for team in numbered if team.get("pairing_number")]
                avisos.append(
                    _fixed_calendar_late_entry_warning(
                        [str(team["name"]) for team in fora],
                        formato="todos-contra-todos por equipes",
                    )
                )
        pairing_numbers = _assign_team_pairing_numbers(numbered, seed_ratings)
        strengths = _team_pairing_strengths(pairing_numbers)
        field = to_pair
        acelerados, vp = self._team_acceleration(
            tournament_id, tournament, settings, pairing_numbers, to_pair, next_number, avisos
        )

        # O método de pareamento por equipes era lido pela exportação e pelo
        # motor de desempate, mas NÃO pela geração de rodada — que era sempre
        # Suíço (PAR-04). Com a constante duplicada consertada, `round_robin`
        # voltou a ser selecionável, e agora ele de fato pareia.
        if team_method == "round_robin":
            if bye_by_team:
                # O calendário do todos-contra-todos é fixo: tirar uma equipe da
                # rotação desloca todo mundo e faz pares se repetirem. Num
                # torneio assim, quem não comparece perde por W.O. — não "folga".
                raise AppError(
                    "Bye solicitado não se aplica a todos contra todos por equipes: "
                    "o calendário é fixo. Registre W.O. no confronto da rodada."
                )
            # O calendário e o campo que recebeu TPN, inclusive quem foi
            # desativado depois: ele perde por W.O. (escalação vazia) e os
            # confrontos das outras não mudam (EQ-01).
            field = numbered
            for team in field:
                rosters.setdefault(int(team["id"]), dict.fromkeys(range(1, boards_count + 1)))
            matches = _round_robin_team_matches(
                field, rosters, strengths, boards_count, settings, next_number
            )
        elif next_number == 1 and acelerados:
            matches = _baku_first_round_team_matches(
                to_pair, rosters, strengths, boards_count, settings, acelerados
            )
        elif next_number == 1:
            matches = _first_round_team_matches(to_pair, rosters, strengths, boards_count, settings)
        else:
            matches = self._swiss_team_matches(
                tournament_id, to_pair, rosters, strengths, boards_count, settings, next_number,
                acceleration=(acelerados, vp),
                enforce_absolute=enforce_absolute,
            )
        matches = self._append_requested_team_byes(matches, bye_by_team, settings, boards_count)

        return {
            "settings": settings,
            "teams": teams,
            "boards_count": boards_count,
            "seed_ratings": seed_ratings,
            "pairing_numbers": pairing_numbers,
            "round_number": next_number,
            "matches": matches,
            "lineup_warnings": _team_lineup_warnings(field, rosters),
            "warnings": avisos,
            "acceleration": {"team_ids": list(acelerados), "bonus": float(vp)},
        }

    def _team_acceleration(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        pairing_numbers: dict[int, int],
        to_pair: list[dict[str, Any]],
        round_number: int,
        avisos: list[str],
    ) -> tuple[list[int], float]:
        """Baku no Suíço por equipes (EQ-07): quem recebe VP nesta rodada, e quanto.

        O GA sai do TPN gravado (EQ-01) e das equipes inscritas até a R1 — o
        mesmo corte do retrato da R1 (`teams_as_of_round`). O VP vale só no
        score de pareamento (`_swiss_team_matches`); a classificação não o vê.
        Outra aceleração, ou Baku no todos-contra-todos, não se aplica: aviso.
        """
        method = str(settings.get("acceleration_method") or "none")
        team_method = str(settings.get("team_pairing_method") or "swiss")
        if not _scheme_is_baku(method):
            if _scheme_applies_bonus(method):
                avisos.append(_team_acceleration_not_applied_warning(
                    _ACCELERATION_METHODS.get(method.partition(":")[0], method)
                ))
            return [], 0.0
        if team_method == "round_robin":
            avisos.append(_team_acceleration_not_applied_warning(method, round_robin=True))
            return [], 0.0
        iniciais = _teams_as_of_round(
            self.db.list_teams(tournament_id, active_only=False),
            self.db.list_team_matches_for_tournament(tournament_id),
            1,
        )
        acelerados, vp = _baku_team_accelerated_ids(
            sorted(pairing_numbers, key=lambda team_id: pairing_numbers[team_id]),
            [int(team["id"]) for team in iniciais],
            int(tournament.get("rounds_count") or 0),
            round_number,
            primary_score=str(settings.get("team_standing_primary") or "match_points"),
            win_points=setting_number(settings, "team_match_win_points", 2.0),
            draw_points=setting_number(settings, "team_match_draw_points", 1.0),
            loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
        )
        pareadas = {int(team["id"]) for team in to_pair}
        return [team_id for team_id in acelerados if team_id in pareadas], vp

    @staticmethod
    def _append_requested_team_byes(
        matches: list[dict[str, Any]],
        bye_by_team: dict[int, str],
        settings: dict[str, Any],
        boards_count: int,
    ) -> list[dict[str, Any]]:
        """Anexa confrontos de bye solicitado (F/H/Z) ao final da rodada por equipes.

        O tipo vai no `result` do confronto; pontuação e 240 derivam dele,
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
    ) -> tuple[dict[int, dict[int, int | None]], dict[int, int]]:
        """Escalacao proposta (EQ-02) e semente de cada equipe."""
        rosters: dict[int, dict[int, int | None]] = {}
        seed_ratings: dict[int, int] = {}
        for team in teams:
            team_id = int(team["id"])
            assignments = self.db.list_team_players(team_id, active_only=True)
            rosters[team_id] = _team_lineup(assignments, boards_count)
            seed_ratings[team_id] = _team_seed(assignments, boards_count)
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
        *,
        acceleration: tuple[list[int], float] = ([], 0.0),
        enforce_absolute: bool = False,
    ) -> list[dict[str, Any]]:
        standings = {int(item["team_id"]): item for item in self._team_standings(tournament_id)}
        # EQ-07: o VP de Baku soma no score de pareamento (C.04.7 1.5) — grupos,
        # ordem e bye. A classificação (`_team_standings`) fica intacta.
        standings = _standings_with_virtual_points(
            standings, *acceleration, score_key="match_points"
        )
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
        matches = _swiss_team_matches(
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
            float_histories=self._team_float_histories(tournament_id),
        )
        if enforce_absolute:
            self._refuse_illegal_team_round(
                tournament_id, round_number, matches, played_pairs, bye_team_ids, teams
            )
        return matches

    def _refuse_illegal_team_round(
        self,
        tournament_id: int,
        round_number: int,
        matches: list[dict[str, Any]],
        played_pairs: set[frozenset[int]],
        bye_team_ids: set[int],
        teams: list[dict[str, Any]],
    ) -> None:
        """Guarda do RG2-07a: rodada que fere a C.04.1 não é gravada.

        O motor de equipes repetia confronto quando havia pareamento sem
        repetição (o redesenho é o RG2-07b). Até lá, a rodada pronta é
        conferida; se repete confronto ou dá um segundo PAB, o caso vai à
        auditoria e a geração para com o motivo — melhor nenhuma rodada do que
        uma ilegal gravada em silêncio.
        """
        names = {int(team["id"]): str(team.get("name") or "") for team in teams}
        problemas = _team_round_violations(matches, played_pairs, bye_team_ids, names)
        if not problemas:
            return
        try:
            self.db.create_audit_event(
                action="team_pairing_refused",
                tournament_id=int(tournament_id),
                entity_type="round",
                reason="; ".join(problemas),
                metadata={"round_number": int(round_number), "problems": problemas},
            )
        except Exception:  # pragma: no cover - a trilha não esconde a recusa
            logger.exception("Falha ao registrar a recusa do pareamento de equipes")
        raise AppError(
            f"O pareamento automático da rodada {round_number} feriria a regra da FIDE "
            "(C.04.1: duas equipes não se enfrentam duas vezes, e nenhuma recebe dois byes):\n"
            + "\n".join(f"- {item}" for item in problemas)
            + "\n\nA rodada não foi gerada, e o caso ficou registrado na auditoria. "
            "O motor de equipes ainda não encontra sozinho a alternativa sem repetição; "
            "confira os confrontos anteriores e as proibições de pareamento antes de tentar de novo."
        )

    def _team_float_histories(self, tournament_id: int) -> dict[int, list[str]]:
        """Flutuacoes por equipe — o que faltava para penalizar float repetido."""
        return _team_float_histories(*self._team_closed_history(tournament_id))

    @requires("tournament_write")
    def update_result(
        self,
        tournament_id: int,
        pairing_id: int,
        result: str,
        reason: str = "",
        *,
        unlock_minutes: int | None = None,
        correction_extra: Mapping[str, Any] | None = None,
        audit_extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Lança ou corrige o resultado de uma mesa.

        `reason` e OBRIGATÓRIO quando a rodada é fechada (ARB-01): antes o
        motivo era uma constante no código, e a trilha registrava que houve
        correção sem nunca dizer por que — inútil na hora de sustentar a decisão
        numa apelação.

        `unlock_minutes` (RGS-20) desbloqueia a rodada fechada com o MESMO
        motivo, na mesma transação da correção — quem chama e o
        `correct_result`. `correction_extra` entra no `after` da correção
        (ex.: `reverts_event_id` de uma reversão). `audit_extra` entra no
        `after` de qualquer evento (ex.: `undo` do Desfazer, RGS-21).
        """
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            self._update_team_board_result(
                tournament_id,
                pairing_id,
                result,
                reason,
                unlock_minutes=unlock_minutes,
                correction_extra=correction_extra,
                audit_extra=audit_extra,
            )
            return

        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
        allowed = set(RESULTS)
        if pairing.get("is_bye"):
            allowed.update({"BYE", "F", "H", "Z"})
        if result not in allowed:
            raise AppError("Resultado inválido.")
        before = {
            "pairing_id": int(pairing_id),
            "result": pairing.get("result", ""),
            "round_status": pairing.get("round_status", ""),
        }
        is_correction = pairing["round_status"] == "closed"
        round_id = int(pairing["round_id"])
        if is_correction:
            reason = self._authorize_correction(
                tournament_id, round_id, reason, will_unlock=unlock_minutes is not None
            )
        action = "result_corrected" if is_correction else "result_updated"
        after = {"pairing_id": int(pairing_id), "result": result, "round_status": pairing.get("round_status", "")}
        if is_correction and correction_extra:
            after.update(correction_extra)
        if audit_extra:
            after.update(audit_extra)

        def gravar() -> None:
            if is_correction and unlock_minutes is not None:
                self._create_correction_unlock(tournament_id, round_id, reason, unlock_minutes)
            self.db.update_pairing_result(pairing_id, result)
            self.db.create_audit_event(
                action=action,
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type="pairing",
                entity_id=int(pairing_id),
                reason=reason if is_correction else "",
                before=before,
                after=after,
            )
            if is_correction:
                self._after_correction(tournament_id, round_id, reason)

        self._commit_result(tournament_id, round_id, is_correction, gravar)
        logger.info("Resultado da mesa %s atualizado para %s", pairing_id, result or "pendente")

    def undo_result(
        self,
        tournament_id: int,
        pairing_id: int,
        *,
        applied: str,
        previous: str,
    ) -> None:
        """Desfaz o lançamento recém-feito na tela de Rodadas (RGS-21).

        Reaplica ``previous`` pelo caminho de sempre (`update_result`), então a
        auditoria ganha o SEGUNDO evento, marcado com ``undo``. Recusa quando a
        mesa não tem mais ``applied`` (outro lançamento, QR aprovado): desfazer
        por cima apagaria um resultado que o árbitro não é vendo. Rodada
        fechada tem caminho próprio, com motivo: "Corrigir resultado...".
        """
        tournament = self.db.get_tournament(tournament_id)
        team = bool(tournament and tournament.get("competition_type") == "team")
        linha = self.db.get_team_board(pairing_id) if team else self.db.get_pairing(pairing_id)
        if not linha or int(linha["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
        mesa = linha.get("board_number", "")
        if linha.get("round_status") == "closed":
            raise AppError(
                f"A rodada da mesa {mesa} já foi fechada; nada foi desfeito.",
                suggestion="Use Corrigir resultado… (Ctrl+E) na mesa, com o motivo.",
            )
        atual = str(linha.get("result") or "")
        if atual != str(applied or ""):
            raise AppError(
                f"O resultado da mesa {mesa} mudou depois do lançamento "
                f"(agora: {atual or 'pendente'}); nada foi desfeito."
            )
        self.update_result(
            tournament_id,
            pairing_id,
            previous,
            audit_extra={"undo": True, "undone_result": str(applied or "")},
        )

    def round_progress(self, tournament_id: int, round_id: int) -> dict[str, Any]:
        """Mesas lançadas x total da rodada — o contador e o botão primário (RGS-21/25).

        Mesma conta do painel do árbitro: ``total_results`` são partidas (sem
        bye); ``pending_results`` inclui o bye sem resultado, que impede fechar.
        """
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            return self._team_round_dashboard_metrics(int(round_id))
        return self._individual_round_dashboard_metrics(int(round_id))

    @requires("tournament_write")
    def close_round(self, tournament_id: int, round_id: int) -> None:
        """Fecha a rodada — individual ou por equipes, pelo mesmo caminho (RGS-11, RG2-08).

        Guarda "já fechada", conferência, backup e uma transação só com status,
        retrato, auditoria e status do torneio. O por equipes só injeta o seu
        passo: conferir os tabuleiros e gravar o resumo de cada confronto.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        if str(round_data.get("status") or "") == "closed":
            # RGS-11: o segundo clique não gera outro backup, outro retrato nem
            # outro evento de fechamento. Reabrir/corrigir tem caminho próprio.
            logger.info("Rodada %s ja estava fechada; nada a fazer", round_id)
            return

        team = tournament.get("competition_type") == "team"
        if team:
            summaries = self._team_close_summaries(tournament_id, round_id)
        else:
            self._check_individual_round_complete(round_id)
            summaries = []

        blocking_issues = self._blocking_arbitration_issues_for_round(tournament_id, round_id)
        if blocking_issues:
            raise AppError(_blocking_issues_message(blocking_issues))

        reason = "close_team_round" if team else "close_round"
        backup_path = self.db.backup_before(reason, tournament_id=tournament_id, round_id=round_id)
        logger.info("Backup criado antes de fechar rodada %s: %s", round_id, backup_path)

        round_number = int(round_data["number"])
        # RGS-11: status, retrato, componentes, auditoria e status do torneio
        # entram juntos. O status vem primeiro DENTRO da transação porque a
        # classificação só conta rodada fechada; quem é fora só vê a rodada
        # fechada quando o retrato já existe.
        with self.db.transaction():
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
            if team:
                standings = self._team_standings(tournament_id)
            else:
                # RGS-10: o mesmo corte da reconciliação, para que o retrato do
                # fechamento e o reconciliado digam a mesma coisa sobre a rodada N
                # (ajuste lançado para rodada futura, inscrito durante a rodada).
                standings = self._standings(tournament_id, up_to_round=round_number)
            self.db.create_standings_snapshot(
                tournament_id=tournament_id,
                round_id=round_id,
                round_number=round_number,
                standings=standings,
            )
            if not team:
                self._persist_tiebreak_components(
                    tournament_id=tournament_id,
                    round_id=round_id,
                    round_number=round_number,
                    standings=standings,
                )
            self.db.create_audit_event(
                action="team_round_closed" if team else "round_closed",
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type="round",
                entity_id=round_id,
                before={"status": round_data.get("status", "")},
                after={"status": "closed", "standings_count": len(standings)},
            )

            latest = self.db.get_latest_round(tournament_id)
            if latest and int(latest["number"]) >= int(tournament["rounds_count"]):
                self.db.update_tournament_status(tournament_id, "finished")
            else:
                self.db.update_tournament_status(tournament_id, "running")
        logger.info("Rodada %s fechada no torneio %s", round_id, tournament_id)

    def _check_individual_round_complete(self, round_id: int) -> None:
        pairings = self.db.get_pairings_for_round(round_id)
        pending = [
            pairing
            for pairing in pairings
            if not pairing["result"] or pairing["result"] not in FINAL_RESULTS
        ]
        if pending:
            # Mesa adiada primeiro, com recado próprio (ARB-02): mandar o árbitro
            # "preencher todos os resultados" quando ele SABE que aquela mesa esta
            # em aberto e o manda procurar o que ele mesmo combinou.
            adiadas = self.db.list_postponed_pairings(round_id)
            if adiadas:
                raise AppError(_postponed_blocking_message(adiadas))
            raise AppError("Preencha todos os resultados antes de fechar a rodada.")

    def _update_team_board_result(
        self,
        tournament_id: int,
        team_board_id: int,
        result: str,
        reason: str = "",
        *,
        unlock_minutes: int | None = None,
        correction_extra: Mapping[str, Any] | None = None,
        audit_extra: Mapping[str, Any] | None = None,
    ) -> None:
        board = self.db.get_team_board(team_board_id)
        if not board or int(board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro não encontrado para o torneio selecionado.")
        if result not in RESULTS:
            raise AppError("Resultado inválido.")
        before = {
            "team_board_id": int(team_board_id),
            "result": board.get("result", ""),
            "round_status": board.get("round_status", ""),
        }
        is_correction = board["round_status"] == "closed"
        round_id = int(board["round_id"])
        if is_correction:
            reason = self._authorize_correction(
                tournament_id, round_id, reason, will_unlock=unlock_minutes is not None
            )
        action = "team_result_corrected" if is_correction else "team_result_updated"
        after = {"team_board_id": int(team_board_id), "result": result, "round_status": board.get("round_status", "")}
        if is_correction and correction_extra:
            after.update(correction_extra)
        if audit_extra:
            after.update(audit_extra)

        def gravar() -> None:
            if is_correction and unlock_minutes is not None:
                self._create_correction_unlock(tournament_id, round_id, reason, unlock_minutes)
            self.db.update_team_board_result(team_board_id, result)
            self.db.create_audit_event(
                action=action,
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type="team_board",
                entity_id=int(team_board_id),
                reason=reason if is_correction else "",
                before=before,
                after=after,
            )
            if is_correction:
                self._after_correction(tournament_id, round_id, reason)

        self._commit_result(tournament_id, round_id, is_correction, gravar)
        logger.info("Resultado do tabuleiro de equipe %s atualizado para %s", team_board_id, result or "pendente")

    # ------------------------------------------------------------------ #
    # Correção em rodada fechada: motivo, desbloqueio, cascata, retratos
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
        """Abre a rodada fechada para correção, com justificativa e prazo.

        Substitui o hábito de ligar `allow_dangerous_changes` e esquecer: aqui a
        permissão e de UMA rodada e morre sozinha. Devolve o retrato para a tela.
        """
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        erro = _unlock_reason_error(reason)
        if erro:
            raise AppError(erro)
        return self._create_correction_unlock(tournament_id, round_id, _clean_reason(reason), minutes)

    def _create_correction_unlock(
        self, tournament_id: int, round_id: int, cleaned: str, minutes: int
    ) -> dict[str, Any]:
        """Grava o desbloqueio e o evento dele. O motivo ja chega validado."""
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

    @requires("tournament_write")
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
                reason="Desbloqueio de correção revogado pelo árbitro.",
                after={"revoked": revogados},
            )
        return revogados

    def _authorize_correction(
        self, tournament_id: int, round_id: int, reason: str, *, will_unlock: bool = False
    ) -> str:
        """Motivo válido + permissão vigente, ou `AppError`. Devolve o motivo limpo.

        A ordem importa: o motivo e checado ANTES da permissão. Quem chegou sem
        motivo precisa saber disso mesmo que a rodada esteja desbloqueada, senão
        desbloqueia, tenta não nomear a razão e leva um recado sobre outra coisa.

        `will_unlock` (RGS-20): o mesmo motivo vai desbloquear a rodada na mesma
        gravação — vale a regra mais estrita das duas, e a permissão e a que
        é sendo criada.
        """
        erro = _shared_reason_error(reason) if will_unlock else _correction_reason_error(reason)
        if erro:
            raise AppError(erro)
        if will_unlock:
            return _clean_reason(reason)
        estado = self.correction_unlock_state(tournament_id, round_id)
        if not estado.allowed:
            # RGS-20: a recusa não manda mais ligar "mudancas perigosas" — era a
            # rota do incidente. Ela aponta o caminho da mesa, onde o mesmo
            # motivo desbloqueia só esta rodada e registra a correção.
            rodada = self.db.get_round(round_id) or {}
            numero = rodada.get("number") or "?"
            raise AppError(
                f"A rodada {numero} está fechada. Desbloqueie a rodada para esta "
                "correção (com motivo e prazo).",
                suggestion=(
                    "Use “Corrigir resultado…” na mesa (clique direito ou Ctrl+E, "
                    "em Rodadas ou no Painel): o mesmo motivo desbloqueia a rodada "
                    f"por {DEFAULT_UNLOCK_MINUTES} min e registra a correção."
                ),
            )
        return _clean_reason(reason)

    def _commit_result(
        self,
        tournament_id: int,
        round_id: int,
        is_correction: bool,
        gravar: Callable[[], None],
    ) -> None:
        """Grava o resultado; na correção, com backup antes e tudo junto (RGS-10).

        A correção era resultado -> auditoria -> cascata -> retratos, cada passo
        numa conexão própria e sem backup: uma falha no meio deixava o placar
        novo com a classificação velha, e o recalculo dos retratos (Gacrux, uma
        vez por rodada) travava a tela. Agora resultado, auditoria, cascata e a
        MARCA dos retratos entram numa transação; o recalculo fica para o
        trabalhador (`reconcile_pending_snapshots`), fora da thread da tela.

        O lançamento em rodada aberta segue como era: o caminho comum não fica
        mais caro por causa da correção.
        """
        if not is_correction:
            gravar()
            return
        backup_path = self.db.backup_before(
            "result_correction", tournament_id=tournament_id, round_id=round_id
        )
        logger.info("Backup criado antes de corrigir a rodada %s: %s", round_id, backup_path)
        with self.db.transaction():
            gravar()
        self._notify_snapshots_pending(tournament_id)

    def _notify_snapshots_pending(self, tournament_id: int) -> None:
        """Avisa o trabalhador. Falha do aviso nao desfaz a correcao ja gravada."""
        ouvinte = self.on_snapshots_pending
        if ouvinte is None:
            return
        try:
            ouvinte(int(tournament_id))
        except Exception:
            logger.exception(
                "Falha ao avisar a reconciliacao dos retratos do torneio %s; "
                "a pendencia fica no banco e e retomada na proxima abertura",
                tournament_id,
            )

    def _after_correction(
        self,
        tournament_id: int,
        round_id: int,
        reason: str,
    ) -> None:
        """O que a correção contamina: pareamento posterior e retratos publicados.

        Só registra — cascata na trilha, retratos marcados. Nada aqui calcula
        classificação (RGS-10): roda dentro da transação da correção.
        """
        round_data = self.db.get_round(round_id)
        corrected_number = int((round_data or {}).get("number") or 0)
        rounds = self.db.list_rounds(tournament_id)
        self._register_correction_cascade(tournament_id, round_id, corrected_number, rounds, reason)
        self.db.mark_standings_snapshots_pending(
            tournament_id,
            corrected_number,
            f"Correção na rodada {corrected_number}: {reason}",
        )

    def _register_correction_cascade(
        self,
        tournament_id: int,
        round_id: int,
        corrected_number: int,
        rounds: list[dict[str, Any]],
        reason: str = "",
    ) -> None:
        """Evento de cascata quando já existe rodada posterior pareada.

        Sem isto, corrigir a rodada 3 com a rodada 4 já pareada não dizia nada: o
        pareamento da 4 nasceu do placar antigo, e quem tinha de decidir se
        repareia nunca era avisado.

        O `reason` e o motivo do árbitro, o mesmo da correção e do desbloqueio
        (RGS-20): a trilha de uma correção conta UMA historia. O recado do que
        fazer (reparear, conferir desempates) vai no `after`.
        """
        afetadas = _cascade_rounds(rounds, corrected_number)
        if not afetadas:
            return
        recado = _cascade_message(corrected_number, afetadas)
        self.db.create_audit_event(
            action="result_correction_cascade",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            reason=_clean_reason(reason) or recado,
            after={"corrected_round": corrected_number, "affected_rounds": afetadas, "message": recado},
        )
        logger.warning(
            "Correcao na rodada %s do torneio %s afeta rodadas ja pareadas: %s",
            corrected_number,
            tournament_id,
            afetadas,
        )

    # ------------------------------------------------------------------ #
    # "Corrigir resultado…" na mesa (RGS-20): um diálogo, um motivo
    # ------------------------------------------------------------------ #

    def _result_target(self, tournament_id: int, target_id: int) -> dict[str, Any]:
        """Mesa (individual) ou tabuleiro (equipes) com rodada e resultado atual."""
        tournament = self.db.get_tournament(tournament_id) or {}
        if tournament.get("competition_type") == "team":
            alvo = self.db.get_team_board(target_id)
            if not alvo or int(alvo["tournament_id"]) != int(tournament_id):
                raise AppError("Tabuleiro não encontrado para o torneio selecionado.")
            return {**alvo, "entity_type": "team_board", "audit_action": "team_result_corrected"}
        alvo = self.db.get_pairing(target_id)
        if not alvo or int(alvo["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
        return {**alvo, "entity_type": "pairing", "audit_action": "result_corrected"}

    def correct_result(
        self,
        tournament_id: int,
        target_id: int,
        result: str,
        reason: str,
        *,
        minutes: int = DEFAULT_UNLOCK_MINUTES,
        reverts_event_id: int | None = None,
    ) -> dict[str, Any]:
        """Corrige o resultado da mesa com UM motivo (RGS-20).

        Rodada fechada sem permissão vigente: o mesmo motivo desbloqueia a
        rodada (por `minutes`) e registra a correção, na mesma gravação — antes
        eram dois diálogos e dois motivos, ou a rota pelas Configurações
        ("mudancas perigosas"). O motivo passa pela regra mais estrita das duas.
        Rodada aberta: lança como o lançamento comum, sem desbloqueio.

        Devolve o que a tela precisa para o passo seguinte: se desbloqueou e a
        cascata (rodada seguinte já pareada).
        """
        alvo = self._result_target(tournament_id, target_id)
        if str(alvo.get("result") or "") == str(result or ""):
            raise AppError(
                "A mesa já tem este resultado.",
                suggestion="Escolha o novo resultado nos botões do diálogo.",
            )
        round_id = int(alvo["round_id"])
        fechada = str(alvo.get("round_status") or "") == "closed"
        desbloquear = False
        if fechada:
            erro = _shared_reason_error(reason)
            if erro:
                raise AppError(erro)
            desbloquear = not self.correction_unlock_state(tournament_id, round_id).allowed
        extra = {"reverts_event_id": int(reverts_event_id)} if reverts_event_id else None
        self.update_result(
            tournament_id,
            target_id,
            result,
            reason,
            unlock_minutes=minutes if desbloquear else None,
            correction_extra=extra,
        )
        rodada = self.db.get_round(round_id) or {}
        return {
            "closed": fechada,
            "unlocked": desbloquear,
            "round_id": round_id,
            "round_number": int(rodada.get("number") or 0),
            "cascade": self.correction_cascade(tournament_id, round_id) if fechada else None,
        }

    def correction_cascade(self, tournament_id: int, round_id: int) -> dict[str, Any] | None:
        """A rodada seguinte, se já foi pareada sobre o resultado desta (RGS-20).

        `repairable` só quando ela é gerada e aberta; `results` diz quantos
        resultados reparear apagaria — com resultado lançado, reparear passa
        pela exclusão com motivo (RGS-34).
        """
        rodada = self.db.get_round(round_id)
        if not rodada:
            return None
        numero = int(rodada.get("number") or 0)
        seguinte = next(
            (
                item
                for item in self.db.list_rounds(tournament_id)
                if int(item.get("number") or 0) == numero + 1
            ),
            None,
        )
        if not seguinte or str(seguinte.get("status") or "") not in ("generated", "closed"):
            return None
        aberta = str(seguinte.get("status") or "") == "generated"
        resultados = len(self._round_results_to_delete(int(seguinte["id"]))) if aberta else 0
        return {
            "round_id": int(seguinte["id"]),
            "number": numero + 1,
            "status": str(seguinte.get("status") or ""),
            "results": resultados,
            "repairable": aberta,
            "message": _deleted_results_message(resultados) if resultados else "",
        }

    def pairing_correction_history(self, tournament_id: int, target_id: int) -> list[dict[str, Any]]:
        """Correcoes desta mesa, da mais recente para a mais antiga (RGS-20)."""
        alvo = self._result_target(tournament_id, target_id)
        historico: list[dict[str, Any]] = []
        for evento in self.db.list_audit_events(
            tournament_id, action=alvo["audit_action"], entity_type=alvo["entity_type"], limit=5000
        ):
            if int(evento.get("entity_id") or 0) != int(target_id):
                continue
            antes = _json_or_empty(evento.get("before_json"))
            depois = _json_or_empty(evento.get("after_json"))
            historico.append(
                {
                    "event_id": int(evento["id"]),
                    "created_at": str(evento.get("created_at") or ""),
                    "actor": str(evento.get("actor") or ""),
                    "reason": str(evento.get("reason") or ""),
                    "before": str(antes.get("result") or ""),
                    "after": str(depois.get("result") or ""),
                    "reverts_event_id": depois.get("reverts_event_id"),
                }
            )
        return historico

    def revert_correction(
        self, tournament_id: int, event_id: int, reason: str, *, minutes: int = DEFAULT_UNLOCK_MINUTES
    ) -> dict[str, Any]:
        """"Reverter esta correção…": reaplica o resultado anterior pelo mesmo fluxo.

        E uma correção como outra qualquer — motivo, desbloqueio se preciso,
        auditoria, cascata, retratos — com `reverts_event_id` apontando a que
        ela desfaz. Só a última correção da mesa: desfazer uma do meio
        reescreveria a historia por baixo das que vieram depois.
        """
        evento = next(
            (
                item
                for acao in ("result_corrected", "team_result_corrected")
                for item in self.db.list_audit_events(tournament_id, action=acao, limit=5000)
                if int(item["id"]) == int(event_id)
            ),
            None,
        )
        if evento is None:
            raise AppError("Correção não encontrada neste torneio.")
        alvo_id = int(evento["entity_id"])
        historico = self.pairing_correction_history(tournament_id, alvo_id)
        if not historico or historico[0]["event_id"] != int(event_id):
            raise AppError(
                "Só a última correção desta mesa pode ser revertida.",
                suggestion="Para voltar a um resultado mais antigo, use “Corrigir resultado…” com o motivo.",
            )
        return self.correct_result(
            tournament_id,
            alvo_id,
            historico[0]["before"],
            reason,
            minutes=minutes,
            reverts_event_id=int(event_id),
        )

    # ------------------------------------------------------------------ #
    # Reconciliação dos retratos (RGS-10): o trabalho do trabalhador
    # ------------------------------------------------------------------ #

    def reconcile_pending_snapshots(self, tournament_id: int | None = None) -> int:
        """Regrava os retratos marcados por uma correção. Devolve quantos gravou.

        Idempotente e retomavel: a pendência mora no banco
        (`standings_snapshots.reconcile_pending`), cada retrato e gravado na
        sua própria transação e só ele baixa a própria marca. Uma falha no
        meio deixa os já gravados gravados e os demais pendentes — o app, ao
        abrir, termina. Sem pendência, não faz nada.

        A classificação e calculada FORA da transação (o Gacrux pode levar
        segundos, e segurar a escrita esse tempo travaria a tela e o
        `result_server`). Por isso a gravação confere a geração da marca: se
        outra correção chegou no meio, o retrato calculado esta velho, não e
        gravado, e a volta seguinte o refaz.
        """
        gravados = 0
        # Cada volta só deixa para a seguinte o retrato que MUDOU enquanto era
        # calculado; o limite só existe para correções chegando sem parar — o
        # que sobrar continua marcado e o próximo pedido termina.
        for _volta in range(self.RECONCILE_MAX_PASSES):
            pendentes = self.db.list_pending_standings_snapshots(tournament_id)
            if not pendentes:
                break
            for pendente in pendentes:
                if self._reconcile_snapshot(pendente):
                    gravados += 1
        if gravados:
            logger.info("Retratos de classificacao reconciliados: %s", gravados)
        return gravados

    def _reconcile_snapshot(self, pendente: dict[str, Any]) -> bool:
        """Um retrato: calcula fora, grava dentro. True se gravou.

        O retrato antigo NÃO é apagado: vai para `standings_snapshot_history`
        com data e motivo, porque é ele que foi publicado e e ele que uma
        apelação vai querer ver. A linha viva passa a ser a reconciliada.

        Cada rodada e recalculada só com o que existia ATÉ ela — pareamentos,
        ajustes, inscritos e status (ver `_standings`). Sem esse corte, o
        retrato da rodada 3 receberia a classificação de hoje, o que seria uma
        segunda informação errada no lugar da primeira.
        """
        tournament_id = int(pendente["tournament_id"])
        round_id = int(pendente["round_id"])
        round_number = int(pendente["round_number"])
        motivo = str(pendente.get("reconcile_reason") or "").strip() or "Correção de resultado"
        tournament = self.db.get_tournament(tournament_id) or {}
        is_team = tournament.get("competition_type") == "team"
        standings = (
            self._team_standings(tournament_id, up_to_round=round_number)
            if is_team
            else self._standings(tournament_id, up_to_round=round_number)
        )

        with self.db.transaction():
            estado = self.db.standings_snapshot_reconcile_state(tournament_id, round_id)
            if (
                not estado
                or not estado["pending"]
                or estado["generation"] != int(pendente.get("reconcile_generation") or 0)
            ):
                return False
            antes = self.db.supersede_standings_snapshot(tournament_id, round_id, motivo)
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
                reason=f"Retrato da rodada {round_number} regravado. {motivo}",
                before={"snapshot_hash": antes},
                after={"snapshot_hash": depois, "superseded": bool(antes)},
            )
        return True

    def _team_close_summaries(self, tournament_id: int, round_id: int) -> list[dict[str, Any]]:
        """O passo de equipes do fechamento: confere os tabuleiros e calcula o resumo
        de cada confronto. Só lê; quem grava é ``close_round``, na transação."""
        matches = self.db.list_team_matches_for_round(round_id)
        if not matches:
            raise AppError("A rodada não possui confrontos por equipes.")

        pending: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        for match in matches:
            if match["is_bye"]:
                summaries.append(
                    _team_bye_summary(
                        match,
                        win_points=setting_number(settings, "team_match_win_points", 2.0),
                        boards_count=int(settings.get("team_boards_count", 4) or 4),
                        draw_points=setting_number(settings, "team_match_draw_points", 1.0),
                        loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
                    )
                )
                continue

            boards = self.db.list_team_boards(int(match["id"]))
            # Pendência DESTE confronto, e não da lista acumulada (PAR-04): com o
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
                    win_points=setting_number(settings, "team_match_win_points", 2.0),
                    loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
                    draw_points=setting_number(settings, "team_match_draw_points", 1.0),
                )
            )

        if pending:
            raise AppError("Preencha todos os resultados dos tabuleiros antes de fechar a rodada.")
        return summaries

    def _round_results_to_delete(self, round_id: int) -> list[dict[str, Any]]:
        """Resultados que a exclusão da rodada apagaria (RGS-34).

        Bye fica de fora: o resultado dele nasce com a rodada (PAB, bye
        solicitado) e volta igual quando ela for gerada de novo. O que conta e
        o que o árbitro anotou das súmulas.
        """
        apagados: list[dict[str, Any]] = []
        for mesa in self.db.get_pairings_for_round(round_id):
            resultado = str(mesa.get("result") or "").strip()
            if mesa.get("is_bye") or not resultado:
                continue
            apagados.append(
                {
                    "pairing_id": int(mesa["id"]),
                    "board": mesa.get("board_number"),
                    "white_player_id": mesa.get("white_player_id"),
                    "black_player_id": mesa.get("black_player_id"),
                    "result": resultado,
                }
            )
        for match in self.db.list_team_matches_for_round(round_id):
            if match.get("is_bye"):
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                resultado = str(board.get("result") or "").strip()
                if not resultado:
                    continue
                apagados.append(
                    {
                        "team_board_id": int(board["id"]),
                        "match": match.get("match_number"),
                        "board": board.get("board_number"),
                        "result": resultado,
                    }
                )
        return apagados

    def round_deletion_preview(self, round_id: int) -> dict[str, Any]:
        """O que excluir esta rodada custa — para a tela perguntar antes (RGS-34)."""
        rodada = self.db.get_round(round_id)
        if not rodada:
            raise AppError("Rodada não encontrada.")
        apagados = self._round_results_to_delete(round_id)
        return {
            "round_id": int(round_id),
            "number": int(rodada.get("number") or 0),
            "status": str(rodada.get("status") or ""),
            "results": len(apagados),
            "deleted": apagados,
            "message": _deleted_results_message(len(apagados)) if apagados else "",
        }

    @requires("tournament_write")
    def delete_generated_round(self, round_id: int, reason: str = "") -> None:
        """Exclui rodada gerada e ainda não fechada.

        Com resultado lançado, exige motivo e guarda os resultados apagados no
        ``before`` do evento (RGS-34): antes a exclusão fazia backup, mas a
        trilha só dizia "exclusao de rodada" com um texto fixo — e o que a mesa 7
        tinha anotado sumia sem que ninguém pudesse dizer por que.
        """
        row = self.db.get_round(round_id)
        if row and row["status"] == "closed":
            raise AppError("Rodada fechada não pode ser excluída.")
        apagados = self._round_results_to_delete(round_id) if row else []
        erro = _round_deletion_reason_error(reason, len(apagados))
        if erro:
            raise AppError(
                erro,
                suggestion=(
                    "Descreva por que a rodada precisa ser excluída, por exemplo "
                    "“reparear depois da correção da rodada anterior”."
                ),
            )
        if not row:
            self.db.delete_round(round_id)
            logger.info("Rodada gerada %s excluida", round_id)
            return
        tournament_id = int(row["tournament_id"])
        self.db.backup_before("delete_generated_round", tournament_id=tournament_id, round_id=round_id)
        with self.db.transaction():
            self.db.delete_round(round_id)
            self.db.create_audit_event(
                action="round_deleted",
                tournament_id=tournament_id,
                round_id=None,
                entity_type="round",
                entity_id=round_id,
                before={
                    "round_id": round_id,
                    "number": int(row["number"]),
                    "status": row["status"],
                    "results": apagados,
                },
                reason=(
                    _clean_reason(reason)
                    if apagados or _clean_reason(reason)
                    else "Exclusão de rodada gerada ainda não fechada."
                ),
            )
        logger.info("Rodada gerada %s excluida (%s resultado(s) apagado(s))", round_id, len(apagados))

    # -- Modo Amistoso: refazer a rodada aberta (MA-03) ---------------------- #

    def _open_round_to_repair(self, tournament_id: int, round_id: int) -> dict[str, Any]:
        from src.services import friendly_mode

        friendly_mode.require_friendly(
            self.db.get_tournament_settings(int(tournament_id)), "Re-emparceirar"
        )
        row = self.db.get_round(int(round_id))
        if not row or int(row["tournament_id"]) != int(tournament_id):
            raise AppError("Selecione uma rodada do torneio para re-emparceirar.")
        if row["status"] == "closed":
            raise AppError("Rodada fechada não pode ser re-emparceirada.")
        ultima = self.db.get_latest_round(int(tournament_id)) or {}
        if int(ultima.get("id") or 0) != int(round_id):
            raise AppError("Só a última rodada gerada pode ser re-emparceirada.")
        return dict(row)

    def _pending_qr_submissions(self, tournament_id: int, round_id: int) -> list[dict[str, Any]]:
        """Submissões QR não revisadas da rodada: somem em cascata com ela."""
        return [
            {
                "submission_id": int(item["id"]),
                "pairing_id": int(item["pairing_id"]),
                "board": item.get("board_number"),
                "submitted_result": item.get("submitted_result"),
                "submitter": item.get("submitter") or "",
            }
            for item in self.db.list_result_submissions(int(tournament_id), status="submitted")
            if int(item.get("round_id") or 0) == int(round_id)
        ]

    def repair_open_round_preview(self, tournament_id: int, round_id: int) -> dict[str, int]:
        """O que o re-emparceiramento apagaria: a tela mostra antes de pedir motivo."""
        self._open_round_to_repair(tournament_id, round_id)
        return {
            "results": len(self._round_results_to_delete(int(round_id))),
            "qr_submissions": len(self._pending_qr_submissions(tournament_id, round_id)),
        }

    @requires("tournament_write")
    def repair_open_round(
        self,
        tournament_id: int,
        round_id: int,
        reason: str = "",
        *,
        reserve_engine: bool = False,
    ) -> dict[str, Any]:
        """Apaga a rodada aberta e gera de novo com quem está ativo — ou nada (MA-03).

        Os dois passos correm numa transação: se a geração falha (recusa do
        Gacrux, menos de 2 alunos ativos), a rodada original volta intacta,
        com os resultados anotados. Resultado lançado ou submissão QR pendente
        exige motivo (a regra do RGS-34), e os dois ficam no ``before`` do
        evento ``round_repaired``.
        """
        row = self._open_round_to_repair(tournament_id, round_id)
        resultados = self._round_results_to_delete(int(round_id))
        submissoes = self._pending_qr_submissions(tournament_id, round_id)
        motivo = _repair_reason(reason, len(resultados) + len(submissoes))
        with self.db.transaction():
            self.delete_generated_round(int(round_id), reason=motivo if resultados else "")
            self.generate_next_round(int(tournament_id), reserve_engine=reserve_engine)
            nova = _round_ref(self.db.get_latest_round(int(tournament_id)))
            self.db.create_audit_event(
                action="round_repaired",
                tournament_id=int(tournament_id),
                round_id=nova["round_id"] or None,
                entity_type="round",
                entity_id=nova["round_id"] or None,
                reason=motivo,
                before={
                    "round_id": int(round_id),
                    "number": int(row["number"]),
                    "results": resultados,
                    "qr_submissions": submissoes,
                },
                after=nova,
            )
        logger.info("Rodada %s re-emparceirada no modo amistoso", round_id)
        return nova

    @requires("tournament_write")
    def delete_player_if_unpaired(self, tournament_id: int, player_id: int) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        player = self.db.get_player(player_id)
        if not player or int(player["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador não encontrado para o torneio selecionado.")
        if self.db.count_player_participation(player_id):
            raise AppError(
                "Não é possível excluir jogador que já aparece em rodada. "
                "Use \"Retirar do torneio…\" (Desistente) para preservar o histórico."
            )
        self.db.delete_player(player_id)
        logger.info("Jogador %s excluido do torneio %s antes de entrar em rodadas", player_id, tournament_id)

    @requires("tournament_write")
    def adjust_pairing_player(
        self,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        color: str,
        replacement_player_id: int,
        reason: str = "",
    ) -> None:
        """Troca manual de jogador numa mesa da rodada gerada (RGS-16).

        C.04.2: alteração manual do pareamento e registrada. O motivo e
        obrigatório, e o evento `pairing_manual_adjustment` guarda as mesas
        antes e depois e o que o verificador holandês (Gacrux, `-c`) diz da
        rodada ajustada — a divergência e ESPERADA aqui e não bloqueia: e a
        decisão do árbitro, agora com trilha.
        """
        motivo = str(reason or "").strip()
        erro_motivo = _manual_adjustment_reason_error(motivo)
        if erro_motivo:
            raise AppError(erro_motivo)
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada não pode ser ajustada.")
        if color not in {"white", "black"}:
            raise AppError("Cor inválida para ajuste.")

        replacement = self.db.get_player(replacement_player_id)
        if not replacement or int(replacement["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador substituto não pertence ao torneio.")
        if not replacement["active"]:
            raise AppError("Jogador substituto precisa estar ativo.")

        pairings = self.db.get_pairings_for_round(round_id)
        if not pairings:
            raise AppError("A rodada não possui mesas para ajustar.")

        pairing_by_id = {int(pairing["id"]): pairing for pairing in pairings}
        source_pairing = pairing_by_id.get(int(pairing_id))
        if not source_pairing:
            raise AppError("Mesa selecionada não encontrada.")
        if color == "black" and (source_pairing["is_bye"] or not source_pairing["black_player_id"]):
            raise AppError("Bye não possui jogador de pretas para trocar.")

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
            raise AppError("Jogador de origem inválido.")
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
        self._record_manual_adjustment(
            tournament_id,
            round_data,
            pairings,
            motivo,
            {
                "pairing_id": int(pairing_id),
                "color": color,
                "source_player_id": int(source_player_id),
                "replacement_player_id": int(replacement_player_id),
            },
        )

    def _record_manual_adjustment(
        self,
        tournament_id: int,
        round_data: dict[str, Any],
        before_pairings: list[dict[str, Any]],
        reason: str,
        change: dict[str, Any],
    ) -> None:
        """Evento `pairing_manual_adjustment` com a divergencia do verificador."""
        round_id = int(round_data["id"])
        round_number = int(round_data["number"])
        after_pairings = self.db.get_pairings_for_round(round_id)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        if self._pairing_checker_applies(settings):
            check = self._check_round_against_dutch(tournament_id, round_number)
        else:
            check = _unchecked_round(
                round_number, "o motor de pareamento do torneio não é o Gacrux"
            )
        self.db.create_audit_event(
            action="pairing_manual_adjustment",
            tournament_id=int(tournament_id),
            round_id=round_id,
            entity_type="round",
            entity_id=round_id,
            before={"pairs": [list(pair) for pair in sorted(_stored_pairs(before_pairings))]},
            after={
                "pairs": [list(pair) for pair in sorted(_stored_pairs(after_pairings))],
                "change": change,
            },
            reason=reason,
            metadata={"round_number": round_number, "checker": check.as_dict()},
        )

    def swap_pairing_colors(
        self, tournament_id: int, round_id: int, pairing_id: int, *, reason: str = ""
    ) -> None:
        """Inverte as cores de uma mesa, com auditoria (PAR-04, RGS-16).

        A tela chamava `db.swap_pairing_colors` direto: era a ÚNICA mutação de
        rodada que não passava pelo serviço e, por isso, a única sem evento de
        auditoria. Cor decidida pelo árbitro entra no TRF e no histórico de
        cores — e alteração manual do emparceiramento (C.04.2): motivo
        obrigatório e o mesmo evento `pairing_manual_adjustment` da troca de
        jogador, com a conferência do holandês.
        """
        motivo = str(reason or "").strip()
        erro_motivo = _manual_adjustment_reason_error(motivo)
        if erro_motivo:
            raise AppError(erro_motivo)
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada não pode ser ajustada.")
        pairing = self.db.get_pairing(pairing_id)
        if not pairing or int(pairing["tournament_id"]) != int(tournament_id):
            raise AppError("Mesa não encontrada para o torneio selecionado.")
        if pairing.get("is_bye"):
            raise AppError("Mesa de bye não tem cores para inverter.")
        if pairing["result"]:
            raise AppError("Limpe o resultado da mesa antes de trocar cores.")

        before_pairings = self.db.get_pairings_for_round(round_id)
        self.db.swap_pairing_colors(pairing_id)
        logger.info("Cores trocadas na mesa %s", pairing_id)
        self._record_manual_adjustment(
            tournament_id,
            round_data,
            before_pairings,
            motivo,
            {
                "kind": "colors_swapped",
                "pairing_id": int(pairing_id),
                "white_player_id": pairing.get("black_player_id"),
                "black_player_id": pairing.get("white_player_id"),
            },
        )

    @requires("tournament_write")
    @atomic
    def swap_team_board_colors(self, tournament_id: int, round_id: int, team_board_id: int) -> None:
        round_data = self.db.get_round(round_id)
        if not round_data or int(round_data["tournament_id"]) != int(tournament_id):
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada não pode ser ajustada.")
        board = self.db.get_team_board(team_board_id)
        if not board or int(board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro não encontrado para o torneio selecionado.")
        if board["result"]:
            raise AppError("Limpe o resultado do tabuleiro antes de trocar cores.")
        before = {
            "team_board_id": int(team_board_id),
            "white_player_id": board.get("white_player_id"),
            "black_player_id": board.get("black_player_id"),
        }
        self.db.swap_team_board_colors(team_board_id)
        # Passava pelo serviço, mas sem trilha — mesma lacuna do individual.
        self.db.create_audit_event(
            action="team_board_colors_swapped",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="team_board",
            entity_id=int(team_board_id),
            reason="Cores invertidas pelo árbitro.",
            before=before,
            after={
                "team_board_id": int(team_board_id),
                "white_player_id": before["black_player_id"],
                "black_player_id": before["white_player_id"],
            },
        )
        logger.info("Cores trocadas no tabuleiro por equipes %s", team_board_id)

    @requires("tournament_write")
    @atomic
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
            raise AppError("Rodada não encontrada para o torneio selecionado.")
        if round_data["status"] == "closed":
            raise AppError("Rodada fechada não pode ser ajustada.")
        if color not in {"white", "black"}:
            raise AppError("Cor inválida para ajuste.")

        source_board = self.db.get_team_board(team_board_id)
        if not source_board or int(source_board["tournament_id"]) != int(tournament_id):
            raise AppError("Tabuleiro selecionado não encontrado.")

        replacement = self.db.get_player(replacement_player_id)
        if not replacement or int(replacement["tournament_id"]) != int(tournament_id):
            raise AppError("Jogador substituto não pertence ao torneio.")
        if not replacement["active"]:
            raise AppError("Jogador substituto precisa estar ativo.")

        source_player_id = source_board["white_player_id"] if color == "white" else source_board["black_player_id"]
        if source_player_id is None:
            raise AppError("Jogador de origem inválido.")
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
                raise AppError("Limite de substituições da equipe nesta rodada foi atingido.")

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
            raise AppError("A rodada não possui tabuleiros para ajustar.")

        board_by_id = {int(board["id"]): board for board in boards}
        selected_board = board_by_id.get(int(team_board_id))
        if not selected_board:
            raise AppError("Tabuleiro selecionado não encontrado.")

        target_slot = self._find_team_board_player_slot(boards, replacement_player_id)
        affected_board_ids = {int(team_board_id)}
        if target_slot:
            affected_board_ids.add(int(target_slot["board"]["id"]))

        for board_id in affected_board_ids:
            board = board_by_id[board_id]
            if board["result"]:
                raise AppError("Substituição depois de resultado exige correção formal: limpe o resultado antes.")

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
        """Classificação para PUBLICAR — tela, exportação, prêmio, pódio, ata.

        Em modo estrito (TBK-02), motor FIDE caído levanta `AppError` aqui: e o
        "bloquear a publicacao" do critério de aceite.
        """
        return self._standings(tournament_id, honor_strict=True)

    def _standings(
        self,
        tournament_id: int,
        *,
        honor_strict: bool = False,
        up_to_round: int | None = None,
    ) -> list[dict[str, Any]]:
        """Motor da classificação individual. `honor_strict` diz para que serve.

        Com `honor_strict=False` — pareamento, prévia, snapshot de rodada,
        diagnóstico do painel — a falha do motor FIDE degrada para o motor
        próprio mesmo em modo estrito, e de propósito: esses usos só precisam da
        ORDEM POR PONTOS, que os dois motores calculam igual. Barrar aqui pararia
        o torneio (não se fecharia rodada nem se gerariam pares) por causa de um
        problema de RELATÓRIO — trocaria um risco de publicação por um risco de
        operação, que é maior. O registro e o alerta acontecem de qualquer forma.

        `up_to_round` recorta a classificação "como estava depois da rodada N",
        que é o que um retrato de rodada guarda (ARB-01). Sem o corte, reconciliar
        o retrato da rodada 3 gravaria nele a classificação de hoje. O corte vale
        para tudo o que muda com o tempo (RGS-10): pareamentos, ajustes de pontos
        (`round_number <= N`), inscritos (até N) e status (o vigente na rodada N).
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            return []

        players = self.db.list_players(tournament_id, active_only=False)
        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        adjustment_rows = self.db.list_point_adjustments(tournament_id)
        if up_to_round is not None:
            closed_pairings = [
                pairing
                for pairing in closed_pairings
                if int(pairing.get("round_number") or 0) <= int(up_to_round)
            ]
            players = _players_as_of_round(
                players,
                self.db.list_player_status_events(tournament_id),
                closed_pairings,
                int(up_to_round),
            )
            adjustment_rows = _adjustments_up_to_round(adjustment_rows, int(up_to_round))
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
            adjustments=_aggregate_player_adjustments(adjustment_rows),
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
        """Desempates pelo motor FIDE (Gacrux), ou None para usar o motor próprio.

        Retorna None quando: o motor configurado não é o Gacrux; e torneio por
        equipes (Fase 5); não há rodada fechada; ou o motor falhou (fallback ao
        Albericus, hoje registrado e visível — ver `_run_tiebreak_engine`). O
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
        # Chamada aninhada vinda do export do TRF: usa o motor próprio (evita
        # recursao standings -> Gacrux -> export -> standings). NÃO é fallback —
        # não registra nada, não alerta e não vale o modo estrito, senão o export
        # que o próprio motor pediu ficaria impossível.
        if int(tournament_id) in _tiebreak_inflight():
            return None

        # A sequência vai INTEIRA (código + parâmetros) para o motor: era só a
        # lista de códigos, então o corte que o árbitro configurou na TBK-04
        # chegava ao registro 212 do arquivo FIDE mas não ao cálculo em execução
        # — o motor rodava com os padrões e a tela mostrava outro número.
        codes: list[Any] = (
            [dict(item) for item in sequence]
            if sequence
            else list(_DEFAULT_PLAYER_TIEBREAKS)
        )
        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
        engine = GacruxTiebreakEngine(self.db)
        return self._run_tiebreak_engine(
            tournament_id,
            engine_name,
            settings,
            lambda: engine.prepare(tournament_id, codes, current_round=current_round),
            engine.run,
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
        prepare: Callable[[], TiebreakJob | None],
        run: Callable[[TiebreakJob], dict[int, dict[str, Any]]],
        *,
        honor_strict: bool,
    ) -> dict[int, dict[str, Any]] | None:
        """Roda o motor FIDE e responde pelo que aconteceu.

        Antes da TBK-02 esta falha era um `logger.warning` e um `return None`: o
        mesmo torneio podia publicar duas classificações diferentes entre rodadas
        sem nenhum aviso ao árbitro. Agora ela deixa retrato (para a faixa da
        tela), evento de auditoria (para o relatório e para o painel) e, em modo
        estrito, barra a publicação em vez de degradar.

        O retrato e o registro NÃO dependem de `honor_strict`: a falha e a mesma,
        e o modo estrito do torneio e que diz se ela bloqueia. `honor_strict` só
        decide se ESTE chamador recebe a exceção — quem só precisa da ordem por
        pontos (pareamento, snapshot) segue pelo motor próprio.

        `prepare` gera o TRF que o motor vai receber, e a chave do cache e o hash
        dele (RGS-36): qualquer dado que mude o arquivo — bye, pontos iniciais,
        ajuste — recalcula. `run` só roda quando a chave e nova. O export do TRF
        chama standings() de novo, por isso a guarda de reentrância já cobre o
        `prepare`.
        """
        strict = bool(settings.get("tiebreak_strict"))
        inflight = _tiebreak_inflight()
        inflight.add(int(tournament_id))
        try:
            try:
                job = prepare()
            except AppError as exc:
                # Sem TRF não há hash: a falha do export vale pela mensagem.
                return self._tiebreak_engine_failed(
                    tournament_id, engine_name, strict, (int(tournament_id), "export", str(exc)),
                    exc, honor_strict=honor_strict,
                )
            if job is None:
                # Nenhuma rodada fechada no recorte: nada a calcular.
                self._remember_engine(tournament_id, _report_engine_ok(engine_name))
                return {}
            cache_key = (int(tournament_id), job.fingerprint)
            cached = self._cached_engine_outcome(cache_key)
            if cached is not None:
                return self._replay_engine_outcome(
                    tournament_id, engine_name, cached, honor_strict=honor_strict
                )
            try:
                tiebreaks = run(job)
            except AppError as exc:
                return self._tiebreak_engine_failed(
                    tournament_id, engine_name, strict, cache_key, exc, honor_strict=honor_strict
                )
        finally:
            inflight.discard(int(tournament_id))

        self._store_engine_outcome(
            tournament_id, cache_key, _report_engine_ok(engine_name), tiebreaks
        )
        return tiebreaks

    def _tiebreak_engine_failed(
        self,
        tournament_id: int,
        engine_name: str,
        strict: bool,
        cache_key: tuple,
        exc: AppError,
        *,
        honor_strict: bool,
    ) -> dict[int, dict[str, Any]] | None:
        """Falha do motor: retrato, auditoria (uma vez por estado) e modo estrito."""
        cached = self._cached_engine_outcome(cache_key)
        if cached is not None:
            # Mesma falha no mesmo estado: sem evento novo na trilha.
            return self._replay_engine_outcome(
                tournament_id, engine_name, cached, honor_strict=honor_strict
            )
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

    def _replay_engine_outcome(
        self,
        tournament_id: int,
        engine_name: str,
        cached: EngineOutcome,
        *,
        honor_strict: bool,
    ) -> dict[int, dict[str, Any]] | None:
        self._remember_engine(tournament_id, cached.report)
        if cached.report.blocked and honor_strict:
            raise AppError(_strict_block_message(engine_name, cached.report.error))
        return cached.tiebreaks

    @staticmethod
    def _cached_engine_outcome(cache_key: tuple) -> EngineOutcome | None:
        with _GACRUX_TIEBREAK_CACHE_LOCK:
            cached = _GACRUX_TIEBREAK_CACHE.get(cache_key)
            if cached is not None:
                _GACRUX_TIEBREAK_CACHE.move_to_end(cache_key)
            return cached

    def _store_engine_outcome(
        self,
        tournament_id: int,
        cache_key: tuple,
        report: EngineReport,
        tiebreaks: dict[int, dict[str, Any]] | None,
    ) -> None:
        with _GACRUX_TIEBREAK_CACHE_LOCK:
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

        Uma falha por ESTADO do torneio, não por chamada: o cache guarda o
        fracasso junto com o sucesso, então fechar uma rodada nova gera um evento
        novo (o árbitro precisa saber que aconteceu de novo) e repintar a tela
        não gera nenhum.
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
        """Retrato do ultimo cálculo de desempate deste torneio.

        Sem cálculo registrado, devolve o motor configurado como usado — que é a
        verdade disponível ("nada foi calculado ainda") e permite a faixa dizer
        de saída qual motor vai assinar a tabela.
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
        """Esquece o cálculo cacheado deste torneio e tenta o motor de novo.

        Falha cacheada e o que evita a enxurrada de subprocessos, mas também
        prende o torneio numa falha que pode ter sido passageira. O "Recalcular"
        da tela de classificação chama aqui: e o caminho explicito de volta ao
        motor configurado, sem precisar mexer em resultado nenhum.
        """
        target = int(tournament_id)
        with _GACRUX_TIEBREAK_CACHE_LOCK:
            for key in [key for key in _GACRUX_TIEBREAK_CACHE if key[0] == target]:
                _GACRUX_TIEBREAK_CACHE.pop(key, None)
        _LAST_TIEBREAK_ENGINE.pop(target, None)

    def crosstable(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
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
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Tabela cruzada por equipes disponível apenas para torneios por equipes.")
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
            # E6: o retrato da rodada N não traz a equipe inscrita depois dela.
            teams = _teams_as_of_round(teams, closed_matches, int(up_to_round))
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
                if up_to_round is None
                # RGS-10: o retrato da rodada N só vê os ajustes até N.
                else _adjustments_up_to_round(
                    self.db.list_point_adjustments(tournament_id), int(up_to_round)
                )
            ),
            board_results=self._team_board_results(tournament_id, sequence, up_to_round),
        )

    def _team_board_results(
        self,
        tournament_id: int,
        sequence: list[dict[str, Any]] | None,
        up_to_round: int | None,
    ) -> list[dict[str, Any]] | None:
        """Resultados por tabuleiro — só quando algum critério precisa (TBK-05).

        A classificação e recalculada a cada abertura de tela e a cada seção de
        relatório; a consulta só vale a pena quando o board count é na
        sequência configurada, o que não acontece em nenhum torneio por padrão.
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
        """Desempates de EQUIPES pelo motor FIDE (Gacrux), ou None p/ o próprio.

        Espelha _gacrux_player_tiebreaks, inclusive no registro da troca de motor
        (TBK-02): None quando o motor não é o Gacrux, não há confronto fechado, ou
        o motor falhou; cache por assinatura + guarda de reentrância (o export
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
        if int(tournament_id) in _tiebreak_inflight():
            return None

        # Sequência inteira, com parâmetros — ver `_gacrux_player_tiebreaks`.
        codes: list[Any] = [dict(item) for item in (sequence or []) if item.get("code")]
        if not codes:
            primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
            secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
            codes = [primary, secondary, "buchholz", "wins"]

        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
        engine = GacruxTiebreakEngine(self.db)
        return self._run_tiebreak_engine(
            tournament_id,
            engine_name,
            settings,
            lambda: engine.prepare_teams(tournament_id, codes, current_round=current_round),
            engine.run,
            honor_strict=honor_strict,
        )

    def _knockout_pairings(
        self,
        tournament_id: int,
        players: list[dict[str, Any]],
        next_number: int,
        settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Próxima fase do mata-mata, com o avanço explicado (PAR-03).

        A fase só é gerada quando toda mesa da anterior tem vencedor — do
        tabuleiro ou por decisão registrada. Empate, dupla ausência e mesa em
        branco promoviam o melhor número inicial em silêncio; agora eles PARAM a
        geração e pedem a decisão do árbitro.
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
            # não devolve ninguém a chave principal.
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

    # ---- Registros do árbitro: ajustes, proibições, byes de equipe, jogadores (RG2-04) ---- #
    # A tela gravava estes direto no banco, por fora da permissão. Agora passam
    # por aqui: @requires checa quem opera e @atomic grava registro e auditoria
    # juntos. A descrição legível (``summary``) vem de quem sabe descrevê-la.

    _ADJUSTMENT_FIELDS = ("round_number", "player_id", "team_id", "aat_type", "match_points", "game_points", "reason")

    @requires("tournament_write")
    @atomic
    def add_point_adjustment(
        self, tournament_id: int, payload: Mapping[str, Any], summary: str = "", *, restored: bool = False
    ) -> int:
        registro = {campo: payload.get(campo) for campo in self._ADJUSTMENT_FIELDS}
        registro["round_number"] = int(registro.get("round_number") or 0)
        registro["aat_type"] = str(registro.get("aat_type") or "")
        registro["match_points"] = float(registro.get("match_points") or 0.0)
        registro["game_points"] = float(registro.get("game_points") or 0.0)
        registro["reason"] = str(registro.get("reason") or "").strip()
        registro["id"] = int(self.db.add_point_adjustment(int(tournament_id), **registro))
        acao = "point_adjustment_restored" if restored else "point_adjustment_added"
        self._audit_point_adjustment(acao, tournament_id, summary, registro)
        return registro["id"]

    @requires("tournament_write")
    @atomic
    def delete_point_adjustment(
        self, tournament_id: int, adjustment_id: int, record: Mapping[str, Any] | None = None, summary: str = ""
    ) -> None:
        self.db.delete_point_adjustment(int(adjustment_id))
        self._audit_point_adjustment(
            "point_adjustment_removed", tournament_id, summary, {**(record or {}), "id": int(adjustment_id)}
        )

    def _audit_point_adjustment(
        self, action: str, tournament_id: int, summary: str, record: Mapping[str, Any]
    ) -> None:
        """Na trilha do torneio, onde o ``export_tournament_audit`` procura (TBK-01)."""
        metadata: dict[str, Any] = {"summary": summary}
        metadata.update(
            {campo: record[campo] for campo in self._ADJUSTMENT_FIELDS[:-1] if record.get(campo) is not None}
        )
        self.db.create_audit_event(
            action=action,
            tournament_id=int(tournament_id),
            entity_type="point_adjustment",
            entity_id=int(record.get("id") or 0) or None,
            reason=str(record.get("reason") or "").strip(),
            metadata=metadata,
        )

    @requires("tournament_write")
    def add_prohibited_pairing(
        self, tournament_id: int, target_a_id: int, target_b_id: int, *, is_team: bool = False, **payload: Any
    ) -> int:
        adicionar = self.db.add_prohibited_team_pairing if is_team else self.db.add_prohibited_pairing
        return int(adicionar(int(tournament_id), int(target_a_id), int(target_b_id), **payload))

    @requires("tournament_write")
    def delete_prohibited_pairing(self, prohibition_id: int, *, is_team: bool = False) -> None:
        if is_team:
            self.db.delete_prohibited_team_pairing(int(prohibition_id))
        else:
            self.db.delete_prohibited_pairing(int(prohibition_id))

    @requires("tournament_write")
    def add_requested_team_bye(
        self, tournament_id: int, team_id: int, round_number: int, bye_type: str, reason: str = ""
    ) -> int:
        # Equipes não têm política de bye (ARB-04 é do individual): só a permissão.
        return int(self.db.add_requested_team_bye(int(tournament_id), int(team_id), int(round_number), bye_type, reason=reason))

    @requires("tournament_write")
    def delete_requested_team_bye(self, requested_bye_id: int) -> None:
        self.db.delete_requested_team_bye(int(requested_bye_id))

    @requires("tournament_write")
    def create_player(self, tournament_id: int, **payload: Any) -> int:
        return int(self.db.create_player(int(tournament_id), **payload))

    @requires("tournament_write")
    def update_player(self, player_id: int, **payload: Any) -> None:
        self.db.update_player(int(player_id), **payload)

    @requires("tournament_write")
    def set_player_scheveningen_group(self, player_id: int, group: str) -> None:
        self.db.set_player_scheveningen_group(int(player_id), group)

    def _operator_name(self) -> str:
        operator = self.db.current_operator()
        return operator.name if operator else SYSTEM_ACTOR

    @requires("tournament_write")
    @atomic
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
            # RG2-43: sem ator explícito, quem está logado (a tela mandava "").
            actor=actor.strip() or self._operator_name(),
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
            raise AppError("Selecione um torneio válido.")
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
        acceleration: tuple[Sequence[int], float] | None = None,
    ) -> list[dict[str, Any]]:
        """Motor próprio. `acceleration` e o plano da rodada (`_acceleration_plan`);
        sem ele, o plano e calculado aqui."""
        standings = {item["player_id"]: item for item in self._standings(tournament_id)}
        settings = self.db.get_tournament_settings(tournament_id) or {}
        seeding = self._seeding(players, settings)
        # Topscorers (C.3/A.7) saem da classificação REAL, antes da aceleração:
        # ponto fictício de pareamento não coloca ninguém na liderança (PAR-04).
        tournament = self.db.get_tournament(tournament_id) or {}
        topscorers = _topscorer_ids(
            standings,
            round_number=round_number,
            rounds_total=int(tournament.get("rounds_count") or 0),
        )
        if acceleration is None:
            acelerados, bonus, _motor = self._acceleration_plan(
                tournament_id, players, settings, round_number, False, []
            )
            acceleration = (acelerados, bonus)
        standings = _standings_with_virtual_points(standings, *acceleration)
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
            topscorers=topscorers,
            # Número de pareamento = ordem inicial (RGS-13), para a cor E.4/E.5.
            pairing_numbers={player_id: number for number, player_id in enumerate(seeding, start=1)},
            # E.5 com a cor inicial do torneio (RGS-14), não brancas fixas.
            initial_color=resolve_initial_color(self.db, tournament_id, settings),
        )

    def _team_closed_history(
        self, tournament_id: int
    ) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
        """Confrontos fechados e os tabuleiros de cada um (EQ-03).

        O W.O. é nos tabuleiros, não na linha do confronto: sem eles o
        histórico tratava o confronto inteiro por W.O. como jogado.
        """
        matches = self.db.list_team_matches_for_tournament(tournament_id, closed_only=True)
        boards = {
            int(match["id"]): self.db.list_team_boards(int(match["id"]))
            for match in matches
            if not match.get("is_bye")
        }
        return matches, boards

    def _team_played_pairs(self, tournament_id: int) -> set[frozenset[int]]:
        return _team_played_pairs(*self._team_closed_history(tournament_id))

    def _team_bye_ids(self, tournament_id: int) -> set[int]:
        return _team_bye_ids(*self._team_closed_history(tournament_id))

    def _team_color_histories(self, tournament_id: int) -> dict[int, list[str]]:
        return _team_color_histories(*self._team_closed_history(tournament_id))

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
