"""ORG-01 — categorias configuráveis por torneio.

Três problemas na mesma raiz: a categoria era CÓDIGO, não dado.

1. **As faixas eram constantes** em `core/categories.py` — Sub-08 a Sub-20,
   S50+/S65+ e cortes de 1400/1800/2200. Um edital com Sub-07/09/11/13,
   Veterano 60+ ou cortes de 1600/2000 não tinha onde caber, e o campo
   "Categorias" da configuração era texto livre que só aparecia no cabeçalho de
   um relatório.
2. **"Feminino" era tag de prêmio, não categoria.** Não existia classificação
   feminina: a jogadora aparecia no Sub-10 e em lugar nenhum mais, porque a
   classificação por categoria agrupava pela categoria PRINCIPAL — e principal
   só tem uma.
3. **A data de referência da idade não era parametrizável**: usava o ano do
   torneio, sem alternativa.

O compromisso do item é não mexer no que já existe: torneio sem categoria
cadastrada tem de continuar produzindo exatamente as mesmas faixas de antes.
Por isso metade destes testes compara o motor novo com o comportamento antigo.
"""

from __future__ import annotations

import unittest

from src.core.categories import age_category, competition_category_payload, rating_category
from src.services.categories import (
    AGE,
    RATING,
    CategoryDefinition,
    age_in_year,
    awardable_names,
    categories_of,
    category_names,
    category_of_kind,
    category_standings,
    default_categories,
    group_by_category,
    matches,
    matching_categories,
    narrowest_by_kind,
    primary_category,
)
from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase

PADRAO = default_categories()


def _jogador(**campos: object) -> dict:
    base = {"birth_date": "", "sex": "", "prize_tags": ""}
    base.update(campos)
    return base


class CompatibilidadeComOPadraoTest(unittest.TestCase):
    """O conjunto padrão tem de reproduzir o comportamento anterior ao ORG-01."""

    def test_faixa_etaria_bate_com_o_calculo_antigo(self) -> None:
        for nascimento in ("2018", "2016", "2014", "2012", "2010", "2008", "2006", "2000", "1980", "1975", "1958", "1940"):
            with self.subTest(nascimento=nascimento):
                self.assertEqual(
                    age_category(nascimento, 2026),
                    category_of_kind(
                        PADRAO, AGE, player=_jogador(birth_date=nascimento), reference_year=2026
                    ),
                )

    def test_faixa_de_rating_bate_com_o_calculo_antigo(self) -> None:
        for rating in (0, 800, 1399, 1400, 1799, 1800, 2199, 2200, 2600):
            with self.subTest(rating=rating):
                self.assertEqual(
                    rating_category(rating),
                    category_of_kind(
                        PADRAO, RATING, player=_jogador(), reference_year=2026, rating=rating
                    ),
                )

    def test_adulto_e_aberto_continuam_existindo(self) -> None:
        """Eram os fallbacks implícitos do código antigo; sem eles o padrão muda."""
        nomes = {item.name for item in PADRAO}
        self.assertIn("Adulto", nomes)
        self.assertIn("Aberto", nomes)


class FaixasTest(unittest.TestCase):
    def test_maximo_de_idade_e_inclusivo(self) -> None:
        """"Sub-12" aceita quem completa 12 no ano."""
        sub12 = CategoryDefinition(name="Sub-12", kind=AGE, max_value=12)
        self.assertTrue(matches(sub12, _jogador(birth_date="2014"), reference_year=2026))
        self.assertFalse(matches(sub12, _jogador(birth_date="2013"), reference_year=2026))

    def test_maximo_de_rating_e_exclusivo(self) -> None:
        """"Sub-1400" recusa exatamente 1400 — é como o edital fala."""
        sub1400 = CategoryDefinition(name="Sub-1400", kind=RATING, max_value=1400)
        self.assertTrue(matches(sub1400, _jogador(), reference_year=2026, rating=1399))
        self.assertFalse(matches(sub1400, _jogador(), reference_year=2026, rating=1400))

    def test_faixa_aberta_para_cima(self) -> None:
        veterano = CategoryDefinition(name="Veterano 60+", kind=AGE, min_value=60)
        self.assertTrue(matches(veterano, _jogador(birth_date="1960"), reference_year=2026))
        self.assertFalse(matches(veterano, _jogador(birth_date="1970"), reference_year=2026))

    def test_sem_rating_nao_entra_em_faixa_de_rating(self) -> None:
        sub1400 = CategoryDefinition(name="Sub-1400", kind=RATING, max_value=1400)
        self.assertFalse(matches(sub1400, _jogador(), reference_year=2026, rating=0))

    def test_sem_nascimento_nao_entra_em_faixa_etaria(self) -> None:
        sub12 = CategoryDefinition(name="Sub-12", kind=AGE, max_value=12)
        self.assertFalse(matches(sub12, _jogador(), reference_year=2026))


