"""TBK-04 — parâmetros de critérios editáveis e registro 212 fiel.

Dois defeitos que se encontram no mesmo lugar: o editor devolvia sempre
``params: {}`` (então corte de Buchholz, limiar de Koya e corte do ARO não eram
configuráveis) e o registro 212 do TRF25 era uma lista fixa — o arquivo enviado
à federação **declarava critérios diferentes dos que o motor usava**.
"""

from __future__ import annotations

import json
import unittest

from src.services.federation_exporters.trf25 import TRF25Exporter
from src.services.pairing import (
    PLAYER_TIEBREAKS,
    criterion_params,
    normalize_criterion_params,
    parse_player_tiebreak_sequence,
    player_tiebreak_value,
)
from src.services.pairing.gacrux_tiebreak_map import (
    build_tiebreak_plan,
    specifier_with_params,
)
from tests.support.core_service_base import CoreServiceTestCase


class ParametrosDeclaradosTest(unittest.TestCase):
    """Os parâmetros vivem no registro, não na tela."""

    def test_criterios_com_corte_declaram_seus_parametros(self) -> None:
        chaves = {p.key for p in criterion_params("buchholz_cut1")}
        self.assertEqual({"cut_low", "cut_high", "unplayed"}, chaves)
        self.assertEqual({"threshold"}, {p.key for p in criterion_params("koya")})
        self.assertEqual({"cut"}, {p.key for p in criterion_params("aroc")})

    def test_criterio_sem_parametro_nao_inventa_nenhum(self) -> None:
        self.assertEqual((), criterion_params("sonneborn_berger"))
        self.assertEqual({}, normalize_criterion_params("sonneborn_berger", {"cut_low": 3}))

    def test_normalizacao_completa_o_que_faltou(self) -> None:
        """Quem lê não precisa repetir o padrão em cada ponto de uso."""
        self.assertEqual(
            {"cut_low": 1, "cut_high": 0, "unplayed": "real"},
            normalize_criterion_params("buchholz_cut1", {}),
        )

    def test_valor_fora_da_faixa_volta_para_dentro(self) -> None:
        self.assertEqual(99, normalize_criterion_params("koya", {"threshold": 500})["threshold"])
        self.assertEqual(1, normalize_criterion_params("koya", {"threshold": -3})["threshold"])
        self.assertEqual(5, normalize_criterion_params("buchholz_cut2", {"cut_low": 80})["cut_low"])

    def test_lixo_datilografado_volta_ao_padrao(self) -> None:
        """Desempate que recusa a configuração no meio do torneio seria pior."""
        self.assertEqual(50, normalize_criterion_params("koya", {"threshold": "abc"})["threshold"])
        self.assertEqual(
            "real", normalize_criterion_params("buchholz_cut1", {"unplayed": "xxx"})["unplayed"]
        )

    def test_chave_desconhecida_e_descartada(self) -> None:
        """É como uma sequência antiga sobrevive a um critério que mudou."""
        self.assertNotIn(
            "lixo", normalize_criterion_params("koya", {"threshold": 60, "lixo": 1})
        )

    def test_a_sequencia_salva_chega_normalizada(self) -> None:
        sequencia = parse_player_tiebreak_sequence(
            json.dumps([{"code": "buchholz_cut1", "params": {"cut_low": 3}}])
        )
        self.assertEqual(
            [{"code": "buchholz_cut1", "params": {"cut_low": 3, "cut_high": 0, "unplayed": "real"}}],
            sequencia,
        )


