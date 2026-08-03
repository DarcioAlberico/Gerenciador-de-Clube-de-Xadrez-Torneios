"""PAR-01 — rodízio com calendário persistido, returno e bye de verdade.

O todos contra todos recalculava o círculo a cada rodada a partir da lista de
jogadores ATIVOS ordenada por rating. Desativar um jogador — ou corrigir um
rating — no meio do evento embaralhava os confrontos futuros de **todos os
outros**, sem que nada aparecesse na tela. Não havia returno (o formato padrão de
fechado e de torneio de norma) e o bye do rodízio era gravado como `1-0`.

Agora o calendário é a tabela de Berger (FIDE Handbook C.05, Anexo 1) sobre
números sorteados uma única vez e guardados. A primeira classe deste arquivo
confere a tabela contra o Handbook — é ela que protege o acoplamento à
implementação de referência (`gacrux/berger.py`).
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.pairing.round_robin import (
    annulment_candidates,
    assign_numbers,
    berger_round,
    calendar_rounds,
    missing_from_calendar,
    round_robin_pairings_from_numbers,
    table_size,
)
from tests.support.core_service_base import CoreServiceTestCase

# FIDE Handbook C.05, Anexo 1 — tabelas de Berger, copiadas do Handbook.
BERGER_6 = [
    [(1, 6), (2, 5), (3, 4)],
    [(6, 4), (5, 3), (1, 2)],
    [(2, 6), (3, 1), (4, 5)],
    [(6, 5), (1, 4), (2, 3)],
    [(3, 6), (4, 2), (5, 1)],
]
BERGER_8 = [
    [(1, 8), (2, 7), (3, 6), (4, 5)],
    [(8, 5), (6, 4), (7, 3), (1, 2)],
    [(2, 8), (3, 1), (4, 7), (5, 6)],
    [(8, 6), (7, 5), (1, 4), (2, 3)],
    [(3, 8), (4, 2), (5, 1), (6, 7)],
    [(8, 7), (1, 6), (2, 5), (3, 4)],
    [(4, 8), (5, 3), (6, 2), (7, 1)],
]


class TabelaDeBergerTest(unittest.TestCase):
    """O calendário confere com o Handbook — inclusive as cores."""

    def test_fixture_de_6_jogadores(self) -> None:
        for numero, esperado in enumerate(BERGER_6, start=1):
            self.assertEqual(esperado, berger_round(6, numero), f"rodada {numero}")

    def test_fixture_de_8_jogadores(self) -> None:
        for numero, esperado in enumerate(BERGER_8, start=1):
            self.assertEqual(esperado, berger_round(8, numero), f"rodada {numero}")

    def test_campo_impar_usa_o_numero_fantasma(self) -> None:
        """5 jogadores = tabela de 6; quem cai com o 6 folga naquela rodada."""
        self.assertEqual(6, table_size(5))
        folgas = []
        for numero in range(1, 6):
            pares = berger_round(5, numero)
            fantasma = [par for par in pares if 6 in par]
            self.assertEqual(1, len(fantasma))
            folgas.append(next(n for n in fantasma[0] if n != 6))
        # Cada jogador folga exatamente uma vez no turno.
        self.assertEqual([1, 2, 3, 4, 5], sorted(folgas))

    def test_calendario_tem_n_menos_1_rodadas_e_o_dobro_com_returno(self) -> None:
        self.assertEqual(5, calendar_rounds(6))
        self.assertEqual(10, calendar_rounds(6, double=True))
        self.assertEqual(5, calendar_rounds(5))  # impar sobe para a tabela de 6
        self.assertEqual(14, calendar_rounds(7, double=True))

    def test_returno_repete_o_turno_com_as_cores_trocadas(self) -> None:
        for numero, esperado in enumerate(BERGER_6, start=1):
            invertido = [(preta, branca) for branca, preta in esperado]
            self.assertEqual(invertido, berger_round(6, numero + 5, double=True))

    def test_rodada_fora_do_calendario_e_recusada(self) -> None:
        with self.assertRaises(AppError) as erro:
            berger_round(6, 6)
        self.assertIn("5 rodada(s)", str(erro.exception))
        with self.assertRaises(AppError):
            berger_round(6, 11, double=True)


class MesasDoCalendarioTest(unittest.TestCase):
    def test_bye_sai_como_bye_e_nao_como_vitoria(self) -> None:
        """Era gravado `1-0`: pontuava certo por acaso (bye_points padrão 1,0) e
        aparecia como vitória em tudo que lê o resultado."""
        numeros = assign_numbers([10, 20, 30])
        mesas = round_robin_pairings_from_numbers(numeros, 1)
        bye = next(mesa for mesa in mesas if mesa["is_bye"])
        self.assertEqual("BYE", bye["result"])
        self.assertIsNone(bye["black_player_id"])
        self.assertEqual(2, len(mesas))

    def test_mesas_seguem_os_numeros_e_nao_a_ordem_do_dicionario(self) -> None:
        numeros = {70: 3, 10: 1, 40: 2, 20: 4}
        mesas = round_robin_pairings_from_numbers(numeros, 1)
        self.assertEqual(
            [(10, 20), (40, 70)],
            [(mesa["white_player_id"], mesa["black_player_id"]) for mesa in mesas],
        )

    def test_quem_entrou_depois_do_sorteio_fica_de_fora(self) -> None:
        numeros = assign_numbers([10, 20])
        self.assertEqual([30], missing_from_calendar(numeros, [10, 20, 30]))


class RegraDosCinquentaPorCentoTest(unittest.TestCase):
    """FIDE C.05: quem desiste antes da metade tem os resultados anulados."""

    def test_abaixo_da_metade_entra_na_lista(self) -> None:
        self.assertEqual([7], annulment_candidates({7: 2}, 7, [7]))

    def test_na_metade_ou_acima_nao_entra(self) -> None:
        self.assertEqual([], annulment_candidates({7: 4}, 7, [7]))
        self.assertEqual([], annulment_candidates({7: 7}, 7, [7]))

    def test_sem_calendario_nao_ha_o_que_medir(self) -> None:
        self.assertEqual([], annulment_candidates({7: 0}, 0, [7]))


class CalendarioPersistidoTest(CoreServiceTestCase):
    """O que só o banco prova: o calendário não se move mais."""

    def _rodizio(self, jogadores: int = 6, rodadas: int = 0, **settings) -> list[int]:
        self._set_individual_pairing_method("round_robin")
        if settings:
            self.db.save_tournament_settings(self.tournament_id, settings)
        if rodadas:
            with self.db.connect() as connection:
                connection.execute(
                    "UPDATE tournaments SET rounds_count = ? WHERE id = ?",
                    (int(rodadas), self.tournament_id),
                )
        return self._create_players(jogadores)

    def _pares_por_numero(self, round_id: int) -> list[tuple[int, int]]:
        numeros = self.service.round_robin_numbers(self.tournament_id)
        pares = []
        for pairing in self.db.get_pairings_for_round(round_id):
            branca = numeros[int(pairing["white_player_id"])]
            preta = (
                numeros[int(pairing["black_player_id"])]
                if pairing["black_player_id"]
                else 0
            )
            pares.append((branca, preta))
        return pares

    def _jogar_rodada(self) -> int:
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        return int(rodada["id"])

    def test_numeros_sao_sorteados_uma_vez_e_ficam(self) -> None:
        ids = self._rodizio()
        self.assertEqual({}, self.service.round_robin_numbers(self.tournament_id))
        self._jogar_rodada()
        numeros = self.service.round_robin_numbers(self.tournament_id)
        # Ordem inicial = rating decrescente, que é como `_create_players` cria.
        self.assertEqual({pid: pos for pos, pid in enumerate(ids, start=1)}, numeros)

    def test_previa_nao_sorteia_o_calendario(self) -> None:
        """A prévia não grava rodada — e também não pode gravar o sorteio."""
        self._rodizio()
        self.service.preview_next_round(self.tournament_id)
        self.assertEqual({}, self.service.round_robin_numbers(self.tournament_id))

    def test_desativar_jogador_nao_muda_os_confrontos_dos_outros(self) -> None:
        ids = self._rodizio()
        self._jogar_rodada()
        self.service.set_player_participation(
            self.tournament_id, ids[2], "withdrawn", reason="viagem"
        )
        rodada = self.service.generate_next_round(self.tournament_id)
        self.assertEqual(BERGER_6[1], self._pares_por_numero(int(rodada["id"])))

    def test_mudar_rating_no_meio_nao_mexe_no_calendario(self) -> None:
        ids = self._rodizio()
        self._jogar_rodada()
        numeros = dict(self.service.round_robin_numbers(self.tournament_id))
        with self.db.connect() as connection:
            connection.execute("UPDATE players SET rating = 9999 WHERE id = ?", (ids[-1],))
        self.service.generate_next_round(self.tournament_id)
        self.assertEqual(numeros, self.service.round_robin_numbers(self.tournament_id))

    def test_calendario_inteiro_bate_com_a_tabela_da_fide(self) -> None:
        self._rodizio()
        for esperado in BERGER_6:
            round_id = self._jogar_rodada()
            self.assertEqual(esperado, self._pares_por_numero(round_id))

    def test_desistente_continua_com_mesa_e_o_arbitro_e_avisado(self) -> None:
        ids = self._rodizio()
        self._jogar_rodada()
        self.service.set_player_participation(
            self.tournament_id, ids[2], "withdrawn", reason="viagem"
        )
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertTrue(any("W.O." in aviso for aviso in previa["warnings"]))
        # Menos da metade das partidas jogadas: a regra FIDE de anulacao aparece.
        self.assertTrue(any("C.05" in aviso for aviso in previa["warnings"]))

    def test_inscrito_depois_do_sorteio_fica_fora_e_e_avisado(self) -> None:
        self._rodizio()
        self._jogar_rodada()
        self.db.create_player(
            self.tournament_id, name="Atrasado", rating=2500, club="Clube", category="Absoluto"
        )
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertTrue(any("Fora do calendario" in aviso for aviso in previa["warnings"]))
        mesas = previa["pairings"]
        self.assertNotIn("Atrasado", [mesa["white_name"] for mesa in mesas])

    def test_returno_inverte_as_cores(self) -> None:
        self._rodizio(4, rodadas=6, round_robin_double=1)
        turno = []
        for _ in range(3):
            turno.append(self._pares_por_numero(self._jogar_rodada()))
        returno = []
        for _ in range(3):
            returno.append(self._pares_por_numero(self._jogar_rodada()))
        for ida, volta in zip(turno, returno):
            self.assertEqual([(preta, branca) for branca, preta in ida], volta)

    def test_rodadas_configuradas_diferentes_do_calendario_avisam(self) -> None:
        # 4 jogadores com returno = 6 rodadas; o torneio tem 5 configuradas.
        self._rodizio(4, round_robin_double=1)
        previa = self.service.preview_next_round(self.tournament_id)
        self.assertTrue(any("6 rodada(s)" in aviso for aviso in previa["warnings"]))

    def test_bye_do_rodizio_pontua_pelo_bye_points_do_torneio(self) -> None:
        self._rodizio(5)
        rodada = self.service.generate_next_round(self.tournament_id)
        bye = next(
            pairing
            for pairing in self.db.get_pairings_for_round(int(rodada["id"]))
            if pairing["is_bye"]
        )
        self.assertEqual("BYE", bye["result"])


if __name__ == "__main__":
    unittest.main()
