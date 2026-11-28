"""RG2-23 — o pareamento por equipes agrupa pelo critério principal configurado.

Os grupos e a ordem do suíço por equipes eram sempre por ``match_points``;
``team_standing_primary`` era lido pela classificação e pelo TRF25, mas não
pelo pareamento. Com "pontos de tabuleiro" (``game_points``) como critério
principal, o motor pareava por outra tabela que não a publicada.
"""
from __future__ import annotations

import unittest
from typing import Any

from src.services.pairing import team_swiss
from src.services.pairing.team_swiss import swiss_team_matches


def _equipe(ident: int) -> dict[str, Any]:
    return {"id": ident, "name": f"Equipe {ident}"}


# A e B empatam em match points (2) e diferem em game points; C e D também.
CLASSIFICACAO = {
    1: {"match_points": 2.0, "game_points": 4.0, "position": 1},
    2: {"match_points": 2.0, "game_points": 1.0, "position": 2},
    3: {"match_points": 0.0, "game_points": 3.5, "position": 3},
    4: {"match_points": 0.0, "game_points": 0.0, "position": 4},
}


def _confrontos(primario: str) -> set[frozenset[int]]:
    matches = swiss_team_matches(
        [_equipe(i) for i in (1, 2, 3, 4)],
        {i: {1: None, 2: None} for i in (1, 2, 3, 4)},
        {1: 2000, 2: 1990, 3: 1980, 4: 1970},
        2,
        {"team_standing_primary": primario, "bye_points": 1},
        CLASSIFICACAO,
        {i: ["W"] if i % 2 else ["B"] for i in (1, 2, 3, 4)},
        {frozenset((1, 4)), frozenset((2, 3))},
        set(),
        max_exhaustive_pairing_teams=16,
        repeat_pairing_penalty=1_000_000,
        score_group_float_penalty=10_000,
        score_diff_penalty=1_000,
    )
    return {frozenset((m["white_team_id"], m["black_team_id"])) for m in matches}


class CriterioPrincipalTest(unittest.TestCase):
    def test_match_points_junta_quem_empata_em_match_points(self) -> None:
        self.assertEqual({frozenset((1, 2)), frozenset((3, 4))}, _confrontos("match_points"))

    def test_game_points_separa_quem_empata_em_match_points(self) -> None:
        # Por game points a ordem é 1 (4), 3 (3,5), 2 (1), 4 (0): grupos diferentes.
        self.assertEqual({frozenset((1, 3)), frozenset((2, 4))}, _confrontos("game_points"))

    def test_chaves_do_criterio(self) -> None:
        self.assertEqual(("match_points", "game_points"), team_swiss.team_score_keys({}))
        self.assertEqual(("game_points", "match_points"), team_swiss.team_score_keys({"team_standing_primary": "game_points"}))
        self.assertEqual(("match_points", "game_points"), team_swiss.team_score_keys({"team_standing_primary": "outro"}))


if __name__ == "__main__":
    unittest.main()