class DataDeReferenciaTest(unittest.TestCase):
    """Critério de aceite: a data de referência altera o cálculo de idade."""

    def test_idade_e_a_completada_no_ano_de_referencia(self) -> None:
        self.assertEqual(12, age_in_year("2014", 2026))
        self.assertEqual(11, age_in_year("2014", 2025))

    def test_virada_de_ano_muda_a_categoria(self) -> None:
        """Torneio que atravessa o reveillon: o edital diz qual ano vale."""
        sub12 = CategoryDefinition(name="Sub-12", kind=AGE, max_value=12)
        jogador = _jogador(birth_date="2014")
        self.assertTrue(matches(sub12, jogador, reference_year=2026))
        self.assertFalse(matches(sub12, jogador, reference_year=2027))

    def test_data_da_categoria_ganha_do_ano_do_torneio(self) -> None:
        sub12 = CategoryDefinition(
            name="Sub-12", kind=AGE, max_value=12, reference_date="2026-01-01"
        )
        # O torneio diz 2027; a categoria diz 2026, e é a dela que vale.
        self.assertTrue(matches(sub12, _jogador(birth_date="2014"), reference_year=2027))

    def test_nascimento_em_qualquer_formato(self) -> None:
        for valor in ("2014", "2014-06-15", "15/06/2014"):
            with self.subTest(valor=valor):
                self.assertEqual(12, age_in_year(valor, 2026))


class MultiplasCategoriasTest(unittest.TestCase):
    MENINA = _jogador(birth_date="2016", sex="F", prize_tags="Feminino")

    def test_participa_de_todas_as_faixas_que_a_aceitam(self) -> None:
        nomes = [item.name for item in matching_categories(
            PADRAO, self.MENINA, reference_year=2026, rating=1200
        )]
        self.assertIn("Sub-10", nomes)
        self.assertIn("Sub-20", nomes)  # um Sub-10 cabe no Sub-20
        self.assertIn("Feminino", nomes)

    def test_as_dela_sao_a_mais_estreita_de_cada_dimensao(self) -> None:
        nomes = [item.name for item in narrowest_by_kind(
            PADRAO, self.MENINA, reference_year=2026, rating=1200
        )]
        self.assertEqual(["Sub-10", "Sub-1400", "Feminino"], nomes)

    def test_veterano_fica_com_a_faixa_mais_especifica(self) -> None:
        veterano = _jogador(birth_date="1958", sex="M")
        nomes = awardable_names(PADRAO, player=veterano, reference_year=2026, rating=1900)
        self.assertIn("S65+", nomes)
        self.assertNotIn("S50+", nomes)

    def test_categoria_nao_premiavel_fica_de_fora(self) -> None:
        regras = [
            CategoryDefinition(name="Sub-12", kind=AGE, max_value=12),
            CategoryDefinition(name="Sub-1400", kind=RATING, max_value=1400, awards=False),
        ]
        nomes = awardable_names(
            regras, player=_jogador(birth_date="2016"), reference_year=2026, rating=1200
        )
        self.assertEqual(["Sub-12"], nomes)


class CategoriaPrincipalTest(unittest.TestCase):
    def test_idade_na_frente_do_rating(self) -> None:
        self.assertEqual(
            "Sub-10",
            primary_category(
                PADRAO, _jogador(birth_date="2016"), reference_year=2026, rating=1200
            ),
        )

    def test_nome_inventado_pelo_arbitro_nao_e_apagado(self) -> None:
        self.assertEqual(
            "Convidados",
            primary_category(
                PADRAO,
                _jogador(birth_date="2016"),
                reference_year=2026,
                rating=1200,
                current="Convidados",
            ),
        )

    def test_faixa_gravada_sem_nascimento_permanece(self) -> None:
        """O detalhe que quase se perdeu: "Sub-18" sem data não vira faixa de rating."""
        self.assertEqual(
            "Sub-18",
            primary_category(
                PADRAO, _jogador(), reference_year=2026, rating=1600, current="Sub-18"
            ),
        )

    def test_faixa_gravada_cede_para_o_calculo_da_mesma_dimensao(self) -> None:
        self.assertEqual(
            "Sub-10",
            primary_category(
                PADRAO,
                _jogador(birth_date="2016"),
                reference_year=2026,
                rating=1200,
                current="Sub-18",
            ),
        )


