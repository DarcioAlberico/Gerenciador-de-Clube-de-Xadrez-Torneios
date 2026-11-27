"""RGS-20 e RGS-34 — camada de serviço da correção pela mesa e da exclusão.

RGS-20: um motivo só serve ao desbloqueio e à correção (validado pela regra
mais estrita), tudo numa gravação; a cascata leva o mesmo motivo; reverter uma
correção reaplica o resultado anterior pelo mesmo fluxo.

RGS-34: excluir rodada gerada com resultados exige motivo, diz quantos somem
e guarda os resultados apagados no ``before`` do evento.
"""
from __future__ import annotations

import json
import unittest

from src.services.constants import AppError
from src.services.pairing.corrections import (
    MIN_REASON_LENGTH,
    correction_reason_error,
    shared_reason_error,
    unlock_reason_error,
)
from tests.support.core_service_base import CoreServiceTestCase

MOTIVO = "Súmula da mesa 1 diverge do lançado"


class MotivoUnicoTest(unittest.TestCase):
    """O mesmo texto vale para desbloquear e corrigir: as duas regras andam juntas."""

    AMOSTRAS = ("", "   ", "x", "ok", "erro", "erro!", "12345", " a b c ", MOTIVO, "a" * 300)

    def test_as_duas_regras_continuam_iguais(self) -> None:
        """Se uma ficar mais estrita, o motivo único passa numa e trava na outra."""
        for amostra in self.AMOSTRAS:
            with self.subTest(amostra=amostra):
                self.assertEqual(
                    bool(correction_reason_error(amostra)),
                    bool(unlock_reason_error(amostra)),
                )

    def test_motivo_unico_usa_a_mais_estrita(self) -> None:
        for amostra in self.AMOSTRAS:
            with self.subTest(amostra=amostra):
                estrita = bool(correction_reason_error(amostra)) or bool(unlock_reason_error(amostra))
                self.assertEqual(estrita, bool(shared_reason_error(amostra)))
        self.assertIn(str(MIN_REASON_LENGTH), shared_reason_error("ok"))


class _TorneioComRodadas(CoreServiceTestCase):
    """6 jogadores: R1 e R2 fechadas, R3 gerada sem resultados."""

    def setUp(self) -> None:
        super().setUp()
        self._create_players(6)
        self.round_ids: list[int] = []
        for _ in range(2):
            rodada = self.service.generate_next_round(self.tournament_id)
            self.round_ids.append(int(rodada["id"]))
            for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
                self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(rodada["id"]))
        self.round_ids.append(int(self.service.generate_next_round(self.tournament_id)["id"]))
        self.mesa = self.db.get_pairings_for_round(self.round_ids[1])[0]

    def _eventos(self, acao: str) -> list[dict]:
        return self.db.list_audit_events(self.tournament_id, action=acao, limit=100)


