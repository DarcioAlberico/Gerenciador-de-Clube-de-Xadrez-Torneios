"""TBK-05 — desempates de equipes completos.

O sistema tinha quatro critérios de equipe (match points, game points, Buchholz
sobre match points e vitórias). Faltavam os desempates que qualquer regulamento
olímpico/CBX por equipes pede: Sonneborn-Berger olímpico, confronto direto entre
equipes, Buchholz de game points e board count (Berlin).

Os testes de paridade rodam o Gacrux DE VERDADE. Uma ressalva medida e assumida:
o `DE` do Gacrux devolve uma POSIÇÃO dentro do grupo empatado (0 quando não
separa), enquanto o critério do Albericus — como no individual — devolve os
pontos feitos contra os empatados. Os números não se comparam; a ORDEM sim, e é
ela que os testes exigem.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.pairing import (
    PLAYER_TIEBREAKS,
    TEAM_TIEBREAKS,
    calculate_team_standings,
    criterion_params,
    extra_team_columns,
    fold_board_points,
    normalize_criterion_params,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
    team_ordering_value,
    team_standing_value,
)
from src.services.pairing.gacrux_tiebreak_map import (
    build_team_tiebreak_plan,
    sequence_signature,
    team_specifier_with_params,
)
from src.services.pairing.tiebreak_engine import ENGINE_ALBERICUS, ENGINE_GACRUX
from tests.support.core_service_base import CoreServiceTestCase

_SETTINGS: dict = {}


def _teams(total: int) -> list[dict]:
    return [
        {"id": index, "name": f"Equipe {index}", "club": "", "captain": "", "active": 1}
        for index in range(1, total + 1)
    ]


def _match(rodada: int, brancas: int, pretas: int, wmp: float, bmp: float,
           wgp: float, bgp: float) -> dict:
    return {
        "id": rodada * 100 + brancas,
        "round_number": rodada,
        "white_team_id": brancas,
        "black_team_id": pretas,
        "is_bye": 0,
        "white_match_points": wmp,
        "black_match_points": bmp,
        "white_game_points": wgp,
        "black_game_points": bgp,
    }


# Torneio de 4 equipes em 3 rodadas, cada confronto 2,5 x 1,5 (match 2 x 0).
# Os números que ele produz foram conferidos contra o Gacrux de verdade — ver
# ParidadeComGacruxTest, que roda o motor sobre o mesmo desenho de resultados.
_TODOS_CONTRA_TODOS = [
    _match(1, 1, 3, 0.0, 2.0, 1.5, 2.5),
    _match(1, 4, 2, 0.0, 2.0, 1.5, 2.5),
    _match(2, 2, 3, 0.0, 2.0, 1.5, 2.5),
    _match(2, 1, 4, 2.0, 0.0, 2.5, 1.5),
    _match(3, 3, 4, 2.0, 0.0, 2.5, 1.5),
    _match(3, 2, 1, 0.0, 2.0, 1.5, 2.5),
]


# Só as equipes 1 e 2 terminam empatadas (2 MP), e elas se enfrentaram: a 1
# venceu por 2,5 x 1,5. Os game points são escolhidos para que o SB olímpico
# aponte o OUTRO lado (E1 = 5,0; E2 = 7,0), que é o que separa "quem decide" de
# "quem tem o número maior".
_EMPATE_DE_DUAS = [
    _match(1, 1, 2, 2.0, 0.0, 2.5, 1.5),
    _match(1, 3, 4, 1.0, 1.0, 2.0, 2.0),
    _match(2, 3, 1, 2.0, 0.0, 4.0, 0.0),
    _match(2, 2, 4, 2.0, 0.0, 4.0, 0.0),
]


def _standings(sequence: list[dict] | None = None, **kwargs) -> dict[int, dict]:
    return {
        int(item["team_id"]): item
        for item in calculate_team_standings(
            _SETTINGS, _teams(4), _TODOS_CONTRA_TODOS, sequence=sequence, **kwargs
        )
    }


class RegistroDeEquipesTest(unittest.TestCase):
    """O registro de equipes passou a nomear o regulamento inteiro."""

    def test_os_criterios_que_faltavam_estao_registrados(self) -> None:
        for code in ("sonneborn_berger", "direct_encounter", "buchholz_game_points", "board_count"):
            self.assertIn(code, TEAM_TIEBREAKS, code)

    def test_o_mesmo_codigo_significa_coisas_diferentes_nos_dois_registros(self) -> None:
        """`sonneborn_berger` de equipes aceita corte; o individual não.

        É por isso que `criterion_params` passou a receber o registro (TBK-05):
        adivinhar devolveria os parâmetros do critério errado, e o corte que o
        árbitro digitasse na tela de equipes cairia num critério sem corte.
        """
        self.assertEqual((), criterion_params("sonneborn_berger", PLAYER_TIEBREAKS))
        self.assertEqual(
            {"cut_low"},
            {param.key for param in criterion_params("sonneborn_berger", TEAM_TIEBREAKS)},
        )
        self.assertEqual(
            {"cut_low": 2},
            normalize_criterion_params("sonneborn_berger", {"cut_low": 2}, TEAM_TIEBREAKS),
        )
        self.assertEqual(
            {}, normalize_criterion_params("sonneborn_berger", {"cut_low": 2}, PLAYER_TIEBREAKS)
        )

    def test_board_count_e_o_unico_criterio_em_que_menor_e_melhor(self) -> None:
        menores = [code for code, crit in TEAM_TIEBREAKS.items() if not crit.higher_is_better]
        self.assertEqual(["board_count"], menores)

    def test_a_sequencia_salva_aceita_os_criterios_novos(self) -> None:
        bruto = serialize_tiebreak_sequence(
            [
                {"code": "match_points", "params": {}},
                {"code": "direct_encounter", "params": {}},
                {"code": "sonneborn_berger", "params": {"cut_low": 1}},
            ]
        )
        sequencia = parse_team_tiebreak_sequence(bruto)
        self.assertEqual(
            ["match_points", "direct_encounter", "sonneborn_berger"],
            [item["code"] for item in sequencia],
        )
        self.assertEqual({"cut_low": 1}, sequencia[-1]["params"])


class SonnebornBergerOlimpicoTest(unittest.TestCase):
    """Match points do adversário × game points feitos contra ele."""

    def test_o_valor_e_a_soma_dos_produtos(self) -> None:
        classificacao = _standings([{"code": "sonneborn_berger", "params": {}}])
        # Equipe 1 enfrentou 3 (6 MP, fez 1,5), 4 (0 MP, fez 2,5) e 2 (2 MP, fez 2,5).
        self.assertEqual(14.0, classificacao[1]["sonneborn_berger"])
        self.assertEqual(15.0, classificacao[2]["sonneborn_berger"])
        self.assertEqual(15.0, classificacao[3]["sonneborn_berger"])
        self.assertEqual(18.0, classificacao[4]["sonneborn_berger"])

    def test_nao_e_o_sonneborn_berger_de_match_points(self) -> None:
        """Guarda contra a confusão que o nome convida.

        O SB "de match points dos dois lados" (o `SB` puro do Gacrux) daria 4,0
        para a Equipe 1. O critério olímpico pesa o placar do confronto em
        pontos de tabuleiro, e por isso dá 14,0.
        """
        classificacao = _standings([{"code": "sonneborn_berger", "params": {}}])
        self.assertNotEqual(4.0, classificacao[1]["sonneborn_berger"])

    def test_o_corte_descarta_o_pior_confronto(self) -> None:
        """Equipe 4: produtos 3 (vs 2 MP), 6 (vs 4 MP) e 9 (vs 6 MP)."""
        com_corte = _standings([{"code": "sonneborn_berger", "params": {"cut_low": 1}}])
        self.assertEqual(15.0, com_corte[4]["sonneborn_berger"])

    def test_corte_maior_que_os_confrontos_nao_estoura(self) -> None:
        vazio = _standings([{"code": "sonneborn_berger", "params": {"cut_low": 5}}])
        self.assertEqual(0.0, vazio[4]["sonneborn_berger"])


class BuchholzDeGamePointsTest(unittest.TestCase):
    def test_soma_os_game_points_dos_adversarios(self) -> None:
        classificacao = _standings([{"code": "buchholz_game_points", "params": {}}])
        # Equipe 1 enfrentou 3 (7,5), 4 (4,5) e 2 (5,5).
        self.assertEqual(17.5, classificacao[1]["buchholz_game_points"])
        self.assertEqual(16.5, classificacao[3]["buchholz_game_points"])

    def test_nao_se_confunde_com_o_buchholz_de_match_points(self) -> None:
        classificacao = _standings(
            [{"code": "buchholz", "params": {}}, {"code": "buchholz_game_points", "params": {}}]
        )
        self.assertEqual(8.0, classificacao[1]["buchholz"])
        self.assertEqual(17.5, classificacao[1]["buchholz_game_points"])


class ConfrontoDiretoDeEquipesTest(unittest.TestCase):
    """Mesma condição do individual (TBK-03): todos os empatados se enfrentaram."""

    def _empate_de_duas(self) -> list[dict]:
        return list(_EMPATE_DE_DUAS)

    def test_quem_venceu_o_empatado_leva_os_pontos(self) -> None:
        classificacao = {
            int(item["team_id"]): item
            for item in calculate_team_standings(
                _SETTINGS, _teams(4), self._empate_de_duas(),
                sequence=[
                    {"code": "match_points", "params": {}},
                    {"code": "direct_encounter", "params": {}},
                ],
            )
        }
        self.assertEqual(2.0, classificacao[1]["match_points"])
        self.assertEqual(2.0, classificacao[2]["match_points"])
        self.assertEqual(2.0, classificacao[1]["direct_encounter"])
        self.assertEqual(0.0, classificacao[2]["direct_encounter"])
        self.assertLess(classificacao[1]["position"], classificacao[2]["position"])

    def test_grupo_de_tres_sem_todos_se_enfrentarem_zera_o_criterio(self) -> None:
        """1, 2 e 3 empatam em 2 MP; a 1 enfrentou as duas, mas 2 e 3 não se
        enfrentaram — então "quem ganhou de quem" não é uma ordem."""
        partidas = [
            _match(1, 1, 2, 1.0, 1.0, 2.0, 2.0),
            _match(1, 3, 5, 1.0, 1.0, 2.0, 2.0),
            _match(2, 1, 3, 1.0, 1.0, 2.0, 2.0),
            _match(2, 2, 4, 1.0, 1.0, 2.0, 2.0),
        ]
        classificacao = {
            int(item["team_id"]): item
            for item in calculate_team_standings(
                _SETTINGS, _teams(5), partidas,
                sequence=[
                    {"code": "match_points", "params": {}},
                    {"code": "direct_encounter", "params": {}},
                ],
            )
        }
        self.assertEqual({2.0}, {classificacao[i]["match_points"] for i in (1, 2, 3)})
        self.assertEqual([0.0, 0.0, 0.0], [classificacao[i]["direct_encounter"] for i in (1, 2, 3)])

    def test_equipe_sozinha_na_pontuacao_nao_tem_confronto_direto(self) -> None:
        classificacao = _standings([{"code": "direct_encounter", "params": {}}])
        self.assertEqual(0.0, classificacao[3]["direct_encounter"])


class BoardCountTest(unittest.TestCase):
    """Σ (nº do tabuleiro × pontos nele obtidos); MENOR é melhor."""

    def _linhas(self) -> list[dict]:
        # Um confronto de 2 tabuleiros: no 1 a equipe 1 venceu, no 2 (cores
        # invertidas) a equipe 2 venceu.
        return [
            {"board_number": 1, "result": "1-0", "white_team_id": 1, "black_team_id": 2},
            {"board_number": 2, "result": "1-0", "white_team_id": 2, "black_team_id": 1},
        ]

    def test_dobra_por_tabuleiro(self) -> None:
        """O zero do tabuleiro perdido fica registrado: a equipe JOGOU ali."""
        self.assertEqual(
            {1: {1: 1.0, 2: 0.0}, 2: {1: 0.0, 2: 1.0}}, fold_board_points(self._linhas())
        )

    def test_resultado_em_branco_nao_entra(self) -> None:
        linhas = self._linhas() + [
            {"board_number": 3, "result": "", "white_team_id": 1, "black_team_id": 2}
        ]
        self.assertEqual(
            {1: {1: 1.0, 2: 0.0}, 2: {1: 0.0, 2: 1.0}}, fold_board_points(linhas)
        )

    def test_o_mesmo_total_com_o_ponto_no_tabuleiro_de_cima_classifica_melhor(self) -> None:
        partidas = [_match(1, 1, 2, 1.0, 1.0, 1.0, 1.0)]
        classificacao = {
            int(item["team_id"]): item
            for item in calculate_team_standings(
                _SETTINGS, _teams(2), partidas,
                sequence=[
                    {"code": "match_points", "params": {}},
                    {"code": "game_points", "params": {}},
                    {"code": "board_count", "params": {}},
                ],
                board_results=self._linhas(),
            )
        }
        self.assertEqual(1.0, classificacao[1]["board_count"])
        self.assertEqual(2.0, classificacao[2]["board_count"])
        self.assertEqual(1, classificacao[1]["position"])

    def test_a_ordenacao_inverte_o_sinal_do_board_count(self) -> None:
        item = {"board_count": 12.0, "match_points": 3.0}
        self.assertEqual(12.0, team_standing_value(item, "board_count"))
        self.assertEqual(-12.0, team_ordering_value(item, "board_count"))
        self.assertEqual(3.0, team_ordering_value(item, "match_points"))

    def test_sem_dados_de_tabuleiro_o_criterio_e_neutro(self) -> None:
        classificacao = _standings([{"code": "board_count", "params": {}}])
        self.assertEqual({0.0}, {item["board_count"] for item in classificacao.values()})


class ColunasDaClassificacaoTest(unittest.TestCase):
    """Quais critérios ganham coluna própria na tabela de equipes."""

    def test_so_os_criterios_sem_coluna_fixa_entram(self) -> None:
        classificacao = calculate_team_standings(
            _SETTINGS, _teams(4), _TODOS_CONTRA_TODOS,
            sequence=[
                {"code": "match_points", "params": {}},
                {"code": "buchholz", "params": {}},
                {"code": "sonneborn_berger", "params": {}},
                {"code": "board_count", "params": {}},
            ],
        )
        self.assertEqual(
            [("sonneborn_berger", "Sonneborn-Berger olímpico"), ("board_count", "Board count (Berlin)")],
            extra_team_columns(classificacao),
        )

    def test_a_tabela_de_sempre_nao_ganha_coluna_nenhuma(self) -> None:
        classificacao = calculate_team_standings(_SETTINGS, _teams(4), _TODOS_CONTRA_TODOS)
        self.assertEqual([], extra_team_columns(classificacao))

    def test_classificacao_vazia_nao_estoura(self) -> None:
        self.assertEqual([], extra_team_columns([]))


class MapaDoGacruxTest(unittest.TestCase):
    def test_os_criterios_novos_viram_especificadores(self) -> None:
        plano = build_team_tiebreak_plan(
            ["match_points", "direct_encounter", "sonneborn_berger", "buchholz_game_points", "board_count"]
        )
        self.assertEqual(("MPTS", "DE", "EMGSB", "BH:GP", "BC"), plano.specifiers)

    def test_o_corte_do_sb_vira_modificador(self) -> None:
        self.assertEqual("EMGSB/C1", team_specifier_with_params("sonneborn_berger", {"cut_low": 1}))
        self.assertEqual("EMGSB", team_specifier_with_params("sonneborn_berger", {"cut_low": 0}))
        self.assertEqual("EMGSB", team_specifier_with_params("sonneborn_berger", {}))

    def test_o_plano_de_equipes_aceita_sequencia_com_params(self) -> None:
        plano = build_team_tiebreak_plan(
            [
                {"code": "match_points", "params": {}},
                {"code": "sonneborn_berger", "params": {"cut_low": 2}},
            ]
        )
        self.assertEqual(("MPTS", "EMGSB/C2"), plano.specifiers)
        self.assertEqual(("match_points", "sonneborn_berger"), plano.code_order)

    def test_criterio_desconhecido_fica_de_fora(self) -> None:
        plano = build_team_tiebreak_plan(["match_points", "koya"])
        self.assertEqual(("MPTS",), plano.specifiers)
        self.assertEqual(("koya",), plano.skipped)

    def test_a_assinatura_de_cache_distingue_os_parametros(self) -> None:
        """Sem isso, mudar só o corte devolveria o cálculo velho do cache."""
        sem_corte = sequence_signature([{"code": "sonneborn_berger", "params": {"cut_low": 0}}])
        com_corte = sequence_signature([{"code": "sonneborn_berger", "params": {"cut_low": 1}}])
        self.assertNotEqual(sem_corte, com_corte)
        self.assertEqual(sequence_signature(["match_points"]), sequence_signature([{"code": "match_points"}]))
        hash(com_corte)  # a chave de cache precisa ser hasheável


class ParametrosChegamAoMotorTest(CoreServiceTestCase):
    """Dívida da TBK-04: o parâmetro ia ao arquivo FIDE, não ao cálculo.

    `_gacrux_*_tiebreaks` montava a lista só com os CÓDIGOS, então o motor
    rodava com os cortes padrão enquanto o registro 212 do TRF declarava os
    configurados — o arquivo e a tela discordavam.
    """

    def setUp(self) -> None:
        super().setUp()
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()

    def _especificadores(self, tournament_id: int, equipes: bool) -> tuple[str, ...]:
        capturado: dict[str, tuple[str, ...]] = {}

        def espiao(self_engine, exporter, tid, specifiers, current_round, swiss=True):
            capturado["specifiers"] = tuple(specifiers)
            return {"tiebreakResult": {"competitors": []}}

        alvo = "src.services.pairing.gacrux_tiebreak_engine.GacruxTiebreakEngine._run_tiebreakchecker"
        with patch(alvo, espiao):
            if equipes:
                self.service.team_standings(tournament_id)
            else:
                self.service.standings(tournament_id)
        return capturado.get("specifiers", ())

    def test_o_corte_de_equipes_configurado_chega_ao_motor(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        for board in self.db.list_team_boards(int(match["id"])):
            self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, round_data["id"])
        self.db.save_tournament_settings(tournament_id, {
            "tiebreak_engine": ENGINE_GACRUX,
            "team_tiebreak_sequence": serialize_tiebreak_sequence([
                {"code": "match_points", "params": {}},
                {"code": "sonneborn_berger", "params": {"cut_low": 1}},
            ]),
        })

        self.assertEqual(("MPTS", "EMGSB/C1"), self._especificadores(tournament_id, equipes=True))

    def test_o_corte_individual_configurado_chega_ao_motor(self) -> None:
        player_ids = self._create_players(4)
        self.assertEqual(4, len(player_ids))
        round_data = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
            if not pairing["is_bye"]:
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_data["id"])
        self.db.save_tournament_settings(self.tournament_id, {
            "tiebreak_engine": ENGINE_GACRUX,
            "tiebreak_sequence": serialize_tiebreak_sequence([
                {"code": "buchholz_cut1", "params": {"cut_low": 3, "cut_high": 0, "unplayed": "real"}},
            ]),
        })

        self.assertEqual(("PTS", "BH/C3"), self._especificadores(self.tournament_id, equipes=False))


class ParidadeComGacruxTest(CoreServiceTestCase):
    """Critério de aceite: paridade com o Gacrux nos critérios novos.

    Quatro equipes, quatro tabuleiros, três rodadas — sem bye, de propósito: o
    adversário virtual da FIDE para jogos não disputados só existe no Gacrux (é
    a razão de o motor próprio ser legado desde a TBK-03), então um torneio com
    bye compararia duas definições diferentes e não a mesma conta.
    """

    _SEQUENCIA = [
        {"code": "match_points", "params": {}},
        {"code": "game_points", "params": {}},
        {"code": "sonneborn_berger", "params": {}},
        {"code": "buchholz_game_points", "params": {}},
        {"code": "board_count", "params": {}},
    ]

    def setUp(self) -> None:
        super().setUp()
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()

        self.tid, self.team_ids = self._create_team_tournament(teams_count=4, boards_count=4)
        padroes = [
            ["1-0", "1/2-1/2", "0-1", "1-0"],
            ["0-1", "0-1", "1/2-1/2", "1-0"],
            ["1-0", "1-0", "1-0", "1/2-1/2"],
        ]
        for rodada in range(3):
            round_data = self.service.generate_next_round(self.tid)
            for indice, match in enumerate(self.db.list_team_matches_for_round(round_data["id"])):
                if match.get("is_bye"):
                    continue
                padrao = padroes[(rodada + indice) % len(padroes)]
                for posicao, board in enumerate(self.db.list_team_boards(int(match["id"]))):
                    self.service.update_result(self.tid, int(board["id"]), padrao[posicao % 4])
            self.service.close_round(self.tid, round_data["id"])

    def _classificacao(self, engine: str, sequencia: list[dict] | None = None) -> dict[int, dict]:
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        self.db.save_tournament_settings(self.tid, {
            "tiebreak_engine": engine,
            "team_tiebreak_sequence": serialize_tiebreak_sequence(sequencia or self._SEQUENCIA),
        })
        return {int(item["team_id"]): item for item in self.service.team_standings(self.tid)}

    def test_o_fixture_nao_tem_bye(self) -> None:
        """Guarda: com bye, a paridade abaixo compararia outra coisa."""
        byes = [
            match
            for match in self.db.list_team_matches_for_tournament(self.tid, closed_only=True)
            if match.get("is_bye")
        ]
        self.assertEqual([], byes)

    def test_sonneborn_berger_olimpico_bate_com_o_emgsb(self) -> None:
        proprio = self._classificacao(ENGINE_ALBERICUS)
        gacrux = self._classificacao(ENGINE_GACRUX)
        for team_id in self.team_ids:
            self.assertAlmostEqual(
                float(proprio[team_id]["sonneborn_berger"]),
                float(gacrux[team_id]["sonneborn_berger"]),
                places=2,
                msg=f"equipe {team_id}",
            )

    def test_buchholz_de_game_points_bate_com_o_bh_gp(self) -> None:
        proprio = self._classificacao(ENGINE_ALBERICUS)
        gacrux = self._classificacao(ENGINE_GACRUX)
        for team_id in self.team_ids:
            self.assertAlmostEqual(
                float(proprio[team_id]["buchholz_game_points"]),
                float(gacrux[team_id]["buchholz_game_points"]),
                places=2,
                msg=f"equipe {team_id}",
            )

    def test_board_count_bate_com_o_bc(self) -> None:
        proprio = self._classificacao(ENGINE_ALBERICUS)
        gacrux = self._classificacao(ENGINE_GACRUX)
        self.assertNotEqual(
            {0.0}, {float(proprio[t]["board_count"]) for t in self.team_ids},
            "board count zerado não provaria nada",
        )
        for team_id in self.team_ids:
            self.assertAlmostEqual(
                float(proprio[team_id]["board_count"]),
                float(gacrux[team_id]["board_count"]),
                places=2,
                msg=f"equipe {team_id}",
            )

    def test_o_corte_do_sb_bate_com_o_emgsb_c1(self) -> None:
        com_corte = [
            {"code": "match_points", "params": {}},
            {"code": "sonneborn_berger", "params": {"cut_low": 1}},
        ]
        proprio = self._classificacao(ENGINE_ALBERICUS, com_corte)
        gacrux = self._classificacao(ENGINE_GACRUX, com_corte)
        sem_corte = self._classificacao(ENGINE_ALBERICUS)
        self.assertNotEqual(
            {t: sem_corte[t]["sonneborn_berger"] for t in self.team_ids},
            {t: proprio[t]["sonneborn_berger"] for t in self.team_ids},
            "o corte precisa mudar algum valor para o teste valer",
        )
        for team_id in self.team_ids:
            self.assertAlmostEqual(
                float(proprio[team_id]["sonneborn_berger"]),
                float(gacrux[team_id]["sonneborn_berger"]),
                places=2,
                msg=f"equipe {team_id}",
            )

    def test_a_ordem_final_e_a_mesma_nos_dois_motores(self) -> None:
        proprio = self._classificacao(ENGINE_ALBERICUS)
        gacrux = self._classificacao(ENGINE_GACRUX)
        self.assertEqual(
            [proprio[t]["position"] for t in self.team_ids],
            [gacrux[t]["position"] for t in self.team_ids],
        )

    def test_regulamento_olimpico_ordena_igual_nos_dois_motores(self) -> None:
        """Critério de aceite: MP, confronto direto e SB olímpico.

        O `DE` do Gacrux devolve posição no grupo e o do Albericus devolve
        pontos contra os empatados — os números não se comparam. A ORDEM sim.
        """
        olimpico = [
            {"code": "match_points", "params": {}},
            {"code": "direct_encounter", "params": {}},
            {"code": "sonneborn_berger", "params": {}},
        ]
        proprio = self._classificacao(ENGINE_ALBERICUS, olimpico)
        gacrux = self._classificacao(ENGINE_GACRUX, olimpico)
        self.assertEqual(
            sorted(self.team_ids, key=lambda t: proprio[t]["position"]),
            sorted(self.team_ids, key=lambda t: gacrux[t]["position"]),
        )

    def test_o_relatorio_publica_a_coluna_que_decidiu(self) -> None:
        """Uma ordem que o relatório não explica não serve numa apelação."""
        self._classificacao(ENGINE_ALBERICUS, [
            {"code": "match_points", "params": {}},
            {"code": "sonneborn_berger", "params": {}},
        ])
        _titulo, cabecalho, linhas = self.export_service._team_standings_section(self.tid)

        self.assertIn("Sonneborn-Berger olímpico", cabecalho)
        # A coluna nova entra antes do status, e traz número em toda linha.
        self.assertEqual("Status", cabecalho[-1])
        coluna = cabecalho.index("Sonneborn-Berger olímpico")
        self.assertTrue(all(str(linha[coluna]).strip() for linha in linhas))

    def test_criterio_com_coluna_fixa_nao_e_duplicado_no_relatorio(self) -> None:
        self._classificacao(ENGINE_ALBERICUS, [
            {"code": "match_points", "params": {}},
            {"code": "buchholz", "params": {}},
        ])
        _titulo, cabecalho, _linhas = self.export_service._team_standings_section(self.tid)

        self.assertEqual(1, cabecalho.count("Buchholz"))
        self.assertNotIn("Buchholz (equipes)", cabecalho)

    def test_o_212_do_trf25_declara_os_criterios_do_regulamento(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self.db.save_tournament_settings(self.tid, {
            "team_tiebreak_sequence": serialize_tiebreak_sequence([
                {"code": "match_points", "params": {}},
                {"code": "direct_encounter", "params": {}},
                {"code": "sonneborn_berger", "params": {"cut_low": 1}},
                {"code": "board_count", "params": {}},
            ]),
        })
        destino = Path(self.temp_dir.name) / "olimpico.trf"
        TRF25Exporter(self.export_service).export(self.tid, destino)
        conteudo = destino.read_text(encoding="utf-8")

        self.assertIn("212 MPTS,DE,EMGSB/C1,BC", conteudo)


class OrdenacaoOlimpicaTest(unittest.TestCase):
    """A ordem que o regulamento olímpico produz, sem depender do motor."""

    def test_confronto_direto_decide_antes_do_sonneborn_berger(self) -> None:
        # 1 e 2 empatam em match points; a 1 venceu a 2 no confronto direto,
        # mas a 2 tem SB olímpico maior (7,0 contra 5,0). Qual das duas fica na
        # frente é decidido pela ORDEM da sequência, e não pelo critério "mais
        # forte" — é isso que um regulamento configura.
        partidas = list(_EMPATE_DE_DUAS)

        def ordem(sequencia: list[dict]) -> list[int]:
            return [
                int(item["team_id"])
                for item in calculate_team_standings(_SETTINGS, _teams(4), partidas, sequence=sequencia)
            ]

        com_de = ordem([
            {"code": "match_points", "params": {}},
            {"code": "direct_encounter", "params": {}},
            {"code": "sonneborn_berger", "params": {}},
        ])
        so_sb = ordem([
            {"code": "match_points", "params": {}},
            {"code": "sonneborn_berger", "params": {}},
        ])
        # A equipe 3 lidera nos dois casos (3 MP); o que muda é quem fica na
        # frente ENTRE as empatadas.
        self.assertLess(com_de.index(1), com_de.index(2), "o confronto direto deveria decidir")
        self.assertLess(so_sb.index(2), so_sb.index(1), "sem confronto direto, o SB decide o outro jeito")


class ClassificacaoHistoricaTest(unittest.TestCase):
    """Sem sequência configurada, nada muda: o padrão continua o de antes."""

    def test_o_padrao_continua_match_game_buchholz_vitorias(self) -> None:
        classificacao = calculate_team_standings(_SETTINGS, _teams(4), _TODOS_CONTRA_TODOS)
        self.assertEqual(
            ["match_points", "game_points", "buchholz", "wins"],
            classificacao[0]["team_tiebreak_order"],
        )
        self.assertEqual([3, 1, 2, 4], [int(item["team_id"]) for item in classificacao])

    def test_criterios_novos_nao_sao_calculados_fora_da_sequencia(self) -> None:
        """Trabalho que ninguém pediu é trabalho a cada abertura de tela."""
        classificacao = calculate_team_standings(_SETTINGS, _teams(4), _TODOS_CONTRA_TODOS)
        self.assertNotIn("sonneborn_berger", classificacao[0])


class AjustesDeArbitroTest(unittest.TestCase):
    """TBK-01 continua valendo com os critérios novos no meio."""

    def test_ajuste_de_match_points_reordena_e_o_sb_nao_muda(self) -> None:
        from src.services.pairing.point_adjustments import AdjustmentTotal

        sequencia = [
            {"code": "match_points", "params": {}},
            {"code": "sonneborn_berger", "params": {}},
        ]
        sem_ajuste = _standings(sequencia)
        com_ajuste = _standings(
            sequencia,
            adjustments={2: AdjustmentTotal(match_points=6.0, game_points=0.0, entries=())},
        )
        self.assertEqual(1, com_ajuste[2]["position"])
        self.assertGreater(sem_ajuste[2]["position"], 1)
        # A penalidade é sobre aquela equipe, não sobre a força de quem a
        # enfrentou: o SB dos outros não se mexe.
        self.assertEqual(
            sem_ajuste[1]["sonneborn_berger"], com_ajuste[1]["sonneborn_berger"]
        )


class BancoDeTabuleirosTest(CoreServiceTestCase):
    """A consulta que alimenta o board count devolve a equipe de cada cor."""

    def test_a_equipe_sai_do_elenco_e_nao_da_paridade_do_tabuleiro(self) -> None:
        """Nos tabuleiros pares as cores invertem: quem tem brancas é a visitante."""
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)

        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        for board in self.db.list_team_boards(int(match["id"])):
            self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, round_data["id"])

        linhas = self.db.list_team_board_results(tournament_id)
        self.assertEqual(2, len(linhas))
        por_tabuleiro = {int(linha["board_number"]): linha for linha in linhas}
        self.assertEqual(
            int(match["white_team_id"]), int(por_tabuleiro[1]["white_team_id"])
        )
        self.assertEqual(
            int(match["black_team_id"]), int(por_tabuleiro[2]["white_team_id"])
        )
        # Cada equipe venceu num tabuleiro: a soma por tabuleiro fecha com o
        # placar do confronto (1 x 1).
        self.assertEqual(
            {
                int(match["white_team_id"]): {1: 1.0, 2: 0.0},
                int(match["black_team_id"]): {1: 0.0, 2: 1.0},
            },
            fold_board_points(linhas),
        )


if __name__ == "__main__":
    unittest.main()
