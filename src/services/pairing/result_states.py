"""Ciclo de vida do resultado por mesa (spec §6.4 / §7.3)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def derive_pairing_state(
    *,
    result: str,
    round_closed: bool,
    has_pending_submission: bool = False,
    has_correction: bool = False,
) -> str:
    """Deriva o ciclo de vida da mesa (constants.RESULT_STATES).

    Ordem de prioridade:
      corrected > locked > published > submitted > empty

    Correção tem prioridade sobre locked para manter a marca de auditoria
    visível mesmo após o fechamento da rodada.
    """
    if has_correction:
        return "corrected"
    if round_closed:
        return "locked" if result else "empty"
    if result:
        return "published"
    if has_pending_submission:
        return "submitted"
    return "empty"


def result_states_summary(
    pairings: Iterable[Mapping[str, Any]],
    audit_events: Iterable[Mapping[str, Any]],
    result_submissions: Iterable[Mapping[str, Any]],
    result_states: Iterable[str],
) -> dict[str, int]:
    """Conta mesas por estado derivado a partir de dados ja carregados."""
    counts = {state: 0 for state in result_states}
    pairings = list(pairings)
    if not pairings:
        return counts

    corrected_pairings = {
        int(event["entity_id"])
        for event in audit_events
        if event.get("entity_type") == "pairing"
        and event.get("entity_id") is not None
        and "corrected" in str(event.get("action") or "")
    }
    pending_subs = {
        int(sub["pairing_id"])
        for sub in result_submissions
        if sub.get("pairing_id") is not None
    }

    for pairing in pairings:
        state = derive_pairing_state(
            result=str(pairing.get("result") or ""),
            round_closed=pairing.get("round_status") == "closed",
            has_pending_submission=int(pairing.get("id")) in pending_subs,
            has_correction=int(pairing.get("id")) in corrected_pairings,
        )
        counts[state] += 1
    return counts
