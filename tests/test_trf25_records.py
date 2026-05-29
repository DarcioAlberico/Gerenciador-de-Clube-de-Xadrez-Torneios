"""Testes dos construtores puros de registros TRF25 (geometria de coluna)."""

import unittest

from src.services.federation_exporters.trf25_records import (
    record_240,
    record_299,
    record_300,
    record_310,
    record_320,
    record_330,
    tournament_line,
    trf_ascii,
)


def cols(line: str, start: int, end: int) -> str:
    """Recorta colunas 1-based inclusivas (ex.: cols(line, 5, 7))."""
    return line[start - 1 : end]


class TestTournamentLine(unittest.TestCase):
    def test_simple_code_and_freetext(self):
        self.assertEqual(tournament_line("142", 11), "142 11\r\n")
        self.assertEqual(tournament_line("152", "W"), "152 W\r\n")
        self.assertEqual(
            tournament_line("192", "FIDE_TEAM_TYPEA_MP_GP"),
            "192 FIDE_TEAM_TYPEA_MP_GP\r\n",
        )

    def test_strips_accents(self):
        self.assertEqual(tournament_line("012", "São Paulo"), "012 Sao Paulo\r\n")


class TestTrfAscii(unittest.TestCase):
    def test_collapses_whitespace_and_strips_diacritics(self):
        self.assertEqual(trf_ascii("  José   da\nSilva "), "Jose da Silva")


class TestRecord310(unittest.TestCase):
    def setUp(self):
        self.line = record_310(
            team_pairing_number=1,
            team_name="India",
            nickname="IND",
            strength_factor=2486,
            match_points=15.0,
            game_points=28.0,
            team_rank=11,
            player_start_ranks=[5, 15, 28, 44],
        )

    def test_field_columns(self):
        line = self.line.rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "310")
        self.assertEqual(cols(line, 5, 7), "  1")
        self.assertEqual(cols(line, 9, 40), "India".ljust(32))
        self.assertEqual(cols(line, 42, 46), "IND  ")
        self.assertEqual(cols(line, 48, 53), "  2486")
        self.assertEqual(cols(line, 55, 60), "  15.0")
        self.assertEqual(cols(line, 62, 67), "  28.0")
        self.assertEqual(cols(line, 69, 71), " 11")
        self.assertEqual(cols(line, 74, 77), "   5")
        self.assertEqual(cols(line, 79, 82), "  15")
        self.assertEqual(cols(line, 84, 87), "  28")
        self.assertEqual(cols(line, 89, 92), "  44")

    def test_ends_with_crlf(self):
        self.assertTrue(self.line.endswith("\r\n"))

    def test_empty_strength_is_blank(self):
        line = record_310(
            team_pairing_number=2,
            team_name="Ukraine",
            nickname="UKR",
            strength_factor=0,
            match_points=14.0,
            game_points=26.5,
            team_rank=14,
            player_start_ranks=[4, 20],
        ).rstrip("\r\n")
        self.assertEqual(cols(line, 48, 53), " " * 6)
        self.assertEqual(cols(line, 55, 60), "  14.0")
        self.assertEqual(cols(line, 62, 67), "  26.5")

    def test_long_name_truncated_to_32(self):
        line = record_310(
            team_pairing_number=3,
            team_name="A" * 40,
            nickname="AAAAAA",
            strength_factor=2000,
            match_points=0.0,
            game_points=0.0,
            team_rank=1,
            player_start_ranks=[],
        ).rstrip("\r\n")
        self.assertEqual(cols(line, 9, 40), "A" * 32)
        self.assertEqual(cols(line, 42, 46), "AAAAA")


class TestRecord240(unittest.TestCase):
    def test_half_point_bye_columns(self):
        line = record_240("H", 3, [26, 47]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "240")
        self.assertEqual(cols(line, 5, 5), "H")
        self.assertEqual(cols(line, 7, 9), "  3")
        self.assertEqual(cols(line, 11, 14), "  26")
        self.assertEqual(cols(line, 16, 19), "  47")

    def test_ends_with_crlf(self):
        self.assertTrue(record_240("F", 1, [1]).endswith("\r\n"))


class TestRecord320(unittest.TestCase):
    def test_pab_columns(self):
        line = record_320(2.0, 4.0, [0, 3, 0]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "320")
        self.assertEqual(cols(line, 5, 8), " 2.0")
        self.assertEqual(cols(line, 10, 13), " 4.0")
        self.assertEqual(cols(line, 15, 17), "000")
        self.assertEqual(cols(line, 19, 21), "  3")
        self.assertEqual(cols(line, 23, 25), "000")


class TestRecord330(unittest.TestCase):
    def test_white_wins_forfeit_columns(self):
        line = record_330("+-", 5, 12, 7).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "330")
        self.assertEqual(cols(line, 5, 6), "+-")
        self.assertEqual(cols(line, 8, 10), "  5")
        self.assertEqual(cols(line, 12, 14), " 12")
        self.assertEqual(cols(line, 16, 18), "  7")

    def test_double_forfeit_type(self):
        line = record_330("--", 2, 3, 4).rstrip("\r\n")
        self.assertEqual(cols(line, 5, 6), "--")


class TestRecord300(unittest.TestCase):
    def test_out_of_order_columns(self):
        line = record_300(4, 9, 3, [11, 0, 22]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "300")
        self.assertEqual(cols(line, 5, 7), "  4")
        self.assertEqual(cols(line, 9, 11), "  9")
        self.assertEqual(cols(line, 13, 15), "  3")
        self.assertEqual(cols(line, 17, 20), "  11")
        self.assertEqual(cols(line, 22, 25), "0000")
        self.assertEqual(cols(line, 27, 30), "  22")


class TestRecord299(unittest.TestCase):
    def test_team_penalty_with_negative_points(self):
        line = record_299("", -0.0, -1.0, 0, [5]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "299")
        self.assertEqual(cols(line, 5, 5), " ")
        self.assertEqual(cols(line, 14, 17), "-1.0")
        self.assertEqual(cols(line, 20, 22), "000")
        self.assertEqual(cols(line, 24, 27), "   5")

    def test_typed_team_assignment_columns(self):
        line = record_299("W", 2.0, 4.0, 3, [8, 9]).rstrip("\r\n")
        self.assertEqual(cols(line, 5, 5), "W")
        self.assertEqual(cols(line, 8, 11), " 2.0")
        self.assertEqual(cols(line, 14, 17), " 4.0")
        self.assertEqual(cols(line, 20, 22), "  3")
        self.assertEqual(cols(line, 24, 27), "   8")
        self.assertEqual(cols(line, 29, 32), "   9")


if __name__ == "__main__":
    unittest.main()
