"""Estado puro da tela de Rodadas (``pairing_results/state.py`` — B-6).

Nenhum teste aqui abre janela. É o ponto da migração: as decisões que mais
doem errar — em que estado está um resultado, se o árbitro pode mexer nele,
quantas rodadas o torneio deveria ter — saíram de dentro de métodos de 1.850
linhas, onde a única forma de exercitá-las era clicando.
"""
from __future__ import annotations

import unittest

from src.services.constants import RESULTS
from src.ui.screens.pairing_results.state import (
    RESULT_COLUMN_INDEX,
    RESULT_SHORTCUTS,
    STATE_APPROVED,
    STATE_CORRECTED,
    STATE_EMPTY,
    STATE_LOCKED,
    STATE_RECORDED,
    STATE_REJECTED,
    STATE_SUBMITTED,
    allowed_results,
    first_pending_index,
    format_pairing_preview,
    individual_result_state,
    initial_call_searchable,
    initial_call_summary,
    is_bye_row,
    matches_initial_query,
    needs_round_count_warning,
    next_presence_status,
    projector_capacity,
    projector_column_items,
    projector_page_items,
    projector_total_pages,
    recommended_rounds_for_players,
    result_state_tag,
    team_board_result_state,
)


class EstadoDoResultadoTest(unittest.TestCase):
    """A precedência **é** a regra, e é ela que os testes cobram."""

    def test_mesa_vazia_esta_vazia(self) -> None:
        self.assertEqual(STATE_EMPTY, individual_result_state({"id": 1, "result": ""}, {}, set()))

    def test_mesa_lancada_esta_registrada(self) -> None:
        self.assertEqual(
            STATE_RECORDED, individual_result_state({"id": 1, "result": "1-0"}, {}, set())
        )

    def test_rodada_fechada_bloqueia_a_mesa_vazia(self) -> None:
        estado = individual_result_state(
            {"id": 1, "result": "", "round_status": "closed"}, {}, set()
        )
        self.assertEqual(STATE_LOCKED, estado)

    def test_correcao_de_auditoria_vence_tudo(self) -> None:
        """Uma mesa corrigida continua corrigida mesmo tendo vindo do QR.

        Se o QR vencesse, a correção do árbitro sumiria da tela — e é
        justamente ela que precisa ficar visível numa conferência.
        """
        estado = individual_result_state(
            {"id": 7, "result": "1-0", "round_status": "closed"},
            {7: {"status": "approved"}},
            {7},
        )
        self.assertEqual(STATE_CORRECTED, estado)

    def test_estado_do_qr_vence_rodada_fechada(self) -> None:
        for status, esperado in (
            ("submitted", STATE_SUBMITTED),
            ("approved", STATE_APPROVED),
            ("rejected", STATE_REJECTED),
        ):
            with self.subTest(status=status):
                estado = individual_result_state(
                    {"id": 3, "result": "", "round_status": "closed"},
                    {3: {"status": status}},
                    set(),
                )
                self.assertEqual(esperado, estado)

    def test_status_de_qr_desconhecido_nao_mascara_o_resto(self) -> None:
        estado = individual_result_state(
            {"id": 3, "result": "1-0"}, {3: {"status": "sei_la"}}, set()
        )
        self.assertEqual(STATE_RECORDED, estado)

    def test_tabuleiro_de_equipes_nao_passa_por_qr(self) -> None:
        # O envio por celular e individual; um tabuleiro de equipes so e
        # lancado pelo arbitro, e por isso o estado dele tem menos casos.
        self.assertEqual(STATE_EMPTY, team_board_result_state({"id": 1, "result": ""}, set()))
        self.assertEqual(
            STATE_LOCKED, team_board_result_state({"id": 1, "result": ""}, set(), "closed")
        )
        self.assertEqual(STATE_CORRECTED, team_board_result_state({"id": 1, "result": "1-0"}, {1}))

    def test_tag_do_treeview_normaliza_o_espaco(self) -> None:
        self.assertEqual("result_state_submetido_qr", result_state_tag(STATE_SUBMITTED))
        self.assertEqual("result_state_vazio", result_state_tag(STATE_EMPTY))


class ResultadosPermitidosTest(unittest.TestCase):
    def test_mesa_comum_aceita_so_os_resultados_padrao(self) -> None:
        self.assertEqual(set(RESULTS), allowed_results({"row_type": "individual_pairing"}))

    def test_bye_aceita_ausencia_meio_ponto_e_zero(self) -> None:
        permitidos = allowed_results({"row_type": "individual_pairing", "is_bye": True})
        for extra in ("BYE", "F", "H", "Z"):
            self.assertIn(extra, permitidos)

    def test_sem_mesa_selecionada_ainda_ha_um_conjunto(self) -> None:
        self.assertEqual(set(RESULTS), allowed_results(None))


