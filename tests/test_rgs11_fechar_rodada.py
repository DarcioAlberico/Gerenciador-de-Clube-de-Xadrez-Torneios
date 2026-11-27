"""RGS-11 (F1.8): fechar rodada é idempotente e atômico.

O segundo clique em "Fechar rodada" gerava um segundo ``round_closed``, um
segundo backup e regravava o retrato. E o status ``closed`` era gravado antes
do retrato: uma falha no meio deixava a rodada fechada sem retrato.
"""
from __future__ import annotations

import sqlite3
import unittest
from unittest import mock

from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase


class _Falha(RuntimeError):
    pass


class FecharRodadaTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        self.round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(self.round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")

    def _eventos(self, action: str) -> list[dict]:
        return self.db.list_audit_events(self.tournament_id, action=action, limit=50)

    def _linhas(self, tabela: str) -> int:
        conexao = sqlite3.connect(self.db.db_path)
        try:
            return int(conexao.execute(
                f"SELECT COUNT(*) FROM {tabela} WHERE tournament_id = ?", (self.tournament_id,)
            ).fetchone()[0])
        finally:
            conexao.close()

    def test_fechar_duas_vezes_e_um_fechamento_so(self) -> None:
        espiao = mock.patch.object(
            self.db, "create_standings_snapshot", wraps=self.db.create_standings_snapshot
        )
        with espiao as retratos:
            self.service.close_round(self.tournament_id, self.round_id)
            self.service.close_round(self.tournament_id, self.round_id)

        self.assertEqual(1, len(self._eventos("round_closed")))
        self.assertEqual(1, retratos.call_count)
        self.assertEqual(1, self._linhas("standings_snapshots"))
        self.assertEqual(0, self._linhas("standings_snapshot_history"))
        backups_do_fechamento = [
            evento for evento in self._eventos("backup_created")
            if evento.get("round_id") == self.round_id
        ]
        self.assertEqual(1, len(backups_do_fechamento))
        self.assertEqual(1, len(list(self.backup_dir.glob("*close_round*.db"))))

    def test_falha_no_retrato_nao_deixa_a_rodada_fechada(self) -> None:
        with mock.patch.object(self.db, "create_standings_snapshot", side_effect=_Falha("disco")):
            with self.assertRaises(_Falha):
                self.service.close_round(self.tournament_id, self.round_id)

        self.assertNotEqual("closed", self.db.get_round(self.round_id)["status"])
        self.assertEqual([], self._eventos("round_closed"))
        self.assertEqual(0, self._linhas("standings_snapshots"))
        self.assertEqual(0, self._linhas("tiebreak_components"))

        # O operador tenta de novo e fecha normalmente.
        self.service.close_round(self.tournament_id, self.round_id)
        self.assertEqual("closed", self.db.get_round(self.round_id)["status"])
        self.assertEqual(1, len(self._eventos("round_closed")))
        self.assertEqual(1, self._linhas("standings_snapshots"))

    def test_rodada_pendente_continua_recusada(self) -> None:
        """Caracterização: a idempotência não afrouxa a checagem de resultados."""
        self.service.close_round(self.tournament_id, self.round_id)
        round_2 = self.service.generate_next_round(self.tournament_id)
        with self.assertRaises(AppError):
            self.service.close_round(self.tournament_id, int(round_2["id"]))


class BackupNomeUnicoTest(CoreServiceTestCase):
    def test_dois_backups_no_mesmo_segundo_nao_se_sobrescrevem(self) -> None:
        primeiro = self.db.backup("mesmo_motivo")
        segundo = self.db.backup("mesmo_motivo")

        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(primeiro.exists())
        self.assertTrue(segundo.exists())
        self.assertEqual(2, len(list(self.backup_dir.glob("*.db"))))


if __name__ == "__main__":
    unittest.main()
