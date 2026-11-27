from __future__ import annotations

import unittest

from tests.support.core_service_base import CoreServiceTestCase


class DupCheck(CoreServiceTestCase):
    def test_dup(self) -> None:
        tid = self.tournament_id
        self.db.save_tournament_settings(
            tid,
            {
                "prize_tie_split": "hort",
                "prize_exclude_withdrawn": 1,
                "late_tolerance_minutes": 30,
                "rating_speed": "rapid",
                "rating_regulation": "fide",
                "category_reference_date": "2026-01-01",
                "prize_policy": "cumulative",
                "prize_tax_percent": 12.5,
            },
        )
        self.db.replace_tournament_categories(
            tid,
            [
                {"name": "Sub-07", "kind": "age", "max_value": 7, "position": 0},
                {"name": "Sub-09", "kind": "age", "max_value": 9, "position": 1},
                {"name": "Feminino", "kind": "sex", "sex": "F", "position": 2},
            ],
        )
        self.db.replace_tournament_prizes(
            tid,
            [{"kind": "category", "label": "Sub-07", "category": "Sub-07", "rank_from": 1, "rank_to": 1, "amount": 50.0}],
        )
        src = self.db.get_tournament_settings(tid)
        print("SRC:", {k: src.get(k) for k in ("prize_tie_split", "prize_exclude_withdrawn", "late_tolerance_minutes", "rating_speed", "rating_regulation", "category_reference_date", "prize_policy", "prize_tax_percent")})
        print("SRC cats:", [c["name"] for c in self.db.list_tournament_categories(tid)])

        new_id = self.tournament_service.duplicate_tournament(tid, "Copia 2027")
        dst = self.db.get_tournament_settings(new_id)
        print("DST:", {k: dst.get(k) for k in ("prize_tie_split", "prize_exclude_withdrawn", "late_tolerance_minutes", "rating_speed", "rating_regulation", "category_reference_date", "prize_policy", "prize_tax_percent")})
        print("DST cats:", [c["name"] for c in self.db.list_tournament_categories(new_id)])
        print("DST prizes:", [(p["kind"], p["category"]) for p in self.db.list_tournament_prizes(new_id)])


if __name__ == "__main__":
    unittest.main()
