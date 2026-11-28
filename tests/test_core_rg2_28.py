"""RG2-28 — excluir torneio faz backup e deixa rastro global.

A exclusão apagava o torneio direto: sem backup e sem auditoria — e a
auditoria do torneio (``audit_events``) some junto, por ``ON DELETE CASCADE``.
O rastro fica em ``audit_logs``, que é global.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

from tests.support.core_service_base import CoreServiceTestCase


class ExcluirTorneioTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(rodada["id"])
        self.service.close_round(self.tournament_id, rodada["id"])

    def test_backup_antes_e_registro_global_com_nome_e_contagens(self) -> None:
        self.tournament_service.delete_tournament(self.tournament_id)

        backups = list(self.backup_dir.glob(f"*before_delete_tournament_t{self.tournament_id}_*.db"))
        self.assertEqual(1, len(backups))
        (registro,) = self.db.list_audit_logs(action="tournament_deleted")
        self.assertEqual(self.tournament_id, registro["entity_id"])
        self.assertIn("Torneio teste", registro["description"])
        dados = json.loads(registro["metadata_json"])
        self.assertEqual({"players": 4, "rounds": 1, "closed_rounds": 1}, {k: dados[k] for k in ("players", "rounds", "closed_rounds")})
        self.assertIsNone(self.db.get_tournament(self.tournament_id))

    def test_falha_no_backup_nao_exclui(self) -> None:
        with mock.patch.object(self.db, "backup", side_effect=OSError("disco cheio")):
            with self.assertRaises(OSError):
                self.tournament_service.delete_tournament(self.tournament_id)
        self.assertIsNotNone(self.db.get_tournament(self.tournament_id))
        self.assertEqual([], self.db.list_audit_logs(action="tournament_deleted"))

    def test_resumo_para_a_confirmacao(self) -> None:
        resumo = self.tournament_service.deletion_summary(self.tournament_id)
        self.assertEqual({"name": "Torneio teste", "players": 4, "rounds": 1, "closed_rounds": 1}, resumo)


if __name__ == "__main__":
    unittest.main()
