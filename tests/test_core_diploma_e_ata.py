"""Os dois últimos defeitos `alta` da auditoria: diploma e ata.

1. **O diploma de categoria não acompanhou o ORG-01** — regressão do próprio
   trabalho recente. A classificação e a premiação passaram a usar todas as
   categorias do jogador (`categories_of`); o serviço de diplomas continuou
   olhando só a PRINCIPAL. Com isso o combo não oferecia "Feminino" nem as
   faixas de rating, pedir o diploma da campeã feminina levantava "Nenhum
   jogador encontrado", e no Top N por categoria ela era numerada pela faixa
   etária.
2. **A ata de torneio por equipes descartava a premiação em silêncio.** A
   distribuição automática não se aplica a equipes (depende da classificação
   individual) e a ata engolia o `AppError` — mas o cadastro de prêmios ACEITA
   equipes, inclusive o tipo "Tabuleiro (equipes)", que só existe para elas. O
   documento saía sem uma linha sobre o dinheiro anunciado.
"""

from __future__ import annotations

from tests.support.core_service_base import CoreServiceTestCase


class DiplomaDeCategoriaTest(CoreServiceTestCase):
    """Bruno (M), Ana (F) e Carla (F), todos Sub-12 e Sub-1800."""

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Aberto", rounds_count=3)
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET start_date = ? WHERE id = ?",
                ("2026-03-01", self.tournament_id),
            )
        self.ids = [
            self.db.create_player(
                self.tournament_id, name=nome, birth_date="2015", sex=sexo, rating=rating
            )
            for nome, sexo, rating in (("Bruno", "M", 1600), ("Ana", "F", 1500), ("Carla", "F", 1400))
        ]
        round_id = self.db.create_round_with_pairings(
            self.tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": self.ids[0],
                    "black_player_id": self.ids[1],
                    "result": "1-0",
                }
            ],
        )
        self.db.close_round(round_id)

    def _premiados(self, categoria: str) -> list[tuple[str, str, str]]:
        return [
            (item["name"], item["category"], item["category_position_label"])
            for item in self.certificate_service.tournament_recipients(
                self.tournament_id, certificate_type="category_award", category=categoria
            )
        ]

    def test_combo_oferece_todas_as_categorias_premiaveis(self) -> None:
        """Feminino e as faixas de rating simplesmente nao apareciam."""
        categorias = self.certificate_service.tournament_categories(self.tournament_id)
        self.assertIn("Feminino", categorias)
        self.assertIn("Sub-12", categorias)
        self.assertIn("Sub-1800", categorias)

    def test_campea_feminina_tem_diploma(self) -> None:
        """Antes levantava "Nenhum jogador encontrado para os filtros"."""
        self.assertEqual(
            [("Ana", "Feminino", "1o"), ("Carla", "Feminino", "2o")],
            self._premiados("Feminino"),
        )

    def test_diploma_leva_o_nome_da_categoria_escolhida(self) -> None:
        """Senao a campea do Feminino recebia um papel escrito "Sub-12"."""
        for _nome, categoria, _pos in self._premiados("Feminino"):
            self.assertEqual("Feminino", categoria)

    def test_mesmo_jogador_e_numerado_por_categoria(self) -> None:
        """Ana e 1a do Feminino e 2a do Sub-12 — as duas coisas ao mesmo tempo."""
        por_nome_feminino = {n: p for n, _c, p in self._premiados("Feminino")}
        por_nome_sub12 = {n: p for n, _c, p in self._premiados("Sub-12")}
        self.assertEqual("1o", por_nome_feminino["Ana"])
        self.assertEqual("2o", por_nome_sub12["Ana"])

    def test_homem_nao_entra_na_categoria_feminina(self) -> None:
        self.assertNotIn("Bruno", [nome for nome, _c, _p in self._premiados("Feminino")])

    def test_sem_filtro_continua_usando_a_categoria_principal(self) -> None:
        """Sem categoria escolhida, um diploma por jogador — nao um por faixa."""
        premiados = self.certificate_service.tournament_recipients(
            self.tournament_id, certificate_type="category_award"
        )
        self.assertEqual(3, len(premiados))
        self.assertEqual({"Sub-12"}, {item["category"] for item in premiados})


class AtaDeEquipesTest(CoreServiceTestCase):
    """A premiação anunciada não pode sumir do documento oficial."""

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Copa por equipes",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

    def _secao_de_premiacao(self) -> tuple[str, list[str], list[list]] | None:
        return next(
            (
                secao
                for secao in self.export_service._tournament_minutes_sections(self.tournament_id)
                if "Premia" in secao[0]
            ),
            None,
        )

    def test_premios_cadastrados_saem_na_ata(self) -> None:
        self.prize_service.replace_prizes(
            self.tournament_id,
            [
                {"kind": "overall", "label": "Campea", "rank_from": 1, "rank_to": 1, "amount": "3000"},
                {"kind": "overall", "label": "Vice", "rank_from": 2, "rank_to": 2, "amount": "1500"},
                {"kind": "board", "label": "Melhor 1o tabuleiro", "rank_from": 1, "rank_to": 1, "amount": "500"},
            ],
        )
        secao = self._secao_de_premiacao()
        self.assertIsNotNone(secao)
        assert secao is not None
        texto = str(secao[2])
        self.assertIn("Campea", texto)
        self.assertIn("Melhor 1o tabuleiro", texto)
        self.assertIn("Total anunciado", texto)

    def test_o_total_anunciado_fecha(self) -> None:
        self.prize_service.replace_prizes(
            self.tournament_id,
            [
                {"kind": "overall", "label": "Campea", "rank_from": 1, "rank_to": 1, "amount": "3000"},
                {"kind": "board", "label": "Melhor 1o tabuleiro", "rank_from": 1, "rank_to": 1, "amount": "500"},
            ],
        )
        secao = self._secao_de_premiacao()
        assert secao is not None
        total = next(linha for linha in secao[2] if linha[1] == "Total anunciado")
        self.assertIn("3500", str(total[4]).replace(".", ""))

    def test_equipes_sem_premio_cadastrado_nao_ganha_secao_vazia(self) -> None:
        self.assertIsNone(self._secao_de_premiacao())

    def test_torneio_individual_continua_com_a_distribuicao_calculada(self) -> None:
        """Guarda: a ata individual nao pode ter perdido a alocacao real.

        A secao nova e para EQUIPES; o individual tem de continuar imprimindo a
        premiacao calculada, com vencedor e valor liquido.
        """
        individual = self._torneio_individual()
        self.prize_service.replace_prizes(
            individual,
            [{"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": "1000"}],
        )
        titulos = [
            secao[0]
            for secao in self.export_service._tournament_minutes_sections(individual)
        ]
        self.assertTrue(any("Resumo da premia" in titulo for titulo in titulos))
        self.assertNotIn("Premiação cadastrada", titulos)

    def _torneio_individual(self) -> int:
        tournament_id = self.db.create_tournament("Aberto individual", rounds_count=3)
        ids = [
            self.db.create_player(tournament_id, name=f"J{i}", rating=1500 - i * 10)
            for i in range(4)
        ]
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {"board_number": 1, "white_player_id": ids[0], "black_player_id": ids[1], "result": "1-0"},
                {"board_number": 2, "white_player_id": ids[2], "black_player_id": ids[3], "result": "1-0"},
            ],
        )
        self.db.close_round(round_id)
        return tournament_id
