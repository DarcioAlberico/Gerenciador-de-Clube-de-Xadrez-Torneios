"""Pendências do TRF25: 152 antes da R1 (T1) e corte do entrante tardio (T2).

- T1: o 152 (cor inicial) só saía depois da R1, lido da mesa do cabeça de
  chave. A cor é sorteada quando o torneio nasce (RGS-14) e fica gravada em
  ``tournament_settings.initial_color``: é conhecida antes da R1.
- T2: ``export(..., up_to_round=N)`` cortava só as rodadas; o entrante que se
  inscreveu depois de N aparecia no retrato da rodada N. O corte é o mesmo do
  retrato da classificação (``standings_cut.players_as_of_round``).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from tests.support.core_service_base import CoreServiceTestCase


class _Trf25(CoreServiceTestCase):
    def _linhas(self, up_to_round: int | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            TRF25Exporter(self.export_service).export(
                self.tournament_id, destino, up_to_round=up_to_round
            )
            return destino.read_text(encoding="utf-8").splitlines()


class CorInicialAntesDaR1Test(_Trf25):
    def test_152_sai_antes_da_r1_com_a_cor_gravada(self) -> None:
        self._create_players(4)
        for cor in ("B", "W"):
            self.db.save_tournament_settings(self.tournament_id, {"initial_color": cor})
            registros = [linha.rstrip() for linha in self._linhas() if linha.startswith("152")]
            self.assertEqual([f"152 {cor}"], registros)

    def test_depois_da_r1_continua_a_cor_da_mesa(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"initial_color": "B"})
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)
        registros = [linha.rstrip() for linha in self._linhas() if linha.startswith("152")]
        self.assertEqual(["152 B"], registros)


class EntranteTardioNoRetratoTest(_Trf25):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(rodada["id"]))
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.db.create_player(
            self.tournament_id, name="Entrante Tardio", rating=2500, club="Clube", category="Absoluto"
        )

    def test_retrato_da_r1_nao_tem_quem_entrou_na_r2(self) -> None:
        linhas = self._linhas(up_to_round=1)
        jogadores = [linha for linha in linhas if linha.startswith("001")]
        self.assertEqual(4, len(jogadores))
        self.assertFalse([linha for linha in jogadores if "Entrante Tardio" in linha])
        self.assertIn("062 4", [linha.rstrip() for linha in linhas])

    def test_sem_corte_o_entrante_aparece(self) -> None:
        jogadores = [linha for linha in self._linhas() if linha.startswith("001")]
        self.assertEqual(5, len(jogadores))

    def test_numeracao_do_retrato_e_a_do_trf16(self) -> None:
        """As duas numerações do retrato da R1 saem da mesma lista."""
        nomes = [
            linha[14:47].strip() for linha in self._linhas(up_to_round=1) if linha.startswith("001")
        ]
        esperado = [
            str(jogador["name"])
            for jogador in TRF16Exporter(self.export_service).players(self.tournament_id, up_to_round=1)
        ]
        self.assertEqual(esperado, nomes)