class ParametrosNoMotorProprioTest(unittest.TestCase):
    """O motor próprio já lia os params; o teste cobra que continue lendo."""

    def _stats(self) -> tuple[dict, dict]:
        adversarios = {
            2: {"player_id": 2, "points": 4.0, "rating": 2000},
            3: {"player_id": 3, "points": 3.0, "rating": 1900},
            4: {"player_id": 4, "points": 1.0, "rating": 1500},
        }
        jogador = {
            "player_id": 1,
            "points": 2.0,
            "rating": 1800,
            "opponents": [2, 3, 4],
            "byes": 0,
            "games": [],
            "earned_against": [],
        }
        return jogador, {1: jogador, **adversarios}

    def test_corte_configurado_muda_o_buchholz(self) -> None:
        jogador, stats = self._stats()
        sem_corte = player_tiebreak_value("buchholz_cut1", jogador, stats, {"cut_low": 0}, 3)
        corta_um = player_tiebreak_value("buchholz_cut1", jogador, stats, {"cut_low": 1}, 3)
        corta_dois = player_tiebreak_value("buchholz_cut1", jogador, stats, {"cut_low": 2}, 3)
        self.assertEqual(8.0, sem_corte)
        self.assertEqual(7.0, corta_um, "descarta o adversario de 1,0")
        self.assertEqual(4.0, corta_dois, "descarta 1,0 e 3,0")

    def test_corte_dos_dois_lados(self) -> None:
        jogador, stats = self._stats()
        self.assertEqual(
            3.0,
            player_tiebreak_value(
                "buchholz_cut1", jogador, stats, {"cut_low": 1, "cut_high": 1}, 3
            ),
        )

    def test_limiar_do_koya_e_configuravel(self) -> None:
        jogador, stats = self._stats()
        jogador["earned_against"] = [(2, 1.0), (3, 0.5), (4, 0.5)]
        # 4 rodadas: 50% = 2,0 -> adversarios de 4,0 e 3,0 entram.
        self.assertEqual(1.5, player_tiebreak_value("koya", jogador, stats, {}, 4))
        # 90% = 3,6 -> so o de 4,0 entra.
        self.assertEqual(
            1.0, player_tiebreak_value("koya", jogador, stats, {"threshold": 90}, 4)
        )

    def test_corte_do_aro_e_configuravel(self) -> None:
        jogador, stats = self._stats()
        sem = player_tiebreak_value("aro", jogador, stats, {}, 3)
        com = player_tiebreak_value("aroc", jogador, stats, {"cut": 1}, 3)
        self.assertNotEqual(sem, com)
        self.assertEqual(1900.0, com, "sobra so o do meio")


class EspecificadorDoGacruxTest(unittest.TestCase):
    """Os params viram modificador do motor FIDE — a sintaxe é dele."""

    def test_corte_vira_modificador(self) -> None:
        self.assertEqual("BH/C1", specifier_with_params("buchholz_cut1", {"cut_low": 1}))
        self.assertEqual("BH/C3", specifier_with_params("buchholz_cut1", {"cut_low": 3}))

    def test_corte_simetrico_usa_o_modificador_mediano(self) -> None:
        """`/M<n>` é `cutlow = cuthigh = n` no motor — mais curto que dois cortes."""
        self.assertEqual(
            "BH/M2", specifier_with_params("buchholz_cut2", {"cut_low": 2, "cut_high": 2})
        )

    def test_corte_zerado_volta_ao_buchholz_puro(self) -> None:
        self.assertEqual("BH", specifier_with_params("buchholz_cut2", {"cut_low": 0}))

    def test_limiar_padrao_nao_polui_o_especificador(self) -> None:
        """Especificador enxuto é o que o árbitro reconhece no arquivo."""
        self.assertEqual("KS", specifier_with_params("koya", {"threshold": 50}))
        self.assertEqual("KS/L60", specifier_with_params("koya", {"threshold": 60}))

    def test_criterio_sem_equivalente_devolve_none(self) -> None:
        self.assertIsNone(specifier_with_params("cumulative_opp", {}))

    def test_o_plano_aceita_sequencia_com_params(self) -> None:
        plano = build_tiebreak_plan(
            [
                {"code": "buchholz_cut1", "params": {"cut_low": 2}},
                {"code": "koya", "params": {"threshold": 60}},
            ]
        )
        self.assertEqual(("PTS", "BH/C2", "KS/L60"), plano.specifiers)
        self.assertEqual(("points", "buchholz_cut1", "koya"), plano.code_order)

    def test_o_plano_ainda_aceita_lista_de_codigos(self) -> None:
        """As duas formas coexistem: a sequência salva e a lista padrão."""
        self.assertEqual(
            ("PTS", "BH", "SB"), build_tiebreak_plan(["buchholz", "sonneborn_berger"]).specifiers
        )


