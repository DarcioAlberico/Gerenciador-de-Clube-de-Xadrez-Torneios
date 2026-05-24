import tempfile
import unittest
from pathlib import Path
from src.core.database import Database
from src.services.pairing_service import PairingService

class TestPairingRules(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_pairing.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        
        self.tournament_id = self.db.create_tournament("Test Swiss", rounds_count=5, bye_points=1.0)
        
    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except:
            pass

    def create_players(self, num_players: int, ratings: list[int] = None) -> list[int]:
        ids = []
        for i in range(num_players):
            rating = ratings[i] if ratings else 1500
            self.db.create_player(self.tournament_id, f"Player {i+1}", club="Club", rating=rating, category="ABS")
            ids.append(i + 1)
        return ids

    def test_swiss_first_round_ordering(self):
        ratings = [2000, 1900, 1800, 1700, 1600, 1500, 1400, 1300]
        self.create_players(8, ratings)
        
        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])
        
        self.assertEqual(len(pairings), 4)
        
        top_half = {1, 2, 3, 4}
        bottom_half = {5, 6, 7, 8}
        
        for p in pairings:
            w = p["white_player_id"]
            b = p["black_player_id"]
            self.assertFalse(w in top_half and b in top_half)
            self.assertFalse(w in bottom_half and b in bottom_half)

    def test_pairing_avoids_repeated_matches(self):
        self.create_players(4)
        
        r1 = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(r1["id"])
        
        for p in pairings:
            self.pairing_service.update_result(self.tournament_id, p["id"], "1/2-1/2")
        self.pairing_service.close_round(self.tournament_id, r1["id"])
        
        history = set()
        for p in pairings:
            history.add(frozenset([p["white_player_id"], p["black_player_id"]]))
            
        r2 = self.pairing_service.generate_next_round(self.tournament_id)
        pairings2 = self.db.get_pairings_for_round(r2["id"])
        
        for p in pairings2:
            pair = frozenset([p["white_player_id"], p["black_player_id"]])
            self.assertNotIn(pair, history)

    def test_pairing_color_balance(self):
        self.create_players(4)
        
        with self.db.connect() as conn:
            conn.execute("INSERT INTO rounds (tournament_id, number, status, created_at) VALUES (?, 1, 'closed', '2024-01-01')", (self.tournament_id,))
            conn.execute("INSERT INTO rounds (tournament_id, number, status, created_at) VALUES (?, 2, 'closed', '2024-01-01')", (self.tournament_id,))
            
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (1, 1, 1, 2, '1-0', 0, '2024-01-01')")
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (1, 2, 3, 4, '1-0', 0, '2024-01-01')")
            
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (2, 1, 1, 3, '1-0', 0, '2024-01-01')")
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (2, 2, 4, 2, '1-0', 0, '2024-01-01')")
        
        r3 = self.pairing_service.generate_next_round(self.tournament_id)
        pairings3 = self.db.get_pairings_for_round(r3["id"])
        
        found = False
        for p in pairings3:
            if p["black_player_id"] == 1:
                found = True
            elif p["white_player_id"] == 1:
                self.fail("Player 1 got White for the 3rd time in a row!")
        
        self.assertTrue(found, "Player 1 not found in round 3 pairings.")

    def test_pairing_single_bye_limit(self):
        self.create_players(3)
        
        r1 = self.pairing_service.generate_next_round(self.tournament_id)
        p1 = self.db.get_pairings_for_round(r1["id"])
        bye_player_r1 = next(p["white_player_id"] for p in p1 if p["is_bye"])
        
        for p in p1:
            if not p["is_bye"]:
                self.pairing_service.update_result(self.tournament_id, p["id"], "1-0")
        self.pairing_service.close_round(self.tournament_id, r1["id"])
        
        r2 = self.pairing_service.generate_next_round(self.tournament_id)
        p2 = self.db.get_pairings_for_round(r2["id"])
        bye_player_r2 = next(p["white_player_id"] for p in p2 if p["is_bye"])
        
        self.assertNotEqual(bye_player_r1, bye_player_r2, "Player received a second BYE!")

    def test_score_group_priority(self):
        self.create_players(4)
        
        with self.db.connect() as conn:
            conn.execute("INSERT INTO rounds (tournament_id, number, status, created_at) VALUES (?, 1, 'closed', '2024-01-01')", (self.tournament_id,))
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (1, 1, 1, 3, '1-0', 0, '2024-01-01')")
            conn.execute("INSERT INTO pairings (round_id, board_number, white_player_id, black_player_id, result, is_bye, created_at) VALUES (1, 2, 2, 4, '1-0', 0, '2024-01-01')")
        
        r2 = self.pairing_service.generate_next_round(self.tournament_id)
        p2 = self.db.get_pairings_for_round(r2["id"])
        
        for p in p2:
            pair = {p["white_player_id"], p["black_player_id"]}
            self.assertTrue(pair == {1, 2} or pair == {3, 4}, f"Invalid pairing {pair}, expected 1x2 and 3x4 based on score groups.")

if __name__ == "__main__":
    unittest.main()

