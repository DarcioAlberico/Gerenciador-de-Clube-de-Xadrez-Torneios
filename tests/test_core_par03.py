"""PAR-03 — mata-mata com avanço registrado e Scheveningen com escala fixa.

No mata-mata, quem avançava saía de dois `if`: `1-0` passa as brancas, `0-1`
passa as pretas, **qualquer outra coisa** passa o melhor número inicial. "Qualquer
outra coisa" era o empate (o caso mais comum!), a dupla ausência, a mesa ainda em
branco — e também o W.O. e o resultado por decisão do árbitro, que têm vencedor
claro e mesmo assim eram resolvidos pelo ranking. Nada disso ficava escrito.

No Scheveningen, a escala era refeita a cada rodada com a lista de ativos: uma
desistência deslocava todos os índices seguintes e desigualava os grupos — o que
fazia a geração ser recusada, travando o torneio.
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.pairing.knockout import (
    ADVANCEMENT_CRITERIA,
    advancing_player_ids,
    board_winner,
    bracket,
    criterion_label,
    decision_error,
    third_place_pairing,
    undecided_boards,
)
from src.services.pairing.scheveningen import (
    assign_scale,
    calendar_rounds,
    scheveningen_pairings_from_scale,
)
from src.ui.screens.pairing_results.state import format_knockout_bracket
from tests.support.core_service_base import CoreServiceTestCase


def _mesa(**campos) -> dict:
    base = {
        "id": 1,
        "board_number": 1,
        "white_player_id": 10,
        "black_player_id": 20,
        "result": "",
        "is_bye": 0,
    }
    base.update(campos)
    return base


class QuemAvancaTest(unittest.TestCase):
    """O vencedor sai dos PONTOS do resultado, não de uma lista de códigos."""

    def test_vitoria_normal(self) -> None:
        self.assertEqual(10, board_winner(_mesa(result="1-0")))
        self.assertEqual(20, board_winner(_mesa(result="0-1")))

    def test_wo_e_decisao_do_arbitro_tambem_decidem(self) -> None:
        """Eram tratados como empate: o avanço caía no número inicial."""
        self.assertEqual(10, board_winner(_mesa(result="1F-0F")))
        self.assertEqual(20, board_winner(_mesa(result="0F-1F")))
        self.assertEqual(10, board_winner(_mesa(result="1U-0U")))

    def test_empate_dupla_ausencia_e_mesa_em_branco_nao_decidem(self) -> None:
        self.assertIsNone(board_winner(_mesa(result="1/2-1/2")))
        self.assertIsNone(board_winner(_mesa(result="0F-0F")))
        self.assertIsNone(board_winner(_mesa(result="")))
        self.assertIsNone(board_winner(_mesa(result="1/2U-1/2U")))

    def test_bye_avanca_sozinho(self) -> None:
        self.assertEqual(10, board_winner(_mesa(is_bye=1, black_player_id=None)))

    def test_mesa_sem_decisao_fica_pendente_ate_o_registro(self) -> None:
        mesas = [_mesa(result="1/2-1/2")]
        self.assertEqual(1, len(undecided_boards(mesas, {})))
        decisao = {1: {"player_id": 20, "criterion": "blitz", "notes": ""}}
        self.assertEqual([], undecided_boards(mesas, decisao))
        self.assertEqual([20], advancing_player_ids(mesas, decisao))


class RegistroDoAvancoTest(unittest.TestCase):
    def _erro(self, **campos) -> str:
        base = dict(
            criterion="blitz",
            notes="",
            player_id=10,
            pairing=_mesa(result="1/2-1/2"),
            round_closed=True,
        )
        base.update(campos)
        return decision_error(**base)

    def test_registro_valido(self) -> None:
        self.assertEqual("", self._erro())

    def test_criterio_desconhecido_e_recusado(self) -> None:
        self.assertIn("Criterio de avanco invalido", self._erro(criterion="cara_ou_coroa"))

    def test_jogador_de_fora_da_mesa_e_recusado(self) -> None:
        self.assertIn("nao esta nesta mesa", self._erro(player_id=99))

    def test_mesa_decidida_no_tabuleiro_nao_aceita_avanco(self) -> None:
        """Um avanço registrado não pode virar atalho para corrigir placar."""
        erro = self._erro(pairing=_mesa(result="1-0"))
        self.assertIn("decidida no tabuleiro", erro)

    def test_rodada_aberta_e_recusada(self) -> None:
        self.assertIn("Feche a rodada", self._erro(round_closed=False))

    def test_regulamento_e_decisao_exigem_motivo(self) -> None:
        self.assertIn("Descreva", self._erro(criterion="arbiter"))
        self.assertIn("Descreva", self._erro(criterion="regulation", notes="ok"))
        self.assertEqual("", self._erro(criterion="arbiter", notes="sorteio publico"))

    def test_bye_nao_tem_desempate(self) -> None:
        erro = self._erro(pairing=_mesa(is_bye=1, black_player_id=None))
        self.assertIn("ja avanca sozinho", erro)

    def test_todo_criterio_tem_rotulo(self) -> None:
        for codigo in ADVANCEMENT_CRITERIA:
            self.assertNotEqual(codigo, criterion_label(codigo))


class ChaveTest(unittest.TestCase):
    def test_chave_diz_por_que_cada_um_avancou(self) -> None:
        rounds = [{"number": 1, "status": "closed"}]
        mesas = {1: [_mesa(id=1, result="1/2-1/2"), _mesa(id=2, board_number=2, result="1-0")]}
        decisoes = {1: {"player_id": 20, "criterion": "armageddon", "notes": "armagedom apos 2 rapidas"}}
        fases = bracket(rounds, mesas, decisoes, {10: "Ana", 20: "Bruno"})
        primeira, segunda = fases[0]["boards"]
        self.assertEqual("Bruno", primeira["advanced_name"])
        self.assertEqual("Armagedom", primeira["criterion_label"])
        self.assertEqual("Ana", segunda["advanced_name"])
        self.assertEqual("Resultado no tabuleiro", segunda["criterion_label"])
        self.assertEqual(0, fases[0]["pending"])

    def test_mesa_sem_decisao_aparece_como_pendencia(self) -> None:
        fases = bracket([{"number": 1}], {1: [_mesa(result="1/2-1/2")]}, {}, {10: "Ana", 20: "Bruno"})
        self.assertTrue(fases[0]["boards"][0]["pending"])
        self.assertEqual(1, fases[0]["pending"])

    def test_texto_da_chave_mostra_o_motivo(self) -> None:
        fases = bracket(
            [{"number": 1}],
            {1: [_mesa(result="1/2-1/2")]},
            {1: {"player_id": 10, "criterion": "arbiter", "notes": "sorteio previsto no edital"}},
            {10: "Ana", 20: "Bruno"},
        )
        texto = format_knockout_bracket({"tournament_name": "Copa", "rounds": fases, "pending": 0})
        self.assertIn("avanca Ana (Decisao do arbitro): sorteio previsto no edital", texto)

    def test_terceiro_lugar_sai_dos_dois_perdedores_da_semi(self) -> None:
        semis = [
            _mesa(id=1, white_player_id=1, black_player_id=4, result="1-0"),
            _mesa(id=2, board_number=2, white_player_id=2, black_player_id=3, result="0-1"),
        ]
        mesa = third_place_pairing(semis, {}, 2)
        self.assertEqual({4, 2}, {mesa["white_player_id"], mesa["black_player_id"]})

    def test_sem_dois_perdedores_nao_ha_terceiro_lugar(self) -> None:
        """Semifinal com bye não produz terceiro colocado."""
        semis = [
            _mesa(id=1, white_player_id=1, black_player_id=None, is_bye=1),
            _mesa(id=2, board_number=2, white_player_id=2, black_player_id=3, result="1-0"),
        ]
        self.assertIsNone(third_place_pairing(semis, {}, 2))


class EscalaDoScheveningenTest(unittest.TestCase):
    def test_escala_parte_o_campo_pela_ordem_inicial(self) -> None:
        escala = assign_scale([10, 20, 30, 40])
        self.assertEqual(("A", 1), escala[10])
        self.assertEqual(("A", 2), escala[20])
        self.assertEqual(("B", 1), escala[30])
        self.assertEqual(("B", 2), escala[40])
        self.assertEqual(2, calendar_rounds(escala))

    def test_escala_respeita_os_grupos_manuais(self) -> None:
        escala = assign_scale([10, 20, 30, 40], {10: "A", 40: "A", 20: "B", 30: "B"})
        self.assertEqual("A", escala[40][0])
        self.assertEqual("B", escala[20][0])

    def test_campo_impar_e_grupos_desiguais_sao_recusados(self) -> None:
        with self.assertRaisesRegex(AppError, "par"):
            assign_scale([1, 2, 3])
        with self.assertRaisesRegex(AppError, "mesmo numero"):
            assign_scale([1, 2, 3], {1: "A", 2: "A", 3: "B"})

    def test_cada_cruzamento_acontece_uma_vez(self) -> None:
        escala = assign_scale([1, 2, 3, 4, 5, 6])
        vistos = set()
        for rodada in range(1, calendar_rounds(escala) + 1):
            for mesa in scheveningen_pairings_from_scale(escala, rodada):
                a, b = mesa["white_player_id"], mesa["black_player_id"]
                vistos.add((a, b) if escala[a][0] == "A" else (b, a))
        self.assertEqual({(a, b) for a in (1, 2, 3) for b in (4, 5, 6)}, vistos)

    def test_rodada_fora_do_calendario_e_recusada(self) -> None:
        with self.assertRaisesRegex(AppError, "fora dele"):
            scheveningen_pairings_from_scale(assign_scale([1, 2, 3, 4]), 3)


class MataMataNoBancoTest(CoreServiceTestCase):
    def _mata_mata(self, jogadores: int = 4, **settings) -> list[int]:
        self._set_individual_pairing_method("knockout")
        if settings:
            self.db.save_tournament_settings(self.tournament_id, settings)
        return self._create_players(jogadores)

    def _fechar_rodada(self, resultados: dict[int, str]) -> int:
        """Lança `{board_number: resultado}` e fecha a rodada gerada."""
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            resultado = resultados.get(int(pairing["board_number"]))
            if resultado:
                self.service.update_result(self.tournament_id, int(pairing["id"]), resultado)
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        return int(rodada["id"])

    def test_empate_bloqueia_a_proxima_fase(self) -> None:
        self._mata_mata()
        self._fechar_rodada({1: "1/2-1/2", 2: "1-0"})
        with self.assertRaises(AppError) as erro:
            self.service.generate_next_round(self.tournament_id)
        self.assertIn("sem vencedor no tabuleiro", str(erro.exception))
        self.assertIn("mesa(s) 1", str(erro.exception))

    def test_avanco_registrado_destrava_e_aparece_na_chave(self) -> None:
        self._mata_mata()
        round_id = self._fechar_rodada({1: "1/2-1/2", 2: "1-0"})
        mesa = next(
            pairing
            for pairing in self.db.get_pairings_for_round(round_id)
            if int(pairing["board_number"]) == 1
        )
        perdedor_no_ranking = int(mesa["black_player_id"])
        self.service.register_knockout_advancement(
            self.tournament_id,
            int(mesa["id"]),
            perdedor_no_ranking,
            "armageddon",
            "armagedom apos duas rapidas",
        )
        proxima = self.service.generate_next_round(self.tournament_id)
        finalistas = {
            int(pairing["white_player_id"])
            for pairing in self.db.get_pairings_for_round(int(proxima["id"]))
        } | {
            int(pairing["black_player_id"])
            for pairing in self.db.get_pairings_for_round(int(proxima["id"]))
        }
        # Antes, o melhor numero inicial passava: o adversario dele nem apareceria.
        self.assertIn(perdedor_no_ranking, finalistas)

        chave = self.service.knockout_bracket(self.tournament_id)
        primeira = chave["rounds"][0]["boards"][0]
        self.assertEqual("Armagedom", primeira["criterion_label"])
        self.assertEqual("armagedom apos duas rapidas", primeira["notes"])
        self.assertEqual(perdedor_no_ranking, primeira["advanced_player_id"])
        # A fase resolvida nao tem pendencia; a final, ainda sem resultado, tem.
        self.assertEqual(0, chave["rounds"][0]["pending"])
        self.assertEqual(1, chave["rounds"][1]["pending"])
        self.assertEqual(2, len(finalistas))

    def test_avanco_em_mesa_decidida_e_recusado(self) -> None:
        self._mata_mata()
        round_id = self._fechar_rodada({1: "1-0", 2: "1-0"})
        mesa = self.db.get_pairings_for_round(round_id)[0]
        with self.assertRaises(AppError):
            self.service.register_knockout_advancement(
                self.tournament_id, int(mesa["id"]), int(mesa["black_player_id"]), "blitz"
            )

    def test_wo_avanca_quem_venceu_e_nao_o_melhor_ranking(self) -> None:
        """`1F-0F`/`0F-1F` caíam no ranking: o vencedor por W.O. podia ser eliminado."""
        self._mata_mata()
        round_id = self._fechar_rodada({1: "0F-1F", 2: "1-0"})
        mesa = next(
            pairing
            for pairing in self.db.get_pairings_for_round(round_id)
            if int(pairing["board_number"]) == 1
        )
        vencedor_por_wo = int(mesa["black_player_id"])
        proxima = self.service.generate_next_round(self.tournament_id)
        na_final = {
            lado
            for pairing in self.db.get_pairings_for_round(int(proxima["id"]))
            for lado in (int(pairing["white_player_id"]), int(pairing["black_player_id"] or 0))
        }
        self.assertIn(vencedor_por_wo, na_final)

    def test_disputa_de_terceiro_lugar_entra_na_final(self) -> None:
        self._mata_mata(4, knockout_third_place=1)
        self._fechar_rodada({1: "1-0", 2: "1-0"})
        final = self.service.generate_next_round(self.tournament_id)
        mesas = self.db.get_pairings_for_round(int(final["id"]))
        self.assertEqual(2, len(mesas), "final e disputa de 3o lugar na mesma rodada")

    def test_vencedor_do_terceiro_lugar_nao_volta_a_chave(self) -> None:
        """A final encerra o torneio: ganhar o 3o lugar nao gera outra fase."""
        self._mata_mata(4, knockout_third_place=1)
        self._fechar_rodada({1: "1-0", 2: "1-0"})
        self._fechar_rodada({1: "1-0", 2: "1-0"})
        with self.assertRaises(AppError) as erro:
            self.service.generate_next_round(self.tournament_id)
        self.assertIn("vencedor", str(erro.exception))

    def test_bye_do_mata_mata_e_bye_de_verdade(self) -> None:
        self._mata_mata(3)
        rodada = self.service.generate_next_round(self.tournament_id)
        bye = next(
            pairing
            for pairing in self.db.get_pairings_for_round(int(rodada["id"]))
            if pairing["is_bye"]
        )
        self.assertEqual("BYE", bye["result"])


class ScheveningenNoBancoTest(CoreServiceTestCase):
    def _scheveningen(self, jogadores: int = 6) -> list[int]:
        self._set_individual_pairing_method("scheveningen")
        return self._create_players(jogadores)

    def _jogar_rodada(self) -> int:
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        return int(rodada["id"])

    def _confrontos(self, round_id: int) -> set[frozenset[int]]:
        return {
            frozenset((int(pairing["white_player_id"]), int(pairing["black_player_id"])))
            for pairing in self.db.get_pairings_for_round(round_id)
        }

    def test_escala_e_guardada_no_jogador(self) -> None:
        ids = self._scheveningen()
        self._jogar_rodada()
        escala = {
            int(player["id"]): (player["scheveningen_group"], int(player["scheveningen_number"]))
            for player in self.db.list_players(self.tournament_id, active_only=False)
        }
        self.assertEqual(("A", 1), escala[ids[0]])
        self.assertEqual(("B", 1), escala[ids[3]])

    def test_previa_nao_monta_a_escala(self) -> None:
        ids = self._scheveningen()
        self.service.preview_next_round(self.tournament_id)
        jogador = self.db.get_player(ids[0])
        self.assertEqual(0, int(jogador["scheveningen_number"]))

    def test_desistencia_nao_muda_os_confrontos_que_faltam(self) -> None:
        """Antes, a escala andava uma casa e ainda travava a geração."""
        ids = self._scheveningen()
        self._jogar_rodada()
        esperado = self._confrontos_da_rodada(2)
        self.service.set_player_participation(
            self.tournament_id, ids[1], "withdrawn", reason="lesao"
        )
        rodada = self.service.generate_next_round(self.tournament_id)
        self.assertEqual(esperado, self._confrontos(int(rodada["id"])))

    def _confrontos_da_rodada(self, numero: int) -> set[frozenset[int]]:
        """O que a rodada `numero` traria, lido da escala antes da desistência."""
        from src.services.pairing.scheveningen import scheveningen_pairings_from_scale

        escala = {
            int(player["id"]): (
                str(player["scheveningen_group"]),
                int(player["scheveningen_number"]),
            )
            for player in self.db.list_players(self.tournament_id, active_only=False)
            if int(player["scheveningen_number"] or 0) > 0
        }
        return {
            frozenset((mesa["white_player_id"], mesa["black_player_id"]))
            for mesa in scheveningen_pairings_from_scale(escala, numero)
        }

    def test_desistente_continua_com_mesa_e_o_arbitro_e_avisado(self) -> None:
        ids = self._scheveningen()
        self._jogar_rodada()
        self.service.set_player_participation(
            self.tournament_id, ids[1], "withdrawn", reason="lesao"
        )
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertTrue(any("W.O." in aviso for aviso in previa["warnings"]))


if __name__ == "__main__":
    unittest.main()
