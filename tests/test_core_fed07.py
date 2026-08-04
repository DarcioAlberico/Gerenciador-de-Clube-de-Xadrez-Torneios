"""FED-07 — rating: K correto, piso, ritmo e regulamento como dado.

O relatório de variação de rating tinha o algoritmo certo e os PARÂMETROS
errados:

1. **K = 40 de jogador novo nunca disparava.** A regra existia em
   `fide_k_factor`, mas `build_fide_report_rows` nunca passava `games_played` —
   o argumento ficava `None` e a regra caía fora sozinha, em silêncio.
2. **Sub-18 saía um ano antes.** O B.02 dá K de desenvolvimento até o FIM DO ANO
   do aniversário de 18; o código usava `< 18`, que corta no ano em que o
   jogador completa a idade.
3. **Um rating só para três ritmos.** O snapshot da lista oficial já guardava
   standard, rápido e blitz; o jogador do torneio recebia só o standard, então
   um torneio de rápidas calculava a variação contra a lista de clássicas.
4. **Sem piso e sem rating inicial.** Quem não tinha rating saía só com
   performance — que não é a conta do rating inicial (o 8.2.2 acrescenta dois
   adversários fictícios de 1800, empatados).

E o regulamento vivia como `if`s no meio do cálculo: "usar o regulamento da CBX"
significava reescrever o cálculo. Agora é dado — e o da CBX, que não está
publicado em lugar que o programa consiga ler, sai marcado como NÃO conferido
em vez de inventado.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.federation_exporters.trf25_records import encode_time_control
from src.services.rating import (
    initial_rating,
    k_factor,
    parse_regulation_overrides,
    player_rating_for,
    regulation_for,
    regulation_from_settings,
    resolve_speed,
    serialize_regulation_overrides,
)
from src.services.rating.kfactor import CAPPED, DEFAULT, NEW_PLAYER, OVERRIDE, TOP, YOUTH
from src.services.time_control import (
    below_blitz_minimum,
    classify_speed,
    parse_time_control,
    standard_minimum_seconds,
    total_seconds,
)
from tests.support.core_service_base import CoreServiceTestCase

FIDE_STANDARD = regulation_for("fide", "standard")


class RitmoTest(unittest.TestCase):
    """Um interpretador só para o TRF25 e para o relatório de rating."""

    def test_classificacao_pela_formula_da_fide(self) -> None:
        # tempo + 60 vezes o incremento, que é a partida de 60 lances.
        for texto, esperado in (
            ("90 min + 30 s", "standard"),
            ("90 min / 40 lances + 30 min", "standard"),
            ("60 min", "standard"),
            ("15 min + 10 s", "rapid"),
            ("25 min", "rapid"),
            ("10 min", "blitz"),
            ("3 min + 2 s", "blitz"),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(esperado, classify_speed(texto))

    def test_incremento_entra_na_conta(self) -> None:
        """15+10 são 25 minutos de partida, e por isso é rápido, não blitz."""
        self.assertEqual(25 * 60, total_seconds(parse_time_control("15 min + 10 s")))

    def test_ritmo_nao_reconhecido_nao_inventa_classificacao(self) -> None:
        self.assertEqual("", classify_speed("dois tempos e um cafe"))
        self.assertEqual([], parse_time_control(""))

    def test_ritmo_abaixo_do_minimo_da_fide(self) -> None:
        self.assertTrue(below_blitz_minimum("2 min + 1 s"))
        self.assertFalse(below_blitz_minimum("3 min + 2 s"))

    def test_minimo_de_tempo_para_rating_standard(self) -> None:
        self.assertEqual(120 * 60, standard_minimum_seconds(2450))
        self.assertEqual(90 * 60, standard_minimum_seconds(1900))
        self.assertEqual(60 * 60, standard_minimum_seconds(1500))

    def test_registro_222_do_trf25_nao_mudou(self) -> None:
        """O refactor uniu os dois leitores; o arquivo tem de sair igual."""
        self.assertEqual("600", encode_time_control("10 min"))
        self.assertEqual("900+10", encode_time_control("15 min + 10 s"))
        self.assertEqual("40/5400:1800", encode_time_control("90 min / 40 lances + 30 min"))
        self.assertIsNone(encode_time_control("ritmo livre"))

    def test_ritmo_declarado_ganha_do_texto(self) -> None:
        self.assertEqual(("rapid", "deduzido do ritmo de jogo"), resolve_speed("15 min + 10 s"))
        speed, origem = resolve_speed("15 min + 10 s", "blitz")
        self.assertEqual("blitz", speed)
        self.assertIn("declarado", origem)

    def test_sem_ritmo_reconhecido_cai_no_standard_avisando(self) -> None:
        speed, origem = resolve_speed("")
        self.assertEqual("standard", speed)
        self.assertIn("não reconhecido", origem)


class FatorKTest(unittest.TestCase):
    def test_jogador_com_menos_de_30_partidas_recebe_k_40(self) -> None:
        """Critério de aceite do FED-07."""
        self.assertEqual((40, NEW_PLAYER), k_factor(FIDE_STANDARD, 1800, games_played=12))

    def test_partidas_desconhecidas_nao_viram_estreia(self) -> None:
        """`None` é desconhecido — tratar como estreia daria K=40 ao plantel."""
        self.assertEqual((20, DEFAULT), k_factor(FIDE_STANDARD, 1800, games_played=None))

    def test_trinta_partidas_ja_nao_e_novo(self) -> None:
        self.assertEqual((20, DEFAULT), k_factor(FIDE_STANDARD, 1800, games_played=30))

    def test_sub_18_vale_ate_o_fim_do_ano_do_aniversario(self) -> None:
        """O código antigo usava `< 18` e cortava um ano antes."""
        k, motivo = k_factor(FIDE_STANDARD, 2100, birth_year=2008, tournament_year=2026)
        self.assertEqual((40, YOUTH), (k, motivo))
        # No ano seguinte a regra já não vale.
        self.assertEqual(
            (20, DEFAULT), k_factor(FIDE_STANDARD, 2100, birth_year=2008, tournament_year=2027)
        )

    def test_sub_18_nao_vale_acima_do_teto_de_rating(self) -> None:
        self.assertEqual(
            (20, DEFAULT), k_factor(FIDE_STANDARD, 2350, birth_year=2010, tournament_year=2026)
        )

    def test_rating_alto_usa_k_reduzido(self) -> None:
        self.assertEqual((10, TOP), k_factor(FIDE_STANDARD, 2400))
        self.assertEqual((20, DEFAULT), k_factor(FIDE_STANDARD, 2399))

    def test_k_do_cadastro_ganha_das_faixas(self) -> None:
        self.assertEqual((15, OVERRIDE), k_factor(FIDE_STANDARD, 2400, k_override=15))

    def test_teto_de_k_vezes_n(self) -> None:
        """B.02: K x n não passa de 700 no período."""
        self.assertEqual((38, CAPPED), k_factor(FIDE_STANDARD, 1800, games_played=1, games=18))
        self.assertEqual((40, NEW_PLAYER), k_factor(FIDE_STANDARD, 1800, games_played=1, games=17))

    def test_regulamento_sem_teto_nao_corta(self) -> None:
        cbx = regulation_for("cbx", "standard")
        self.assertEqual(0, cbx.k_games_cap)
        self.assertEqual((40, NEW_PLAYER), k_factor(cbx, 1800, games_played=1, games=40))


class RatingInicialTest(unittest.TestCase):
    def test_menos_de_cinco_partidas_nao_estima(self) -> None:
        estimativa = initial_rating(FIDE_STANDARD, [2000] * 4, 2.0)
        self.assertFalse(estimativa.publishable)
        self.assertIn("insuficientes", estimativa.reason)

    def test_zerar_na_estreia_nao_gera_rating(self) -> None:
        """8.2.1 — o resultado é desprezado."""
        estimativa = initial_rating(FIDE_STANDARD, [2000] * 5, 0.0)
        self.assertFalse(estimativa.publishable)
        self.assertIn("8.2.1", estimativa.reason)

    def test_dois_adversarios_ficticios_de_1800_entram_empatados(self) -> None:
        """5 x 2000 com 3 pontos: Ra = (5*2000 + 2*1800)/7 = 1943 e p = 4/7."""
        estimativa = initial_rating(FIDE_STANDARD, [2000] * 5, 3.0)
        self.assertEqual(1943, estimativa.average_opponent)
        self.assertEqual(1993, estimativa.rating)
        self.assertTrue(estimativa.publishable)

    def test_teto_do_rating_inicial(self) -> None:
        estimativa = initial_rating(FIDE_STANDARD, [2600] * 9, 9.0)
        self.assertEqual(2200, estimativa.rating)
        self.assertIn("teto", estimativa.reason)

    def test_abaixo_do_piso_nao_e_publicavel(self) -> None:
        estimativa = initial_rating(FIDE_STANDARD, [1400] * 6, 0.5)
        self.assertFalse(estimativa.publishable)
        self.assertIn("piso", estimativa.reason)


class RegulamentoComoDadoTest(unittest.TestCase):
    def test_perfil_fide_standard_e_conferido(self) -> None:
        self.assertTrue(FIDE_STANDARD.confirmed)
        self.assertEqual(1400, FIDE_STANDARD.rating_floor)
        self.assertEqual(700, FIDE_STANDARD.k_games_cap)

    def test_perfil_cbx_sai_marcado_como_nao_conferido(self) -> None:
        """Não se achou o regulamento; o programa diz isso em vez de fingir."""
        cbx = regulation_for("cbx", "standard")
        self.assertFalse(cbx.confirmed)
        self.assertIn("CONFERIR", cbx.source)

    def test_ajuste_do_arbitro_sobrescreve_o_perfil(self) -> None:
        regra = regulation_from_settings(
            {"rating_regulation": '{"cbx": {"rating_floor": 1000, "k_top_rating": 2350}}'},
            "cbx",
            "standard",
        )
        self.assertEqual(1000, regra.rating_floor)
        self.assertEqual(2350, regra.k_top_rating)
        # O que não foi ajustado continua vindo do perfil.
        self.assertEqual(20, regra.k_default)

    def test_ajuste_de_uma_base_nao_vaza_para_a_outra(self) -> None:
        settings = {"rating_regulation": '{"cbx": {"rating_floor": 1000}}'}
        self.assertEqual(1400, regulation_from_settings(settings, "fide", "standard").rating_floor)

    def test_json_quebrado_nao_derruba_o_relatorio(self) -> None:
        self.assertEqual({}, parse_regulation_overrides("{isto nao e json"))
        self.assertEqual(1400, regulation_from_settings({"rating_regulation": "{{"}, "fide", "standard").rating_floor)

    def test_campo_desconhecido_e_ignorado(self) -> None:
        self.assertEqual(
            {"cbx": {"rating_floor": 1000}},
            parse_regulation_overrides({"cbx": {"rating_floor": 1000, "invente_um": 7}}),
        )

    def test_serializacao_vazia_quando_nao_ha_ajuste(self) -> None:
        self.assertEqual("", serialize_regulation_overrides({"cbx": {}}))
        self.assertEqual('{"cbx": {"k_top": 10}}', serialize_regulation_overrides({"cbx": {"k_top": "10"}}))


class RatingPorRitmoTest(unittest.TestCase):
    JOGADOR = {
        "international_rating": 2100,
        "rapid_rating": 1950,
        "blitz_rating": 1800,
        "national_rating": 1700,
        "rating": 2100,
    }

    def test_cada_ritmo_usa_a_sua_lista(self) -> None:
        self.assertEqual((2100, "standard"), player_rating_for(self.JOGADOR, "fide", "standard"))
        self.assertEqual((1950, "rápido"), player_rating_for(self.JOGADOR, "fide", "rapid"))
        self.assertEqual((1800, "blitz"), player_rating_for(self.JOGADOR, "fide", "blitz"))

    def test_sem_rating_do_ritmo_cai_no_standard_dizendo(self) -> None:
        """Silêncio aqui daria um ΔElo calculado contra a lista errada."""
        jogador = {**self.JOGADOR, "rapid_rating": 0}
        rating, origem = player_rating_for(jogador, "fide", "rapid")
        self.assertEqual(2100, rating)
        self.assertIn("sem rating rápido", origem)

    def test_base_nacional_usa_o_rating_nacional(self) -> None:
        self.assertEqual((1700, "nacional"), player_rating_for(self.JOGADOR, "cbx", "standard"))


class RelatorioDeRatingTest(CoreServiceTestCase):
    """O relatório completo, com banco, num torneio de rápidas."""

    def _torneio(self, ritmo: str, **settings) -> int:
        tournament_id = self.db.create_tournament("Aberto", rounds_count=3)
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET time_control = ? WHERE id = ?", (ritmo, tournament_id)
            )
        self.db.save_tournament_settings(tournament_id, {"federation": "BRA", **settings})
        return tournament_id

    def _jogadores(self, tournament_id: int, especificacoes: list[dict]) -> list[int]:
        return [
            self.db.create_player(tournament_id, name=f"Jogador {index + 1}", **spec)
            for index, spec in enumerate(especificacoes)
        ]

    def _rodada(self, tournament_id: int, numero: int, mesas: list[tuple[int, int, str]]) -> None:
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            numero,
            [
                {
                    "board_number": mesa + 1,
                    "white_player_id": brancas,
                    "black_player_id": pretas,
                    "result": resultado,
                }
                for mesa, (brancas, pretas, resultado) in enumerate(mesas)
            ],
        )
        self.db.close_round(round_id)

    def _secoes(self, tournament_id: int) -> dict[str, list[list]]:
        return {
            titulo: rows
            for titulo, _headers, rows in self.export_service._fide_rating_sections(
                tournament_id, "fide"
            )
        }

    def test_torneio_rapido_usa_o_rating_rapido_dos_inscritos(self) -> None:
        """Critério de aceite do FED-07."""
        tournament_id = self._torneio("15 min + 10 s")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2100, "rapid_rating": 1950, "rating": 2100},
                {"international_rating": 2000, "rapid_rating": 1900, "rating": 2000},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])

        secoes = self._secoes(tournament_id)
        resumo = {linha[0]: linha[1] for linha in secoes["Resumo do relatório de rating"]}
        self.assertIn("Rápido", str(resumo["Ritmo"]))
        detalhe = secoes["Variacao de rating FIDE"]
        self.assertEqual([1950, 1900], sorted((linha[1] for linha in detalhe), reverse=True))
        self.assertTrue(all(linha[2] == "rápido" for linha in detalhe))

    def test_k_40_de_jogador_novo_aparece_no_relatorio(self) -> None:
        tournament_id = self._torneio("90 min + 30 s")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 1800, "rating": 1800, "games_played": 9},
                {"international_rating": 1850, "rating": 1850, "games_played": 120},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])

        detalhe = self._secoes(tournament_id)["Variacao de rating FIDE"]
        por_nome = {linha[0]: linha for linha in detalhe}
        self.assertEqual(40, por_nome["Jogador 1"][3])
        self.assertEqual("jogador novo", por_nome["Jogador 1"][4])
        self.assertEqual(20, por_nome["Jogador 2"][3])

    def test_estreante_ganha_secao_de_rating_inicial(self) -> None:
        tournament_id = self._torneio("90 min + 30 s")
        estreante, *ratados = self._jogadores(
            tournament_id,
            [{"international_rating": 0, "rating": 0}]
            + [{"international_rating": 2000, "rating": 2000} for _ in range(5)],
        )
        for numero, adversario in enumerate(ratados, start=1):
            self._rodada(tournament_id, numero, [(estreante, adversario, "1-0" if numero <= 3 else "0-1")])

        secoes = self._secoes(tournament_id)
        inicial = secoes["Rating inicial estimado (sem rating na base)"]
        self.assertEqual(1, len(inicial))
        # 5 partidas contra 2000, 3 pontos: mesma conta do teste puro.
        self.assertEqual(5, inicial[0][1])
        self.assertEqual(1993, inicial[0][5])

    def test_aviso_quando_o_regulamento_nao_foi_conferido(self) -> None:
        tournament_id = self._torneio("15 min + 10 s")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2100, "rapid_rating": 1950, "rating": 2100},
                {"international_rating": 2000, "rapid_rating": 1900, "rating": 2000},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])
        avisos = " | ".join(linha[0] for linha in self._secoes(tournament_id)["Aviso"])
        self.assertIn("NAO foram conferidos", avisos)

    def test_aviso_quando_falta_o_rating_do_ritmo(self) -> None:
        tournament_id = self._torneio("15 min + 10 s")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2100, "rating": 2100},
                {"international_rating": 2000, "rating": 2000},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])
        avisos = " | ".join(linha[0] for linha in self._secoes(tournament_id)["Aviso"])
        self.assertIn("sem rating de", avisos)
        self.assertIn("Importe a lista", avisos)

    def test_ritmo_declarado_na_configuracao_ganha(self) -> None:
        tournament_id = self._torneio("90 min + 30 s", rating_speed="blitz")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2100, "blitz_rating": 1700, "rating": 2100},
                {"international_rating": 2000, "blitz_rating": 1650, "rating": 2000},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])
        resumo = {
            linha[0]: linha[1]
            for linha in self._secoes(tournament_id)["Resumo do relatório de rating"]
        }
        self.assertIn("Blitz", str(resumo["Ritmo"]))

    def test_piso_do_regulamento_e_aplicado_e_sinalizado(self) -> None:
        # Piso de 2010: quem entra com 2010 e perde cai para 2008 calculado, e
        # o relatório publica o piso em vez de um rating que não seria aceito.
        tournament_id = self._torneio(
            "90 min + 30 s", rating_regulation='{"fide": {"rating_floor": 2010}}'
        )
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2010, "rating": 2010},
                {"international_rating": 2400, "rating": 2400},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[1], ids[0], "1-0")])

        secoes = self._secoes(tournament_id)
        por_nome = {linha[0]: linha for linha in secoes["Variacao de rating FIDE"]}
        self.assertEqual(2010, por_nome["Jogador 1"][9])  # Rc publicado no piso
        avisos = " | ".join(linha[0] for linha in secoes["Aviso"])
        self.assertIn("abaixo do piso", avisos)

    def test_relatorio_continua_exportavel(self) -> None:
        tournament_id = self._torneio("90 min + 30 s")
        ids = self._jogadores(
            tournament_id,
            [
                {"international_rating": 2100, "rating": 2100},
                {"international_rating": 2000, "rating": 2000},
            ],
        )
        self._rodada(tournament_id, 1, [(ids[0], ids[1], "1-0")])
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "rating.csv"
            self.export_service.export_fide_rating_report(tournament_id, destino, "fide")
            conteudo = destino.read_text(encoding="utf-8-sig")
        self.assertIn("Variacao de rating FIDE", conteudo)
        self.assertIn("Regulamento", conteudo)
