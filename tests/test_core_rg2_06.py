"""RG2-06 — jogador ausente do resultado do motor de desempate não vai ao 1º lugar.

Duas portas:

1. ``GacruxTiebreakEngine.run`` confere a resposta contra o pedido: um
   competidor por número do TRF, ``tiebreakScore`` com uma coluna por critério,
   valores numéricos, rank positivo. Resposta que não confere é falha do motor
   (``AppError``), e a classificação cai no motor próprio com o evento de
   auditoria de sempre.
2. Na ordenação, quem ficou sem rank do motor (o entrante tardio, fora do TRF
   das rodadas fechadas) vai depois de todos os ranqueados com a mesma
   pontuação — antes ia para a frente de todos (``rank or 0``).
"""
from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from src.services import pairing_service as ps
from src.services.constants import AppError
from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine, TiebreakJob
from src.services.pairing.gacrux_tiebreak_map import build_tiebreak_plan
from src.services.pairing.team_tiebreaks import calculate_team_standings
from src.services.pairing.tiebreak_engine import ENGINE_GACRUX
from src.services.pairing.tiebreaks import order_player_standings
from tests.support.core_service_base import CoreServiceTestCase


def _job(jogadores: int = 2) -> TiebreakJob:
    plan = build_tiebreak_plan(["buchholz"])
    return GacruxTiebreakEngine._job(
        b"", plan, 1, True, tuple((cid, 100 + cid) for cid in range(1, jogadores + 1))
    )


def _competidor(cid: Any, rank: Any = None, scores: Any = None) -> dict[str, Any]:
    return {"cid": cid, "rank": cid if rank is None else rank, "tiebreakScore": [1.0, 2.0] if scores is None else scores}


class RespostaDoMotorConferidaTest(unittest.TestCase):
    def _rodar(self, resposta: dict[str, Any], jogadores: int = 2) -> dict[int, dict[str, Any]]:
        motor = GacruxTiebreakEngine.__new__(GacruxTiebreakEngine)
        with mock.patch.object(GacruxTiebreakEngine, "_run_tiebreakchecker", return_value=resposta):
            return motor.run(_job(jogadores))

    def test_resposta_completa_passa(self) -> None:
        saida = self._rodar({"tiebreakResult": {"competitors": [_competidor(1), _competidor(2)]}})
        self.assertEqual({101, 102}, set(saida))
        self.assertEqual(1, saida[101]["rank"])

    def test_resposta_vazia_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {}})

    def test_competidor_que_falta_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {"competitors": [_competidor(1)]}})

    def test_competidor_que_nao_foi_pedido_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {"competitors": [_competidor(1), _competidor(3)]}})

    def test_coluna_que_falta_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {"competitors": [_competidor(1), _competidor(2, scores=[1.0])]}})

    def test_valor_ilegivel_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {"competitors": [_competidor(1), _competidor(2, scores=[1.0, "x"])]}})

    def test_rank_ausente_e_falha_do_motor(self) -> None:
        with self.assertRaises(AppError):
            self._rodar({"tiebreakResult": {"competitors": [_competidor(1), _competidor(2, rank=0)]}})


def _jogador(pid: int, nome: str, pontos: float, rank: int | None) -> dict[str, Any]:
    item: dict[str, Any] = {"player_id": pid, "name": nome, "points": pontos, "rating": 2000}
    if rank is not None:
        item["_gacrux_rank"] = rank
    return item


class SemRankVaiDepoisDoGrupoTest(unittest.TestCase):
    def test_tardio_sem_rank_nao_passa_ninguem_da_mesma_pontuacao_nem_acima(self) -> None:
        stats = {
            1: _jogador(1, "J2", 2.0, 1),
            2: _jogador(2, "J0", 1.0, 2),
            3: _jogador(3, "J1", 1.0, 3),
            4: _jogador(4, "Tardio", 1.0, None),
            5: _jogador(5, "J3", 0.0, 4),
        }
        ordem = [item["name"] for item in order_player_standings(stats)]
        self.assertEqual(["J2", "J0", "J1", "Tardio", "J3"], ordem)

    def test_todos_com_rank_seguem_o_rank_do_motor(self) -> None:
        """Caracterização: sem ninguém faltando, o rank do motor manda."""
        stats = {
            1: _jogador(1, "A", 2.0, 2),
            2: _jogador(2, "B", 2.0, 1),
        }
        self.assertEqual(["B", "A"], [item["name"] for item in order_player_standings(stats)])


class EquipeSemRankVaiDepoisDoGrupoTest(unittest.TestCase):
    def test_equipe_sem_rank_nao_vai_ao_primeiro_lugar(self) -> None:
        equipes = [
            {"id": index, "name": f"Equipe {index}", "club": "", "captain": "", "active": 1}
            for index in (1, 2, 3)
        ]
        partida = {
            "id": 1, "round_number": 1, "white_team_id": 1, "black_team_id": 2, "is_bye": 0,
            "white_match_points": 2.0, "black_match_points": 0.0,
            "white_game_points": 3.0, "black_game_points": 1.0, "boards": [],
        }
        gacrux = {1: {"rank": 1, "scores": {}}, 2: {"rank": 2, "scores": {}}}
        ordem = calculate_team_standings({}, equipes, [partida], gacrux_tiebreaks=gacrux)
        self.assertEqual("Equipe 1", ordem[0]["name"])


class FallbackAuditadoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": ENGINE_GACRUX})

    def test_saida_vazia_do_motor_vira_fallback_auditado(self) -> None:
        with mock.patch.object(
            GacruxTiebreakEngine, "_run_tiebreakchecker", return_value={"tiebreakResult": {}}
        ):
            classificacao = self.service.standings(self.tournament_id)

        self.assertFalse(any("_gacrux_rank" in item for item in classificacao))
        self.assertTrue(self.service.tiebreak_engine_report(self.tournament_id).fallback)
        eventos = self.db.list_audit_events(
            self.tournament_id, action="tiebreak_engine_fallback", limit=10
        )
        self.assertEqual(1, len(eventos))


class EntrantesFuturosSoNaTelaTest(unittest.TestCase):
    def test_entrante_de_rodada_nao_comecada_vai_para_a_secao(self) -> None:
        from src.ui.screens.pairings import split_future_entrants

        classificacao = [
            {"player_id": 1, "name": "J2"},
            {"player_id": 4, "name": "Tardio"},
            {"player_id": 2, "name": "J0"},
        ]
        principais, futuros = split_future_entrants(classificacao, {1: 1, 2: 1, 4: 3}, 2)

        self.assertEqual(["J2", "J0"], [item["name"] for item in principais])
        self.assertEqual({3: ["Tardio"]}, {r: [i["name"] for i in itens] for r, itens in futuros.items()})

    def test_com_a_rodada_de_entrada_gerada_ele_volta_a_lista(self) -> None:
        from src.ui.screens.pairings import split_future_entrants

        principais, futuros = split_future_entrants([{"player_id": 4, "name": "Tardio"}], {4: 3}, 3)

        self.assertEqual(["Tardio"], [item["name"] for item in principais])
        self.assertEqual({}, futuros)
