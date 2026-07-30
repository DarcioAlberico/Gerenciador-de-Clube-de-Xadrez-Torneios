"""TBK-01 — ajustes de pontos do árbitro aplicados à classificação.

Duas camadas: as funções puras (ordenação nos DOIS motores de desempate, sem
banco e sem subprocesso) e o caminho completo pelo `PairingService`, onde se
confere que o número que a tela mostra é o mesmo que sai na ata e no relatório
de auditoria.

O motor Gacrux é simulado pelo parâmetro `gacrux_tiebreaks` — é exatamente o que
o `PairingService` passa quando o subprocesso responde, e testar assim mantém a
suíte determinística e rápida. O que precisa ser provado aqui não é o cálculo do
Gacrux (isso é do `test_pairing_gacrux_tiebreak`), e sim que o ajuste reordena
por cima do rank que ele devolveu.
"""

from __future__ import annotations

import unittest

from src.services.pairing import (
    AdjustmentEntry,
    AdjustmentTotal,
    adjustment_note,
    aggregate_player_adjustments,
    aggregate_team_adjustments,
    calculate_player_standings,
    calculate_team_standings,
    describe_entry,
    format_signed,
    has_adjustment,
    mark_adjusted,
)
from tests.support.core_service_base import CoreServiceTestCase

# --------------------------------------------------------------------------- #
# Cenário individual reaproveitado: 4 jogadores, 2 rodadas.
#
#   R1: 1 vence 2  |  3 vence 4
#   R2: 1 empata 3 |  2 vence 4
#
# Pontos: 1 → 1,5   2 → 1,0   3 → 1,5   4 → 0,0
# Buchholz: 1 → 2,5 (adv. 2 e 3)   3 → 1,5 (adv. 4 e 1)
# Sem ajuste a ordem é 1, 3, 2, 4.
# --------------------------------------------------------------------------- #

_TOURNAMENT = {"bye_points": 1.0}

_PLAYERS = [
    {"id": 1, "name": "Ana", "club": "A", "rating": 2000, "category": "Absoluto", "active": 1},
    {"id": 2, "name": "Bruno", "club": "B", "rating": 1900, "category": "Absoluto", "active": 1},
    {"id": 3, "name": "Carla", "club": "C", "rating": 1800, "category": "Absoluto", "active": 1},
    {"id": 4, "name": "Davi", "club": "D", "rating": 1700, "category": "Absoluto", "active": 1},
]

_PAIRINGS = [
    {"id": 1, "round_number": 1, "white_player_id": 1, "black_player_id": 2, "result": "1-0", "is_bye": 0},
    {"id": 2, "round_number": 1, "white_player_id": 3, "black_player_id": 4, "result": "1-0", "is_bye": 0},
    {"id": 3, "round_number": 2, "white_player_id": 1, "black_player_id": 3, "result": "1/2-1/2", "is_bye": 0},
    {"id": 4, "round_number": 2, "white_player_id": 2, "black_player_id": 4, "result": "1-0", "is_bye": 0},
]

# Rank que o motor FIDE devolveria para o cenário acima (PTS, depois Buchholz).
_GACRUX_RANKS = {
    1: {"rank": 1, "scores": {"buchholz": 2.5}},
    3: {"rank": 2, "scores": {"buchholz": 1.5}},
    2: {"rank": 3, "scores": {"buchholz": 1.5}},
    4: {"rank": 4, "scores": {"buchholz": 3.0}},
}


def _penalidade(player_id: int, pontos: float, motivo: str) -> dict[int, AdjustmentTotal]:
    return aggregate_player_adjustments(
        [
            {
                "player_id": player_id,
                "round_number": 2,
                "aat_type": "",
                "match_points": 0.0,
                "game_points": pontos,
                "reason": motivo,
            }
        ]
    )


def _ordem(standings: list[dict]) -> list[int]:
    return [int(item["player_id"]) for item in standings]


