"""Helpers puros para painel e pendencias de arbitragem."""

from __future__ import annotations

import json
from typing import Any


def result_submission_issue(submission: dict[str, Any]) -> dict[str, Any]:
    return {
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


def audit_issue(
    event: dict[str, Any],
    source: str,
    kind: str,
    title: str,
    severity: str = "decision",
) -> dict[str, Any]:
    """Evento de auditoria → pendência do painel.

    `severity` é parâmetro porque "decision" **bloqueia o fechamento da rodada**
    (ver `_blocking_arbitration_issues_for_round`). Isso é certo para um evento
    de sync rejeitado, que o árbitro precisa resolver antes de seguir, e errado
    para um aviso de motor de desempate: pararia o torneio por causa de um
    problema de relatório. O padrão continua "decision" para não mudar o
    comportamento de quem já chamava sem o argumento.
    """
    event_identifier = event.get("event_id") or event.get("id") or event.get("entity_id") or ""
    return {
        "issue_key": f"{source}:{kind}:{event_identifier}",
        "severity": severity,
        "source": source,
        "kind": kind,
        "title": title,
        "detail": event.get("reason") or event.get("action") or "",
        "round_id": event.get("round_id"),
        "entity_id": event.get("entity_id"),
        "created_at": event.get("created_at") or "",
        "payload": event,
    }


def clock_issue(event: dict[str, Any], title: str) -> dict[str, Any]:
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


def clock_event_issue(event: dict[str, Any]) -> dict[str, Any] | None:
    """Classifica um evento de relógio como pendência de arbitragem, se aplicável.

    Retorna None para eventos que não exigem atenção (ex.: aviso de tempo acima
    do limite crítico de 60s).
    """
    event_type = str(event.get("event_type") or "")
    seconds = int(event.get("seconds_remaining") or 999999)
    if event_type == "flag_fall":
        return clock_issue(event, "Queda de seta registrada")
    if event_type == "absence":
        return clock_issue(event, "Ausencia registrada")
    if event_type == "time_warning" and seconds <= 60:
        return clock_issue(event, "Alerta de tempo critico")
    return None


def finalize_issues(
    issues: list[dict[str, Any]],
    acknowledged_keys: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Remove pendências já tratadas, ordena por data desc e aplica o limite."""
    filtered = [
        issue
        for issue in issues
        if str(issue.get("issue_key") or "") not in acknowledged_keys
    ]
    filtered.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return filtered[:limit]


def issue_metrics(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(issues),
        "qr_pending": sum(1 for item in issues if item["source"] == "qr"),
        "sync_conflicts": sum(1 for item in issues if item["source"] == "sync"),
        "clock_alerts": sum(1 for item in issues if item["source"] == "clock"),
        "pairing_alerts": sum(1 for item in issues if item["source"] == "pairing"),
        "tiebreak_alerts": sum(1 for item in issues if item["source"] == "tiebreak"),
        "decision_required": sum(1 for item in issues if item["severity"] == "decision"),
    }


def acknowledged_issue_keys(events: list[dict[str, Any]]) -> set[str]:
    acknowledged: set[str] = set()
    for event in events:
        try:
            payload = json.loads(event.get("after_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        issue_key = str(payload.get("issue_key") or "").strip()
        if issue_key:
            acknowledged.add(issue_key)
    return acknowledged


def issue_matches_round(issue: dict[str, Any], round_id: int) -> bool:
    raw_round_id = issue.get("round_id")
    if raw_round_id in (None, ""):
        return True
    try:
        return int(raw_round_id) == int(round_id)
    except (TypeError, ValueError):
        return True


def blocking_issues_message(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return ""
    summaries = [
        f"{issue.get('source') or ''}/{issue.get('kind') or ''}".strip("/")
        for issue in issues[:3]
    ]
    suffix = f" ({', '.join(summaries)})" if summaries else ""
    return f"Resolva as pendencias de arbitragem bloqueantes antes de fechar a rodada{suffix}."


def individual_round_dashboard_metrics(
    pairings: list[dict[str, Any]],
    final_results: set[str],
) -> dict[str, Any]:
    pending = [
        item
        for item in pairings
        if not item.get("result") or item.get("result") not in final_results
    ]
    byes = [item for item in pairings if item.get("is_bye")]
    # Progresso = mesas (sem bye) que precisam de resultado x quantas ja tem.
    games = [item for item in pairings if not item.get("is_bye")]
    resolved = [item for item in games if item.get("result") in final_results]
    return {
        "pending_results": len(pending),
        "byes": len(byes),
        "ready_to_close": bool(pairings) and not pending,
        "total_results": len(games),
        "resolved_results": len(resolved),
    }


def team_round_dashboard_metrics(
    matches: list[dict[str, Any]],
    boards_by_match_id: dict[int, list[dict[str, Any]]],
    final_results: set[str],
) -> dict[str, Any]:
    pending = 0
    byes = 0
    total = 0
    resolved = 0
    for match in matches:
        if match.get("is_bye"):
            byes += 1
            continue
        boards = boards_by_match_id.get(int(match["id"]), [])
        total += len(boards)
        for board in boards:
            if not board.get("result") or board.get("result") not in final_results:
                pending += 1
            else:
                resolved += 1
    return {
        "pending_results": pending,
        "byes": byes,
        "ready_to_close": bool(matches) and pending == 0,
        "total_results": total,
        "resolved_results": resolved,
    }