class Registro212Test(CoreServiceTestCase):
    """O 212 declara o que o motor usa — antes era uma lista fixa."""

    def _codigos(self, is_team: bool = False) -> list[str]:
        return TRF25Exporter(self.export_service)._tiebreak_codes_212(
            is_team=is_team, tournament_id=self.tournament_id
        )

    def test_sem_configuracao_sai_o_padrao_do_projeto(self) -> None:
        self.assertEqual(["PTS", "BH", "BH/M1", "SB", "WON"], self._codigos())

    def test_win_virou_won(self) -> None:
        """O motor sempre contou vitórias no tabuleiro; `WIN` era outro critério."""
        codigos = self._codigos()
        self.assertIn("WON", codigos)
        self.assertNotIn("WIN", codigos)

    def test_mudar_a_sequencia_muda_o_212(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "tiebreak_sequence": json.dumps(
                    [{"code": "direct_encounter"}, {"code": "cumulative"}]
                )
            },
        )
        self.assertEqual(["PTS", "DE", "PS"], self._codigos())

    def test_os_parametros_chegam_ao_212(self) -> None:
        """Declarar `BH` quando o árbitro configurou corte 2 seria mentir."""
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "tiebreak_sequence": json.dumps(
                    [{"code": "buchholz_cut1", "params": {"cut_low": 2}},
                     {"code": "koya", "params": {"threshold": 60}}]
                )
            },
        )
        self.assertEqual(["PTS", "BH/C2", "KS/L60"], self._codigos())

    def test_criterio_sem_equivalente_fide_nao_entra_no_212(self) -> None:
        """O 212 é um registro FIDE: só cabe o que a FIDE nomeia."""
        self.db.save_tournament_settings(
            self.tournament_id,
            {"tiebreak_sequence": json.dumps([{"code": "cumulative_opp"}, {"code": "buchholz"}])},
        )
        self.assertEqual(["PTS", "BH"], self._codigos())

    def test_o_arquivo_exportado_carrega_a_sequencia_configurada(self) -> None:
        """Ponta a ponta: o que sai no arquivo é o que está configurado."""
        import tempfile
        from pathlib import Path

        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        for mesa in self.db.get_pairings_for_round(int(round_data["id"])):
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "time_control": "90+30",
                "chief_arbiter": "Arb",
                "federation": "BRA",
                "location": "Sao Paulo",
                "start_date": "2026-07-01",
                "end_date": "2026-07-02",
                "tiebreak_sequence": json.dumps(
                    [{"code": "sonneborn_berger"}, {"code": "koya", "params": {"threshold": 60}}]
                ),
            },
        )
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "torneio.trf"
            TRF25Exporter(self.export_service).export(self.tournament_id, destino)
            linhas = [
                linha
                for linha in destino.read_text(encoding="utf-8").splitlines()
                if linha.startswith("212")
            ]
        self.assertEqual(1, len(linhas))
        self.assertIn("PTS", linhas[0])
        self.assertIn("SB", linhas[0])
        self.assertIn("KS/L60", linhas[0])


class EditorDeSequenciaTest(unittest.TestCase):
    """O editor devolve os params — antes era sempre `{}`."""

    def test_o_registro_de_criterios_declara_rotulo_para_cada_param(self) -> None:
        """Sem rótulo a tela mostraria a chave crua ("cut_low") ao árbitro."""
        for code, criterio in PLAYER_TIEBREAKS.items():
            for param in criterio.params:
                self.assertTrue(param.label, f"{code}.{param.key} sem rotulo")
                self.assertNotIn("_", param.label, f"{code}.{param.key} usa a chave crua")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
