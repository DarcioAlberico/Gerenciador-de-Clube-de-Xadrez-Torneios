"""RGS-19 — a saída do Gacrux é conferida antes de virar rodada.

Antes, ``GacruxEngine.pair_round`` pulava em silêncio o número sem
mapeamento e aceitava jogador repetido: uma saída corrompida virava uma rodada
com gente faltando ou em duas mesas. Agora cada jogador a parear aparece
exatamente uma vez, ninguém de fora aparece, e o contrário é ``AppError`` com
o TRF de entrada no log.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from src.services.constants import AppError
from src.services.pairing.gacrux_engine import GacruxEngine, pairings_from_gacrux
from tests.support.core_service_base import CoreServiceTestCase

# Start-rank do TRF -> id do jogador. O 5 existe no torneio mas não joga a rodada.
MAPA = {1: 11, 2: 12, 3: 13, 4: 14, 5: 15}
A_PAREAR = {1, 2, 3, 4}


class ConferenciaDosParesTest(unittest.TestCase):
    def test_saida_correta_vira_mesas_e_bye(self) -> None:
        mesas = pairings_from_gacrux([[1, 3], [4, 2]], MAPA, A_PAREAR)
        self.assertEqual(
            [(11, 13), (14, 12)],
            [(m["white_player_id"], m["black_player_id"]) for m in mesas],
        )
        mesas = pairings_from_gacrux([[1, 3], [2, 0]], MAPA, {1, 2, 3})
        self.assertEqual([1, 2], [m["board_number"] for m in mesas])
        self.assertEqual(12, mesas[1]["white_player_id"])
        self.assertEqual(1, mesas[1]["is_bye"])

    def test_jogador_duplicado_e_recusado(self) -> None:
        with self.assertRaises(AppError) as ctx:
            pairings_from_gacrux([[1, 3], [3, 2], [4, 0]], MAPA, A_PAREAR)
        self.assertIn("mais de uma vez", str(ctx.exception))

    def test_jogador_faltante_e_recusado(self) -> None:
        with self.assertRaises(AppError) as ctx:
            pairings_from_gacrux([[1, 3]], MAPA, A_PAREAR)
        self.assertIn("faltando", str(ctx.exception))

    def test_jogador_que_nao_devia_jogar_e_recusado(self) -> None:
        with self.assertRaises(AppError) as ctx:
            pairings_from_gacrux([[1, 3], [2, 5], [4, 0]], MAPA, A_PAREAR)
        self.assertIn("não deveria", str(ctx.exception))

    def test_numero_desconhecido_e_recusado(self) -> None:
        with self.assertRaises(AppError):
            pairings_from_gacrux([[1, 3], [2, 4], [9, 0]], MAPA, A_PAREAR)

    def test_saida_vazia_diz_que_nao_ha_pareamento_legal(self) -> None:
        """O Gacrux devolve ``pairs: []`` com status 0 quando nada respeita o C.04.1."""
        with self.assertRaises(AppError) as ctx:
            pairings_from_gacrux([], MAPA, A_PAREAR)
        self.assertIn("critérios absolutos", str(ctx.exception))

    def test_dois_byes_sao_recusados(self) -> None:
        with self.assertRaises(AppError):
            pairings_from_gacrux([[1, 3], [2, 0], [4, 0]], MAPA, A_PAREAR)


class SaidaCorrompidaNoMotorTest(CoreServiceTestCase):
    """``pair_round`` com um Gacrux falso que devolve JSON corrompido."""

    def _gacrux_falso(self, pares: list[list[int]]):
        def run(cmd, **_kwargs):
            saida = Path(cmd[cmd.index("-o") + 1])
            saida.write_text(
                json.dumps({"status": {"code": 0}, "pairingResult": {"pairs": pares}}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        return run

    def test_json_com_jogador_duplicado_e_recusado_com_o_trf_no_log(self) -> None:
        self._create_players(4)
        jogadores = self.db.list_players(self.tournament_id, active_only=True)
        motor = GacruxEngine(self.db)
        with mock.patch(
            "src.services.pairing.gacrux_engine.subprocess.run",
            side_effect=self._gacrux_falso([[1, 2], [2, 3]]),
        ), self.assertLogs("src.services.pairing.gacrux_engine", level="ERROR") as log:
            with self.assertRaises(AppError):
                motor.pair_round(self.tournament_id, jogadores, 1)
        texto = "\n".join(log.output)
        self.assertIn("001", texto)  # o TRF que gerou a saída vai junto


if __name__ == "__main__":
    unittest.main()
