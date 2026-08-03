"""PAR-04 (parcial) — dívidas técnicas pontuais do núcleo de pareamento.

Quatro defeitos independentes, três deles invisíveis até alguém tentar usar a
funcionalidade: o round-robin por equipes era inalcançável por uma constante
duplicada; a troca de cores no individual era a única mutação de rodada sem
auditoria; o fechamento por equipes descartava o sumário de confrontos completos;
e um tabuleiro em branco virava `KeyError` cru.
"""

from __future__ import annotations

import unittest

from src.services.constants import RESULT_POINTS, TEAM_PAIRING_METHODS, AppError
from src.services.pairing import (
    float_histories,
    round_robin_team_matches,
    search_dutch_pairing,
    team_float_histories,
    team_match_summary,
    team_pair_penalty,
    topscorer_ids,
)
from tests.support.core_service_base import CoreServiceTestCase

_RESULT_POINTS = {"1-0": (1.0, 0.0), "0-1": (0.0, 1.0), "1/2-1/2": (0.5, 0.5)}
# Os pontos DE VERDADE (inclusive W.O. e decisao do arbitro), para o historico
# de flutuacao saber quem pontuou sem jogar.
_RESULT_POINTS_COMPLETO = RESULT_POINTS


def _equipes(total: int) -> list[dict[str, object]]:
    return [{"id": i, "name": f"Equipe {i}"} for i in range(1, total + 1)]


def _seeds(total: int) -> dict[int, int]:
    return {i: 2000 - i * 10 for i in range(1, total + 1)}


def _rosters(total: int, boards: int) -> dict[int, dict[int, int]]:
    return {
        team_id: {board: team_id * 100 + board for board in range(1, boards + 1)}
        for team_id in range(1, total + 1)
    }


class ConstanteDuplicadaTest(unittest.TestCase):
    def test_round_robin_por_equipes_voltou_a_existir(self) -> None:
        """Uma segunda atribuição na mesma constante apagava o método em silêncio."""
        self.assertIn("round_robin", TEAM_PAIRING_METHODS)
        self.assertIn("swiss", TEAM_PAIRING_METHODS)

    def test_constante_nao_e_redefinida_no_modulo(self) -> None:
        """Guarda contra a reincidência: o defeito era invisível ao ler o topo."""
        import inspect

        import src.services.constants as constants

        fonte = inspect.getsource(constants)
        self.assertEqual(
            1,
            sum(
                1
                for linha in fonte.splitlines()
                if linha.startswith("TEAM_PAIRING_METHODS")
            ),
            "TEAM_PAIRING_METHODS definido mais de uma vez",
        )


class RoundRobinPorEquipesTest(unittest.TestCase):
    """Berger sobre equipes: cada par se encontra uma vez, e só uma."""

    @staticmethod
    def _rodadas_do_calendario(total: int) -> int:
        """Rodadas de um todos-contra-todos: N-1 com N par, N com N ímpar.

        Ímpar precisa de uma rodada a mais porque a equipe fantasma ocupa um
        lugar: cada equipe real folga exatamente uma vez.
        """
        return total - 1 if total % 2 == 0 else total

    def _todas_as_rodadas(self, total: int, boards: int = 2) -> list[list[dict]]:
        return [
            round_robin_team_matches(
                _equipes(total), _rosters(total, boards), _seeds(total), boards, {}, rodada
            )
            for rodada in range(1, self._rodadas_do_calendario(total) + 1)
        ]

    def test_par_de_equipes_se_enfrenta_exatamente_uma_vez(self) -> None:
        confrontos: list[frozenset[int]] = []
        for rodada in self._todas_as_rodadas(4):
            for match in rodada:
                if not match["is_bye"]:
                    confrontos.append(
                        frozenset((int(match["white_team_id"]), int(match["black_team_id"])))
                    )
        self.assertEqual(6, len(confrontos), "4 equipes => 6 confrontos em 3 rodadas")
        self.assertEqual(len(confrontos), len(set(confrontos)), "houve confronto repetido")

    def test_numero_impar_de_equipes_da_um_bye_por_rodada(self) -> None:
        folgas: list[int] = []
        for rodada in self._todas_as_rodadas(5):
            byes = [match for match in rodada if match["is_bye"]]
            self.assertEqual(1, len(byes), "cada rodada tem exatamente um bye")
            folgas.append(int(byes[0]["white_team_id"]))
        self.assertEqual(sorted(folgas), [1, 2, 3, 4, 5], "cada equipe folga uma vez")

    def test_as_cores_de_equipe_alternam_entre_as_rodadas(self) -> None:
        """Sem a alternância, a equipe que não gira jogaria sempre de brancas."""
        brancas_da_1 = [
            any(
                int(match.get("white_team_id") or 0) == 1
                for match in rodada
                if not match["is_bye"]
            )
            for rodada in self._todas_as_rodadas(4)
        ]
        self.assertIn(True, brancas_da_1)
        self.assertIn(False, brancas_da_1, "a equipe 1 nunca jogou de pretas")

    def test_rodada_alem_do_calendario_e_recusada_com_recado(self) -> None:
        with self.assertRaises(AppError) as erro:
            round_robin_team_matches(_equipes(4), _rosters(4, 2), _seeds(4), 2, {}, 4)
        self.assertIn("maximo de rodadas", str(erro.exception))

    def test_confronto_traz_os_tabuleiros_montados(self) -> None:
        rodada = round_robin_team_matches(_equipes(4), _rosters(4, 3), _seeds(4), 3, {}, 1)
        confronto = next(match for match in rodada if not match["is_bye"])
        self.assertEqual(3, len(confronto["boards"]))
        # O tabuleiro par inverte as cores — regra do `team_match_payload`.
        primeiro, segundo = confronto["boards"][0], confronto["boards"][1]
        self.assertNotEqual(
            primeiro["white_player_id"] // 100, segundo["white_player_id"] // 100
        )


