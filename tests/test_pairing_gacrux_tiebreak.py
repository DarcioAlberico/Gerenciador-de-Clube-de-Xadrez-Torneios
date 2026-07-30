"""Fase 1 da integracao de desempates FIDE via Gacrux.

Cobre o modulo PURO de mapeamento (sem subprocesso) e um teste de integracao do
motor de I/O ``GacruxTiebreakEngine`` (roda o ``tiebreakchecker.py`` real, como
os testes de pareamento Gacrux ja fazem).
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.core.database import Database
from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
from src.services.pairing.gacrux_tiebreak_map import (
    POINTS_CODE,
    TiebreakPlan,
    build_team_tiebreak_plan,
    build_tiebreak_plan,
    parse_competitors,
)
from src.services.pairing_service import PairingService
from src.services.tournament_service import TeamService, TournamentService


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

    def test_build_team_plan_maps_team_codes(self):
        plan = build_team_tiebreak_plan(["match_points", "game_points", "buchholz", "wins"])
        self.assertEqual(plan.specifiers, ("MPTS", "GPTS", "BH", "WON"))
        self.assertEqual(plan.code_order, ("match_points", "game_points", "buchholz", "wins"))

    def test_build_team_plan_falls_back_to_match_points(self):
        plan = build_team_tiebreak_plan([])
        self.assertEqual(plan.specifiers, ("MPTS",))
        self.assertEqual(plan.code_order, ("match_points",))

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


class TestGacruxTeamTiebreaks(unittest.TestCase):
    """Fase 5 (follow-up): desempate por EQUIPES via Gacrux (TRF-25 -> isteam).

    Com o placar padrao FIDE (2/1/0), os match/game points do Gacrux devem bater
    com os do motor proprio — valida o round-trip TRF-25 e o mapa cid->team_id.
    """

    def setUp(self) -> None:
        import src.services.pairing_service as ps
        ps._GACRUX_TIEBREAK_CACHE.clear()

        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux_team.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.tournament_id = self.tournament_service.create_tournament({
            "name": "Interclubes", "competition_type": "team",
            "rounds_count": "3", "bye_points": "1",
        })
        self.db.save_tournament_settings(self.tournament_id, {
            "team_boards_count": "2",
            "team_match_win_points": "2", "team_match_draw_points": "1", "team_match_loss_points": "0",
            "team_pairing_method": "swiss",
            "team_standing_primary": "match_points", "team_standing_secondary": "game_points",
            "time_control": "10 min", "chief_arbiter": "Arb", "federation": "BRA",
            "location": "Sao Paulo", "start_date": "2026-06-09", "end_date": "2026-06-10",
        })
        self.team_ids = []
        for team_index in range(4):
            team_id = self.team_service.create_team(self.tournament_id, {
                "name": f"Equipe {team_index + 1}",
                "club": f"Clube {team_index + 1}",
                "captain": f"Cap {team_index + 1}",
            })
            self.team_ids.append(team_id)
            for board in range(1, 3):
                player_id = self.db.create_player(
                    self.tournament_id, name=f"E{team_index + 1} J{board}",
                    rating=2200 - team_index * 100 - board * 10, club=f"Clube {team_index + 1}",
                )
                self.team_service.add_player(team_id, player_id, board_number=str(board), role="starter")
        for _ in range(2):
            round_data = self.pairing_service.generate_next_round(self.tournament_id)
            for match in self.db.list_team_matches_for_round(round_data["id"]):
                if match["is_bye"]:
                    continue
                for board in self.db.list_team_boards(match["id"]):
                    self.pairing_service.update_result(self.tournament_id, board["id"], "1-0")
            self.pairing_service.close_round(self.tournament_id, round_data["id"])

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def _team_standings_by_id(self, engine: str) -> dict[int, dict]:
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": engine})
        return {item["team_id"]: item for item in self.pairing_service.team_standings(self.tournament_id)}

    def test_gacrux_team_engine_matches_points_and_ranks(self):
        gacrux = self._team_standings_by_id("gacrux")
        albericus = self._team_standings_by_id("albericus")

        self.assertEqual(set(gacrux.keys()), set(self.team_ids))
        # Placar padrao 2/1/0 => match/game points do Gacrux == motor proprio.
        for team_id in self.team_ids:
            self.assertEqual(gacrux[team_id]["match_points"], albericus[team_id]["match_points"])
            self.assertEqual(gacrux[team_id]["game_points"], albericus[team_id]["game_points"])

        self.assertTrue(all("_gacrux_rank" in item for item in gacrux.values()))
        positions = sorted(item["position"] for item in gacrux.values())
        self.assertEqual(positions, list(range(1, len(self.team_ids) + 1)))

    def test_albericus_team_engine_has_no_gacrux_rank(self):
        albericus = self._team_standings_by_id("albericus")
        self.assertTrue(albericus)
        self.assertFalse(any("_gacrux_rank" in item for item in albericus.values()))

    def test_ajuste_de_pontos_nao_derruba_o_motor(self):
        """Registro 299 no TRF-25 deixou de matar o subprocesso.

        O `parse_trf_abnormal` do Gacrux v1.9.52 lia a rodada da fatia do
        gamePoints: com "-0.5" o `parse_int` estourava e o motor morria. O
        Albericus caia no motor proprio em silencio — exatamente o que a TBK-02
        passou a denunciar. Depois do patch local, o 299 e lido e ignorado pelo
        desempate (o ajuste quem aplica e o Albericus, TBK-01) e o rank do motor
        continua chegando.
        """
        import src.services.pairing_service as ps
        ps._GACRUX_TIEBREAK_CACHE.clear()

        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=1,
            team_id=self.team_ids[0],
            match_points=-2.0,
            game_points=-0.5,
            reason="Escalacao irregular",
        )
        gacrux = self._team_standings_by_id("gacrux")

        self.assertTrue(
            all("_gacrux_rank" in item for item in gacrux.values()),
            "sem _gacrux_rank o motor caiu e a classificacao veio do motor proprio",
        )
        punida = gacrux[self.team_ids[0]]
        self.assertEqual(-2.0, punida["adjustment_match_points"])
        self.assertEqual(-0.5, punida["adjustment_game_points"])


class TestGacruxRoundRobin(unittest.TestCase):
    """Round-robin: o motor deve usar regras pre-determinadas (-p), nao Suico (-s).

    Os tiebreaks da FIDE diferem entre Suico e round-robin, entao o flag enviado
    ao tiebreakchecker depende do metodo de pareamento do torneio.
    """

    def setUp(self) -> None:
        import src.services.pairing_service as ps
        ps._GACRUX_TIEBREAK_CACHE.clear()

        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_gacrux_rr.db"
        self.db = Database(db_path=str(db_path))
        self.db.connect()
        self.db.initialize()
        self.pairing_service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament("RR", rounds_count=3, bye_points=1.0)
        self.db.save_tournament_settings(self.tournament_id, {
            "time_control": "10 min", "chief_arbiter": "Arb", "federation": "BRA",
            "location": "Sao Paulo", "start_date": "2026-06-09", "end_date": "2026-06-09",
        })
        self.player_ids = [
            self.db.create_player(
                self.tournament_id, f"Jogador {i + 1:03d}", club="Club",
                rating=rating, category="ABS", sex="m", birth_date="2000-01-01",
            )
            for i, rating in enumerate([2200, 2100, 2000, 1900])
        ]

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def _configure_and_play(self, pairing_method: str, n_rounds: int) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"pairing_method": pairing_method})
        for _ in range(n_rounds):
            round_data = self.pairing_service.generate_next_round(self.tournament_id)
            for pairing in self.db.get_pairings_for_round(round_data["id"]):
                if not pairing["is_bye"]:
                    self.pairing_service.update_result(self.tournament_id, pairing["id"], "1-0")
            self.pairing_service.close_round(self.tournament_id, round_data["id"])

    def _capture_tiebreak_flag(self) -> list[str]:
        """Roda compute() com o subprocesso mockado e devolve o cmd capturado."""
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            out_path = cmd[cmd.index("-o") + 1]
            Path(out_path).write_text(
                json.dumps({"status": {"code": 0}, "tiebreakResult": {"competitors": []}}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with mock.patch(
            "src.services.pairing.gacrux_tiebreak_engine.subprocess.run", side_effect=fake_run
        ):
            GacruxTiebreakEngine(self.db).compute(self.tournament_id, ["buchholz"])
        return captured["cmd"]

    def test_round_robin_passes_predetermined_flag(self):
        self._configure_and_play("round_robin", 1)
        cmd = self._capture_tiebreak_flag()
        self.assertIn("-p", cmd)
        self.assertNotIn("-s", cmd)

    def test_swiss_still_passes_swiss_flag(self):
        self._configure_and_play("swiss", 1)
        cmd = self._capture_tiebreak_flag()
        self.assertIn("-s", cmd)
        self.assertNotIn("-p", cmd)

    def test_round_robin_standings_end_to_end(self):
        # RR completo (3 rodadas, 4 jogadores) calculado pelo Gacrux real com -p.
        self._configure_and_play("round_robin", 3)
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": "gacrux"})
        standings = self.pairing_service.standings(self.tournament_id)
        positions = sorted(item["position"] for item in standings)
        self.assertEqual(positions, list(range(1, len(self.player_ids) + 1)))
        self.assertTrue(all("_gacrux_rank" in item for item in standings))


class TestRegistro299RoundTrip(unittest.TestCase):
    """O que o Albericus escreve no 299, o Gacrux tem de ler igual.

    Teste rapido (sem subprocesso) do patch local em `parse_trf_abnormal`: e o
    unico lugar onde o escritor e o leitor do registro 299 se encontram, e as
    tres colunas em disputa (rodada, entidades) sao aritmetica de posicao, que
    quebra em silencio. Importa o modulo do motor com o diretorio dele no
    sys.path porque o Gacrux usa imports planos (`import qdefs`).
    """

    def _parser(self):
        gacrux_dir = str(
            Path(__file__).resolve().parent.parent
            / "src" / "services" / "pairing" / "gacrux"
        )
        if gacrux_dir not in sys.path:
            sys.path.insert(0, gacrux_dir)
        from trf2json import trf2json

        return trf2json()

    def test_rodada_e_entidades_voltam_das_colunas_certas(self):
        from src.services.federation_exporters.trf25_records import record_299

        parser = self._parser()
        parser.parse_trf_abnormal({}, record_299("", 0.0, -0.5, 3, [7]).rstrip())
        parser.parse_trf_abnormal({}, record_299("W", -2.0, -1.0, 0, [2, 9]).rstrip())

        primeiro, segundo = parser.aatlist
        self.assertEqual(3, primeiro["round"], "rodada lida da fatia do gamePoints")
        self.assertEqual([7], primeiro["teams"])
        self.assertEqual(-0.5, float(primeiro["gamePoints"]))
        self.assertEqual(0, segundo["round"])
        self.assertEqual([2, 9], segundo["teams"])
        self.assertEqual(-2.0, float(segundo["matchPoints"]))
        self.assertEqual("W", segundo["att"])

    def test_ajuste_nominal_nao_redefine_o_sistema_de_pontos(self):
        """Com entidade nomeada o 299 vai para a lista, e nao ao score system.

        `add_unplayed` reescreveria quanto vale um jogo nao disputado no torneio
        inteiro — consequencia bem maior do que a penalidade de um competidor.
        """
        from src.services.federation_exporters.trf25_records import record_299

        parser = self._parser()
        # `scores` nasce so quando o motor le um torneio; aqui um espiao basta.
        parser.scores = mock.Mock()
        parser.parse_trf_abnormal({}, record_299("", 0.0, -0.5, 0, [4]).rstrip())

        parser.scores.add_unplayed.assert_not_called()
        self.assertEqual(1, len(parser.aatlist))


if __name__ == "__main__":
    unittest.main()
