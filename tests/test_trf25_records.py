"""Testes dos construtores puros de registros TRF25 (geometria de coluna)."""

import unittest

from src.services.federation_exporters.trf25_records import (
    encode_time_control,
    record_162,
    record_172,
    record_212,
    record_240,
    record_250,
    record_260,
    record_299,
    record_300,
    record_310,
    record_320,
    record_330,
    record_362,
    record_802,
    record_national_rating,
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


class TestRecord162(unittest.TestCase):
    def test_individual_scoring_columns(self):
        line = record_162([("W", 1.0), ("D", 0.5), ("L", 0.0)]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "162")
        self.assertEqual(cols(line, 6, 6), "W")
        self.assertEqual(cols(line, 7, 10), " 1.0")
        self.assertEqual(cols(line, 15, 15), "D")
        self.assertEqual(cols(line, 16, 19), " 0.5")
        self.assertEqual(cols(line, 24, 24), "L")
        self.assertEqual(cols(line, 25, 28), " 0.0")


class TestRecord362(unittest.TestCase):
    def test_team_scoring_columns(self):
        line = record_362([("TW", 3.0), ("TD", 1.0), ("TL", 0.0)]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "362")
        self.assertEqual(cols(line, 5, 6), "TW")
        self.assertEqual(cols(line, 7, 10), " 3.0")
        self.assertEqual(cols(line, 14, 15), "TD")
        self.assertEqual(cols(line, 16, 19), " 1.0")
        self.assertEqual(cols(line, 23, 24), "TL")
        self.assertEqual(cols(line, 25, 28), " 0.0")


class TestRecord212(unittest.TestCase):
    def test_csv_descriptor_with_modifiers(self):
        self.assertEqual(
            record_212(["PTS", "BH", "BH/M1", "SB", "WIN"]),
            "212 PTS,BH,BH/M1,SB,WIN\r\n",
        )

    def test_team_score_base_is_preserved(self):
        self.assertEqual(record_212(["PTS", "BH:MP", "WIN"]), "212 PTS,BH:MP,WIN\r\n")


class TestRecord802(unittest.TestCase):
    def test_fixed_columns_bye_then_played_round(self):
        line = record_802(
            3, "GEO", 19.0, 32.5,
            [("FPB", "", 4.0, ""), ("16", "w", 2.5, "")],
        ).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "802")
        self.assertEqual(cols(line, 5, 7), "  3")
        self.assertEqual(cols(line, 9, 13), "GEO  ")
        self.assertEqual(cols(line, 15, 20), "  19.0")
        self.assertEqual(cols(line, 22, 27), "  32.5")
        # Rodada 1 (bye full-point): código no 29-31, cor vazia, GP no 35-38.
        self.assertEqual(cols(line, 29, 31), "FPB")
        self.assertEqual(cols(line, 33, 33), " ")
        self.assertEqual(cols(line, 35, 38), " 4.0")
        # Rodada 2 (+13 colunas): oponente 16, cor w, GP 2.5.
        self.assertEqual(cols(line, 42, 44), "16 ")
        self.assertEqual(cols(line, 46, 46), "w")
        self.assertEqual(cols(line, 48, 51), " 2.5")

    def test_forfeit_indicator_and_blank_gp(self):
        line = record_802(1, "AAA", 0.0, 0.0, [("9", "b", None, "f")]).rstrip("\r\n")
        self.assertEqual(cols(line, 42 - 13, 44 - 13), "9  ")
        self.assertEqual(cols(line, 35, 38), "    ")
        self.assertEqual(cols(line, 39, 39), "f")