class AgregacaoTest(unittest.TestCase):
    def test_lancamentos_do_mesmo_jogador_somam(self) -> None:
        totais = aggregate_player_adjustments(
            [
                {"player_id": 7, "game_points": -0.5, "reason": "celular", "round_number": 3},
                {"player_id": 7, "game_points": -0.5, "reason": "atraso", "round_number": 5},
                {"player_id": 9, "game_points": 1.0, "reason": "bônus"},
            ]
        )
        self.assertEqual(-1.0, totais[7].game_points)
        self.assertEqual(2, len(totais[7].entries))
        self.assertEqual(1.0, totais[9].game_points)

    def test_match_points_nao_entram_no_individual(self) -> None:
        """MP é grandeza de equipe: linha com MP não pode mover o individual."""
        totais = aggregate_player_adjustments(
            [{"player_id": 7, "match_points": -2.0, "game_points": -0.5}]
        )
        self.assertEqual(0.0, totais[7].match_points)
        self.assertEqual(-0.5, totais[7].game_points)

    def test_linha_sem_alvo_e_ignorada(self) -> None:
        """Ajuste de equipe na tabela de um torneio individual (e vice-versa)."""
        self.assertEqual({}, aggregate_player_adjustments([{"team_id": 3, "game_points": -1.0}]))
        self.assertEqual({}, aggregate_team_adjustments([{"player_id": 3, "game_points": -1.0}]))

    def test_equipes_somam_as_duas_grandezas(self) -> None:
        totais = aggregate_team_adjustments(
            [{"team_id": 4, "match_points": -2.0, "game_points": -1.5, "reason": "escalação"}]
        )
        self.assertEqual(-2.0, totais[4].match_points)
        self.assertEqual(-1.5, totais[4].game_points)


class TextoTest(unittest.TestCase):
    def test_sinal_e_virgula_decimal(self) -> None:
        self.assertEqual("-0,5", format_signed(-0.5))
        self.assertEqual("+1", format_signed(1.0))
        self.assertEqual("+2,25", format_signed(2.25))

    def test_unidade_so_aparece_quando_ha_match_points(self) -> None:
        """No individual "pontos" é inequívoco; o rótulo MP/GP seria ruído."""
        individual = AdjustmentEntry(3, "", 0.0, -0.5, "celular tocou")
        equipe = AdjustmentEntry(2, "", -2.0, -1.0, "escalação irregular")
        self.assertEqual("-0,5 (rodada 3): celular tocou", describe_entry(individual))
        self.assertEqual(
            "-2 MP / -1 GP (rodada 2): escalação irregular", describe_entry(equipe)
        )

    def test_lancamento_sem_efeito_nos_pontos_se_explica(self) -> None:
        self.assertEqual("tipo W: decisão do júri", describe_entry(AdjustmentEntry(0, "W", 0, 0, "decisão do júri")))

    def test_nota_junta_os_lancamentos(self) -> None:
        total = AdjustmentTotal(
            0.0,
            -1.0,
            (AdjustmentEntry(1, "", 0, -0.5, "a"), AdjustmentEntry(4, "", 0, -0.5, "b")),
        )
        self.assertEqual("-0,5 (rodada 1): a; -0,5 (rodada 4): b", adjustment_note(total))
        self.assertEqual("", adjustment_note(None))

    def test_marcador_so_com_ajuste(self) -> None:
        self.assertEqual("4,5 *", mark_adjusted("4,5", -0.5))
        self.assertEqual("4,5", mark_adjusted("4,5", 0.0))
        self.assertFalse(has_adjustment({"adjustment_points": 0.0}))
        self.assertTrue(has_adjustment({"adjustment_points": -0.5}))
        self.assertTrue(has_adjustment({"adjustment_match_points": -2.0}))


