"""Fase 1 da integracao de desempates FIDE via Gacrux.

Cobre o modulo PURO de mapeamento (sem subprocesso) e um teste de integracao do
motor de I/O ``GacruxTiebreakEngine`` (roda o ``tiebreakchecker.py`` real, como
os testes de pareamento Gacrux ja fazem).
"""

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.pairing_service import PairingService
from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
from src.services.pairing.gacrux_tiebreak_map import (
    POINTS_CODE,
    TiebreakPlan,
    build_tiebreak_plan,
    parse_competitors,
)


class TestGacruxTiebreakMap(unittest.TestCase):
    """Mapeamento e parse puros — rapidos, sem motor."""

    def test_build_plan_default_sequence(self):
        plan = build_tiebreak_plan(["buchholz", "sonneborn_berger", "wins"])
        self.assertEqual(plan.specifiers, ("PTS", "BH", "SB", "WON"))
        self.assertEqual(plan.code_order, ("points", "buchholz", "sonneborn_berger", "wins"))
        self.assertEqual(plan.skipped, ())

    def test_build_plan_starts_with_points(self):
        plan = build_tiebreak_plan([])
        self.assertEqual(plan.specifiers, ("PTS",))
        self.assertEqual(plan.code_order, (POINTS_CODE,))

    def test_build_plan_drops_points_duplicates_and_unsupported(self):
        plan = build_tiebreak_plan(
            ["points", "buchholz", "buchholz", "cumulative_opp", "buchholz_median"]
        )
        # 'points' e a duplicata sao ignorados; 'cumulative_opp' nao tem
        # equivalente Gacrux e vai para skipped.
        self.assertEqual(plan.specifiers, ("PTS", "BH", "BH/M1"))
        self.assertEqual(plan.code_order, ("points", "buchholz", "buchholz_median"))
        self.assertEqual(plan.skipped, ("cumulative_opp",))

    def test_build_plan_maps_cut_and_rating_criteria(self):
        plan = build_tiebreak_plan(["buchholz_cut1", "buchholz_cut2", "aro", "aroc", "performance"])
        self.assertEqual(plan.specifiers, ("PTS", "BH/C1", "BH/C2", "ARO", "ARO/M1", "TPR"))

    def test_parse_competitors_aligns_scores_to_codes(self):
        plan = build_tiebreak_plan(["buchholz", "sonneborn_berger", "wins"])
        competitors = [
            {"cid": 1, "rank": 1, "tiebreakScore": [3.0, 5.5, 7.0, 2]},
            {"cid": 2, "rank": 2, "tiebreakScore": [2.0, 4.0, 3.0, 1]},
        ]
        parsed = parse_competitors(competitors, plan)
        self.assertEqual(parsed[1]["rank"], 1)
        self.assertEqual(parsed[1]["scores"], {
            "points": 3.0, "buchholz": 5.5, "sonneborn_berger": 7.0, "wins": 2.0,
        })
        self.assertEqual(parsed[2]["scores"]["points"], 2.0)

    def test_parse_competitors_tolerates_short_rows_and_bad_cid(self):
        plan = build_tiebreak_plan(["buchholz"])
        competitors = [
            {"cid": 5, "rank": 1, "tiebreakScore": [4.0]},  # falta coluna do buchholz
            {"cid": None, "rank": 2, "tiebreakScore": [1.0, 1.0]},  # cid invalido
            {"cid": "7", "rank": 3, "tiebreakScore": ["2.5", "9.0"]},  # strings
        ]
        parsed = parse_competitors(competitors, plan)
        self.assertEqual(parsed[5]["scores"], {"points": 4.0})  # buchholz ausente
        self.assertNotIn(None, parsed)
        self.assertEqual(parsed[7]["scores"], {"points": 2.5, "buchholz": 9.0})

    def test_plan_is_immutable(self):
        plan = build_tiebreak_plan(["buchholz"])
        self.assertIsInstance(plan, TiebreakPlan)
        with self.assertRaises(Exception):
            plan.specifiers = ("X",)  # frozen dataclass


