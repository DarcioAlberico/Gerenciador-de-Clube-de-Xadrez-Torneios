"""RG2-16 — "apenas o maior prêmio" repassa o prêmio e não soma categorias.

Antes, cada faixa era calculada sozinha e a política era aplicada depois, por
jogador, com ``max``: o 1º colocado que também era o 1º do Sub-12, do Sub-1400
e do Feminino levava 150 (as três categorias somadas), os 100 do geral não iam
para ninguém e o 2º ficava com 0 — saíam 150 de 250 anunciados.

**D1** (decidida pelo dono em 2026-11-28): os prêmios não cumulativos são
alocados do **maior valor para o menor**; valor igual segue a **ordem do
edital**. Cada prêmio vai ao melhor elegível que ainda não tem prêmio; o que
não encontra ninguém fica em ``undistributed``. Prêmio marcado como "soma"
(``cumulative``) fica fora da trava. Empate (Hort ou divisão igual): o grupo
empatado divide primeiro o bolo das posições que ocupa, como antes; a trava
vale sobre o que cada um recebeu.
"""
from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.prizes import allocate_prizes
from tests.support.core_service_base import CoreServiceTestCase


def _linha(player_id: int, posicao: float, pontos: float, categorias: str) -> dict:
    return {
        "player_id": player_id,
        "name": f"J{player_id}",
        "position": posicao,
        "points": pontos,
        "category": categorias.split(";")[0].strip(),
        "categories": categorias,
        "player_status": "active",
        "active": 1,
    }


def _premio(kind: str, valor: float, categoria: str = "", de: int = 1, ate: int | None = None, **extra) -> dict:
    return {
        "kind": kind,
        "label": categoria or "Geral",
        "category": categoria,
        "rank_from": de,
        "rank_to": ate or de,
        "amount": valor,
        **extra,
    }


def _por_jogador(resultado: dict) -> dict[int, float]:
    return {item["player_id"]: item["gross"] for item in resultado["allocations"]}


R8_T1_CLASSIFICACAO = [
    _linha(1, 1, 5, "Sub-12; Sub-1400; Feminino"),
    _linha(2, 2, 4, "Sub-12; Sub-1400"),
    _linha(3, 3, 3, "Sub-12; Sub-1400; Feminino"),
]
R8_T1_PREMIOS = [
    _premio("overall", 100),
    _premio("category", 50, "Sub-12"),
    _premio("category", 50, "Sub-1400"),
    _premio("category", 50, "Feminino"),
]


class AlocacaoSequencialTest(unittest.TestCase):
    def test_aceite_r8_t1(self) -> None:
        resultado = allocate_prizes(R8_T1_CLASSIFICACAO, R8_T1_PREMIOS, policy="best_only")
        self.assertEqual({1: 100.0, 2: 50.0, 3: 50.0}, _por_jogador(resultado))
        self.assertEqual(
            [("category", "Feminino", 1, 50.0)],
            [(u["kind"], u["category"], u["position"], u["amount"]) for u in resultado["undistributed"]],
        )
        self.assertEqual(250.0, resultado["total_announced"])
        self.assertEqual(0, resultado["excluded_withdrawn"])
        self.assertEqual(50.0, resultado["total_undistributed"])
        self.assertEqual(250.0, resultado["total_gross"] + resultado["total_undistributed"])

    def test_cada_jogador_sabe_que_premio_recebeu(self) -> None:
        resultado = allocate_prizes(R8_T1_CLASSIFICACAO, R8_T1_PREMIOS, policy="best_only")
        premios = {
            item["player_id"]: [(a["kind"], a["category"], a["position"]) for a in item["awards"]]
            for item in resultado["allocations"]
        }
        self.assertEqual(
            {1: [("overall", "", 1)], 2: [("category", "Sub-12", 1)], 3: [("category", "Sub-1400", 1)]},
            premios,
        )

    def test_d1_maior_valor_primeiro_repassa_o_geral(self) -> None:
        """O Sub-12 (60) vem antes do 2º geral (40): J2 fica com 60 e o 2º geral desce para J3."""
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 4, "Sub-12"), _linha(3, 3, 3, "Adulto")]
        premios = [_premio("overall", 100), _premio("overall", 40, de=2), _premio("category", 60, "Sub-12")]
        resultado = allocate_prizes(classificacao, premios, policy="best_only")
        self.assertEqual({1: 100.0, 2: 60.0, 3: 40.0}, _por_jogador(resultado))
        self.assertEqual([], resultado["undistributed"])

    def test_d1_valor_igual_segue_a_ordem_do_edital(self) -> None:
        classificacao = [_linha(1, 1, 5, "Sub-12; Feminino")]
        premios = [_premio("category", 50, "Feminino"), _premio("category", 50, "Sub-12")]
        resultado = allocate_prizes(classificacao, premios, policy="best_only")
        (unico,) = resultado["allocations"]
        self.assertEqual([("category", "Feminino", 1)], [(a["kind"], a["category"], a["position"]) for a in unico["awards"]])
        self.assertEqual("Sub-12", resultado["undistributed"][0]["category"])

    def test_premio_de_posicao_nao_sobe_para_quem_nao_ganhou_nada(self) -> None:
        """O 2º geral é do 2º colocado, mesmo sem prêmio para o 1º."""
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 4, "Adulto")]
        resultado = allocate_prizes(classificacao, [_premio("overall", 40, de=2)], policy="best_only")
        self.assertEqual({2: 40.0}, _por_jogador(resultado))

    def test_premio_que_soma_fica_fora_da_trava(self) -> None:
        premios = [*R8_T1_PREMIOS[:3], _premio("category", 50, "Feminino", cumulative=1)]
        resultado = allocate_prizes(R8_T1_CLASSIFICACAO, premios, policy="best_only")
        self.assertEqual({1: 150.0, 2: 50.0, 3: 50.0}, _por_jogador(resultado))
        self.assertEqual([], resultado["undistributed"])

    def test_politica_acumular_nao_trava(self) -> None:
        resultado = allocate_prizes(R8_T1_CLASSIFICACAO, R8_T1_PREMIOS, policy="cumulative")
        self.assertEqual({1: 250.0}, _por_jogador(resultado))
        self.assertEqual(250.0, resultado["total_gross"])

    def test_categoria_sem_ninguem_fica_nao_distribuida(self) -> None:
        resultado = allocate_prizes(
            R8_T1_CLASSIFICACAO, [_premio("category", 70, "Sub-8", de=1, ate=2)], policy="cumulative"
        )
        self.assertEqual([1, 2], [u["position"] for u in resultado["undistributed"]])
        self.assertEqual(140.0, resultado["total_undistributed"])