class ClassificacaoIndividualTest(unittest.TestCase):
    def test_sem_ajuste_a_ordem_e_a_de_sempre(self) -> None:
        ordem = _ordem(calculate_player_standings(_TOURNAMENT, _PLAYERS, _PAIRINGS))
        self.assertEqual([1, 3, 2, 4], ordem)

    def test_penalidade_de_meio_ponto_reordena_no_motor_proprio(self) -> None:
        standings = calculate_player_standings(
            _TOURNAMENT,
            _PLAYERS,
            _PAIRINGS,
            adjustments=_penalidade(1, -0.5, "celular tocou"),
        )
        self.assertEqual([3, 1, 2, 4], _ordem(standings))
        ana = standings[1]
        self.assertEqual(1.0, ana["points"])
        self.assertEqual(-0.5, ana["adjustment_points"])
        self.assertEqual("-0,5 (rodada 2): celular tocou", ana["adjustment_note"])

    def test_penalidade_reordena_tambem_por_cima_do_rank_do_gacrux(self) -> None:
        """O motor FIDE não recebe a tabela de ajustes — quem reordena é o Albericus."""
        sem_ajuste = calculate_player_standings(
            _TOURNAMENT, _PLAYERS, _PAIRINGS, gacrux_tiebreaks=_GACRUX_RANKS
        )
        self.assertEqual([1, 3, 2, 4], _ordem(sem_ajuste))

        com_ajuste = calculate_player_standings(
            _TOURNAMENT,
            _PLAYERS,
            _PAIRINGS,
            gacrux_tiebreaks=_GACRUX_RANKS,
            adjustments=_penalidade(1, -0.5, "celular tocou"),
        )
        self.assertEqual([3, 1, 2, 4], _ordem(com_ajuste))
        # Empatada em 1,0 com Bruno, Ana fica à frente pelo rank do Gacrux —
        # o motor continua decidindo o que o ajuste não decidiu.
        self.assertEqual(1.0, com_ajuste[1]["points"])
        self.assertEqual(1.0, com_ajuste[2]["points"])

    def test_desempates_medem_o_tabuleiro_e_nao_a_penalidade(self) -> None:
        """Buchholz/SB dos adversários não mudam: a penalidade é sobre o punido.

        É também o que mantém os dois motores dizendo o mesmo número — o Gacrux
        calcula o Buchholz sobre os pontos de partida, sem ajuste nenhum.
        """
        base = calculate_player_standings(_TOURNAMENT, _PLAYERS, _PAIRINGS)
        buchholz_base = {int(item["player_id"]): item["buchholz"] for item in base}

        punido = calculate_player_standings(
            _TOURNAMENT, _PLAYERS, _PAIRINGS, adjustments=_penalidade(1, -0.5, "celular")
        )
        buchholz_punido = {int(item["player_id"]): item["buchholz"] for item in punido}

        self.assertEqual(buchholz_base, buchholz_punido)
        self.assertEqual(1.5, buchholz_punido[2])  # adversário de Ana não perde nada

    def test_todo_jogador_recebe_os_campos_mesmo_sem_ajuste(self) -> None:
        for item in calculate_player_standings(_TOURNAMENT, _PLAYERS, _PAIRINGS):
            self.assertEqual(0.0, item["adjustment_points"])
            self.assertEqual("", item["adjustment_note"])


# --------------------------------------------------------------------------- #
# Cenário por equipes: 3 equipes, todos contra todos.
#   Alfa 2x0 Beta (3-1) | Alfa 2x0 Gama (3-1) | Beta 2x0 Gama (2,5-1,5)
#   MP: Alfa 4, Beta 2, Gama 0
# --------------------------------------------------------------------------- #

_TEAM_SETTINGS = {"team_standing_primary": "match_points", "team_standing_secondary": "game_points"}

_TEAMS = [
    {"id": 1, "name": "Alfa", "active": 1},
    {"id": 2, "name": "Beta", "active": 1},
    {"id": 3, "name": "Gama", "active": 1},
]

_MATCHES = [
    {"id": 1, "white_team_id": 1, "black_team_id": 2, "white_match_points": 2.0,
     "black_match_points": 0.0, "white_game_points": 3.0, "black_game_points": 1.0},
    {"id": 2, "white_team_id": 1, "black_team_id": 3, "white_match_points": 2.0,
     "black_match_points": 0.0, "white_game_points": 3.0, "black_game_points": 1.0},
    {"id": 3, "white_team_id": 2, "black_team_id": 3, "white_match_points": 2.0,
     "black_match_points": 0.0, "white_game_points": 2.5, "black_game_points": 1.5},
]

_GACRUX_TEAM_RANKS = {
    1: {"rank": 1, "scores": {}},
    2: {"rank": 2, "scores": {}},
    3: {"rank": 3, "scores": {}},
}


def _ordem_equipes(standings: list[dict]) -> list[int]:
    return [int(item["team_id"]) for item in standings]


def _penalidade_equipe(team_id: int, match_points: float, motivo: str) -> dict[int, AdjustmentTotal]:
    return aggregate_team_adjustments(
        [
            {
                "team_id": team_id,
                "round_number": 1,
                "aat_type": "",
                "match_points": match_points,
                "game_points": 0.0,
                "reason": motivo,
            }
        ]
    )


