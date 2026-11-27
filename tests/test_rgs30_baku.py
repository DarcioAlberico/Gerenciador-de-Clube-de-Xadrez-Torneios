"""RGS-30 — aceleração de Baku (FIDE C.04.7), de verdade.

Antes, ``baku`` era guardado: nenhum ponto virtual, nenhum 250, nenhum
``_BAKU`` e o aviso ``BAKU_NOT_IMPLEMENTED``. A regra está no FIDE Handbook
(C.04.7, aplicado desde 01/02/2026; antes C.04.5.1):

- GA = os primeiros ``2 × ⌈N/4⌉`` da lista inicial; GB = o resto;
- aceleradas = a primeira metade das rodadas, arredondada para cima;
- VP = pontos de uma vitória na primeira metade (arredondada para cima) das
  aceleradas, metade disso no resto, zero depois;
- o VP entra só no score de pareamento; o último do GA continua o mesmo com
  entrada tardia (o GA pode ficar ímpar).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from src.services.constants import ACCELERATION_METHODS, AppError
from src.services.federation_exporters import TRF25Exporter
from src.services.pairing.acceleration import (
    baku_accelerated_player_ids,
    baku_group_a_size,
    baku_virtual_points,
)
from tests.support.core_service_base import CoreServiceTestCase


class GrupoATest(unittest.TestCase):
    def test_ga_e_a_metade_arredondada_para_cima_ate_o_par(self) -> None:
        self.assertEqual(
            [2, 2, 4, 4, 4, 6, 6, 6, 6, 8],
            [baku_group_a_size(n) for n in (1, 2, 5, 7, 8, 9, 10, 11, 12, 13)],
        )

    def test_campo_vazio_nao_tem_ga(self) -> None:
        self.assertEqual(0, baku_group_a_size(0))


class PontosVirtuaisTest(unittest.TestCase):
    def _vp_por_rodada(self, total_rounds: int, start_rank: int = 1, total_players: int = 8) -> list[float]:
        return [
            baku_virtual_points(total_players, total_rounds, rodada, start_rank)
            for rodada in range(1, total_rounds + 1)
        ]

    def test_exemplo_do_handbook_nove_rodadas(self) -> None:
        """C.04.7 1.4.4: 9 rodadas → 5 aceleradas; VP 1 nas R1–R3 e 0,5 nas R4–R5."""
        self.assertEqual([1.0, 1.0, 1.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0], self._vp_por_rodada(9))

    def test_onze_rodadas_seis_aceleradas(self) -> None:
        self.assertEqual(
            [1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0], self._vp_por_rodada(11)
        )

    def test_gb_nunca_recebe_vp(self) -> None:
        # 8 jogadores: GA = 1..4.
        self.assertEqual(1.0, baku_virtual_points(8, 9, 1, 4))
        self.assertEqual([0.0] * 9, self._vp_por_rodada(9, start_rank=5))

    def test_vp_e_o_valor_da_vitoria(self) -> None:
        """Exemplo 2 do Handbook: vitória = 2 → VP 2 e depois 1."""
        self.assertEqual(2.0, baku_virtual_points(8, 11, 3, 1, win_points=2.0, draw_points=1.0))
        self.assertEqual(1.0, baku_virtual_points(8, 11, 4, 1, win_points=2.0, draw_points=1.0))

    def test_pontuacao_fora_da_regra_e_recusada(self) -> None:
        with self.assertRaises(AppError) as recusa:
            baku_virtual_points(8, 9, 1, 1, win_points=3.0, draw_points=1.0)
        self.assertIn("C.04.7", str(recusa.exception))
        with self.assertRaises(AppError):
            baku_virtual_points(8, 9, 1, 1, loss_points=0.5)

    def test_fora_do_torneio_nao_ha_vp(self) -> None:
        self.assertEqual(0.0, baku_virtual_points(8, 9, 0, 1))
        self.assertEqual(0.0, baku_virtual_points(8, 9, 10, 1))
        self.assertEqual(0.0, baku_virtual_points(8, 9, 1, 0))


class EntradaTardiaTest(unittest.TestCase):
    """C.04.7 1.3: o último do GA continua o mesmo; o GA pode ficar ímpar."""

    def test_entrante_acima_do_ultimo_do_ga_entra_no_ga(self) -> None:
        self.assertEqual(1.0, baku_virtual_points(8, 9, 2, 5, late_entrants_above=1))
        self.assertEqual(0.0, baku_virtual_points(8, 9, 2, 6, late_entrants_above=1))

    def test_lista_com_entrante_acima_e_abaixo(self) -> None:
        iniciais = [10, 20, 30, 40, 50, 60, 70, 80]
        # 99 entrou acima do 3º; 98, abaixo do último do GA (40).
        seeding = [10, 20, 99, 30, 40, 50, 98, 60, 70, 80]
        acelerados, vp = baku_accelerated_player_ids(seeding, iniciais, 9, 2)
        self.assertEqual([10, 20, 99, 30, 40], acelerados)  # GA ímpar
        self.assertEqual(1.0, vp)

    def test_sem_entrante_o_ga_e_o_topo(self) -> None:
        iniciais = [10, 20, 30, 40, 50, 60, 70, 80]
        self.assertEqual(([10, 20, 30, 40], 0.5), baku_accelerated_player_ids(iniciais, iniciais, 9, 4))
        self.assertEqual(([], 0.0), baku_accelerated_player_ids(iniciais, iniciais, 9, 6))


class RotuloTest(unittest.TestCase):
    def test_rotulo_cita_a_regra(self) -> None:
        self.assertEqual("Baku (FIDE C.04.7)", ACCELERATION_METHODS["baku"])


class _TorneioBaku(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Baku", rounds_count=9)
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "pairing_system": "gacrux_swiss",
                "pairing_method": "swiss",
                "acceleration_method": "baku",
                "time_control": "10 min",
                "chief_arbiter": "Arbitro Teste",
                "federation": "BRA",
                "location": "Sao Paulo",
                "start_date": "2026-07-31",
                "end_date": "2026-07-31",
            },
        )

    def _trf25(self) -> tuple[list[str], list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "baku.trf"
            avisos = TRF25Exporter(self.export_service).export(self.tournament_id, destino)
            return destino.read_text(encoding="utf-8").splitlines(), avisos


class Trf25BakuTest(_TorneioBaku):
    def test_250_e_sufixo_baku(self) -> None:
        self._create_players(8)
        linhas, avisos = self._trf25()
        registros = [linha for linha in linhas if linha.startswith("250")]
        # game points (10-13), rodadas (15-17, 19-21), competidores (23-26, 28-31).
        self.assertEqual(
            [("1.0", "1", "3", "1", "4"), ("0.5", "4", "5", "1", "4")],
            [
                (r[9:13].strip(), r[14:17].strip(), r[18:21].strip(), r[22:26].strip(), r[27:31].strip())
                for r in registros
            ],
        )
        tipo = next(linha for linha in linhas if linha.startswith("192"))
        self.assertRegex(tipo.rstrip(), r"^192 FIDE_DUTCH(_20\d\d)?_BAKU$")
        self.assertFalse([aviso for aviso in avisos if "Baku" in aviso])

    def test_trf16_leva_o_mesmo_250(self) -> None:
        """O TRF16 (o arquivo que o motor lê) declara os mesmos blocos do TRF25."""
        from src.services.federation_exporters import TRF16Exporter

        self._create_players(8)
        trf16 = TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()
        linhas, _avisos = self._trf25()
        self.assertEqual(
            [linha for linha in linhas if linha.startswith("250")],
            [linha for linha in trf16 if linha.startswith("250")],
        )
        self.assertEqual(2, sum(1 for linha in trf16 if linha.startswith("250")))

    def test_250_cobre_o_entrante_acima_do_ultimo_do_ga(self) -> None:
        self._create_players(8)
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(rodada["id"]))
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.db.create_player(self.tournament_id, name="Tardio", rating=1990, club="Clube", category="Absoluto")
        linhas, _avisos = self._trf25()
        registros = [linha for linha in linhas if linha.startswith("250")]
        self.assertEqual({"5"}, {r[27:31].strip() for r in registros})


class PareamentoBakuTest(_TorneioBaku):
    def test_plano_da_r2_com_entrante_tardio_tem_ga_impar(self) -> None:
        ids = self._create_players(8)
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(rodada["id"]))
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        tardio = self.db.create_player(
            self.tournament_id, name="Tardio", rating=1990, club="Clube", category="Absoluto"
        )
        plano = self.service._individual_next_round_plan(
            self.tournament_id, self.db.get_tournament(self.tournament_id)
        )
        self.assertEqual(1.0, plano["acceleration"]["bonus"])
        self.assertEqual(
            {ids[0], int(tardio), ids[1], ids[2], ids[3]},
            set(plano["acceleration"]["player_ids"]),
        )


@pytest.mark.gacrux
class GacruxBakuTest(_TorneioBaku):
    """O Gacrux de verdade: VP 1 no GA separa GA de GB na R1."""

    def _pares_por_ordem(self, round_id: int, ids: list[int]) -> set[tuple[int, int]]:
        pares = set()
        for pairing in self.db.get_pairings_for_round(round_id):
            if pairing["is_bye"]:
                continue
            branca = ids.index(int(pairing["white_player_id"])) + 1
            preta = ids.index(int(pairing["black_player_id"])) + 1
            pares.add((min(branca, preta), max(branca, preta)))
        return pares

    def test_r1_pareia_ga_separado_de_gb(self) -> None:
        ids = self._create_players(8)
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertEqual([], previa["warnings"])
        rodada = self.service.generate_next_round(self.tournament_id)
        # Sem aceleração seria 1x5, 2x6, 3x7, 4x8.
        self.assertEqual(
            {(1, 3), (2, 4), (5, 7), (6, 8)},
            self._pares_por_ordem(int(rodada["id"]), ids),
        )

    def test_vp_nao_entra_na_classificacao(self) -> None:
        self._create_players(8)
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(rodada["id"]))
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        pontos = sorted(float(item["points"]) for item in self.service.standings(self.tournament_id))
        self.assertEqual([0.0] * 4 + [1.0] * 4, pontos)


@pytest.mark.gacrux
class HistoricoDaAceleracaoTest(_TorneioBaku):
    """Os floats das rodadas passadas se medem pelo score de pareamento delas.

    O arquivo do Gacrux levava só o 250 da rodada pareada; o motor media os
    floats da R1/R2 sem o VP e divergia do bbpPairings v6.0.0 na R3 e na R4.
    Valores esperados (branca, preta) tirados do bbp (192 `FIDE_DUTCH_2025_BAKU`)
    sobre o mesmo torneio: 16 jogadores, 9 rodadas, resultado por regra fixa.
    """

    ESPERADO = {
        1: {(1, 5), (3, 7), (6, 2), (8, 4), (9, 13), (11, 15), (14, 10), (16, 12)},
        2: {(2, 9), (4, 14), (5, 16), (7, 1), (8, 6), (10, 13), (11, 3), (12, 15)},
        3: {(1, 11), (3, 10), (5, 2), (6, 4), (7, 8), (9, 12), (13, 14), (15, 16)},
        4: {(2, 11), (4, 5), (6, 3), (8, 1), (9, 7), (10, 15), (14, 12), (16, 13)},
    }

    @staticmethod
    def _resultado(branca: int, preta: int) -> str:
        return "0-1" if (branca + preta) % 5 == 0 else "1-0"

    def test_r3_e_r4_iguais_ao_bbp(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"initial_color": "W"})
        ids = self._create_players(16)
        for numero in range(1, 5):
            rodada = self.service.generate_next_round(self.tournament_id)
            mesas = self.db.get_pairings_for_round(int(rodada["id"]))
            pares = {
                (ids.index(int(m["white_player_id"])) + 1, ids.index(int(m["black_player_id"])) + 1)
                for m in mesas
                if not m["is_bye"]
            }
            self.assertEqual(self.ESPERADO[numero], pares, f"R{numero}")
            for mesa, (branca, preta) in zip(mesas, [
                (ids.index(int(m["white_player_id"])) + 1, ids.index(int(m["black_player_id"])) + 1)
                for m in mesas
            ]):
                self.service.update_result(self.tournament_id, int(mesa["id"]), self._resultado(branca, preta))
            self.service.close_round(self.tournament_id, int(rodada["id"]))


if __name__ == "__main__":
    unittest.main()
