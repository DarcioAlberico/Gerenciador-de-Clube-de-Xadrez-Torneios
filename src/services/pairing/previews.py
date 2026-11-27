"""Payloads puros de pré-visualização de emparceiramento."""

from __future__ import annotations

from typing import Any

from src.services.constants import player_pairing_name
from src.services.pairing.diagnostics import pairing_diagnostics


def individual_preview_payload(
    *,
    tournament_id: int,
    tournament: dict[str, Any],
    plan: dict[str, Any],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
    standings: dict[int, dict[str, Any]],
    float_histories: dict[int, list[str]] | None = None,
    pairing_engine_version: str,
    ruleset_version: str,
) -> dict[str, Any]:
    players_by_id = {int(player["id"]): player for player in plan["players"]}
    diagnostics = pairing_diagnostics(
        plan["pairings"],
        histories,
        played_pairs,
        bye_player_ids,
        players=plan["players"],
        standings=standings,
        float_histories=float_histories,
    )
    diagnostics_by_board: dict[int, list[dict[str, Any]]] = {}
    for diagnostic in diagnostics:
        diagnostics_by_board.setdefault(int(diagnostic.get("board_number") or 0), []).append(diagnostic)

    preview_pairings = []
    alert_count = 0
    for pairing in plan["pairings"]:
        white_id = int(pairing["white_player_id"])
        black_id = int(pairing["black_player_id"]) if pairing.get("black_player_id") else None
        board_number = int(pairing["board_number"])
        alerts = []
        explanation = []
        for diagnostic in diagnostics_by_board.get(board_number, []):
            alerts.append(_diagnostic_alert(diagnostic))
            explanation.append(str(diagnostic.get("detail") or ""))
        if pairing.get("is_bye"):
            code = str(pairing.get("result") or "").strip().upper()
            if code in {"F", "H", "Z"}:
                alerts.append("Bye solicitado")
                explanation.append(f"Bye solicitado pelo árbitro (tipo {code}).")
            else:
                alerts.append("Bye")
                explanation.append("Jogador recebeu bye por número ímpar de participantes ativos.")
        elif black_id is not None:
            white_score = float(standings.get(white_id, {}).get("points", 0.0) or 0.0)
            black_score = float(standings.get(black_id, {}).get("points", 0.0) or 0.0)
            if abs(white_score - black_score) > 1.0:
                alerts.append("Scoregroup distante")
            explanation.append(
                "Pareado por pontuação e critérios do método configurado; "
                f"placares atuais {white_score:g} x {black_score:g}."
            )

        alert_count += len(alerts)
        white = players_by_id.get(white_id, {})
        black = players_by_id.get(black_id or 0, {})
        preview_pairings.append(
            {
                "board_number": board_number,
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
    # Avisos da rodada inteira (PAR-02) — não pertencem a nenhuma mesa, mas
    # contam como alerta: é por eles que o árbitro fica sabendo que a aceleração
    # trocou de motor, ou que alguém será pareado com pontuação diferente da
    # classificação.
    warnings = [str(item) for item in plan.get("warnings") or []]
    return {
        "competition_type": "individual",
        "tournament_id": tournament_id,
        "tournament_name": tournament.get("name", ""),
        "round_number": int(plan["round_number"]),
        "pairing_system": str(plan["settings"].get("pairing_system") or "custom_authorized"),
        "pairing_engine_version": pairing_engine_version,
        "ruleset_version": ruleset_version,
        "pairings": preview_pairings,
        "warnings": warnings,
        "alerts_count": alert_count + len(warnings),
    }


def _diagnostic_alert(diagnostic: dict[str, Any]) -> str:
    title = str(diagnostic.get("title") or "Alerta de pareamento")
    avoidable = diagnostic.get("avoidable")
    if avoidable is True:
        return f"{title} evitável"
    if avoidable is False:
        return f"{title} inevitável"
    return title


def team_preview_payload(
    *,
    tournament_id: int,
    tournament: dict[str, Any],
    plan: dict[str, Any],
    played_pairs: set[frozenset[int]],
    pairing_engine_version: str,
    ruleset_version: str,
) -> dict[str, Any]:
    teams_by_id = {int(team["id"]): team for team in plan["teams"]}
    lineup_warnings = {int(item["team_id"]): item for item in plan.get("lineup_warnings") or []}
    preview_matches = []
    alert_count = 0
    for match in plan["matches"]:
        white_team_id = int(match["white_team_id"])
        black_team_id = int(match["black_team_id"]) if match.get("black_team_id") else None
        alerts = []
        explanation = []
        if match.get("is_bye"):
            code = str(match.get("result") or "").strip().upper()
            if code in {"F", "H", "Z"}:
                alerts.append("Bye solicitado")
                explanation.append(f"Bye solicitado pelo árbitro (tipo {code}).")
            else:
                alerts.append("Bye da equipe")
                explanation.append("Equipe recebeu bye por número ímpar de equipes ativas.")
        elif black_team_id is not None:
            if frozenset((white_team_id, black_team_id)) in played_pairs:
                alerts.append("Confronto repetido")
            explanation.append("Match gerado pelo método de emparceiramento por equipes configurado.")
            # EQ-02.5: escalação incompleta e aviso visível antes de gerar.
            for team_id in (white_team_id, black_team_id):
                aviso = lineup_warnings.get(team_id)
                if not aviso:
                    continue
                if "Escalação incompleta" not in alerts:
                    alerts.append("Escalação incompleta")
                explanation.append(_lineup_warning_text(aviso))
        alert_count += len(alerts)
        # Equipe desativada no todos-contra-todos não é em `teams` (ativas).
        white_team = teams_by_id.get(white_team_id) or {
            "name": lineup_warnings.get(white_team_id, {}).get("team_name")
        }
        black_team = teams_by_id.get(black_team_id or 0) or {
            "name": lineup_warnings.get(black_team_id or 0, {}).get("team_name")
        }
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
        "pairing_engine_version": pairing_engine_version,
        "ruleset_version": ruleset_version,
        "matches": preview_matches,
        "alerts_count": alert_count,
        # Vai para o topo da prévia (`format_pairing_preview`), como os avisos
        # do individual: escalação incompleta nunca some no corte por `limit`.
        "warnings": [
            *(str(aviso) for aviso in plan.get("warnings") or []),
            *(_lineup_warning_text(aviso) for aviso in lineup_warnings.values()),
        ],
    }


def _lineup_warning_text(aviso: dict[str, Any]) -> str:
    """Texto do aviso de escalacao incompleta (EQ-02.5)."""
    nome = aviso.get("team_name") or aviso.get("team_id")
    if aviso.get("empty"):
        return (
            f"{nome}: nenhum jogador presente. Registre um bye Z para a equipe "
            "ou confirme o W.O. do confronto inteiro ao gerar a rodada."
        )
    vagas = ", ".join(str(board) for board in aviso["empty_boards"])
    rotulo = "tabuleiro" if len(aviso["empty_boards"]) == 1 else "tabuleiros"
    return f"{nome}: {rotulo} {vagas} sem jogador presente (W.O.)."
