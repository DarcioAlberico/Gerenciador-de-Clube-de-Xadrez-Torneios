"""RG2-21 — a verificação holandesa continua rodando depois de uma entrada tardia com pontos.

``with_round_cells`` terminava em ``rstrip()``. Quando a última célula da linha
001 é a mesa recém-gerada, ainda sem resultado (``   4 w  ``), o corte comia a
coluna do resultado e a célula sumia para quem lê por coluna: o Gacrux ``-c``
respondia "Error reading file" e a rodada ficava ``pairing_check_unverified``
da R3 em diante (regressão do RGS-24 sobre o RGS-16).
"""
from __future__ import annotations

import unittest

import pytest

from src.services.pairing.gacrux_trf import (
    PairingScore,
    implied_points,
    rebased_score_lines,
    reconcile_scores,
    with_round_cells,
)
from src.services.trf_layout import cell_blocks
from tests.support.core_service_base import CoreServiceTestCase

PENDENTE = "   4 w  "  # mesa gerada, sem resultado: é assim que o exportador a deixa


def _linha_001(pontos: str, celulas: list[str], rank: int = 1) -> str:
    """Linha 001 com a geometria do exportador, terminando na célula pendente."""
    base = f"001 {rank:4d} m    {'Tardio':<33} {1900:4d} BRA {'':>11} {'2000/01/01':<10} {pontos:>4} {1:4d}  "
    return base + "".join(celulas)


class CelulaPendenteTest(unittest.TestCase):
    def test_trocar_a_ausencia_nao_apaga_a_celula_pendente(self) -> None:
        linha = _linha_001("0.5", ["0000 - Z  ", "0000 - Z  ", PENDENTE])
        trocada = with_round_cells(linha, {1: "H"})
        self.assertEqual(3, len(cell_blocks(trocada)))
        self.assertEqual(len(linha), len(trocada))
        self.assertEqual(PENDENTE, cell_blocks(trocada)[2][: len(PENDENTE)])

    def test_reconciliar_mantem_as_tres_rodadas(self) -> None:
        linhas = [_linha_001("0.5", ["0000 - Z  ", "0000 - Z  ", PENDENTE])]
        ajustadas, avisos = reconcile_scores(linhas)
        self.assertEqual([], avisos)
        self.assertEqual(3, len(cell_blocks(ajustadas[0])))
        self.assertEqual(0.5, implied_points(ajustadas[0]))

    def test_retrato_do_desempate_mantem_a_celula_pendente(self) -> None:
        linhas = [_linha_001("0.5", ["0000 - Z  ", "0000 - Z  ", PENDENTE])]
        refeitas, problemas = rebased_score_lines(linhas, PairingScore(), {1: 0.5})
        self.assertEqual([], problemas)
        jogador = next(linha for linha in refeitas if linha.startswith("001"))
        self.assertEqual(3, len(cell_blocks(jogador)))


@pytest.mark.gacrux  # roda o Gacrux de verdade: é ele quem precisa ler o arquivo
class VerificacaoDepoisDaEntradaTardiaTest(CoreServiceTestCase):
    def test_r3_com_entrante_de_meio_ponto_confere(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {"pairing_method": "swiss", "pairing_system": "gacrux_swiss", "initial_color": "W"},
        )
        self._create_players(6)
        for _ in range(2):
            rodada = self.service.generate_next_round(self.tournament_id)
            for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
                if not mesa["is_bye"]:
                    self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.service.register_late_entry(
            self.tournament_id, {"name": "Tardio", "rating": 1900, "sex": "m", "birth_date": "2000"}, 0.5
        )
        rodada = self.service.generate_next_round(self.tournament_id)
        rodada_id = int(rodada["id"])
        nao_verificadas = [
            evento
            for evento in self.db.list_audit_events(self.tournament_id, action="pairing_check_unverified")
            if int(evento["round_id"] or 0) == rodada_id
        ]
        self.assertEqual([], [evento["reason"] for evento in nao_verificadas])
        conferidas = [
            evento
            for evento in self.db.list_audit_events(self.tournament_id, action="pairing_check")
            if int(evento["round_id"] or 0) == rodada_id
        ]
        self.assertTrue(conferidas)
        self.assertIn("confere", conferidas[0]["reason"])


if __name__ == "__main__":
    unittest.main()
