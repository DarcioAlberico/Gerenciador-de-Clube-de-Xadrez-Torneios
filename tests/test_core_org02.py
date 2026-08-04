"""ORG-02 — premiação conforme o edital.

O alocador tinha três defeitos que só aparecem quando se compara a planilha do
programa com o edital impresso:

1. **Prêmio de categoria casava só com a categoria PRINCIPAL do jogador.** O
   prêmio "Feminino" nunca era alocado sozinho, e um Sub-12/Sub-1400 concorria a
   um só. A ORG-01 deu a cada jogador todas as suas categorias; aqui o alocador
   passou a enxergá-las.
2. **A política era do torneio inteiro.** Quase todo edital soma o prêmio
   Feminino ao geral mesmo dizendo "apenas o maior prêmio" para o resto — e não
   havia como dizer isso.
3. **O "Sistema Hort" não era o Sistema Hort.** O que existia combinava geral
   com categoria (`max(geral, (geral+categoria)/2)`), uma "interpretação comum"
   que não confere com fonte nenhuma. O Hort é regra de rateio entre EMPATADOS:
   cada um recebe 50% do prêmio da própria posição no desempate mais 50% do bolo
   dividido por igual.

E desistente continuava concorrendo a prêmio, o que nenhum edital admite.
"""

from __future__ import annotations

import unittest

from src.services.prizes import (
    PRIZE_POLICIES,
    PRIZE_TIE_SPLITS,
    allocate_prizes,
    is_withdrawn,
)
from tests.support.core_service_base import CoreServiceTestCase


def _linha(player_id: int, nome: str, posicao: int, pontos: float, categorias: str, **extra) -> dict:
    base = {
        "player_id": player_id,
        "name": nome,
        "position": posicao,
        "points": pontos,
        "category": categorias.split(";")[0].strip(),
        "categories": categorias,
        "player_status": "active",
        "active": 1,
    }
    base.update(extra)
    return base


