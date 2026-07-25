import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.pairing_service import PairingService


class TestPairingGacrux(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        
        self.tournament_id = self.db.create_tournament("Test Gacrux Swiss", rounds_count=5, bye_points=1.0)
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_system": "gacrux_swiss",
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Test Arbiter",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
        })
        
    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def create_players(self, num_players: int, ratings: list[int] = None) -> list[int]:
        ids = []
        for i in range(num_players):
            rating = ratings[i] if ratings else 1500
            p_id = self.db.create_player(
                self.tournament_id, 
                f"Jogador {i+1:03d}", 
                club="Club", 
                rating=rating, 
                category="ABS",
                sex="m",
                birth_date="2000-01-01"
            )
            ids.append(p_id)
        return ids

    def test_gacrux_first_round(self):
        ratings = [2200, 2100, 2000, 1900, 1800, 1700, 1600, 1500]
        self.create_players(8, ratings)
        
        # Round 1 generation
        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])
        
        self.assertEqual(len(pairings), 4)
        
        # Verify FIDE Dutch pairing pattern for Round 1:
        # Top half paired with bottom half:
        # P1 (2200) vs P5 (1800)
        # P2 (2100) vs P6 (1700)
        # P3 (2000) vs P7 (1600)
        # P4 (1900) vs P8 (1500)
        expected_pairs = {
            (1, 5), (2, 6), (3, 7), (4, 8)
        }
        actual_pairs = {
            (min(p["white_player_id"], p["black_player_id"]), max(p["white_player_id"], p["black_player_id"]))
            for p in pairings
        }
        self.assertEqual(actual_pairs, expected_pairs)

    def test_gacrux_bye_generation(self):
        ratings = [2200, 2100, 2000]
        self.create_players(3, ratings)
        
        # Generating Round 1 (odd number of players, should generate 1 bye)
        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])
        
        self.assertEqual(len(pairings), 2)  # 1 normal board, 1 bye board
        
        bye_boards = [p for p in pairings if p["is_bye"]]
        self.assertEqual(len(bye_boards), 1)
        self.assertEqual(bye_boards[0]["result"], "BYE")
        self.assertIsNone(bye_boards[0]["black_player_id"])
        
    def test_gacrux_prevents_repeated_matches(self):
        self.create_players(4)
        
        # Round 1
        r1 = self.pairing_service.generate_next_round(self.tournament_id)
        pairings1 = self.db.get_pairings_for_round(r1["id"])
        
        for p in pairings1:
            self.pairing_service.update_result(self.tournament_id, p["id"], "1-0")
        self.pairing_service.close_round(self.tournament_id, r1["id"])
        
        history = {frozenset([p["white_player_id"], p["black_player_id"]]) for p in pairings1}
        
        # Round 2
        r2 = self.pairing_service.generate_next_round(self.tournament_id)
        pairings2 = self.db.get_pairings_for_round(r2["id"])
        
        for p in pairings2:
            pair = frozenset([p["white_player_id"], p["black_player_id"]])
            self.assertNotIn(pair, history)

    def test_gacrux_requested_byes(self):
        player_ids = self.create_players(4)
        
        # Request a half-point bye for player 4 in Round 1
        self.db.add_requested_bye(self.tournament_id, round_number=1, player_id=player_ids[3], bye_type="H")
        
        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])
        
        # Should have 3 pairings: 1 board between player 1-2, 1 automatic bye for player 3, and 1 requested bye for player 4
        self.assertEqual(len(pairings), 3)
        
        requested_byes = [p for p in pairings if p["is_bye"]]
        self.assertEqual(len(requested_byes), 2)
        
        requested_bye = next(p for p in requested_byes if p["result"] == "H")
        automatic_bye = next(p for p in requested_byes if p["result"] == "BYE")
        self.assertEqual(requested_bye["white_player_id"], player_ids[3])
        self.assertEqual(automatic_bye["white_player_id"], player_ids[2])

    def test_gacrux_handles_non_ascii_names(self):
        # Nomes com Unicode nao-decomponivel (o-cortado, eszett, thorn) sobrevivem
        # ao _trf_clean e ficam multibyte em UTF-8. Como o TRF e gravado em UTF-8 e
        # tem colunas de largura fixa, o motor precisa le-lo em UTF-8 (flag -b);
        # caso contrario as colunas desalinham (status 467) e o pareamento falha.
        # Regressao do fix de encoding na integracao Gacrux.
        ratings = [2200, 2100, 2000, 1900]
        names = ["Bjorn Sorensen", "Weiss Muller", "Bjørn Sørensen", "Þór Æsir"]
        ids = []
        for i in range(4):
            p_id = self.db.create_player(
                self.tournament_id,
                names[i],
                club="Club",
                rating=ratings[i],
                category="ABS",
                sex="m",
                birth_date="2000-01-01",
            )
            ids.append(p_id)

        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])

        self.assertEqual(len(pairings), 2)
        paired_ids = set()
        for p in pairings:
            paired_ids.add(p["white_player_id"])
            paired_ids.add(p["black_player_id"])
        self.assertEqual(paired_ids, set(ids))

if __name__ == "__main__":
    unittest.main()