class CorrecaoPelaMesaTest(_TorneioComRodadas):
    def test_um_motivo_gera_desbloqueio_correcao_e_cascata_com_o_mesmo_texto(self) -> None:
        saida = self.service.correct_result(
            self.tournament_id, int(self.mesa["id"]), "0-1", MOTIVO
        )

        self.assertEqual("0-1", self.db.get_pairing(int(self.mesa["id"]))["result"])
        desbloqueios = self._eventos("round_correction_unlocked")
        correcoes = self._eventos("result_corrected")
        cascatas = self._eventos("result_correction_cascade")
        self.assertEqual((1, 1, 1), (len(desbloqueios), len(correcoes), len(cascatas)))
        self.assertEqual(
            {MOTIVO},
            {desbloqueios[0]["reason"], correcoes[0]["reason"], cascatas[0]["reason"]},
        )
        # O recado da cascata (o que fazer) continua no evento, fora do motivo.
        self.assertIn("reparear", json.loads(cascatas[0]["after_json"])["message"])
        self.assertTrue(saida["unlocked"])
        self.assertEqual(
            1, len(self.db.list_correction_unlocks(self.tournament_id, self.round_ids[1]))
        )

    def test_com_desbloqueio_vigente_nao_abre_outro(self) -> None:
        self.service.unlock_round_for_correction(
            self.tournament_id, self.round_ids[1], "Reclamação do jogador"
        )
        saida = self.service.correct_result(
            self.tournament_id, int(self.mesa["id"]), "0-1", MOTIVO
        )
        self.assertFalse(saida["unlocked"])
        self.assertEqual(1, len(self._eventos("round_correction_unlocked")))

    def test_motivo_curto_nao_grava_nada(self) -> None:
        with self.assertRaises(AppError) as erro:
            self.service.correct_result(self.tournament_id, int(self.mesa["id"]), "0-1", "ok")
        self.assertIn(str(MIN_REASON_LENGTH), str(erro.exception))
        self.assertEqual([], self._eventos("round_correction_unlocked"))
        self.assertEqual([], self.db.list_correction_unlocks(self.tournament_id, self.round_ids[1]))
        self.assertEqual("1-0", self.db.get_pairing(int(self.mesa["id"]))["result"])

    def test_resultado_invalido_nao_deixa_desbloqueio_para_tras(self) -> None:
        """Desbloqueio e correção entram juntos: um sem o outro não fica."""
        with self.assertRaises(AppError):
            self.service.correct_result(self.tournament_id, int(self.mesa["id"]), "9-9", MOTIVO)
        self.assertEqual([], self._eventos("round_correction_unlocked"))
        self.assertEqual([], self.db.list_correction_unlocks(self.tournament_id, self.round_ids[1]))

    def test_mesmo_resultado_e_recusado(self) -> None:
        with self.assertRaises(AppError):
            self.service.correct_result(self.tournament_id, int(self.mesa["id"]), "1-0", MOTIVO)
        self.assertEqual([], self._eventos("result_corrected"))

    def test_rodada_aberta_lanca_sem_desbloqueio(self) -> None:
        aberta = self.db.get_pairings_for_round(self.round_ids[2])[0]
        saida = self.service.correct_result(self.tournament_id, int(aberta["id"]), "1-0", "")
        self.assertFalse(saida["unlocked"])
        self.assertEqual("1-0", self.db.get_pairing(int(aberta["id"]))["result"])
        self.assertEqual([], self._eventos("round_correction_unlocked"))


class CascataDaCorrecaoTest(_TorneioComRodadas):
    def test_rodada_seguinte_aberta_sem_resultados_pode_ser_repareada(self) -> None:
        cascata = self.service.correction_cascade(self.tournament_id, self.round_ids[1])
        self.assertEqual(3, cascata["number"])
        self.assertEqual(self.round_ids[2], cascata["round_id"])
        self.assertEqual(0, cascata["results"])
        self.assertTrue(cascata["repairable"])

    def test_com_resultados_lancados_conta_quantos_seriam_apagados(self) -> None:
        for mesa in self.db.get_pairings_for_round(self.round_ids[2])[:2]:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        cascata = self.service.correction_cascade(self.tournament_id, self.round_ids[1])
        self.assertEqual(2, cascata["results"])
        self.assertTrue(cascata["repairable"])

    def test_ultima_rodada_nao_tem_cascata(self) -> None:
        self.assertIsNone(self.service.correction_cascade(self.tournament_id, self.round_ids[2]))

    def test_rodada_seguinte_fechada_nao_e_repareavel(self) -> None:
        cascata = self.service.correction_cascade(self.tournament_id, self.round_ids[0])
        self.assertEqual(2, cascata["number"])
        self.assertFalse(cascata["repairable"])