class ClassificacaoPorCategoriaTest(unittest.TestCase):
    CLASSIFICACAO = [
        {"position": 1, "name": "Duda", "category": "Adulto", "categories": "Adulto; Sub-2200"},
        {"position": 2, "name": "Bia", "category": "Sub-12", "categories": "Sub-12; Sub-1800; Feminino"},
        {"position": 3, "name": "Ana", "category": "Sub-10", "categories": "Sub-10; Sub-1400; Feminino"},
    ]

    def test_jogadora_entra_na_classificacao_feminina_e_na_faixa_dela(self) -> None:
        grupos = group_by_category(self.CLASSIFICACAO)
        self.assertEqual(["Bia", "Ana"], [item["name"] for item in grupos["Feminino"]])
        self.assertEqual(["Ana"], [item["name"] for item in grupos["Sub-10"]])

    def test_classificacao_da_categoria_renumera_e_guarda_a_geral(self) -> None:
        feminina = category_standings(self.CLASSIFICACAO, "Feminino")
        self.assertEqual([1, 2], [item["position"] for item in feminina])
        self.assertEqual([2, 3], [item["overall_position"] for item in feminina])

    def test_categoria_escrita_a_mao_nao_some(self) -> None:
        """Base sem `categories` (anterior ao ORG-01) continua agrupando."""
        antiga = [{"position": 1, "name": "Zé", "category": "Absoluto"}]
        self.assertEqual(["Absoluto"], categories_of(antiga[0]))
        self.assertEqual(["Absoluto"], category_names(antiga))

    def test_categoria_inexistente_devolve_vazio(self) -> None:
        self.assertEqual([], category_standings(self.CLASSIFICACAO, "Sub-08"))
        self.assertEqual([], category_standings(self.CLASSIFICACAO, ""))


class TorneioComEditalProprioTest(CoreServiceTestCase):
    """Critério de aceite: edital fora do padrão, configurável sem texto livre."""

    EDITAL = [
        {"name": "Sub-07", "kind": "age", "max_value": 7, "position": 0},
        {"name": "Sub-09", "kind": "age", "max_value": 9, "position": 1},
        {"name": "Sub-11", "kind": "age", "max_value": 11, "position": 2},
        {"name": "Sub-13", "kind": "age", "max_value": 13, "position": 3},
        {"name": "Veterano 60+", "kind": "age", "min_value": 60, "position": 4},
        {"name": "Sub-1600", "kind": "rating", "max_value": 1600, "position": 5},
        {"name": "Feminino", "kind": "sex", "sex": "F", "position": 6},
    ]

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Aberto do Edital", rounds_count=3)
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET start_date = ? WHERE id = ?",
                ("2026-03-01", self.tournament_id),
            )

    def test_faixas_fora_do_padrao_valem_para_o_jogador(self) -> None:
        self.db.replace_tournament_categories(self.tournament_id, self.EDITAL)
        player_id = self.db.create_player(
            self.tournament_id, name="Ana", birth_date="2017", sex="F", rating=1300
        )
        player = self.db.get_player(player_id)
        self.assertEqual("Sub-09", player["category"])
        self.assertEqual("Sub-09", player["age_category"])
        self.assertEqual("Sub-1600", player["rating_category"])
        self.assertEqual("Sub-09; Sub-1600; Feminino", player["categories"])

    def test_torneio_sem_edital_usa_o_padrao(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id, name="Ana", birth_date="2017", sex="F", rating=1300
        )
        player = self.db.get_player(player_id)
        self.assertEqual("Sub-10", player["category"])
        self.assertEqual("Sub-10; Sub-1400; Feminino", player["categories"])

    def test_data_de_referencia_do_torneio_muda_a_faixa(self) -> None:
        self.db.replace_tournament_categories(self.tournament_id, self.EDITAL)
        self.db.save_tournament_settings(
            self.tournament_id, {"category_reference_date": "2028-01-01"}
        )
        player_id = self.db.create_player(
            self.tournament_id, name="Ana", birth_date="2017", sex="F", rating=1300
        )
        # Em 2028 ela completa 11, e ja nao e Sub-09.
        self.assertEqual("Sub-11", self.db.get_player(player_id)["category"])

    def test_categorias_sao_regravadas_por_inteiro(self) -> None:
        self.db.replace_tournament_categories(self.tournament_id, self.EDITAL)
        self.db.replace_tournament_categories(
            self.tournament_id, [{"name": "Única", "kind": "open"}]
        )
        salvas = self.db.list_tournament_categories(self.tournament_id)
        self.assertEqual(["Única"], [item["name"] for item in salvas])

    def test_linha_sem_nome_e_descartada(self) -> None:
        self.db.replace_tournament_categories(
            self.tournament_id,
            [{"name": "  ", "kind": "age"}, {"name": "Sub-13", "kind": "age", "max_value": 13}],
        )
        salvas = self.db.list_tournament_categories(self.tournament_id)
        self.assertEqual(["Sub-13"], [item["name"] for item in salvas])

    def test_servico_recusa_nome_repetido(self) -> None:
        """A tabela tem UNIQUE; sem esta checagem o erro do SQLite ia para a tela."""
        with self.assertRaises(AppError) as erro:
            self.tournament_service.replace_categories(
                self.tournament_id,
                [
                    {"name": "Sub-13", "kind": "age", "max_value": 13},
                    {"name": "sub-13", "kind": "age", "max_value": 14},
                ],
            )
        self.assertIn("repetida", str(erro.exception))

    def test_servico_guarda_a_ordem_das_linhas(self) -> None:
        self.tournament_service.replace_categories(
            self.tournament_id,
            [
                {"name": "Feminino", "kind": "sex", "sex": "F"},
                {"name": "Sub-13", "kind": "age", "max_value": 13},
            ],
        )
        salvas = self.tournament_service.list_categories(self.tournament_id)
        self.assertEqual(["Feminino", "Sub-13"], [item["name"] for item in salvas])
        self.assertEqual([0, 1], [item["position"] for item in salvas])

    def test_servico_normaliza_o_que_veio_da_tela(self) -> None:
        self.tournament_service.replace_categories(
            self.tournament_id,
            [{"name": "  Sub-13  ", "kind": "AGE", "max_value": "13", "sex": "f"}],
        )
        salva = self.tournament_service.list_categories(self.tournament_id)[0]
        self.assertEqual("Sub-13", salva["name"])
        self.assertEqual("age", salva["kind"])
        self.assertEqual(13, salva["max_value"])


