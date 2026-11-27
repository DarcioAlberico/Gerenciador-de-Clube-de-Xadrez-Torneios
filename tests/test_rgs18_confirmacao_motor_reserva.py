"""RGS-18 (decisão) — escolher o motor reserva exige confirmação.

O motor próprio (`fide_dutch.py`) é reserva: não segue o holandês completo e não
é homologado pela FIDE. O seletor já mostrava o rótulo e a rodada pareada por
ele já ganhava aviso persistente; faltava a confirmação ao ESCOLHÊ-LO. Ela entra
no plano de confirmações (RGS-09), no mesmo diálogo único, e a auditoria entra
na transação do salvamento (RGS-08).
"""
from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from typing import Any
from unittest import mock

from src.services.constants import RESERVE_ENGINE_LABEL, AppError
from src.services.tournament_configuration import (
    TIPO_MOTOR_RESERVA,
    PerfilTorneio,
    plan_tournament_configuration,
)
from tests.support.core_service_base import CoreServiceTestCase


def _plano(atual: str, pedido: dict[str, Any], rodadas: int = 0) -> list:
    validados = {"pairing_system": pedido.get("pairing_system", atual)}
    return plan_tournament_configuration(
        rodadas_geradas=rodadas,
        ajustes_atuais={"pairing_system": atual},
        ajustes_pedidos=pedido,
        ajustes_validados=validados,
        total_rodadas=5,
        agenda=[],
    )


class PlanoTest(unittest.TestCase):
    def test_trocar_para_o_motor_reserva_pede_confirmacao_com_o_rotulo(self) -> None:
        plano = _plano("gacrux_swiss", {"pairing_system": "fide_dutch"})
        self.assertEqual([TIPO_MOTOR_RESERVA], [item.tipo for item in plano])
        self.assertIn(RESERVE_ENGINE_LABEL, plano[0].mensagem)

    def test_vale_antes_da_r1_e_para_todo_sistema_reserva(self) -> None:
        for sistema in ("fide_dutch", "dubov", "burstein", "lim", "custom_authorized"):
            with self.subTest(sistema=sistema):
                self.assertEqual(
                    [TIPO_MOTOR_RESERVA],
                    [item.tipo for item in _plano("gacrux_swiss", {"pairing_system": sistema})],
                )

    def test_sem_troca_nao_pede(self) -> None:
        self.assertEqual([], _plano("fide_dutch", {"pairing_system": "fide_dutch"}))
        self.assertEqual([], _plano("fide_dutch", {}))

    def test_voltar_ao_gacrux_ou_suico_por_equipes_nao_pede(self) -> None:
        self.assertEqual([], _plano("fide_dutch", {"pairing_system": "gacrux_swiss"}))
        self.assertEqual([], _plano("gacrux_swiss", {"pairing_system": "team_swiss"}))


def _eventos(db_path, acao: str) -> int:
    with closing(sqlite3.connect(db_path)) as conexao:
        return int(
            conexao.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", (acao,)).fetchone()[0]
        )


class SalvarTest(CoreServiceTestCase):
    TORNEIO = {
        "name": "Torneio teste",
        "scope": "standalone",
        "competition_type": "individual",
        "rounds_count": "5",
        "bye_points": "1",
    }

    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(self.tournament_id, {"pairing_system": "gacrux_swiss"})

    def _perfil(self) -> PerfilTorneio:
        return PerfilTorneio(torneio=dict(self.TORNEIO), ajustes={"pairing_system": "fide_dutch"}, agenda=[])

    def _salvar(self, confirmadas: list[str]) -> None:
        self.tournament_service.save_tournament_configuration(
            self.tournament_id,
            self._perfil(),
            [],
            [],
            ["position", "name", "points"],
            confirmadas=confirmadas,
        )

    def _sistema(self) -> str:
        return str(self.db.get_tournament_settings(self.tournament_id)["pairing_system"])

    def test_plano_do_servico_lista_a_confirmacao(self) -> None:
        plano = self.tournament_service.plan_configuration(
            self.tournament_id, self._perfil(), [], [], ["position", "name", "points"]
        )
        self.assertEqual([TIPO_MOTOR_RESERVA], [item.tipo for item in plano])

    def test_sem_confirmar_recusa_e_nao_grava(self) -> None:
        with self.assertRaises(AppError) as erro:
            self._salvar([])
        self.assertIn(RESERVE_ENGINE_LABEL, str(erro.exception))
        self.assertEqual("gacrux_swiss", self._sistema())
        self.assertEqual(0, _eventos(self.db.db_path, "reserve_engine_selected"))

    def test_confirmado_grava_e_audita(self) -> None:
        self._salvar([TIPO_MOTOR_RESERVA])
        self.assertEqual("fide_dutch", self._sistema())
        eventos = self.db.list_audit_events(self.tournament_id, action="reserve_engine_selected")
        self.assertEqual(1, len(eventos))

    def test_auditoria_esta_na_transacao_do_salvamento(self) -> None:
        with mock.patch.object(self.db, "save_report_layout", side_effect=RuntimeError("falha no fim")):
            with self.assertRaises(RuntimeError):
                self._salvar([TIPO_MOTOR_RESERVA])
        self.assertEqual("gacrux_swiss", self._sistema())
        self.assertEqual(0, _eventos(self.db.db_path, "reserve_engine_selected"))


if __name__ == "__main__":
    unittest.main()