class ReverterCorrecaoTest(_TorneioComRodadas):
    def test_reverter_devolve_o_resultado_original_com_uma_correcao_nova(self) -> None:
        self.service.correct_result(self.tournament_id, int(self.mesa["id"]), "0-1", MOTIVO)
        original = self._eventos("result_corrected")[0]

        historico = self.service.pairing_correction_history(self.tournament_id, int(self.mesa["id"]))
        self.assertEqual(1, len(historico))
        self.assertEqual(("1-0", "0-1"), (historico[0]["before"], historico[0]["after"]))

        self.service.revert_correction(
            self.tournament_id, int(original["id"]), "Árbitro conferiu a súmula de novo"
        )

        self.assertEqual("1-0", self.db.get_pairing(int(self.mesa["id"]))["result"])
        correcoes = self._eventos("result_corrected")
        self.assertEqual(2, len(correcoes))
        nova = correcoes[0]
        self.assertEqual("Árbitro conferiu a súmula de novo", nova["reason"])
        self.assertEqual(int(original["id"]), json.loads(nova["after_json"])["reverts_event_id"])

    def test_so_a_ultima_correcao_pode_ser_revertida(self) -> None:
        self.service.correct_result(self.tournament_id, int(self.mesa["id"]), "0-1", MOTIVO)
        primeira = self._eventos("result_corrected")[0]
        self.service.correct_result(
            self.tournament_id, int(self.mesa["id"]), "1/2-1/2", "Decisão de apelação"
        )
        with self.assertRaises(AppError):
            self.service.revert_correction(
                self.tournament_id, int(primeira["id"]), "Reverter a primeira"
            )


class ExcluirRodadaComResultadosTest(_TorneioComRodadas):
    """RGS-34 — aceite: 3 resultados sem motivo → recusa; com motivo → evento com os 3."""

    def setUp(self) -> None:
        super().setUp()
        self.aberta = self.round_ids[2]
        self.mesas = self.db.get_pairings_for_round(self.aberta)
        self.assertEqual(3, len(self.mesas))
        for mesa, resultado in zip(self.mesas, ("1-0", "0-1", "1/2-1/2")):
            self.service.update_result(self.tournament_id, int(mesa["id"]), resultado)

    def test_previa_diz_quantos_resultados_seriam_apagados(self) -> None:
        previa = self.service.round_deletion_preview(self.aberta)
        self.assertEqual(3, previa["results"])
        self.assertIn("3 resultados serão apagados", previa["message"])

    def test_sem_motivo_e_recusado_e_nada_muda(self) -> None:
        with self.assertRaises(AppError) as erro:
            self.service.delete_generated_round(self.aberta)
        self.assertIn("3 resultados serão apagados", str(erro.exception))
        self.assertIsNotNone(self.db.get_round(self.aberta))
        self.assertEqual([], self._eventos("round_deleted"))

    def test_motivo_curto_tambem_e_recusado(self) -> None:
        with self.assertRaises(AppError):
            self.service.delete_generated_round(self.aberta, reason="ok")
        self.assertIsNotNone(self.db.get_round(self.aberta))

    def test_com_motivo_o_evento_guarda_os_resultados_apagados(self) -> None:
        motivo = "Rodada pareada antes da correção da R2"
        self.service.delete_generated_round(self.aberta, reason=motivo)

        self.assertIsNone(self.db.get_round(self.aberta))
        eventos = self._eventos("round_deleted")
        self.assertEqual(1, len(eventos))
        self.assertEqual(motivo, eventos[0]["reason"])
        antes = json.loads(eventos[0]["before_json"])
        apagados = antes["results"]
        self.assertEqual(3, len(apagados))
        self.assertEqual(
            sorted(("1-0", "0-1", "1/2-1/2")), sorted(item["result"] for item in apagados)
        )
        self.assertEqual(
            sorted(int(m["id"]) for m in self.mesas), sorted(item["pairing_id"] for item in apagados)
        )

    def test_rodada_sem_resultados_continua_sem_pedir_motivo(self) -> None:
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "")
        self.service.delete_generated_round(self.aberta)
        self.assertIsNone(self.db.get_round(self.aberta))
        self.assertEqual(1, len(self._eventos("round_deleted")))