class PrimeiraMesaPendenteTest(unittest.TestCase):
    def test_acha_a_primeira_sem_resultado(self) -> None:
        linhas = [(1, "a", "b", "1-0"), (2, "c", "d", ""), (3, "e", "f", "")]
        self.assertEqual(1, first_pending_index(linhas, 3))

    def test_todas_lancadas_volta_para_a_primeira(self) -> None:
        linhas = [(1, "a", "b", "1-0"), (2, "c", "d", "0-1")]
        self.assertEqual(0, first_pending_index(linhas, 3))

    def test_linha_curta_conta_como_pendente(self) -> None:
        self.assertEqual(0, first_pending_index([(1, "a")], 3))

    def test_a_coluna_do_resultado_muda_no_modo_equipes(self) -> None:
        """Era a dobra que fazia a busca olhar a coluna errada por equipes."""
        self.assertEqual(3, RESULT_COLUMN_INDEX["individual"])
        self.assertEqual(6, RESULT_COLUMN_INDEX["team"])


class RodadasRecomendadasTest(unittest.TestCase):
    def test_potencia_de_dois_exata(self) -> None:
        self.assertEqual(3, recommended_rounds_for_players(8))

    def test_um_jogador_acima_pede_uma_rodada_a_mais(self) -> None:
        self.assertEqual(4, recommended_rounds_for_players(9))

    def test_torneio_minusculo_pede_uma_rodada(self) -> None:
        self.assertEqual(1, recommended_rounds_for_players(1))
        self.assertEqual(1, recommended_rounds_for_players(0))

    def test_avisa_quando_faltam_rodadas(self) -> None:
        self.assertTrue(
            needs_round_count_warning(
                players_count=16, configured_rounds=3, has_rounds=False, team_mode=False
            )
        )

    def test_nao_avisa_depois_da_primeira_rodada(self) -> None:
        # Mudar o total de rodadas com o torneio em andamento e outra conversa.
        self.assertFalse(
            needs_round_count_warning(
                players_count=16, configured_rounds=3, has_rounds=True, team_mode=False
            )
        )

    def test_nao_avisa_por_equipes_nem_com_dois_jogadores(self) -> None:
        self.assertFalse(
            needs_round_count_warning(
                players_count=16, configured_rounds=1, has_rounds=False, team_mode=True
            )
        )
        self.assertFalse(
            needs_round_count_warning(
                players_count=2, configured_rounds=1, has_rounds=False, team_mode=False
            )
        )


class PreviaDaRodadaTest(unittest.TestCase):
    def test_corta_e_diz_quantas_sobraram(self) -> None:
        preview = {
            "round_number": 2,
            "pairings": [
                {"board_number": n, "white_name": f"B{n}", "black_name": f"P{n}"}
                for n in range(1, 16)
            ],
        }
        texto = format_pairing_preview(preview, limit=12)
        self.assertIn("Mesa 1: B1 x P1", texto)
        self.assertIn("... mais 3 item(ns)", texto)
        self.assertIn("nao gravou rodada", texto)

    def test_alertas_entram_entre_colchetes(self) -> None:
        preview = {
            "round_number": 1,
            "pairings": [
                {
                    "board_number": 1,
                    "white_name": "A",
                    "black_name": "B",
                    "alerts": ["cor repetida", "mesmo clube"],
                }
            ],
        }
        self.assertIn("[cor repetida; mesmo clube]", format_pairing_preview(preview))

    def test_previa_por_equipes_usa_match(self) -> None:
        preview = {
            "round_number": 1,
            "competition_type": "team",
            "matches": [
                {"match_number": 1, "white_team_name": "A", "black_team_name": "B"}
            ],
        }
        self.assertIn("Match 1: A x B", format_pairing_preview(preview))

    def test_rodada_sem_mesa_diz_isso(self) -> None:
        self.assertIn(
            "Nenhuma mesa prevista.", format_pairing_preview({"round_number": 1, "pairings": []})
        )

    def test_aviso_da_rodada_aparece_antes_das_mesas(self) -> None:
        """PAR-02: o corte por `limit` nao pode engolir o aviso do pareamento."""
        preview = {
            "round_number": 1,
            "warnings": ["Aceleracao caiu no motor proprio."],
            "pairings": [
                {"board_number": n, "white_name": f"B{n}", "black_name": f"P{n}"}
                for n in range(1, 16)
            ],
        }
        texto = format_pairing_preview(preview, limit=2)
        self.assertIn("Aviso: Aceleracao caiu no motor proprio.", texto)
        self.assertLess(texto.index("Aviso:"), texto.index("Mesa 1"))


