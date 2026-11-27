"""RGS-15 (F3.3) — proibição de pareamento vai ao Gacrux pelo registro 260.

Antes, uma única proibição ativa derrubava a rodada inteira para o motor
reserva (``fide_dutch``), em silêncio para o árbitro: o TRF do pareamento não
levava o registro 260 (TRF25 §5.2), que o Gacrux lê (``trf2json.parse_trf_
prohibited`` -> ``crosstable.list_edges``: o par fica ``canmeet = False``).

Agora o arquivo do pareamento leva um 260 por proibição que vale NA rodada, e a
rodada continua saindo do motor FIDE.

Dialeto: o Gacrux lê ``lastRound = 0`` como "só a primeira rodada", e no
Albericus ``last_round = 0`` quer dizer "até o fim". Por isso o 260 sai sempre
com ``first = last = rodada pareada``.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from src.core.database import Database
from src.services.pairing.gacrux_engine import GacruxEngine
from src.services.pairing.gacrux_trf import prohibition_records
from src.services.pairing_service import PairingService


class RegistroDeProibicaoTest(unittest.TestCase):
    RANKS = {10: 1, 20: 2, 30: 3, 40: 4}

    def _proibicao(self, a: int, b: int, primeira: int = 1, ultima: int = 0) -> dict:
        return {"player_a_id": a, "player_b_id": b, "first_round": primeira, "last_round": ultima}

    def test_proibicao_da_rodada_vira_260_nas_colunas_do_gacrux(self) -> None:
        (linha,) = prohibition_records([self._proibicao(30, 10)], 2, self.RANKS)
        # Fatias de `gacrux/trf2json.parse_trf_prohibited` (0-based).
        self.assertEqual("260", linha[0:3])
        self.assertEqual(2, int(linha[4:7]))
        self.assertEqual(2, int(linha[8:11]))
        self.assertEqual([1, 3], [int(linha[12:16]), int(linha[17:21])])

    def test_proibicao_fora_da_rodada_nao_entra(self) -> None:
        proibicoes = [self._proibicao(10, 20, primeira=3), self._proibicao(10, 30, ultima=1)]
        self.assertEqual([], prohibition_records(proibicoes, 2, self.RANKS))

    def test_jogador_fora_do_torneio_nao_entra(self) -> None:
        self.assertEqual([], prohibition_records([self._proibicao(10, 99)], 1, self.RANKS))


class _Torneio(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(db_path=Path(self._tmp.name) / "t.db", backup_dir=Path(self._tmp.name) / "bk")
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-15", rounds_count=5, bye_points=1.0)
        self.db.save_tournament_settings(self.tid, {
            "pairing_system": "gacrux_swiss",
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Arbitro",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-06-09",
            "end_date": "2026-06-09",
        })
        # Ordem inicial 1..4: a R1 natural seria 1-3 e 2-4.
        self.ids = [
            self.db.create_player(self.tid, f"J{i}", rating=2000 - 100 * i, sex="m", birth_date="2000")
            for i in range(4)
        ]
        self.db.add_prohibited_pairing(self.tid, self.ids[0], self.ids[2], reason="irmaos")

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TrfDoPareamentoTest(_Torneio):
    def test_trf_do_pareamento_leva_o_260(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "r1.trf"
            GacruxEngine(self.db).write_pairing_trf(self.tid, 1, caminho)
            linhas = caminho.read_text(encoding="utf-8").splitlines()
        self.assertEqual(["260   1   1    1    3"], [linha for linha in linhas if linha.startswith("260")])

    def test_rodada_com_proibicao_continua_no_gacrux(self) -> None:
        """Sem rodar o motor: a geração CHAMA o Gacrux em vez de cair no reserva."""
        respostas = [
            {"board_number": 1, "white_player_id": self.ids[0], "black_player_id": self.ids[3],
             "result": "", "is_bye": 0},
            {"board_number": 2, "white_player_id": self.ids[1], "black_player_id": self.ids[2],
             "result": "", "is_bye": 0},
        ]
        with mock.patch.object(GacruxEngine, "pair_round", return_value=respostas) as motor:
            self.service.generate_next_round(self.tid)
        motor.assert_called_once()


@pytest.mark.gacrux
class GacruxRealTest(_Torneio):
    def test_gacrux_respeita_a_proibicao(self) -> None:
        original = GacruxEngine.pair_round
        with mock.patch.object(GacruxEngine, "pair_round", autospec=True, side_effect=original) as motor:
            rodada = self.service.generate_next_round(self.tid)
        motor.assert_called_once()
        pares = {
            frozenset((int(p["white_player_id"]), int(p["black_player_id"])))
            for p in self.db.get_pairings_for_round(int(rodada["id"]))
            if not p["is_bye"]
        }
        self.assertEqual(2, len(pares))
        self.assertNotIn(frozenset((self.ids[0], self.ids[2])), pares)


if __name__ == "__main__":
    unittest.main()
