"""Carregador de cenários de torneio descritos em JSON.

Spec §15.2 sugere uma pasta `tests/fixtures/tournaments/` com cenários
reproduzíveis. Este módulo expõe um único `load_tournament_fixture(name, db,
pairing_service)` que cria torneio, jogadores, gera/fecha rodadas conforme
a descrição e devolve o `tournament_id`.

Schema esperado de cada arquivo `.json`:

    {
      "name": str,
      "description": str,
      "rounds_count": int,
      "competition_type": "individual" | "team",   # default "individual"
      "players": [
        {"name": str, "rating": int, "club": str?, "category": str?,
         "surname": str?, "given_name": str?}
      ],
      "rounds": [
        {
          "results_by_board": {"1": "1-0", "2": "1/2-1/2", ...},
          "close": true   # opcional, default True
        }
      ]
    }

Tabuleiros sem resultado declarado ficam como "" (vazio); a rodada é fechada
mesmo assim se o cenário pedir, simulando rodada incompleta.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "tournaments"


def load_tournament_fixture(
    name: str,
    db: Any,
    pairing_service: Any,
) -> int:
    """Lê `<name>.json`, materializa no banco e retorna `tournament_id`."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture não encontrada: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    tournament_id = db.create_tournament(
        data["name"],
        rounds_count=int(data.get("rounds_count", 1)),
    )

    for player in data.get("players", []):
        db.create_player(
            tournament_id,
            name=player.get("name", ""),
            surname=player.get("surname", ""),
            given_name=player.get("given_name", ""),
            rating=int(player.get("rating", 0) or 0),
            club=player.get("club", ""),
            category=player.get("category", "Absoluto"),
        )

    for round_spec in data.get("rounds", []):
        round_data = pairing_service.generate_next_round(tournament_id)
        round_id = int(round_data["id"])
        pairings = db.get_pairings_for_round(round_id)
        results_map = round_spec.get("results_by_board", {})
        for pairing in pairings:
            board = str(int(pairing["board_number"]))
            result = results_map.get(board, "")
            if result:
                pairing_service.update_result(
                    tournament_id, int(pairing["id"]), result
                )
        if round_spec.get("close", True):
            pairing_service.close_round(tournament_id, round_id)

    return tournament_id