class ProjetorTest(unittest.TestCase):
    """A paginação decidia se a última mesa aparecia na parede."""

    def test_capacidade_e_colunas_por_linhas(self) -> None:
        self.assertEqual(30, projector_capacity(2, 15))
        self.assertEqual(1, projector_capacity(0, 0), "capacidade nunca e zero")

    def test_uma_mesa_a_mais_abre_a_segunda_pagina(self) -> None:
        self.assertEqual(1, projector_total_pages(30, 30))
        self.assertEqual(2, projector_total_pages(31, 30))

    def test_sem_mesa_ainda_ha_uma_pagina(self) -> None:
        self.assertEqual(1, projector_total_pages(0, 30))

    def test_a_ultima_pagina_traz_o_resto(self) -> None:
        itens = list(range(31))
        self.assertEqual(30, len(projector_page_items(itens, 0, 30)))
        self.assertEqual([30], projector_page_items(itens, 1, 30))

    def test_pagina_alem_do_fim_volta_ao_comeco(self) -> None:
        itens = list(range(10))
        self.assertEqual(projector_page_items(itens, 0, 5), projector_page_items(itens, 2, 5))

    def test_coluna_recebe_a_propria_fatia(self) -> None:
        pagina = list(range(30))
        self.assertEqual(list(range(15)), projector_column_items(pagina, 0, 15))
        self.assertEqual(list(range(15, 30)), projector_column_items(pagina, 1, 15))

    def test_linha_de_bye_e_reconhecida_dos_dois_lados(self) -> None:
        self.assertTrue(is_bye_row({"white": "Silva", "black": "BYE"}))
        self.assertTrue(is_bye_row({"white": "BYE", "black": "Equipe A"}))
        self.assertFalse(is_bye_row({"white": "Silva", "black": "Costa"}))


class ChamadaInicialTest(unittest.TestCase):
    def test_resumo_conta_presentes_e_ausentes(self) -> None:
        jogadores = [
            {"player_status": "active"},
            {"player_status": "active"},
            {"player_status": "absent"},
        ]
        self.assertEqual((2, 1, 3), initial_call_summary(jogadores))

    def test_busca_varre_nome_clube_categoria_e_rating(self) -> None:
        jogador = {"club": "Clube A", "category": "Sub-18", "rating": 1750}
        varrido = initial_call_searchable(jogador, "Ana Silva")
        for termo in ("ana silva", "clube a", "sub-18", "1750"):
            self.assertIn(termo, varrido)

    def test_busca_vazia_deixa_tudo_passar(self) -> None:
        self.assertTrue(matches_initial_query("ana silva", "   "))

    def test_busca_ignora_caixa(self) -> None:
        self.assertTrue(matches_initial_query("ana silva", "ANA"))
        self.assertFalse(matches_initial_query("ana silva", "bruno"))

    def test_grupo_misto_vira_todos_presentes(self) -> None:
        """Alternar um grupo misto não pode deixar metade em cada estado."""
        misto = [{"player_status": "active"}, {"player_status": "absent"}]
        self.assertEqual("active", next_presence_status(misto))

    def test_grupo_todo_presente_vira_ausente(self) -> None:
        todos = [{"player_status": "active"}, {"player_status": "active"}]
        self.assertEqual("absent", next_presence_status(todos))


class AtalhosTest(unittest.TestCase):
    def test_teclado_numerico_tem_a_propria_entrada(self) -> None:
        # `<KP_1>` nao e `1`: um `if` encadeado esconderia essa dobra.
        self.assertEqual(RESULT_SHORTCUTS["1"], RESULT_SHORTCUTS["<KP_1>"])
        self.assertEqual(RESULT_SHORTCUTS["-"], RESULT_SHORTCUTS["<KP_Subtract>"])

    def test_apagar_lanca_resultado_vazio(self) -> None:
        self.assertEqual("", RESULT_SHORTCUTS["<BackSpace>"])
        self.assertEqual("", RESULT_SHORTCUTS["<Delete>"])

    def test_todo_atalho_produz_resultado_valido(self) -> None:
        for tecla, resultado in RESULT_SHORTCUTS.items():
            with self.subTest(tecla=tecla):
                self.assertIn(resultado, set(RESULTS))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