class SumarioDeConfrontoTest(unittest.TestCase):
    def test_resultado_invalido_vira_recado_e_nao_KeyError(self) -> None:
        boards = [
            {"board_number": 1, "white_player_id": 1, "black_player_id": 2, "result": "1-0"},
            {"board_number": 2, "white_player_id": 3, "black_player_id": 4, "result": ""},
        ]
        with self.assertRaises(AppError) as erro:
            team_match_summary(
                {"id": 1, "white_team_id": 1, "black_team_id": 2},
                boards,
                {1, 3},
                {2, 4},
                _RESULT_POINTS,
                win_points=2.0,
                loss_points=0.0,
                draw_points=1.0,
            )
        self.assertIn("Tabuleiro 2", str(erro.exception))
        self.assertIn("em branco", str(erro.exception))

    def test_confronto_completo_soma_normalmente(self) -> None:
        boards = [
            {"board_number": 1, "white_player_id": 1, "black_player_id": 2, "result": "1-0"},
            {"board_number": 2, "white_player_id": 4, "black_player_id": 3, "result": "0-1"},
        ]
        resumo = team_match_summary(
            {"id": 1, "white_team_id": 1, "black_team_id": 2},
            boards,
            {1, 3},
            {2, 4},
            _RESULT_POINTS,
            win_points=2.0,
            loss_points=0.0,
            draw_points=1.0,
        )
        self.assertEqual(2.0, resumo["white_game_points"])
        self.assertEqual(0.0, resumo["black_game_points"])
        self.assertEqual("1-0", resumo["result"])


