"""PAR-02 — aceleração e entrada tardia no caminho Gacrux.

O motor FIDE (Gacrux) recebe o torneio como TRF-16 e recalcula tudo a partir das
células de rodada. Duas decisões do Albericus não chegavam nele:

- a **aceleração** só existia no motor próprio; com `pairing_system` no Gacrux —
  que é o padrão — ela era ignorada sem uma linha de aviso;
- os **pontos de entrada tardia** aparecem no campo de pontos da linha 001, mas
  as rodadas anteriores à inscrição saem como `0000 - Z`, então o entrante era
  pareado num grupo de pontuação diferente do que a classificação publica.

Os testes de ponta a ponta rodam o Gacrux de verdade (subprocesso): é o único
jeito de provar que o registro 250 e as células ajustadas dizem ao motor o que
achamos que dizem.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.pairing.acceleration import (
    BAKU_NOT_IMPLEMENTED,
    accelerated_player_ids,
)
from src.services.pairing.gacrux_trf import (
    acceleration_records,
    compensation_letters,
    declared_points,
    entry_gap_rounds,
    implied_points,
    rank_ranges,
    reconcile_scores,
    with_round_cells,
)
from tests.support.core_service_base import CoreServiceTestCase


def _linha_001(pontos: str, celulas: list[str]) -> str:
    """Linha 001 com a geometria do exportador (pontos em 81-84, células em 92)."""
    base = f"001 {1:4d} m    {'Jogador':<33} {2000:4d} BRA {'':>11} {'2000/01/01':<10} {pontos:>4} {1:4d}  "
    return (base + "".join(celulas)).rstrip()


class CelulasEPontosTest(unittest.TestCase):
    """As funções puras sobre a linha 001, sem banco e sem motor."""

    def test_o_motor_le_as_celulas_e_nao_o_campo_de_pontos(self) -> None:
        """A divergência da entrada tardia em uma linha: 1.0 declarado, 0.0 somado."""
        linha = _linha_001("1.0", ["0000 - Z  ", "   3 w 1  "])
        self.assertEqual(1.0, declared_points(linha))
        self.assertEqual(1.0, implied_points(linha))
        entrante = _linha_001("1.0", ["0000 - Z  ", "0000 - Z  "])
        self.assertEqual(1.0, declared_points(entrante))
        self.assertEqual(0.0, implied_points(entrante))

    def test_rodadas_de_ausencia_sao_so_o_prefixo(self) -> None:
        """Um `0000 - Z` no meio é bye pedido ao árbitro, não ausência de inscrição."""
        linha = _linha_001("1.0", ["0000 - Z  ", "0000 - Z  ", "   3 w 1  ", "0000 - Z  "])
        self.assertEqual([1, 2], entry_gap_rounds(linha))

    def test_compensacao_prefere_meio_ponto(self) -> None:
        self.assertEqual(["H", "H"], compensation_letters(1.0, 2))
        self.assertEqual(["H"], compensation_letters(0.5, 2))
        self.assertEqual(["F", "H"], compensation_letters(1.5, 2))

    def test_compensacao_usa_ponto_inteiro_quando_nao_cabe_em_meios(self) -> None:
        self.assertEqual(["F"], compensation_letters(1.0, 1))

    def test_compensacao_recusa_o_que_nao_fecha(self) -> None:
        self.assertIsNone(compensation_letters(0.25, 4))  # não é múltiplo de meio ponto
        self.assertIsNone(compensation_letters(3.0, 2))   # mais pontos do que rodadas
        self.assertIsNone(compensation_letters(1.0, 0))   # sem rodada de ausência

    def test_celula_trocada_mantem_a_geometria(self) -> None:
        linha = _linha_001("1.0", ["0000 - Z  ", "   3 w 1  "])
        trocada = with_round_cells(linha, {1: "F"})
        self.assertEqual(1.0, implied_points(trocada) - implied_points(linha))
        self.assertEqual(linha[:91], trocada[:91])
        self.assertEqual("   3 w 1", trocada[101:109].rstrip())

    def test_reconciliacao_zera_a_diferenca(self) -> None:
        linhas = ["012 Torneio", _linha_001("1.0", ["0000 - Z  ", "   3 w 1  ", "0000 - Z  "])]
        ajustadas, avisos = reconcile_scores(linhas)
        self.assertEqual([], avisos)
        self.assertEqual("012 Torneio", ajustadas[0])
        self.assertEqual(declared_points(ajustadas[1]), implied_points(ajustadas[1]))

    def test_reconciliacao_avisa_quando_nao_da_para_representar(self) -> None:
        """Diferença negativa não vira célula: seria desfazer um resultado."""
        linhas = [_linha_001("0.0", ["   3 w 1  "])]
        ajustadas, avisos = reconcile_scores(linhas)
        self.assertEqual(linhas, ajustadas)
        self.assertEqual(1, len(avisos))
        self.assertIn("Jogador", avisos[0])

    def test_reconciliacao_avisa_quando_nao_ha_rodada_de_ausencia(self) -> None:
        linhas = [_linha_001("1.5", ["   3 w 1  "])]
        _ajustadas, avisos = reconcile_scores(linhas)
        self.assertEqual(1, len(avisos))
        self.assertIn("+0.5", avisos[0])


class RegistroDeAceleracaoTest(unittest.TestCase):
    """O registro 250, nas colunas que o parser do Gacrux lê."""

    def test_faixas_contiguas_viram_um_registro_so(self) -> None:
        self.assertEqual([(1, 4)], rank_ranges([3, 1, 2, 4]))

    def test_faixas_picadas_viram_registros_separados(self) -> None:
        """Com ordem inicial que não é a do start-rank, a metade acelerada é picada."""
        self.assertEqual([(1, 2), (5, 5)], rank_ranges([1, 2, 5]))

    def test_colunas_do_250_batem_com_o_parser(self) -> None:
        # Fatias de `gacrux/trf2json.parse_trf_accelerated` (0-based).
        linha = acceleration_records(1.0, 2, [1, 2, 3, 4])[0]
        self.assertEqual("250", linha[0:3])
        self.assertEqual("", linha[4:8].strip())      # match points: só equipes
        self.assertEqual("1.0", linha[9:13].strip())  # game points = bônus
        self.assertEqual("2", linha[14:17].strip())   # primeira rodada acelerada
        self.assertEqual("2", linha[18:21].strip())   # última rodada acelerada
        self.assertEqual("1", linha[22:26].strip())   # primeiro competidor
        self.assertEqual("4", linha[27:31].strip())   # último competidor

    def test_bonus_nao_representavel_nao_emite_registro(self) -> None:
        """O 250 vira código de resultado no motor: 0,75 viraria zero em silêncio."""
        self.assertEqual([], acceleration_records(0.75, 1, [1, 2]))
        self.assertEqual([], acceleration_records(2.0, 1, [1, 2]))

    def test_acelerados_saem_do_topo_do_seeding_e_so_nas_rodadas_do_esquema(self) -> None:
        seeding = [10, 20, 30, 40]
        self.assertEqual([10, 20], accelerated_player_ids(seeding, 1, "accelerated"))
        self.assertEqual([10, 20], accelerated_player_ids(seeding, 2, "accelerated"))
        self.assertEqual([], accelerated_player_ids(seeding, 3, "accelerated"))
        self.assertEqual([], accelerated_player_ids(seeding, 1, "none"))


class GeometriaDoExportadorTest(CoreServiceTestCase):
    """As colunas assumidas pelo módulo puro são as que o exportador escreve.

    Sem este teste, uma mudança no `_trf_player_line` deslocaria as células e o
    ajuste de PAR-02 passaria a corromper o arquivo em silêncio.
    """

    def test_linha_exportada_e_lida_nas_mesmas_colunas(self) -> None:
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(rodada["id"]):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))

        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "torneio.trf"
            self.export_service.export_chess_results_trf(self.tournament_id, destino)
            linhas = [
                linha
                for linha in destino.read_text(encoding="utf-8").splitlines()
                if linha.startswith("001")
            ]

        self.assertEqual(4, len(linhas))
        pontos = sorted(declared_points(linha) for linha in linhas)
        self.assertEqual([0.0, 0.0, 1.0, 1.0], pontos)
        for linha in linhas:
            self.assertEqual(declared_points(linha), implied_points(linha))
            self.assertEqual([], entry_gap_rounds(linha))


class PareamentoAceleradoTest(CoreServiceTestCase):
    """Ponta a ponta com o motor FIDE de verdade."""

    def _configurar(self, **extra) -> None:
        base = {
            "pairing_system": "gacrux_swiss",
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Arbitro Teste",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-07-31",
            "end_date": "2026-07-31",
        }
        base.update(extra)
        self.db.save_tournament_settings(self.tournament_id, base)

    def _pares_por_ordem(self, round_id: int, ids: list[int]) -> set[tuple[int, int]]:
        """Mesas como pares de posições no ranking inicial (1 = cabeça de chave)."""
        pares = set()
        for pairing in self.db.get_pairings_for_round(round_id):
            if pairing["is_bye"]:
                continue
            branca = ids.index(int(pairing["white_player_id"])) + 1
            preta = ids.index(int(pairing["black_player_id"])) + 1
            pares.add((min(branca, preta), max(branca, preta)))
        return pares

    def test_aceleracao_classica_muda_a_rodada_1_no_gacrux(self) -> None:
        """Era ignorada em silêncio: o pareamento saía igual ao sem aceleração."""
        self._configurar(acceleration_method="accelerated")
        ids = self._create_players(8)
        rodada = self.service.generate_next_round(self.tournament_id)
        # Metade de cima com +1 ponto fictício: os grupos {1..4} e {5..8} se
        # enfrentam por dentro. Sem aceleração seria 1x5, 2x6, 3x7, 4x8.
        self.assertEqual(
            {(1, 3), (2, 4), (5, 7), (6, 8)},
            self._pares_por_ordem(int(rodada["id"]), ids),
        )

    def test_sem_aceleracao_a_rodada_1_segue_metade_contra_metade(self) -> None:
        self._configurar(acceleration_method="none")
        ids = self._create_players(8)
        rodada = self.service.generate_next_round(self.tournament_id)
        self.assertEqual(
            {(1, 5), (2, 6), (3, 7), (4, 8)},
            self._pares_por_ordem(int(rodada["id"]), ids),
        )

    def test_bonus_nao_representavel_cai_no_motor_proprio_com_aviso(self) -> None:
        self._configurar(acceleration_method="custom:rounds=2;bonus=0.75;upper=0.5")
        self._create_players(8)
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertTrue(any("motor proprio" in aviso for aviso in previa["warnings"]))
        self.assertGreaterEqual(previa["alerts_count"], 1)

        self.service.generate_next_round(self.tournament_id)
        acoes = [
            evento
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
            if evento["action"] == "pairing_warning"
        ]
        self.assertEqual(1, len(acoes))

    def test_baku_avisa_que_nao_aplica_bonus(self) -> None:
        self._configurar(acceleration_method="baku")
        self._create_players(8)
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertIn(BAKU_NOT_IMPLEMENTED, previa["warnings"])

    def test_sem_aceleracao_nao_ha_aviso(self) -> None:
        self._configurar(acceleration_method="none")
        self._create_players(8)
        self.assertEqual([], self.service.preview_next_round(self.tournament_id)["warnings"])


class EntradaTardiaTest(CoreServiceTestCase):
    """O entrante tardio é pareado com os pontos que a classificação publica."""

    def _fixture_com_entrante(self, late_entry_points: float = 1.0) -> tuple[list[int], int]:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "pairing_system": "gacrux_swiss",
                "pairing_method": "swiss",
                "time_control": "10 min",
                "chief_arbiter": "Arbitro Teste",
                "federation": "BRA",
                "location": "Sao Paulo",
                "start_date": "2026-07-31",
                "end_date": "2026-07-31",
                "late_entry_points": late_entry_points,
            },
        )
        ids = self._create_players(6)
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(rodada["id"]):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        # Três vencedores com 1.0 e três derrotados com 0.0; o entrante chega
        # com 1.0 e fecha o grupo de cima em quatro.
        tardio = self.db.create_player(
            self.tournament_id, name="Entrante Tardio", rating=1975, club="Clube",
            category="Absoluto",
        )
        return ids, int(tardio)

    def test_entrante_e_pareado_no_grupo_de_pontuacao_dele(self) -> None:
        _ids, tardio = self._fixture_com_entrante()
        self.assertEqual(1.0, float(self.db.get_player(tardio)["starting_points"]))
        pontos = {
            int(item["player_id"]): float(item["points"])
            for item in self.service.standings(self.tournament_id)
        }
        self.assertEqual(1.0, pontos[tardio])

        rodada = self.service.generate_next_round(self.tournament_id)
        mesa = next(
            pairing
            for pairing in self.db.get_pairings_for_round(int(rodada["id"]))
            if tardio in (pairing["white_player_id"], pairing["black_player_id"])
        )
        self.assertFalse(mesa["is_bye"], "o entrante caiu no bye do grupo de baixo")
        adversario = (
            int(mesa["black_player_id"])
            if int(mesa["white_player_id"]) == tardio
            else int(mesa["white_player_id"])
        )
        # Sem os pontos de entrada tardia o motor o poria contra alguem de 0.0.
        self.assertEqual(1.0, pontos[adversario])

    def test_pareamento_do_entrante_nao_gera_aviso(self) -> None:
        """A diferença coube nas rodadas de ausência: não há o que avisar."""
        self._fixture_com_entrante()
        self.assertEqual([], self.service.preview_next_round(self.tournament_id)["warnings"])


if __name__ == "__main__":
    unittest.main()