class TestRecord250(unittest.TestCase):
    def test_individual_acceleration_columns(self):
        line = record_250(0.0, 1.0, 1, 2, [3, 7]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "250")
        self.assertEqual(cols(line, 5, 8), "    ")
        self.assertEqual(cols(line, 10, 13), " 1.0")
        self.assertEqual(cols(line, 15, 17), "  1")
        self.assertEqual(cols(line, 19, 21), "  2")
        self.assertEqual(cols(line, 23, 26), "   3")
        self.assertEqual(cols(line, 28, 31), "   7")

    def test_team_acceleration_with_match_points(self):
        line = record_250(2.0, 0.0, 1, 1, [5]).rstrip("\r\n")
        self.assertEqual(cols(line, 5, 8), " 2.0")
        self.assertEqual(cols(line, 10, 13), "    ")
        self.assertEqual(cols(line, 23, 26), "   5")


class TestRecord260(unittest.TestCase):
    def test_prohibited_pair_columns(self):
        line = record_260(1, 9, [4, 12]).rstrip("\r\n")
        self.assertEqual(cols(line, 1, 3), "260")
        self.assertEqual(cols(line, 5, 7), "  1")
        self.assertEqual(cols(line, 9, 11), "  9")
        self.assertEqual(cols(line, 13, 16), "   4")
        self.assertEqual(cols(line, 18, 21), "  12")

    def test_third_entity_offset(self):
        line = record_260(2, 2, [1, 2, 3]).rstrip("\r\n")
        self.assertEqual(cols(line, 23, 26), "   3")


class TestEncodeTimeControl(unittest.TestCase):
    def test_single_period_no_increment(self):
        self.assertEqual(encode_time_control("10 min"), "600")

    def test_single_period_with_increment(self):
        self.assertEqual(encode_time_control("15 min + 10 s"), "900+10")
        self.assertEqual(encode_time_control("3 min + 2 s"), "180+2")
        self.assertEqual(encode_time_control("90 min + 30 s"), "5400+30")

    def test_multi_period_with_increment(self):
        self.assertEqual(
            encode_time_control("90 min / 40 lances + 30 min + 30 s"),
            "40/5400+30:1800+30",
        )

    def test_multi_period_without_increment(self):
        self.assertEqual(
            encode_time_control("100 min / 40 lances + 15 min"),
            "40/6000:900",
        )

    def test_unparseable_returns_none(self):
        self.assertIsNone(encode_time_control(""))
        self.assertIsNone(encode_time_control("ritmo livre"))
        self.assertIsNone(encode_time_control(None))


class TestRecordNationalRating(unittest.TestCase):
    def test_column_geometry_with_national_id(self):
        line = record_national_rating("bra", 1, 1928, national_id="55501")
        self.assertEqual(cols(line, 1, 3), "BRA")     # federacao (maiuscula)
        self.assertEqual(cols(line, 5, 8).strip(), "1")    # start-rank
        self.assertEqual(cols(line, 49, 52), "1928")   # rating nacional
        self.assertEqual(cols(line, 58, 68).strip(), "55501")  # nº nacional

    def test_national_id_omitted_when_absent(self):
        line = record_national_rating("FID", 12, 2401)
        self.assertEqual(cols(line, 1, 3), "FID")
        self.assertEqual(cols(line, 5, 8).strip(), "12")
        self.assertEqual(cols(line, 49, 52), "2401")
        # Sem nº nacional, a linha termina no rating (rstrip).
        self.assertEqual(len(line.rstrip("\r\n")), 52)


class TestRecord172(unittest.TestCase):
    def test_column_geometry(self):
        line = record_172("bra", "FIDE")
        self.assertEqual(cols(line, 1, 3), "172")
        self.assertEqual(cols(line, 5, 7), "BRA")            # federacao (maiuscula)
        self.assertEqual(cols(line, 9, 13).strip(), "FIDE")  # metodo
        self.assertTrue(line.endswith("\r\n"))

    def test_defaults_to_fide(self):
        self.assertEqual(cols(record_172("FID"), 9, 13).strip(), "FIDE")

    def test_unknown_method_falls_back_to_other(self):
        self.assertEqual(cols(record_172("FID", "estranho"), 9, 13).strip(), "OTHER")


if __name__ == "__main__":
    unittest.main()
