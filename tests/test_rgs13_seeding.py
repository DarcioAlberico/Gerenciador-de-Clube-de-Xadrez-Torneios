"""RGS-13 (F3.2) — uma única ordem inicial para o TRF, os dois motores e a aceleração.

FIDE C.04.2 (ordem inicial): força (rating), depois título FIDE
(GM, IM, WGM, FM, WIM, CM, WFM, WCM, sem título), depois ordem alfabética —
salvo regulamento. Antes:

- o TRF do Gacrux numerava pelo primeiro rating não nulo (internacional, depois
  principal, depois nacional) e ignorava ``initial_order``;
- os dois motores desempatavam rating só pelo nome: "Alpha" sem título passava
  à frente de "Zeta" GM.

Com ``initial_order=national_rating`` o Gacrux dava A-C/D-B e o motor próprio,
o correto, B-D/C-A.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from src.core.database import Database
from src.services.pairing.constraints import seeding_key
from src.services.pairing.fide_dutch import first_round_pairings
from src.services.pairing.gacrux_engine import GacruxEngine
from src.services.pairing_service import PairingService


def _jogador(pid: int, nome: str, rating: int = 2000, titulo: str = "", **extra) -> dict:
    return {"id": pid, "name": nome, "rating": rating, "title": titulo, **extra}


class SeedingKeyTest(unittest.TestCase):
    def test_rating_depois_titulo_depois_nome(self) -> None:
        jogadores = [
            _jogador(1, "Alpha"),
            _jogador(2, "Zeta", titulo="GM"),
            _jogador(3, "Beta", rating=2100),
            _jogador(4, "Gama", titulo="FM"),
        ]
        ordem = sorted(jogadores, key=lambda p: seeding_key(p, "rating"))
        self.assertEqual(["Beta", "Zeta", "Gama", "Alpha"], [p["name"] for p in ordem])

    def test_ordem_dos_titulos_e_a_do_c04(self) -> None:
        titulos = ["", "WCM", "WFM", "CM", "WIM", "FM", "WGM", "IM", "GM"]
        jogadores = [_jogador(i, "Mesmo Nome", titulo=t) for i, t in enumerate(titulos, start=1)]
        ordem = sorted(jogadores, key=lambda p: seeding_key(p, "rating"))
        self.assertEqual(list(reversed(titulos)), [p["title"] for p in ordem])

    def test_titulo_no_dialeto_trf_tambem_conta(self) -> None:
        """O TRF grava `g`, `m`, `wg`...; jogador importado pode vir assim."""
        ordem = sorted(
            [_jogador(1, "Alpha"), _jogador(2, "Zeta", titulo="g")],
            key=lambda p: seeding_key(p, "rating"),
        )
        self.assertEqual("Zeta", ordem[0]["name"])

    def test_ordem_inicial_escolhe_o_rating(self) -> None:
        a = _jogador(1, "A", rating=2000, national_rating=1500)
        d = _jogador(2, "D", rating=1700, national_rating=1800)
        ordem = sorted([a, d], key=lambda p: seeding_key(p, "national_rating"))
        self.assertEqual(["D", "A"], [p["name"] for p in ordem])


class _Torneio(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(db_path=Path(self._tmp.name) / "t.db", backup_dir=Path(self._tmp.name) / "bk")
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-13", rounds_count=5, bye_points=1.0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _configurar(self, **extra) -> None:
        self.db.save_tournament_settings(self.tid, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Arbitro",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
            **extra,
        })

    def _alpha_zeta(self) -> dict[str, int]:
        return {
            "Alpha": self.db.create_player(self.tid, "Alpha", rating=2000, sex="m", birth_date="2000"),
            "Zeta": self.db.create_player(self.tid, "Zeta", rating=2000, title="GM", sex="m", birth_date="2000"),
            "Carlos": self.db.create_player(self.tid, "Carlos", rating=1900, sex="m", birth_date="2000"),
            "Davi": self.db.create_player(self.tid, "Davi", rating=1800, sex="m", birth_date="2000"),
        }

    def _nacional(self) -> dict[str, int]:
        """Ordem por rating: A, B, C, D (A-C, B-D). Ordem nacional: A, C, B, D (A-B, C-D)."""
        return {
            nome: self.db.create_player(
                self.tid, nome, rating=rating, national_rating=nacional, sex="m", birth_date="2000"
            )
            for nome, rating, nacional in (
                ("A", 2000, 1800), ("B", 1900, 1600), ("C", 1800, 1700), ("D", 1700, 1500),
            )
        }

    def _pares(self, rodada: dict) -> set[frozenset[int]]:
        return {
            frozenset((int(p["white_player_id"]), int(p["black_player_id"])))
            for p in self.db.get_pairings_for_round(int(rodada["id"]))
            if not p["is_bye"]
        }


class MotorProprioTest(_Torneio):
    def test_gm_e_o_numero_1_no_empate_de_rating(self) -> None:
        self._configurar(pairing_system="fide_dutch")
        ids = self._alpha_zeta()
        settings = self.db.get_tournament_settings(self.tid)
        jogadores = self.db.list_players(self.tid, active_only=True)
        self.assertEqual(ids["Zeta"], self.service._seeding(jogadores, settings)[0])
        mesa1 = first_round_pairings(jogadores, settings)[0]
        self.assertEqual({ids["Zeta"], ids["Carlos"]}, {mesa1["white_player_id"], mesa1["black_player_id"]})


class NumeracaoDoTrfTest(_Torneio):
    def _numeracao(self) -> dict[int, int]:
        with tempfile.TemporaryDirectory() as tmp:
            return GacruxEngine(self.db).write_pairing_trf(self.tid, 1, Path(tmp) / "r1.trf")

    def test_gm_e_o_numero_1_no_trf(self) -> None:
        self._configurar(pairing_system="gacrux_swiss")
        ids = self._alpha_zeta()
        self.assertEqual(ids["Zeta"], self._numeracao()[1])

    def test_trf_numera_pela_ordem_inicial_do_torneio(self) -> None:
        self._configurar(pairing_system="gacrux_swiss", initial_order="national_rating")
        ids = self._nacional()
        numeracao = self._numeracao()
        self.assertEqual([ids[n] for n in "ACBD"], [numeracao[r] for r in (1, 2, 3, 4)])


@pytest.mark.gacrux
class GacruxRealTest(_Torneio):
    def test_gm_e_o_numero_1_no_gacrux(self) -> None:
        self._configurar(pairing_system="gacrux_swiss")
        ids = self._alpha_zeta()
        pares = self._pares(self.service.generate_next_round(self.tid))
        self.assertIn(frozenset((ids["Zeta"], ids["Carlos"])), pares)

    def test_rating_nacional_da_o_mesmo_pareamento_nos_dois_motores(self) -> None:
        self._configurar(pairing_system="gacrux_swiss", initial_order="national_rating")
        ids = self._nacional()
        gacrux = self._pares(self.service.generate_next_round(self.tid))
        esperado = {frozenset((ids["A"], ids["B"])), frozenset((ids["C"], ids["D"]))}
        self.assertEqual(esperado, gacrux)
        settings = self.db.get_tournament_settings(self.tid)
        proprio = {
            frozenset((p["white_player_id"], p["black_player_id"]))
            for p in first_round_pairings(self.db.list_players(self.tid, active_only=True), settings)
        }
        self.assertEqual(esperado, proprio)


if __name__ == "__main__":
    unittest.main()