class ClassificacaoFemininaAutomaticaTest(CoreServiceTestCase):
    """Critério de aceite: classificação feminina sai sozinha quando configurada."""

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Aberto", rounds_count=3)
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET start_date = ? WHERE id = ?",
                ("2026-03-01", self.tournament_id),
            )
        self.ids = [
            self.db.create_player(self.tournament_id, name="Ana", birth_date="2016", sex="F", rating=1300),
            self.db.create_player(self.tournament_id, name="Bia", birth_date="2014", sex="F", rating=1500),
            self.db.create_player(self.tournament_id, name="Caio", birth_date="2016", sex="M", rating=1600),
            self.db.create_player(self.tournament_id, name="Duda", birth_date="2000", sex="M", rating=2100),
        ]
        round_id = self.db.create_round_with_pairings(
            self.tournament_id,
            1,
            [
                {"board_number": 1, "white_player_id": self.ids[3], "black_player_id": self.ids[0], "result": "1-0"},
                {"board_number": 2, "white_player_id": self.ids[1], "black_player_id": self.ids[2], "result": "1-0"},
            ],
        )
        self.db.close_round(round_id)

    def test_ata_traz_a_classificacao_feminina(self) -> None:
        _titulo, _headers, rows = self.export_service._category_winners_section(self.tournament_id)
        femininas = [row[2] for row in rows if row[0] == "Feminino"]
        self.assertEqual(["Bia", "Ana"], femininas)

    def test_jogadora_aparece_na_faixa_dela_tambem(self) -> None:
        _titulo, _headers, rows = self.export_service._category_winners_section(self.tournament_id)
        sub10 = {row[2] for row in rows if row[0] == "Sub-10"}
        self.assertIn("Ana", sub10)

    def test_podio_tem_campea_feminina(self) -> None:
        dados = self.export_service._podium_data(self.tournament_id)
        por_categoria = {item["category"]: item["name"] for item in dados["categories"]}
        self.assertEqual("Bia", por_categoria["Feminino"])

    def test_classificacao_carrega_as_categorias_do_jogador(self) -> None:
        standings = self.service.standings(self.tournament_id)
        ana = next(item for item in standings if item["name"] == "Ana")
        self.assertIn("Feminino", categories_of(ana))
        self.assertIn("Sub-10", categories_of(ana))


class PayloadDeCategoriaTest(unittest.TestCase):
    def test_membro_sem_torneio_usa_o_padrao(self) -> None:
        payload = competition_category_payload(birth_date="2016", rating=1200, sex="F", year=2026)
        self.assertEqual("Sub-10", payload["category"])
        self.assertEqual("Sub-10; Sub-1400; Feminino", payload["categories"])
        self.assertEqual("Feminino", payload["prize_tags"])

    def test_edital_proprio_substitui_o_padrao(self) -> None:
        regras = [CategoryDefinition(name="Sub-09", kind=AGE, max_value=9)]
        payload = competition_category_payload(
            birth_date="2017", rating=1200, year=2026, definitions=regras
        )
        self.assertEqual("Sub-09", payload["category"])
        self.assertEqual("Sub-09", payload["categories"])

    def test_data_de_referencia_explicita(self) -> None:
        payload = competition_category_payload(
            birth_date="2014", rating=1200, year=2026, reference_date="2028-06-01"
        )
        self.assertEqual("Sub-14", payload["category"])