class ClassificacaoPorEquipesTest(unittest.TestCase):
    def test_sem_ajuste_a_ordem_e_a_de_sempre(self) -> None:
        ordem = _ordem_equipes(calculate_team_standings(_TEAM_SETTINGS, _TEAMS, _MATCHES))
        self.assertEqual([1, 2, 3], ordem)

    def test_deducao_de_match_points_reordena_no_motor_proprio(self) -> None:
        standings = calculate_team_standings(
            _TEAM_SETTINGS,
            _TEAMS,
            _MATCHES,
            adjustments=_penalidade_equipe(1, -3.0, "escalação irregular"),
        )
        self.assertEqual([2, 1, 3], _ordem_equipes(standings))
        alfa = standings[1]
        self.assertEqual(1.0, alfa["match_points"])
        self.assertEqual(-3.0, alfa["adjustment_match_points"])
        self.assertEqual(
            "-3 MP (rodada 1): escalação irregular", alfa["adjustment_note"]
        )

    def test_deducao_reordena_tambem_por_cima_do_rank_do_gacrux(self) -> None:
        sem_ajuste = calculate_team_standings(
            _TEAM_SETTINGS, _TEAMS, _MATCHES, gacrux_tiebreaks=_GACRUX_TEAM_RANKS
        )
        self.assertEqual([1, 2, 3], _ordem_equipes(sem_ajuste))

        com_ajuste = calculate_team_standings(
            _TEAM_SETTINGS,
            _TEAMS,
            _MATCHES,
            gacrux_tiebreaks=_GACRUX_TEAM_RANKS,
            adjustments=_penalidade_equipe(1, -3.0, "escalação irregular"),
        )
        self.assertEqual([2, 1, 3], _ordem_equipes(com_ajuste))

    def test_ajuste_de_game_points_desempata_com_o_rank_do_gacrux_intacto(self) -> None:
        """Bônus de GP não muda MP: a ordem por MP fica, o desempate é o do motor."""
        standings = calculate_team_standings(
            _TEAM_SETTINGS,
            _TEAMS,
            _MATCHES,
            gacrux_tiebreaks=_GACRUX_TEAM_RANKS,
            adjustments=aggregate_team_adjustments(
                [{"team_id": 3, "match_points": 0.0, "game_points": 2.0, "reason": "bônus"}]
            ),
        )
        self.assertEqual([1, 2, 3], _ordem_equipes(standings))
        self.assertEqual(2.0, standings[2]["adjustment_game_points"])


class AjusteNoServicoTest(CoreServiceTestCase):
    """Caminho completo: banco → PairingService → ata → relatório de auditoria."""

    def _torneio_com_uma_rodada(self) -> list[int]:
        player_ids = self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)
        return player_ids

    def test_penalidade_derruba_o_lider_na_classificacao_do_servico(self) -> None:
        self._torneio_com_uma_rodada()
        lider = self.service.standings(self.tournament_id)[0]
        self.assertEqual(1.0, lider["points"])

        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=1,
            player_id=int(lider["player_id"]),
            game_points=-0.5,
            reason="Celular tocou no salão",
        )

        standings = self.service.standings(self.tournament_id)
        punido = next(
            item for item in standings if int(item["player_id"]) == int(lider["player_id"])
        )
        self.assertEqual(0.5, punido["points"])
        self.assertEqual(-0.5, punido["adjustment_points"])
        self.assertIn("Celular tocou no salão", punido["adjustment_note"])
        self.assertGreater(int(punido["position"]), 1)

    def test_ata_final_registra_o_motivo_por_extenso(self) -> None:
        """A classificação leva o asterisco; a ata leva quem, quando e por quê."""
        player_ids = self._torneio_com_uma_rodada()
        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=1,
            player_id=player_ids[0],
            game_points=-0.5,
            reason="Celular tocou no salão",
        )

        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        titulos = [titulo for titulo, _headers, _rows in secoes]
        self.assertIn("Ajustes de pontos do árbitro (TRF25 §7.3)", titulos)

        _titulo, headers, rows = next(
            secao for secao in secoes if secao[0].startswith("Ajustes de pontos")
        )
        self.assertIn("Motivo", headers)
        self.assertEqual(1, len(rows))
        self.assertIn("Celular tocou no salão", rows[0])
        self.assertIn("-0,5", rows[0])

    def test_ata_sem_ajuste_nao_ganha_secao_vazia(self) -> None:
        self._torneio_com_uma_rodada()
        titulos = [
            titulo
            for titulo, _headers, _rows in self.export_service._tournament_minutes_sections(
                self.tournament_id
            )
        ]
        self.assertNotIn("Ajustes de pontos do árbitro (TRF25 §7.3)", titulos)

    def test_classificacao_exportada_marca_a_linha_ajustada(self) -> None:
        player_ids = self._torneio_com_uma_rodada()
        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=1,
            player_id=player_ids[0],
            game_points=-0.5,
            reason="Celular tocou",
        )
        _titulo, headers, rows = self.export_service._standings_section(self.tournament_id)
        coluna = headers.index("Pts")
        marcadas = [row for row in rows if str(row[coluna]).endswith("*")]
        self.assertEqual(1, len(marcadas), "só a linha ajustada leva o asterisco")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
