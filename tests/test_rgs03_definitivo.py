"""RGS-03 definitivo (F3.1) — o TRF do pareamento diz ao Gacrux o placar real.

FIDE C.04.1/C.04.3: os grupos de pontuação usam a pontuação oficial do torneio.
O Gacrux soma as células da linha 001 e, sem o registro 162, ainda DEDUZ o
sistema de pontos delas. Duas coisas não chegavam nele:

- o valor do PAB (``bye_points``): a célula ``U`` valia sempre 1 ponto;
- os ajustes manuais de pontos do árbitro (TRF25 §7.3, registro 299).

Agora o arquivo do pareamento leva o **162** (TRF25 §1.1, ``P`` = valor do PAB)
e um **299** nominal por ajuste. A checagem de consistência continua depois de
``reconcile_scores``: o que o arquivo não consegue dizer ao motor ainda vira
``GacruxScoreMismatch`` antes de o Gacrux rodar.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from src.services.pairing.gacrux_trf import (
    PairingScore,
    declared_points,
    implied_points,
    pairing_score,
    reconcile_scores,
    score_system_record,
)
from tests.support.gacrux_scores import gacrux_pairing_scores


def _linha_001(rank: int, pontos: str, celulas: list[str]) -> str:
    """Linha 001 com a geometria do exportador (pontos em 81-84, células em 92)."""
    base = (
        f"001 {rank:4d} m    {f'Jogador {rank}':<33} {2000 - rank:4d} BRA {'':>11} "
        f"{'2000/01/01':<10} {pontos:>4} {rank:4d}  "
    )
    return (base + "".join(celulas)).rstrip()


def _sistema_de_pontos(linha: str) -> dict[str, float]:
    """O 162 lido pelas fatias de ``gacrux/trf2json.parse_trf_scoresystem``."""
    return {
        linha[pos]: float(linha[pos + 1:pos + 5])
        for pos in range(5, len(linha) - 1, 9)
    }


class RegistroDoSistemaDePontosTest(unittest.TestCase):
    def test_162_leva_o_valor_do_pab(self) -> None:
        for pab in (0.0, 0.5, 1.0):
            with self.subTest(pab=pab):
                linha = score_system_record(pab)
                self.assertEqual("162", linha[:3])
                self.assertEqual(
                    {"W": 1.0, "D": 0.5, "L": 0.0, "A": 0.0, "P": pab, "X": 0.5},
                    _sistema_de_pontos(linha),
                )

    def test_pab_que_o_motor_nao_representa_e_recusado_quando_alguem_o_recebe(self) -> None:
        """O Gacrux traduz o P para W/D/L/Z: 0,25 não é nenhum deles."""
        score = pairing_score(0.25, [], {}, 2)
        self.assertNotIn("P", _sistema_de_pontos(score.records()[0]))
        sem_pab = [_linha_001(1, "1.0", ["   2 w 1  "])]
        self.assertEqual([], reconcile_scores(sem_pab, score)[1])
        com_pab = [_linha_001(5, "0.2", ["0000 - U  "])]
        (problema,) = reconcile_scores(com_pab, score)[1]
        self.assertIn("0.25", problema)
        self.assertIn("Jogador 5", problema)


class SomaComOValorDoPabTest(unittest.TestCase):
    def test_celula_u_vale_o_bye_points(self) -> None:
        linha = _linha_001(5, "0.5", ["0000 - U  "])
        self.assertEqual(0.5, implied_points(linha, pab_points=0.5))
        self.assertEqual(1.0, implied_points(linha))  # padrão FIDE sem 162

    def test_bye_de_meio_ponto_nao_diverge(self) -> None:
        linhas = [_linha_001(5, "0.5", ["0000 - U  "])]
        ajustadas, avisos = reconcile_scores(linhas, PairingScore(pab_points=0.5))
        self.assertEqual([], avisos)
        self.assertEqual(linhas, ajustadas)


class AjustesDePontosTest(unittest.TestCase):
    MAPA = {101: 1, 102: 2, 103: 3}

    def _ajuste(self, player_id: int, pontos: float, rodada: int = 1) -> dict:
        return {"player_id": player_id, "game_points": pontos, "round_number": rodada}

    def test_ajuste_vira_299_nas_colunas_que_o_gacrux_le(self) -> None:
        score = pairing_score(1.0, [self._ajuste(103, -0.5)], self.MAPA, 2)
        self.assertEqual({3: -0.5}, dict(score.adjustments))
        (linha,) = score.adjustment_lines
        # Fatias de `gacrux/trf2json.parse_trf_abnormal` (0-based).
        self.assertEqual("299", linha[0:3])
        self.assertEqual(" ", linha[4])                 # tipo em branco: penalidade/bônus
        self.assertEqual("-0.5", linha[13:17].strip())  # pontos
        self.assertEqual("1", linha[19:22].strip())     # rodada
        self.assertEqual("3", linha[23:27].strip())     # start-rank

    def test_celulas_ficam_com_o_que_nao_e_ajuste(self) -> None:
        """O 001 do motor declara a soma das células; o 299 leva o resto."""
        linhas = [_linha_001(3, "0.5", ["   1 b 1  "])]  # venceu e perdeu meio ponto
        score = pairing_score(1.0, [self._ajuste(103, -0.5)], self.MAPA, 2)
        ajustadas, avisos = reconcile_scores(linhas, score)
        self.assertEqual([], avisos)
        self.assertEqual(1.0, declared_points(ajustadas[0]))
        self.assertEqual(implied_points(ajustadas[0]), declared_points(ajustadas[0]))

    def test_ajuste_de_rodada_futura_nao_vai_ao_motor_e_diverge(self) -> None:
        """O Gacrux conta o 299 só a partir da rodada dele; a classificação já conta.

        É o caso que continua sem representação: a checagem recusa a rodada.
        """
        score = pairing_score(1.0, [self._ajuste(103, 0.5, rodada=2)], self.MAPA, 2)
        self.assertEqual({}, dict(score.adjustments))
        _ajustadas, avisos = reconcile_scores([_linha_001(3, "1.5", ["   1 b 1  "])], score)
        self.assertEqual(1, len(avisos))


@pytest.mark.gacrux
class GacruxLeOPlacarTest(unittest.TestCase):
    """O próprio Gacrux, lendo um TRF com 162 e 299, pareia com o placar real."""

    def test_acc_do_gacrux_inclui_pab_e_ajustes(self) -> None:
        score = pairing_score(
            0.5,
            [
                {"player_id": 1, "game_points": -0.5, "round_number": 1},
                {"player_id": 2, "game_points": 0.5, "round_number": 1},
            ],
            {pid: pid for pid in range(1, 6)},
            2,
        )
        linhas = [
            "012 RGS-03",
            "142 4",
            _linha_001(1, "0.5", ["   3 w 1  "]),
            _linha_001(2, "0.5", ["   4 b 0  "]),
            _linha_001(3, "0.0", ["   1 b 0  "]),
            _linha_001(4, "1.0", ["   2 w 1  "]),
            _linha_001(5, "0.5", ["0000 - U  "]),
        ]
        ajustadas, avisos = reconcile_scores(linhas, score)
        self.assertEqual([], avisos)
        with tempfile.TemporaryDirectory() as tmp:
            trf = Path(tmp) / "pareamento.trf"
            trf.write_text("\r\n".join([*ajustadas, *score.records()]) + "\r\n", encoding="utf-8")
            pontos = gacrux_pairing_scores(trf, closed_rounds=1)
        self.assertEqual({1: 0.5, 2: 0.5, 3: 0.0, 4: 1.0, 5: 0.5}, pontos)


if __name__ == "__main__":
    unittest.main()