class CorrecaoDeTabuleiroDeEquipesTest(CoreServiceTestCase):
    """O mesmo fluxo vale para o tabuleiro de equipes (desbloqueio + correção + reversão)."""

    def setUp(self) -> None:
        super().setUp()
        self.tid, _equipes = self._create_team_tournament(teams_count=2, boards_count=2)
        rodada = self.service.generate_next_round(self.tid)
        self.round_id = int(rodada["id"])
        for match in self.db.list_team_matches_for_round(self.round_id):
            if match["is_bye"]:
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(self.tid, int(board["id"]), "1-0")
        self.service.close_round(self.tid, self.round_id)
        self.board = self.db.list_team_boards(
            int(self.db.list_team_matches_for_round(self.round_id)[0]["id"])
        )[0]

    def test_corrigir_e_reverter_tabuleiro(self) -> None:
        saida = self.service.correct_result(self.tid, int(self.board["id"]), "0-1", MOTIVO)
        self.assertTrue(saida["unlocked"])
        self.assertEqual("0-1", self.db.get_team_board(int(self.board["id"]))["result"])
        historico = self.service.pairing_correction_history(self.tid, int(self.board["id"]))
        self.assertEqual(1, len(historico))

        self.service.revert_correction(self.tid, historico[0]["event_id"], "Capitão mostrou a súmula")
        self.assertEqual("1-0", self.db.get_team_board(int(self.board["id"]))["result"])
        self.assertEqual(
            2, len(self.db.list_audit_events(self.tid, action="team_result_corrected", limit=10))
        )


class MudancasPerigosasEmAvancadoTest(_TorneioComRodadas):
    """RGS-20: a opção sai da aba Regras e grava sozinha, pelo mesmo plano de confirmações."""

    def _ajuste(self) -> int:
        return int(self.db.get_tournament_settings(self.tournament_id)["allow_dangerous_changes"] or 0)

    def test_ligar_pede_a_confirmacao_do_plano(self) -> None:
        from src.services.tournament_configuration import TIPO_MUDANCAS_PERIGOSAS

        plano = self.tournament_service.plan_dangerous_changes(self.tournament_id, True)
        self.assertEqual([TIPO_MUDANCAS_PERIGOSAS], [item.tipo for item in plano])
        self.assertIn("Corrigir resultado", plano[0].mensagem)
        with self.assertRaises(AppError):
            self.tournament_service.save_dangerous_changes(self.tournament_id, True)
        self.assertEqual(0, self._ajuste())

    def test_grava_so_a_opcao_mesmo_com_premio_invalido_no_banco(self) -> None:
        """Gravar sozinha: um prêmio em branco em outra aba não trava (nem é tocado)."""
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [{"kind": "overall", "label": "", "rank_from": 1, "rank_to": 1, "amount": 0}],
        )
        antes = dict(self.db.get_tournament_settings(self.tournament_id))
        self.tournament_service.save_dangerous_changes(
            self.tournament_id, True, confirmadas=[item.tipo for item in
                self.tournament_service.plan_dangerous_changes(self.tournament_id, True)]
        )
        depois = dict(self.db.get_tournament_settings(self.tournament_id))
        self.assertEqual(1, int(depois.pop("allow_dangerous_changes")))
        antes.pop("allow_dangerous_changes")
        depois.pop("updated_at", None)
        antes.pop("updated_at", None)
        self.assertEqual(antes, depois)
        self.assertEqual(1, len(self._eventos("dangerous_changes_enabled")))

    def test_desligar_nao_pede_confirmacao_e_fica_na_trilha(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"allow_dangerous_changes": 1})
        self.assertEqual([], self.tournament_service.plan_dangerous_changes(self.tournament_id, False))
        self.tournament_service.save_dangerous_changes(self.tournament_id, False)
        self.assertEqual(0, self._ajuste())
        self.assertEqual(1, len(self._eventos("dangerous_changes_disabled")))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