class BordasDaAlocacaoTest(unittest.TestCase):
    def test_sem_imposto_o_liquido_e_o_bruto(self) -> None:
        resultado = allocate_prizes(R8_T1_CLASSIFICACAO, R8_T1_PREMIOS, policy="best_only")
        self.assertEqual([100.0, 50.0, 50.0], [item["net"] for item in resultado["allocations"]])

    def test_tres_empatados_dividem_em_centavos(self) -> None:
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 5, "Adulto"), _linha(3, 3, 5, "Adulto")]
        resultado = allocate_prizes(classificacao, [_premio("overall", 100)], policy="best_only", tax_percent=10)
        self.assertEqual([33.33] * 3, [item["gross"] for item in resultado["allocations"]])
        self.assertEqual([33.33] * 3, [item["overall"] for item in resultado["allocations"]])
        self.assertEqual([30.0] * 3, [item["net"] for item in resultado["allocations"]])
        self.assertEqual([33.33], [award["amount"] for award in resultado["allocations"][0]["awards"]])
        self.assertEqual(99.99, resultado["total_gross"])
        self.assertEqual(89.99, resultado["total_net"])
        self.assertEqual(10.0, resultado["total_tax"])

    def test_tres_empatados_na_categoria_dividem_em_centavos(self) -> None:
        classificacao = [_linha(1, 1, 5, "Sub-12"), _linha(2, 2, 5, "Sub-12"), _linha(3, 3, 5, "Sub-12")]
        resultado = allocate_prizes(classificacao, [_premio("category", 100, "Sub-12")], policy="best_only")
        self.assertEqual([33.33] * 3, [item["category_prize"] for item in resultado["allocations"]])

    def test_so_o_2o_premio_com_empate_no_topo_divide_entre_os_dois(self) -> None:
        classificacao = [_linha(1, 1, 5, "Adulto"), _linha(2, 2, 5, "Adulto"), _linha(3, 3, 4, "Adulto")]
        resultado = allocate_prizes(classificacao, [_premio("overall", 60, de=2)], policy="best_only")
        self.assertEqual({1: 30.0, 2: 30.0}, _por_jogador(resultado))

    def test_valor_abaixo_de_1_segue_a_d1_e_o_zero_nao_conta(self) -> None:
        classificacao = [_linha(1, 1, 5, "A; B")]
        premios = [_premio("category", 0.3, "A"), _premio("category", 0.5, "B"), _premio("category", 0, "A", de=2)]
        resultado = allocate_prizes(classificacao, premios, policy="best_only")
        self.assertEqual({1: 0.5}, _por_jogador(resultado))
        self.assertEqual([("A", 1, 0.3)], [(u["category"], u["position"], u["amount"]) for u in resultado["undistributed"]])
        self.assertEqual(0.8, resultado["total_announced"])

    def test_categoria_com_dois_pontos_no_nome(self) -> None:
        classificacao = [_linha(1, 1, 5, "Clube: Sócio")]
        resultado = allocate_prizes(classificacao, [_premio("category", 40, "Clube: Sócio")], policy="best_only")
        self.assertEqual({1: 40.0}, _por_jogador(resultado))


