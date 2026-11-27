"""RGS-21 e RGS-25 sem janela: o estado do botão primário, o contador e o Desfazer.

O que a tela de Rodadas decide (qual é a próxima ação da rodada, quantas mesas
já têm resultado) é dado puro em ``pairing_results/state.py``; o Desfazer é do
serviço, porque é ele que sabe se a mesa ainda tem o resultado que se quer
desfazer. Os testes de janela ficam em ``test_ui_rgs21_25_rodadas``.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.core.services import AppError, PairingService, TournamentService
from src.services.constants import RESULTS
from src.ui.screens.pairing_results.state import (
    WALKOVER_SHORTCUTS,
    primary_round_action,
    results_counter_text,
)


class BotaoPrimarioTest(unittest.TestCase):
    """RGS-25: os três estados (e o quarto, do torneio terminado)."""

    def test_rodada_aberta_com_pendencia_pede_lancar(self) -> None:
        acao = primary_round_action(
            round_number=3, round_status="generated", resolved=32, total=40, pending=8, rounds_count=5
        )
        self.assertEqual(("launch", "Lançar resultados (32/40)"), (acao.kind, acao.label))

    def test_rodada_aberta_completa_pede_fechar(self) -> None:
        acao = primary_round_action(
            round_number=3, round_status="generated", resolved=40, total=40, pending=0, rounds_count=5
        )
        self.assertEqual(("close", "Fechar rodada 3"), (acao.kind, acao.label))

    def test_rodada_fechada_pede_gerar_a_seguinte(self) -> None:
        acao = primary_round_action(
            round_number=3, round_status="closed", resolved=40, total=40, pending=0, rounds_count=5
        )
        self.assertEqual(("generate", "Gerar rodada 4"), (acao.kind, acao.label))

    def test_ultima_rodada_fechada_leva_a_classificacao(self) -> None:
        acao = primary_round_action(
            round_number=5, round_status="closed", resolved=40, total=40, pending=0, rounds_count=5
        )
        self.assertEqual("finished", acao.kind)
        self.assertEqual("Ver classificação final", acao.label)

    def test_bye_sem_resultado_ainda_e_pendencia(self) -> None:
        # O bye não entra no total de partidas, mas sem resultado impede fechar.
        acao = primary_round_action(
            round_number=1, round_status="generated", resolved=3, total=3, pending=1, rounds_count=5
        )
        self.assertEqual("launch", acao.kind)


class ContadorTest(unittest.TestCase):
    def test_texto_do_contador(self) -> None:
        self.assertEqual("32/40 lançadas", results_counter_text(32, 40))


class TeclasDeWoTest(unittest.TestCase):
    def test_letras_lancam_os_tres_wo(self) -> None:
        self.assertEqual({"w": "1F-0F", "p": "0F-1F", "a": "0F-0F"}, WALKOVER_SHORTCUTS)
        for resultado in WALKOVER_SHORTCUTS.values():
            self.assertIn(resultado, set(RESULTS))


class _Torneio(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Desfazer", "rounds_count": "3", "bye_points": "1"}
        )
        for indice in range(5):
            self.db.create_player(self.tournament_id, name=f"J{indice}", rating=1900 - indice * 30)
        self.servico = PairingService(self.db)
        self.round_id = int(self.servico.generate_next_round(self.tournament_id)["id"])
        self.mesa = next(p for p in self.db.get_pairings_for_round(self.round_id) if not p["is_bye"])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _eventos(self) -> list[dict]:
        return self.db.list_audit_events(self.tournament_id, action="result_updated", limit=50)


class DesfazerLancamentoTest(_Torneio):
    """RGS-21: lançar e desfazer → resultado anterior no banco e 2 eventos."""

    def test_lancar_e_desfazer_volta_o_anterior_com_dois_eventos(self) -> None:
        pid = int(self.mesa["id"])
        self.servico.update_result(self.tournament_id, pid, "1-0")
        self.servico.undo_result(self.tournament_id, pid, applied="1-0", previous="")

        self.assertEqual("", self.db.get_pairing(pid)["result"])
        eventos = self._eventos()
        self.assertEqual(2, len(eventos))
        desfeito = json.loads(eventos[0]["after_json"])
        self.assertEqual("", desfeito["result"])
        self.assertTrue(desfeito["undo"])
        self.assertEqual("1-0", desfeito["undone_result"])

    def test_desfazer_devolve_o_resultado_anterior_nao_vazio(self) -> None:
        pid = int(self.mesa["id"])
        self.servico.update_result(self.tournament_id, pid, "0-1")
        self.servico.update_result(self.tournament_id, pid, "1-0")
        self.servico.undo_result(self.tournament_id, pid, applied="1-0", previous="0-1")
        self.assertEqual("0-1", self.db.get_pairing(pid)["result"])

    def test_mesa_que_mudou_depois_nao_e_desfeita(self) -> None:
        pid = int(self.mesa["id"])
        self.servico.update_result(self.tournament_id, pid, "1-0")
        self.servico.update_result(self.tournament_id, pid, "0-1")  # outro lançamento
        with self.assertRaisesRegex(AppError, "mudou"):
            self.servico.undo_result(self.tournament_id, pid, applied="1-0", previous="")
        self.assertEqual("0-1", self.db.get_pairing(pid)["result"])
        self.assertEqual(2, len(self._eventos()))

    def test_rodada_fechada_nao_se_desfaz_por_aqui(self) -> None:
        for mesa in self.db.get_pairings_for_round(self.round_id):
            if not mesa["is_bye"]:
                self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.servico.close_round(self.tournament_id, self.round_id)
        with self.assertRaisesRegex(AppError, "fechada"):
            self.servico.undo_result(
                self.tournament_id, int(self.mesa["id"]), applied="1-0", previous=""
            )
        self.assertEqual("1-0", self.db.get_pairing(int(self.mesa["id"]))["result"])


class ProgressoDaRodadaTest(_Torneio):
    def test_conta_partidas_lancadas_sem_o_bye(self) -> None:
        progresso = self.servico.round_progress(self.tournament_id, self.round_id)
        self.assertEqual((0, 2, 2), (progresso["resolved_results"], progresso["total_results"], progresso["pending_results"]))
        self.servico.update_result(self.tournament_id, int(self.mesa["id"]), "1-0")
        progresso = self.servico.round_progress(self.tournament_id, self.round_id)
        self.assertEqual((1, 2, 1), (progresso["resolved_results"], progresso["total_results"], progresso["pending_results"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