class RoundRobinPorEquipesNoServicoTest(CoreServiceTestCase):
    """O critério de aceite: selecionável **e** de fato pareando."""

    def setUp(self) -> None:
        super().setUp()
        self.team_tournament_id, self.team_ids = self._create_team_tournament(
            teams_count=4, boards_count=2
        )

    def test_validacao_do_torneio_aceita_round_robin(self) -> None:
        """Antes a validação recusava: a constante duplicada só tinha "swiss"."""
        self.tournament_service.save_profile(
            self.team_tournament_id,
            {
                "name": "Interclubes",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {"team_pairing_method": "round_robin", "team_boards_count": "2"},
            [],
        )
        settings = self.db.get_tournament_settings(self.team_tournament_id) or {}
        self.assertEqual("round_robin", settings["team_pairing_method"])

    def test_rodadas_geradas_seguem_o_calendario_de_todos_contra_todos(self) -> None:
        """A geração ignorava `team_pairing_method` e era sempre Suíço."""
        self.db.save_tournament_settings(
            self.team_tournament_id, {"team_pairing_method": "round_robin"}
        )
        confrontos: list[frozenset[int]] = []
        for _ in range(3):
            round_data = self.service.generate_next_round(self.team_tournament_id)
            round_id = int(round_data["id"])
            for match in self.db.list_team_matches_for_round(round_id):
                if match["is_bye"]:
                    continue
                confrontos.append(
                    frozenset((int(match["white_team_id"]), int(match["black_team_id"])))
                )
                for board in self.db.list_team_boards(int(match["id"])):
                    self.service.update_result(self.team_tournament_id, int(board["id"]), "1-0")
            self.service.close_round(self.team_tournament_id, round_id)

        self.assertEqual(6, len(confrontos), "4 equipes em 3 rodadas => 6 confrontos")
        self.assertEqual(
            len(confrontos), len(set(confrontos)), "todos contra todos nao repete confronto"
        )

    def test_bye_solicitado_e_recusado_no_calendario_fixo(self) -> None:
        """Tirar uma equipe da rotação desloca todo mundo e repete confrontos.

        A recusa é explícita porque o silêncio aqui seria pior: a rodada sairia
        pareada, só que errada, e ninguém veria até o confronto repetido.
        """
        self.db.save_tournament_settings(
            self.team_tournament_id, {"team_pairing_method": "round_robin"}
        )
        self.db.add_requested_team_bye(
            self.team_tournament_id,
            team_id=self.team_ids[0],
            round_number=1,
            bye_type="H",
            reason="Viagem",
        )
        with self.assertRaises(AppError) as erro:
            self.service.generate_next_round(self.team_tournament_id)
        self.assertIn("calendario e fixo", str(erro.exception))


class TrocaDeCoresTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        self.round_id = int(round_data["id"])
        self.pairing = self.db.get_pairings_for_round(self.round_id)[0]

    def test_troca_inverte_as_cores_e_deixa_trilha(self) -> None:
        """Era a única mutação de rodada que não passava pelo serviço."""
        branca_antes = int(self.pairing["white_player_id"])
        preta_antes = int(self.pairing["black_player_id"])

        self.service.swap_pairing_colors(
            self.tournament_id, self.round_id, int(self.pairing["id"])
        )

        depois = self.db.get_pairing(int(self.pairing["id"]))
        self.assertEqual(preta_antes, int(depois["white_player_id"]))
        self.assertEqual(branca_antes, int(depois["black_player_id"]))

        eventos = self.db.list_audit_events(
            self.tournament_id, action="pairing_colors_swapped", limit=5
        )
        self.assertEqual(1, len(eventos))
        self.assertEqual(str(branca_antes), _campo(eventos[0]["before_json"], "white_player_id"))
        self.assertEqual(str(preta_antes), _campo(eventos[0]["after_json"], "white_player_id"))

    def test_rodada_fechada_recusa_a_troca(self) -> None:
        for pairing in self.db.get_pairings_for_round(self.round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, self.round_id)

        with self.assertRaises(AppError) as erro:
            self.service.swap_pairing_colors(
                self.tournament_id, self.round_id, int(self.pairing["id"])
            )
        self.assertIn("fechada", str(erro.exception))

    def test_mesa_com_resultado_recusa_a_troca(self) -> None:
        """Inverter cores depois do resultado trocaria quem ganhou de quem."""
        self.service.update_result(self.tournament_id, int(self.pairing["id"]), "1-0")
        with self.assertRaises(AppError) as erro:
            self.service.swap_pairing_colors(
                self.tournament_id, self.round_id, int(self.pairing["id"])
            )
        self.assertIn("Limpe o resultado", str(erro.exception))

    def test_mesa_de_outro_torneio_e_recusada(self) -> None:
        outro = self.db.create_tournament("Outro", rounds_count=3)
        with self.assertRaises(AppError):
            self.service.swap_pairing_colors(outro, self.round_id, int(self.pairing["id"]))


class TrocaDeCoresPorEquipesTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.team_tournament_id, self.team_ids = self._create_team_tournament(
            teams_count=2, boards_count=2
        )
        round_data = self.service.generate_next_round(self.team_tournament_id)
        self.round_id = int(round_data["id"])
        match = self.db.list_team_matches_for_round(self.round_id)[0]
        self.board = self.db.list_team_boards(int(match["id"]))[0]

    def test_troca_de_tabuleiro_tambem_deixa_trilha(self) -> None:
        """Passava pelo serviço, mas sem auditoria — a mesma lacuna."""
        self.service.swap_team_board_colors(
            self.team_tournament_id, self.round_id, int(self.board["id"])
        )
        eventos = self.db.list_audit_events(
            self.team_tournament_id, action="team_board_colors_swapped", limit=5
        )
        self.assertEqual(1, len(eventos))


class FechamentoPorEquipesTest(CoreServiceTestCase):
    def test_pendencia_num_confronto_nao_apaga_o_sumario_dos_outros(self) -> None:
        """O `pending` acumulado fazia todo confronto seguinte pular o sumário."""
        tournament_id, _team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        round_id = int(round_data["id"])
        confrontos = [
            match for match in self.db.list_team_matches_for_round(round_id)
            if not match["is_bye"]
        ]
        self.assertEqual(2, len(confrontos))

        # Deixa UM tabuleiro do PRIMEIRO confronto em branco; o segundo fica
        # completo. Antes, o segundo era descartado do sumario junto.
        primeiro_boards = self.db.list_team_boards(int(confrontos[0]["id"]))
        for board in primeiro_boards[1:]:
            self.service.update_result(tournament_id, int(board["id"]), "1-0")
        for board in self.db.list_team_boards(int(confrontos[1]["id"])):
            self.service.update_result(tournament_id, int(board["id"]), "1-0")

        with self.assertRaises(AppError) as erro:
            self.service.close_round(tournament_id, round_id)
        self.assertIn("tabuleiros", str(erro.exception))

        # Completado o que faltava, o fechamento sai com os DOIS sumarios.
        self.service.update_result(tournament_id, int(primeiro_boards[0]["id"]), "1-0")
        self.service.close_round(tournament_id, round_id)

        fechados = self.db.list_team_matches_for_round(round_id)
        for match in fechados:
            if match["is_bye"]:
                continue
            self.assertTrue(str(match["result"]), f"confronto {match['id']} sem resultado")


class TopscorersTest(unittest.TestCase):
    """C.3/A.7: o único critério de cor ABSOLUTO não vale entre dois líderes."""

    def _standings(self, pontos: dict[int, float]) -> dict[int, dict[str, float]]:
        return {pid: {"points": valor} for pid, valor in pontos.items()}

    def test_conceito_so_existe_na_ultima_rodada(self) -> None:
        classificacao = self._standings({1: 3.0, 2: 1.0})
        self.assertEqual(set(), topscorer_ids(classificacao, round_number=4, rounds_total=5))
        self.assertEqual({1}, topscorer_ids(classificacao, round_number=5, rounds_total=5))

    def test_limiar_e_MAIS_de_metade_do_disputado(self) -> None:
        # Rodada 5: cada um disputou 4 partidas, entao o limite e 2.0.
        classificacao = self._standings({1: 2.5, 2: 2.0, 3: 1.5})
        self.assertEqual({1}, topscorer_ids(classificacao, round_number=5, rounds_total=5))

    def test_sem_total_de_rodadas_ninguem_e_topscorer(self) -> None:
        self.assertEqual(
            set(), topscorer_ids(self._standings({1: 9.0}), round_number=5, rounds_total=0)
        )

    def _busca(self, topscorers: set[int]):
        """Dois jogadores que devem a MESMA cor (ambos com duas brancas seguidas)."""
        jogadores = [
            {"id": 1, "name": "A", "rating": 2000},
            {"id": 2, "name": "B", "rating": 1900},
        ]
        historicos = {1: ["W", "W"], 2: ["W", "W"]}
        return search_dutch_pairing(
            jogadores, historicos, set(), strict_colors=True, topscorers=topscorers
        )

    def test_dois_nao_topscorers_com_a_mesma_cor_absoluta_nao_se_enfrentam(self) -> None:
        self.assertIsNone(self._busca(set()))

    def test_dois_topscorers_podem_se_enfrentar(self) -> None:
        """É o que a última rodada costuma exigir: os dois líderes se enfrentam."""
        pares = self._busca({1, 2})
        self.assertEqual(1, len(pares or []))

    def test_um_topscorer_so_nao_libera_o_par(self) -> None:
        self.assertIsNone(self._busca({1}))


class HistoricoDeFlutuacaoTest(unittest.TestCase):
    """A mesma partida contava de três jeitos: cor e repetição excluíam o W.O.,
    a flutuação não. A regra passa a ser a do motor FIDE."""

    def _mesas(self, *resultados: tuple[int, int | None, str, int]) -> list[dict[str, object]]:
        return [
            {
                "white_player_id": branca,
                "black_player_id": preta,
                "result": resultado,
                "is_bye": bye,
            }
            for branca, preta, resultado, bye in resultados
        ]

    def _historico(self, mesas, jogadores=(1, 2), bye_points: float = 1.0):
        return float_histories(
            mesas,
            [{"id": pid, "starting_points": 0.0} for pid in jogadores],
            bye_points,
            _RESULT_POINTS_COMPLETO,
        )

    def test_partida_jogada_flutua_os_dois_lados(self) -> None:
        historico = self._historico(
            self._mesas((1, 2, "1-0", 0), (1, 2, "1-0", 0)),
        )
        self.assertEqual(["=", "down"], historico[1])
        self.assertEqual(["=", "up"], historico[2])

    def test_wo_nao_flutua_por_pontuacao(self) -> None:
        """Quem venceu por W.O. pontuou sem jogar: conta como DOWNFLOAT; o outro
        lado nao flutua (e o ramo `dutch` do `compute_flt` do Gacrux)."""
        historico = self._historico(self._mesas((1, 2, "1F-0F", 0)))
        self.assertEqual(["down"], historico[1])
        self.assertEqual([], historico[2])

    def test_dupla_ausencia_nao_flutua_ninguem(self) -> None:
        historico = self._historico(self._mesas((1, 2, "0F-0F", 0)))
        self.assertEqual([], historico[1])
        self.assertEqual([], historico[2])

    def test_bye_que_pontua_e_downfloat(self) -> None:
        historico = self._historico(self._mesas((1, None, "BYE", 1)))
        self.assertEqual(["bye", "down"], historico[1])

    def test_bye_de_zero_ponto_nao_flutua(self) -> None:
        historico = self._historico(self._mesas((1, None, "Z", 1)))
        self.assertEqual(["bye"], historico[1])


class FlutuacaoPorEquipesTest(unittest.TestCase):
    """O Suíço por equipes não penalizava float repetido — o individual sim."""

    def _confrontos(self) -> list[dict[str, object]]:
        return [
            {
                "round_number": 1, "white_team_id": 1, "black_team_id": 2,
                "white_match_points": 2.0, "black_match_points": 0.0, "is_bye": 0,
            },
            {
                "round_number": 2, "white_team_id": 1, "black_team_id": 3,
                "white_match_points": 2.0, "black_match_points": 0.0, "is_bye": 0,
            },
        ]

    def test_historico_sai_dos_match_points(self) -> None:
        historico = team_float_histories(self._confrontos())
        self.assertEqual(["=", "down"], historico[1])
        self.assertEqual(["="], historico[2])
        self.assertEqual(["up"], historico[3])

    def test_bye_de_equipe_que_pontua_e_downfloat(self) -> None:
        historico = team_float_histories(
            [{
                "round_number": 1, "white_team_id": 1, "black_team_id": None,
                "white_match_points": 2.0, "black_match_points": 0.0, "is_bye": 1,
            }]
        )
        self.assertEqual(["bye", "down"], historico[1])

    def test_float_repetido_encarece_o_confronto(self) -> None:
        equipes = {1: {"match_points": 4.0}, 2: {"match_points": 2.0}}
        argumentos = dict(
            repeat_pairing_penalty=1000,
            score_group_float_penalty=50,
            score_diff_penalty=10,
        )
        base = team_pair_penalty(
            {"id": 1, "name": "A"}, {"id": 2, "name": "B"}, equipes, set(), {1: 1, 2: 2},
            **argumentos,
        )
        com_historico = team_pair_penalty(
            {"id": 1, "name": "A"}, {"id": 2, "name": "B"}, equipes, set(), {1: 1, 2: 2},
            float_histories={1: ["down", "down"], 2: ["up"]},
            **argumentos,
        )
        self.assertGreater(com_historico, base)


def _campo(payload_json: str, chave: str) -> str:
    import json

    return str(json.loads(payload_json or "{}").get(chave, ""))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
