"""RGS-16 (F3.5) — verificação holandesa depois de toda geração; ajuste manual com trilha.

C.04.2 (regras gerais do Suíço): o pareamento publicado é o do sistema, e toda
alteração manual é registrada. Antes:

- ``adjust_pairing_player`` trocava jogadores sem motivo e sem evento — dava
  para pôr alguém na mesa do bye ou num reencontro sem deixar rastro;
- o verificador do Gacrux (``pairingchecker -c``) nunca rodava.

Agora:

- rodada gerada pelo Gacrux passa pelo verificador; divergência é DEFEITO e
  vira pendência que bloqueia o fechamento (``pairing_check_divergence``);
- ajuste manual exige motivo e grava ``pairing_manual_adjustment`` com antes,
  depois, motivo e a divergência que o verificador acusa — sem bloquear.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from src.core.database import Database
from src.services.constants import AppError
from src.services.pairing.gacrux_engine import GacruxEngine
from src.services.pairing.pairing_check import PairingCheck, stored_pairs
from src.services.pairing_service import PairingService

_CONFIG = {
    "pairing_method": "swiss",
    "time_control": "10 min",
    "chief_arbiter": "Arbitro",
    "federation": "BRA",
    "location": "Sao Paulo",
    "start_date": "2026-06-09",
    "end_date": "2026-06-09",
}


def _json(texto: str | None) -> dict:
    return json.loads(texto or "{}")


class _Torneio(unittest.TestCase):
    sistema = "gacrux_swiss"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(db_path=Path(self._tmp.name) / "t.db", backup_dir=Path(self._tmp.name) / "bk")
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-16", rounds_count=5, bye_points=1.0)
        self.db.save_tournament_settings(self.tid, {**_CONFIG, "pairing_system": self.sistema})
        self.ids = [
            self.db.create_player(self.tid, f"J{i}", rating=2000 - 50 * i, sex="m", birth_date="2000")
            for i in range(6)
        ]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _eventos(self, acao: str) -> list[dict]:
        return self.db.list_audit_events(self.tid, action=acao, limit=50)

    def _fechar(self, rodada: dict, resultado: str = "1-0") -> None:
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.service.update_result(self.tid, int(pairing["id"]), resultado)
        self.service.close_round(self.tid, int(rodada["id"]))


def _check(rodada: int, gravado, esperado) -> PairingCheck:
    return PairingCheck(round_number=rodada, checked=True, stored=tuple(gravado), expected=tuple(esperado))


class AjusteManualTest(_Torneio):
    """Rodada gerada pelo motor reserva; o verificador é trocado por um dublê."""

    sistema = "fide_dutch"

    def setUp(self) -> None:
        super().setUp()
        self.rodada = self.service.generate_next_round(self.tid)
        self.mesas = self.db.get_pairings_for_round(int(self.rodada["id"]))

    def _trocar(self, **extra) -> None:
        primeira, segunda = self.mesas[0], self.mesas[1]
        self.service.adjust_pairing_player(
            self.tid, int(self.rodada["id"]), int(primeira["id"]), "white",
            int(segunda["black_player_id"]), **extra,
        )

    def test_ajuste_sem_motivo_e_recusado(self) -> None:
        antes = stored_pairs(self.db.get_pairings_for_round(int(self.rodada["id"])))
        for motivo in ({}, {"reason": ""}, {"reason": "   "}):
            with self.subTest(motivo=motivo), self.assertRaises(AppError) as erro:
                self._trocar(**motivo)
            self.assertIn("motivo", str(erro.exception).lower())
        self.assertEqual(antes, stored_pairs(self.db.get_pairings_for_round(int(self.rodada["id"]))))
        self.assertEqual([], self._eventos("pairing_manual_adjustment"))

    def test_ajuste_com_motivo_grava_um_evento_com_a_divergencia(self) -> None:
        self.db.save_tournament_settings(self.tid, {"pairing_system": "gacrux_swiss"})
        antes = stored_pairs(self.db.get_pairings_for_round(int(self.rodada["id"])))
        divergencia = _check(1, [(self.ids[0], self.ids[1])], [(self.ids[0], self.ids[3])])
        with mock.patch.object(
            PairingService, "_check_round_against_dutch", return_value=divergencia
        ) as verificador:
            self._trocar(reason="Irmãos no mesmo tabuleiro")
        verificador.assert_called_once()
        (evento,) = self._eventos("pairing_manual_adjustment")
        self.assertEqual("Irmãos no mesmo tabuleiro", evento["reason"])
        self.assertEqual(int(self.rodada["id"]), int(evento["round_id"]))
        before, after = _json(evento["before_json"]), _json(evento["after_json"])
        self.assertEqual([list(p) for p in sorted(antes)], before["pairs"])
        depois = stored_pairs(self.db.get_pairings_for_round(int(self.rodada["id"])))
        self.assertEqual([list(p) for p in sorted(depois)], after["pairs"])
        checker = _json(evento["metadata_json"])["checker"]
        self.assertTrue(checker["checked"])
        self.assertFalse(checker["matches"])
        self.assertEqual([[self.ids[0], self.ids[3]]], checker["only_expected"])

    def test_ajuste_nao_bloqueia_o_fechamento(self) -> None:
        self.db.save_tournament_settings(self.tid, {"pairing_system": "gacrux_swiss"})
        divergencia = _check(1, [(1, 2)], [(1, 3)])
        with mock.patch.object(PairingService, "_check_round_against_dutch", return_value=divergencia):
            self._trocar(reason="Erro de digitação na inscrição")
        self._fechar(self.rodada)
        self.assertEqual("closed", self.db.get_round(int(self.rodada["id"]))["status"])

    def test_motor_reserva_registra_sem_rodar_o_verificador(self) -> None:
        with mock.patch.object(PairingService, "_check_round_against_dutch") as verificador:
            self._trocar(reason="Pedido do organizador")
        verificador.assert_not_called()
        (evento,) = self._eventos("pairing_manual_adjustment")
        self.assertFalse(_json(evento["metadata_json"])["checker"]["checked"])


class VerificacaoDaGeracaoTest(_Torneio):
    """Geração pelo Gacrux, com o motor e o verificador trocados por dublês."""

    def _gerar(self, verificacao_divergente: bool) -> dict:
        jogadores = self.ids
        mesas = [
            {"board_number": 1, "white_player_id": jogadores[0], "black_player_id": jogadores[3],
             "result": "", "is_bye": 0},
            {"board_number": 2, "white_player_id": jogadores[4], "black_player_id": jogadores[1],
             "result": "", "is_bye": 0},
            {"board_number": 3, "white_player_id": jogadores[2], "black_player_id": jogadores[5],
             "result": "", "is_bye": 0},
        ]
        gravado = [(m["white_player_id"], m["black_player_id"]) for m in mesas]
        esperado = [(jogadores[3], jogadores[0]), *gravado[1:]] if verificacao_divergente else gravado
        with mock.patch.object(GacruxEngine, "pair_round", return_value=mesas), \
                mock.patch.object(GacruxEngine, "check_round", return_value=_check(1, gravado, esperado)):
            return self.service.generate_next_round(self.tid)

    def test_rodada_que_confere_nao_bloqueia(self) -> None:
        rodada = self._gerar(verificacao_divergente=False)
        self.assertTrue(rodada["pairing_check"]["matches"])
        (evento,) = self._eventos("pairing_check")
        self.assertEqual(int(rodada["id"]), int(evento["round_id"]))
        self.assertEqual([], self._eventos("pairing_check_divergence"))
        self._fechar(rodada)

    def test_rodada_gerada_divergente_bloqueia_o_fechamento(self) -> None:
        rodada = self._gerar(verificacao_divergente=True)
        self.assertFalse(rodada["pairing_check"]["matches"])
        self.assertEqual(1, len(self._eventos("pairing_check_divergence")))
        with self.assertRaises(AppError) as erro:
            self._fechar(rodada)
        self.assertIn("check_divergence", str(erro.exception))
        # Ciente registrado, a rodada fecha: a decisão fica na trilha.
        (pendencia,) = [
            item for item in self.service.arbitration_issues(self.tid)["issues"]
            if item["kind"] == "check_divergence"
        ]
        self.service.acknowledge_arbitration_issue(self.tid, pendencia["issue_key"], "Conferido à mão")
        self.service.close_round(self.tid, int(rodada["id"]))


@pytest.mark.gacrux
class GacruxRealTest(_Torneio):
    def setUp(self) -> None:
        super().setUp()
        self.ids.append(self.db.create_player(self.tid, "J6", rating=1650, sex="m", birth_date="2000"))

    def test_rodadas_geradas_conferem_com_o_holandes(self) -> None:
        resultados = ["1-0", "0-1", "1/2-1/2"]
        for numero in range(1, 4):
            rodada = self.service.generate_next_round(self.tid)
            check = rodada["pairing_check"]
            self.assertTrue(check["checked"], check["error"])
            self.assertTrue(check["matches"], check["differences"])
            self._fechar(rodada, resultados[numero - 1])
        self.assertEqual([], self._eventos("pairing_check_divergence"))

    def test_ajuste_manual_leva_a_divergencia_do_verificador(self) -> None:
        rodada = self.service.generate_next_round(self.tid)
        mesas = [m for m in self.db.get_pairings_for_round(int(rodada["id"])) if not m["is_bye"]]
        self.service.adjust_pairing_player(
            self.tid, int(rodada["id"]), int(mesas[0]["id"]), "white",
            int(mesas[1]["black_player_id"]), reason="Pedido do árbitro-chefe",
        )
        (evento,) = self._eventos("pairing_manual_adjustment")
        checker = _json(evento["metadata_json"])["checker"]
        self.assertTrue(checker["checked"], checker["error"])
        self.assertFalse(checker["matches"])
        self.assertTrue(checker["only_stored"])
        self.assertTrue(checker["only_expected"])


if __name__ == "__main__":
    unittest.main()
