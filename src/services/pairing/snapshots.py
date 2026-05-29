"""Serialização pura de snapshots de pareamento."""

from __future__ import annotations

from typing import Any


def pairing_input_snapshot(
    tournament: dict[str, Any],
    settings: dict[str, Any],
    round_number: int,
    participants: list[dict[str, Any]],
    previous_rounds: list[dict[str, Any]],
    previous_pairings: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