class TestGacruxTiebreakEngine(unittest.TestCase):
    """Integracao: roda o tiebreakchecker.py real sobre um torneio fechado."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux_tb.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament(
            "Test Gacrux Tiebreak", rounds_count=3, bye_points=1.0
        )
        # Dados minimos para um TRF-16 valido (mesmo conjunto do teste de pareamento).
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Test Arbiter",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
        })
        self.player_ids = []
        for index, rating in enumerate([2200, 2100, 2000, 1900, 1800, 1700]):
            self.player_ids.append(self.db.create_player(
                self.tournament_id,
                f"Jogador {index + 1:03d}",
                club="Club",
                rating=rating,
                category="ABS",
                sex="m",
                birth_date="2000-01-01",
            ))

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def _play_round(self) -> None:
        round_data = self.pairing_service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(round_data["id"]):
            if not pairing["is_bye"]:
                self.pairing_service.update_result(self.tournament_id, pairing["id"], "1-0")
        self.pairing_service.close_round(self.tournament_id, round_data["id"])

    def test_compute_returns_ranks_and_scores_per_player(self):
        self._play_round()
        self._play_round()

        engine = GacruxTiebreakEngine(self.db)
        result = engine.compute(
            self.tournament_id,
            ["buchholz", "sonneborn_berger", "wins"],
            current_round=2,
        )

        # Todos os jogadores do TRF voltam mapeados para player_id.
        self.assertEqual(set(result.keys()), set(self.player_ids))
        for payload in result.values():
            self.assertGreaterEqual(payload["rank"], 1)
            self.assertLessEqual(payload["rank"], len(self.player_ids))
            for code in ("points", "buchholz", "sonneborn_berger", "wins"):
                self.assertIn(code, payload["scores"])

        ranks = sorted(payload["rank"] for payload in result.values())
        self.assertEqual(ranks[0], 1)  # ha um lider

        # O lider (rank 1) tem a maior pontuacao do campo.
        leader = min(result.values(), key=lambda payload: payload["rank"])
        top_points = max(payload["scores"]["points"] for payload in result.values())
        self.assertEqual(leader["scores"]["points"], top_points)

    def test_compute_without_closed_rounds_is_empty(self):
        engine = GacruxTiebreakEngine(self.db)
        self.assertEqual(engine.compute(self.tournament_id, ["buchholz"]), {})


class TestGacruxTiebreakStandings(unittest.TestCase):
    """Roteamento de standings() pelo motor configurado (Fase 2)."""

    def setUp(self) -> None:
        import src.services.pairing_service as ps
        ps._GACRUX_TIEBREAK_CACHE.clear()  # isola do estado de outros testes

        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux_tb_routing.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament(
            "Routing", rounds_count=3, bye_points=1.0
        )
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Test Arbiter",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
        })
        self.player_ids = [
            self.db.create_player(
                self.tournament_id, f"Jogador {i + 1:03d}", club="Club",
                rating=rating, category="ABS", sex="m", birth_date="2000-01-01",
            )
            for i, rating in enumerate([2200, 2100, 2000, 1900, 1800, 1700])
        ]
        for _ in range(2):
            round_data = self.pairing_service.generate_next_round(self.tournament_id)
            for pairing in self.db.get_pairings_for_round(round_data["id"]):
                if not pairing["is_bye"]:
                    self.pairing_service.update_result(self.tournament_id, pairing["id"], "1-0")
            self.pairing_service.close_round(self.tournament_id, round_data["id"])

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def _set_engine(self, engine: str) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": engine})

    def test_gacrux_engine_drives_standings(self):
        self._set_engine("gacrux")
        standings = self.pairing_service.standings(self.tournament_id)

        positions = sorted(item["position"] for item in standings)
        self.assertEqual(positions, list(range(1, len(self.player_ids) + 1)))
        # O caminho Gacrux carimba o rank do motor FIDE em cada linha.
        self.assertTrue(all("_gacrux_rank" in item for item in standings))

        # Os valores exibidos batem com o motor FIDE chamado diretamente.
        engine = GacruxTiebreakEngine(self.db)
        direct = engine.compute(
            self.tournament_id,
            ["buchholz", "buchholz_median", "sonneborn_berger", "wins"],
            current_round=2,
        )
        for item in standings:
            scores = direct[item["player_id"]]["scores"]
            self.assertEqual(item["tiebreak_values"]["buchholz"], scores["buchholz"])
            self.assertEqual(item["tiebreak_values"]["sonneborn_berger"], scores["sonneborn_berger"])

    def test_albericus_engine_keeps_own_calculation(self):
        self._set_engine("albericus")
        standings = self.pairing_service.standings(self.tournament_id)
        self.assertTrue(standings)
        # Sem motor FIDE: nenhuma linha carrega o rank do Gacrux.
        self.assertFalse(any("_gacrux_rank" in item for item in standings))

    def test_prizes_follow_gacrux_standings(self):
        # Fase 4: a premiacao consome standings() -> respeita o ranking do Gacrux
        # sem qualquer mudanca no motor de premios (contrato preservado).
        from src.services.prize_service import PrizeService
        self._set_engine("gacrux")
        prize_service = PrizeService(self.db)
        prize_service.replace_prizes(self.tournament_id, [
            {"kind": "overall", "label": "Campeao", "rank_from": 1, "rank_to": 1, "amount": 100.0},
        ])
        allocation = prize_service.allocate(self.tournament_id)
        standings = self.pairing_service.standings(self.tournament_id)
        leader = next(item for item in standings if item["position"] == 1)
        self.assertTrue(allocation["allocations"])
        winner = allocation["allocations"][0]
        self.assertEqual(winner["position"], 1)
        self.assertEqual(winner["player_id"], leader["player_id"])

    def test_trf_export_runs_in_gacrux_mode(self):
        # Fase 4: o export externo do TRF (nao-reentrante) usa o rank do Gacrux e
        # nao recai na recursao standings -> Gacrux -> export -> standings.
        from src.services.export_service import ExportService
        from src.services.federation_exporters.trf16 import TRF16Exporter
        self._set_engine("gacrux")
        export_service = ExportService(self.db, self.pairing_service)
        exporter = TRF16Exporter(export_service)
        out_path = Path(self.temp_dir.name) / "export.trf"
        exporter.export(self.tournament_id, out_path)
        self.assertTrue(out_path.exists())
        player_lines = [
            line for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("001 ")
        ]
        self.assertEqual(len(player_lines), len(self.player_ids))


class TestGacruxFideParity(unittest.TestCase):
    """Fase 6: confirma que o motor FIDE muda o calculo onde a FIDE diverge.

    Numero impar de jogadores => ha byes => o adversario virtual (item #1 do
    backlog) entra em acao: o Buchholz do motor Gacrux difere do calculo proprio
    (modo 'real', que ignora jogos nao disputados), enquanto os pontos sao
    identicos (mesmos resultados; so o desempate muda).
    """

    def setUp(self) -> None:
        import src.services.pairing_service as ps
        ps._GACRUX_TIEBREAK_CACHE.clear()

        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux_parity.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament("Parity", rounds_count=3, bye_points=1.0)
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Test Arbiter",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
        })
        # 5 jogadores (impar) garante um bye por rodada.
        self.player_ids = [
            self.db.create_player(
                self.tournament_id, f"Jogador {i + 1:03d}", club="Club",
                rating=rating, category="ABS", sex="m", birth_date="2000-01-01",
            )
            for i, rating in enumerate([2200, 2100, 2000, 1900, 1800])
        ]
        for _ in range(2):
            round_data = self.pairing_service.generate_next_round(self.tournament_id)
            for pairing in self.db.get_pairings_for_round(round_data["id"]):
                if not pairing["is_bye"]:
                    self.pairing_service.update_result(self.tournament_id, pairing["id"], "1-0")
            self.pairing_service.close_round(self.tournament_id, round_data["id"])

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def _standings_by_id(self, engine: str) -> dict[int, dict]:
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": engine})
        return {item["player_id"]: item for item in self.pairing_service.standings(self.tournament_id)}

    def test_virtual_opponent_changes_buchholz_but_not_points(self):
        gacrux = self._standings_by_id("gacrux")
        albericus = self._standings_by_id("albericus")

        # Mesmos resultados => pontos identicos nos dois motores.
        for pid in self.player_ids:
            self.assertEqual(
                gacrux[pid]["points"], albericus[pid]["points"],
                f"pontos divergiram para o jogador {pid}",
            )

        # O adversario virtual (FIDE) faz o Buchholz do Gacrux divergir do
        # calculo proprio em ao menos um jogador (os que pegaram bye).
        differs = [
            pid for pid in self.player_ids
            if gacrux[pid]["tiebreak_values"]["buchholz"]
            != albericus[pid]["tiebreak_values"]["buchholz"]
        ]
        self.assertTrue(
            differs,
            "Buchholz identico nos dois motores: adversario virtual nao aplicado.",
        )

    def test_wins_mapping_matches_without_forfeits(self):
        # Valida o mapeamento wins -> WON: sem W.O./forfeits, o numero de vitorias
        # do Albericus deve bater com o "games won" (WON) do Gacrux.
        gacrux = self._standings_by_id("gacrux")
        albericus = self._standings_by_id("albericus")
        for pid in self.player_ids:
            self.assertEqual(
                gacrux[pid]["tiebreak_values"]["wins"],
                albericus[pid]["tiebreak_values"]["wins"],
                f"vitorias (WON) divergiram para o jogador {pid}",
            )


if __name__ == "__main__":
    unittest.main()
