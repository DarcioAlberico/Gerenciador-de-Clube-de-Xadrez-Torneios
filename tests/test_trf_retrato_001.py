"""Linha 001 no retrato de uma rodada antiga (``up_to_round=N``).

O retrato cortava as células, os inscritos e o status na rodada N, mas o campo
de pontos (81-84) e a posição (86-89) da linha 001 saíam da classificação de
HOJE. O arquivo da R1 de um torneio na R3 dizia, na mesma linha, "1 ponto nas
células" e "3 pontos, 1º lugar". Os dois campos agora são os do retrato da
classificação da rodada N — o mesmo que o fechamento da rodada grava.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from src.services.pairing.gacrux_trf import declared_points, implied_points, is_player_line
from src.services.trf_layout import POINTS, RANK, START_RANK, field
from tests.support.core_service_base import CoreServiceTestCase


class Linha001NoRetratoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(6)
        for _ in range(3):
            rodada = self.service.generate_next_round(self.tournament_id)
            self._fill_decisive_results(int(rodada["id"]))
            self.service.close_round(self.tournament_id, int(rodada["id"]))

    def _retrato_da_classificacao(self, rodada: int) -> dict[int, tuple[float, int]]:
        """``{player_id: (pontos, posição)}`` gravado no fechamento da rodada."""
        retrato = next(
            item
            for item in self.db.list_standings_snapshots(self.tournament_id)
            if int(item["round_number"]) == rodada
        )
        return {
            int(linha["player_id"]): (float(linha["points"]), int(linha["position"]))
            for linha in json.loads(retrato["standings_json"])
        }

    def _linha_001_por_jogador(self, linhas: list[str], rodada: int) -> dict[int, tuple[float, int]]:
        numeros = {
            numero: int(jogador["id"])
            for numero, jogador in enumerate(
                TRF16Exporter(self.export_service).players(self.tournament_id, up_to_round=rodada),
                start=1,
            )
        }
        return {
            numeros[int(field(linha, START_RANK))]: (
                float(field(linha, POINTS)),
                int(field(linha, RANK)),
            )
            for linha in linhas
            if linha.startswith("001")
        }

    def _trf16(self, rodada: int) -> list[str]:
        return TRF16Exporter(self.export_service).render(
            self.tournament_id, up_to_round=rodada
        ).splitlines()

    def _trf25(self, rodada: int) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            TRF25Exporter(self.export_service).export(
                self.tournament_id, destino, up_to_round=rodada
            )
            return destino.read_text(encoding="utf-8").splitlines()

    def test_o_cenario_distingue_a_r1_de_hoje(self) -> None:
        self.assertNotEqual(self._retrato_da_classificacao(1), self._retrato_da_classificacao(3))

    def test_trf16_da_r1_traz_pontos_e_posicao_da_r1(self) -> None:
        self.assertEqual(
            self._retrato_da_classificacao(1),
            self._linha_001_por_jogador(self._trf16(1), 1),
        )

    def test_trf25_da_r1_traz_pontos_e_posicao_da_r1(self) -> None:
        self.assertEqual(
            self._retrato_da_classificacao(1),
            self._linha_001_por_jogador(self._trf25(1), 1),
        )

    def test_sem_corte_continua_a_classificacao_de_hoje(self) -> None:
        self.assertEqual(
            self._retrato_da_classificacao(3),
            self._linha_001_por_jogador(self._trf16(3), 3),
        )


class Linha001NoRetratoPorEquipesTest(CoreServiceTestCase):
    """Por equipes os pontos do jogador saem dos tabuleiros — também até N."""

    def setUp(self) -> None:
        super().setUp()
        self.tid, _equipes = self._create_team_tournament(teams_count=4, boards_count=2)
        for _ in range(2):
            rodada = self.service.generate_next_round(self.tid)
            self._close_team_round_with_decisive_boards(self.tid, int(rodada["id"]))

    def test_pontos_da_001_conferem_com_as_celulas_da_r1(self) -> None:
        linhas = [
            linha
            for linha in TRF16Exporter(self.export_service).render(self.tid, up_to_round=1).splitlines()
            if is_player_line(linha)
        ]
        self.assertTrue(linhas)
        self.assertEqual(
            [implied_points(linha) for linha in linhas],
            [declared_points(linha) for linha in linhas],
        )