class SistemaHortTest(unittest.TestCase):
    """O Hort de verdade: 50% da própria posição + 50% do bolo por igual."""

    EMPATADOS = [
        _linha(1, "A", 1, 5.0, "Adulto"),
        _linha(2, "B", 2, 5.0, "Adulto"),
    ]
    PREMIOS = [
        {"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 1000},
        {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 600},
    ]

    def test_divisao_igual_e_o_padrao(self) -> None:
        resultado = allocate_prizes(self.EMPATADOS, self.PREMIOS, "best_only", 0.0)
        self.assertEqual([800.0, 800.0], [item["gross"] for item in resultado["allocations"]])

    def test_hort_reconhece_o_desempate_sem_dar_tudo_ao_primeiro(self) -> None:
        # A: 50% de 1000 + metade do bolo/2 = 500 + 400 = 900
        # B: 50% de  600 + 400 = 700
        resultado = allocate_prizes(
            self.EMPATADOS, self.PREMIOS, "best_only", 0.0, tie_split="hort"
        )
        por_nome = {item["name"]: item["gross"] for item in resultado["allocations"]}
        self.assertEqual(900.0, por_nome["A"])
        self.assertEqual(700.0, por_nome["B"])

    def test_hort_nao_cria_nem_destroi_dinheiro(self) -> None:
        """A soma tem de fechar com o bolo, seja qual for o rateio."""
        for split in PRIZE_TIE_SPLITS:
            with self.subTest(split=split):
                resultado = allocate_prizes(
                    self.EMPATADOS, self.PREMIOS, "best_only", 0.0, tie_split=split
                )
                self.assertEqual(1600.0, resultado["total_gross"])

    def test_sem_empate_o_hort_nao_muda_nada(self) -> None:
        sozinhos = [_linha(1, "A", 1, 5.0, "Adulto"), _linha(2, "B", 2, 4.0, "Adulto")]
        igual = allocate_prizes(sozinhos, self.PREMIOS, "best_only", 0.0)
        hort = allocate_prizes(sozinhos, self.PREMIOS, "best_only", 0.0, tie_split="hort")
        self.assertEqual(
            [item["gross"] for item in igual["allocations"]],
            [item["gross"] for item in hort["allocations"]],
        )

    def test_hort_saiu_das_politicas_de_combinacao(self) -> None:
        """Ele nunca foi política de combinação — ver o cabeçalho de `prizes`."""
        self.assertNotIn("hort", PRIZE_POLICIES)
        self.assertIn("hort", PRIZE_TIE_SPLITS)


class CategoriasDoJogadorTest(unittest.TestCase):
    CLASSIFICACAO = [
        _linha(1, "Duda", 1, 5.0, "Adulto; Sub-2200"),
        _linha(2, "Bia", 2, 4.0, "Sub-12; Sub-1800; Feminino"),
        _linha(3, "Ana", 3, 3.0, "Sub-10; Sub-1400; Feminino"),
    ]

    def test_premio_feminino_e_alocado_automaticamente(self) -> None:
        """Critério de aceite do ORG-02."""
        premios = [
            {"kind": "category", "label": "Feminino", "category": "Feminino",
             "rank_from": 1, "rank_to": 1, "amount": 300},
        ]
        resultado = allocate_prizes(self.CLASSIFICACAO, premios, "best_only", 0.0)
        self.assertEqual([("Bia", 300.0)], [(i["name"], i["gross"]) for i in resultado["allocations"]])

    def test_jogador_concorre_a_todas_as_categorias_dele(self) -> None:
        premios = [
            {"kind": "category", "label": "Feminino", "category": "Feminino",
             "rank_from": 1, "rank_to": 1, "amount": 300},
            {"kind": "category", "label": "Sub-12", "category": "Sub-12",
             "rank_from": 1, "rank_to": 1, "amount": 200},
        ]
        resultado = allocate_prizes(self.CLASSIFICACAO, premios, "cumulative", 0.0)
        por_nome = {item["name"]: item["gross"] for item in resultado["allocations"]}
        self.assertEqual(500.0, por_nome["Bia"])

    def test_politica_do_torneio_vale_para_a_categoria(self) -> None:
        """Critério de aceite: multi-categoria segue a política configurada."""
        premios = [
            {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 400},
            {"kind": "category", "label": "Feminino", "category": "Feminino",
             "rank_from": 1, "rank_to": 1, "amount": 300},
        ]
        melhor = allocate_prizes(self.CLASSIFICACAO, premios, "best_only", 0.0)
        acumula = allocate_prizes(self.CLASSIFICACAO, premios, "cumulative", 0.0)
        self.assertEqual(400.0, {i["name"]: i["gross"] for i in melhor["allocations"]}["Bia"])
        self.assertEqual(700.0, {i["name"]: i["gross"] for i in acumula["allocations"]}["Bia"])

    def test_premio_marcado_como_soma_acumula_apesar_da_politica(self) -> None:
        """É o caso do Feminino em quase todo edital brasileiro."""
        premios = [
            {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 400},
            {"kind": "category", "label": "Feminino", "category": "Feminino",
             "rank_from": 1, "rank_to": 1, "amount": 300, "cumulative": 1},
        ]
        resultado = allocate_prizes(self.CLASSIFICACAO, premios, "best_only", 0.0)
        self.assertEqual(700.0, {i["name"]: i["gross"] for i in resultado["allocations"]}["Bia"])

    def test_classificacao_antiga_sem_categorias_ainda_funciona(self) -> None:
        """Base anterior à ORG-01 só tem a principal, e ela continua valendo."""
        antiga = [{"player_id": 1, "name": "Zé", "position": 1, "points": 5.0, "category": "Absoluto"}]
        premios = [{"kind": "category", "label": "Absoluto", "category": "Absoluto",
                    "rank_from": 1, "rank_to": 1, "amount": 100}]
        resultado = allocate_prizes(antiga, premios, "best_only", 0.0)
        self.assertEqual(100.0, resultado["allocations"][0]["gross"])


class DesistentesTest(unittest.TestCase):
    CLASSIFICACAO = [
        _linha(1, "Duda", 1, 5.0, "Adulto"),
        _linha(2, "Fuga", 2, 4.0, "Adulto", player_status="withdrawn"),
        _linha(3, "Ana", 3, 3.0, "Adulto"),
    ]
    PREMIOS = [
        {"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 500},
        {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 300},
    ]

    def test_por_padrao_o_desistente_continua_concorrendo(self) -> None:
        """Mudar isso calado alteraria a premiacao de todo torneio existente."""
        resultado = allocate_prizes(self.CLASSIFICACAO, self.PREMIOS, "best_only", 0.0)
        self.assertIn("Fuga", [item["name"] for item in resultado["allocations"]])

    def test_edital_pode_excluir_desistentes(self) -> None:
        resultado = allocate_prizes(
            self.CLASSIFICACAO, self.PREMIOS, "best_only", 0.0, exclude_withdrawn=True
        )
        nomes = [item["name"] for item in resultado["allocations"]]
        self.assertEqual(["Duda", "Ana"], nomes)
        self.assertEqual(1, resultado["excluded_withdrawn"])
        # Ana sobe para o 2o premio, que era do desistente.
        self.assertEqual(300.0, {i["name"]: i["gross"] for i in resultado["allocations"]}["Ana"])

    def test_jogador_inativo_tambem_conta_como_fora(self) -> None:
        self.assertTrue(is_withdrawn({"player_status": "active", "active": 0}))
        self.assertTrue(is_withdrawn({"player_status": "desistente", "active": 1}))
        self.assertFalse(is_withdrawn({"player_status": "active", "active": 1}))


class EditalRealTest(unittest.TestCase):
    """Critério de aceite: fixture de premiação conhecida confere.

    Edital de open pequeno: geral 1º/2º/3º, melhor Feminino e melhor Sub-14,
    ambos somando ao geral (como o edital brasileiro típico escreve), com dois
    empatados no topo e rateio Hort.
    """

    CLASSIFICACAO = [
        _linha(1, "Rafael", 1, 5.0, "Adulto; Sub-2200"),
        _linha(2, "Marina", 2, 5.0, "Adulto; Sub-1800; Feminino"),
        _linha(3, "Tiago", 3, 4.0, "Sub-14; Sub-1400"),
        _linha(4, "Helena", 4, 3.0, "Sub-14; Sub-1400; Feminino"),
    ]
    EDITAL = [
        {"kind": "overall", "label": "1o geral", "rank_from": 1, "rank_to": 1, "amount": 1000},
        {"kind": "overall", "label": "2o geral", "rank_from": 2, "rank_to": 2, "amount": 600},
        {"kind": "overall", "label": "3o geral", "rank_from": 3, "rank_to": 3, "amount": 400},
        {"kind": "category", "label": "Melhor Feminino", "category": "Feminino",
         "rank_from": 1, "rank_to": 1, "amount": 300, "cumulative": 1},
        {"kind": "category", "label": "Melhor Sub-14", "category": "Sub-14",
         "rank_from": 1, "rank_to": 1, "amount": 200, "cumulative": 1},
    ]

    def test_edital_fecha_com_a_bolsa_anunciada(self) -> None:
        resultado = allocate_prizes(
            self.CLASSIFICACAO, self.EDITAL, "best_only", 0.0, tie_split="hort"
        )
        por_nome = {item["name"]: item["gross"] for item in resultado["allocations"]}

        # Rafael e Marina empatam: Hort sobre 1000 + 600.
        self.assertEqual(900.0, por_nome["Rafael"])
        # Marina soma o Feminino ao que o Hort lhe deu (700 + 300).
        self.assertEqual(1000.0, por_nome["Marina"])
        # Tiago fica com o 3o geral e o Sub-14.
        self.assertEqual(600.0, por_nome["Tiago"])
        # Helena nao ganha: e a 2a do Feminino e o 2o do Sub-14.
        self.assertNotIn("Helena", por_nome)

        # A bolsa anunciada e 1000+600+400+300+200 = 2500.
        self.assertEqual(2500.0, resultado["total_gross"])

    def test_imposto_incide_sobre_o_total(self) -> None:
        resultado = allocate_prizes(
            self.CLASSIFICACAO, self.EDITAL, "best_only", 10.0, tie_split="hort"
        )
        self.assertEqual(2250.0, resultado["total_net"])
        self.assertEqual(250.0, resultado["total_tax"])


class PersistenciaDoPremioTest(CoreServiceTestCase):
    def test_politica_por_premio_e_moeda_sobrevivem(self) -> None:
        self.prize_service.replace_prizes(
            self.tournament_id,
            [
                {
                    "kind": "category",
                    "label": "Melhor Feminino",
                    "category": "Feminino",
                    "rank_from": "1",
                    "rank_to": "1",
                    "amount": "300",
                    "cumulative": True,
                    "currency": "BRL",
                }
            ],
        )
        salvo = self.db.list_tournament_prizes(self.tournament_id)[0]
        self.assertEqual(1, salvo["cumulative"])
        self.assertEqual("BRL", salvo["currency"])

    def test_configuracao_de_rateio_e_validada(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError):
            self.tournament_service.save_profile(
                self.tournament_id,
                {"name": "T", "rounds_count": "5", "bye_points": "1"},
                {"prize_tie_split": "inventado"},
                [],
            )
