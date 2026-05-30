"""Payloads puros de pré-visualização de emparceiramento."""

from __future__ import annotations

from typing import Any

from src.services.constants import player_pairing_name
from src.services.pairing.constraints import would_make_three_colors


def individual_preview_payload(
    *,
    tournament_id: int,
    tournament: dict[str, Any],
    plan: dict[str, Any],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    standings: dict[int, dict[str, Any]],
    pairing_engine_version: str,
    ruleset_version: str,
) -> dict[str, Any]:
    players_by_id = {int(player["id"]): player for player in plan["players"]}
    preview_pairings = []
    alert_count = 0
    for pairing in plan["pairings"]:
        white_id = int(pairing["white_player_id"])
        black_id = int(pairing["black_player_id"]) if pairing.get("black_player_id") else None
        alerts = []
        explanation = []
        if pairing.get("is_bye"):
            code = str(pairing.get("result") or "").strip().upper()
            if code in {"F", "H", "Z"}:
                alerts.append("Bye solicitado")
                explanation.append(f"Bye solicitado pelo arbitro (tipo {code}).")
            else:
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
            if would_make_three_colors(white_id, "W", histories):
                alerts.append("Brancas pela terceira vez seguida")
            if would_make_three_colors(black_id, "B", histories):
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
        "pairing_engine_version": pairing_engine_version,
        "ruleset_version": ruleset_version,
        "pairings": preview_pairings,
        "alerts_count": alert_count,
    }


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
                explanation.append(f"Bye solicitado pelo arbitro (tipo {code}).")
            else:
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
        "pairing_engine_version": pairing_engine_version,
        "ruleset_version": ruleset_version,
        "matches": preview_matches,
        "alerts_count": alert_count,
    }