class EmpateAntesDaTravaTest(unittest.TestCase):
    """Empate divide o bolo das posições primeiro; a trava vale sobre o que cada um recebeu."""

    CLASSIFICACAO = [_linha(1, 1, 5, "Sub-12"), _linha(2, 2, 5, "Sub-12"), _linha(3, 3, 4, "Sub-12")]
    PREMIOS = [_premio("overall", 100), _premio("overall", 60, de=2), _premio("category", 50, "Sub-12")]

    def test_hort_com_dois_empatados_soma_igual_a_de_antes(self) -> None:
        resultado = allocate_prizes(self.CLASSIFICACAO, self.PREMIOS, policy="best_only", tie_split="hort")
        por_jogador = _por_jogador(resultado)
        self.assertEqual(90.0, por_jogador[1])
        self.assertEqual(70.0, por_jogador[2])
        self.assertEqual(160.0, por_jogador[1] + por_jogador[2])
        self.assertEqual(50.0, por_jogador[3], "o Sub-12 passa para o primeiro sem prêmio")

    def test_divisao_igual(self) -> None:
        resultado = allocate_prizes(self.CLASSIFICACAO, self.PREMIOS, policy="best_only")
        self.assertEqual({1: 80.0, 2: 80.0, 3: 50.0}, _por_jogador(resultado))


class CategoriaInexistenteTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.replace_tournament_categories(
            self.tournament_id,
            [{"name": "Sub-12", "kind": "age", "max_value": 12}, {"name": "Feminino", "kind": "sex", "sex": "F"}],
        )

    def test_premio_de_categoria_que_nao_existe_e_recusado(self) -> None:
        with self.assertRaisesRegex(AppError, "Sub12"):
            self.prize_service.replace_prizes(
                self.tournament_id, [_premio("category", 50, "Sub12", label="Sub12")]
            )
        self.assertEqual([], self.db.list_tournament_prizes(self.tournament_id))

    def test_caixa_e_acento_nao_importam(self) -> None:
        self.prize_service.replace_prizes(self.tournament_id, [{**_premio("category", 50, "sub-12"), "label": "Sub"}])
        self.assertEqual(1, len(self.db.list_tournament_prizes(self.tournament_id)))

    def test_categoria_escrita_a_mao_no_jogador_vale(self) -> None:
        """Categoria manual ("Convidados") não está no edital, mas está na classificação."""
        self.db.create_player(self.tournament_id, name="Zé", category="Convidados")
        self.prize_service.replace_prizes(self.tournament_id, [_premio("category", 50, "Convidados")])
        self.assertEqual(1, len(self.db.list_tournament_prizes(self.tournament_id)))

    def test_a_tela_de_configuracoes_tambem_recusa(self) -> None:
        """A tela grava prêmios e categorias juntos: vale o edital que está sendo salvo."""
        from src.services.tournament_configuration import PerfilTorneio

        perfil = PerfilTorneio(
            torneio={"name": "Torneio teste", "scope": "standalone", "competition_type": "individual", "rounds_count": "3"},
            ajustes={},
            agenda=[],
        )
        with self.assertRaisesRegex(AppError, "Sub12"):
            self.tournament_service.save_tournament_configuration(
                self.tournament_id,
                perfil,
                [_premio("category", 50, "Sub12")],
                [{"name": "Sub-12", "kind": "age", "max_value": 12}],
                ["position", "name", "points"],
            )



class RelatorioAnunciadoDistribuidoTest(CoreServiceTestCase):
    def test_relatorio_mostra_o_anunciado_e_o_que_nao_saiu(self) -> None:
        from pathlib import Path

        self._create_players(2)
        rodada = self.service.generate_next_round(self.tournament_id)
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.prize_service.replace_prizes(
            self.tournament_id, [_premio("overall", 100), _premio("overall", 30, de=3, label="3º geral")]
        )
        caminho = Path(self.temp_dir.name) / "premiacao.csv"
        self.export_service.export_prize_report(self.tournament_id, caminho)
        conteudo = caminho.read_text(encoding="utf-8-sig")
        self.assertIn("Total anunciado", conteudo)
        self.assertIn("Prêmios não distribuídos", conteudo)
        self.assertIn("3º geral", conteudo)


if __name__ == "__main__":
    unittest.main()
