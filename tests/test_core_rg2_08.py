"""RG2-08 — fechar rodada por equipes pelo mesmo caminho do individual.

O RGS-11 deu guarda "já fechada" e transação só ao fechamento individual. No
por equipes, o duplo clique em "Fechar rodada" duplicava backup e auditoria, e
uma falha entre fechar a rodada e gravar o retrato deixava a rodada fechada sem
retrato — que a reconciliação não conserta.
"""
from __future__ import annotations

import unittest
from unittest import mock

from tests.support.core_service_base import CoreServiceTestCase


class FecharRodadaPorEquipesTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tid, _equipes = self._create_team_tournament(teams_count=4, boards_count=2)
        self.rodada = self.service.generate_next_round(self.tid)
        for confronto in self.db.list_team_matches_for_round(self.rodada["id"]):
            for tabuleiro in self.db.list_team_boards(int(confronto["id"])):
                self.service.update_result(self.tid, int(tabuleiro["id"]), "1-0")

    def _backups_de_fechamento(self) -> list:
        return sorted(self.backup_dir.glob("*close_team_round*")) if self.backup_dir.exists() else []

    def _eventos_de_fechamento(self) -> list:
        return self.db.list_audit_events(self.tid, action="team_round_closed")

    def test_dois_fechamentos_um_evento_e_um_backup(self) -> None:
        self.service.close_round(self.tid, self.rodada["id"])
        self.service.close_round(self.tid, self.rodada["id"])
        self.assertEqual(1, len(self._eventos_de_fechamento()))
        self.assertEqual(1, len(self._backups_de_fechamento()))
        self.assertEqual(1, len(self.db.list_standings_snapshots(self.tid)))

    def test_falha_no_retrato_deixa_a_rodada_aberta(self) -> None:
        with mock.patch.object(self.db, "create_standings_snapshot", side_effect=RuntimeError("falha injetada")):
            with self.assertRaises(RuntimeError):
                self.service.close_round(self.tid, self.rodada["id"])
        self.assertEqual("generated", self.db.get_round(self.rodada["id"])["status"])
        self.assertEqual([], self._eventos_de_fechamento())
        self.assertEqual([], self.db.list_standings_snapshots(self.tid))
        for confronto in self.db.list_team_matches_for_round(self.rodada["id"]):
            self.assertEqual("", confronto["result"] or "", "o resumo do confronto também volta")

    def test_depois_da_falha_fecha_normalmente(self) -> None:
        with mock.patch.object(self.db, "create_standings_snapshot", side_effect=RuntimeError("falha injetada")):
            with self.assertRaises(RuntimeError):
                self.service.close_round(self.tid, self.rodada["id"])
        self.service.close_round(self.tid, self.rodada["id"])
        self.assertEqual("closed", self.db.get_round(self.rodada["id"])["status"])
        self.assertEqual(1, len(self._eventos_de_fechamento()))
        self.assertEqual(1, len(self.db.list_standings_snapshots(self.tid)))


if __name__ == "__main__":
    unittest.main()
