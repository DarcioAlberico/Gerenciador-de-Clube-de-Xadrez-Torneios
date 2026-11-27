"""RGS-17 — falso "bye repetido" bloqueava o fechamento da rodada.

FIDE C.04.1 (c): quem já recebeu o bye alocado pelo pareamento (PAB) não recebe
outro PAB. O bye **solicitado** (Z/H/F, C.04.1 / regulamento do torneio) não é
PAB: é o jogador que pediu para não jogar a rodada. O diagnóstico olhava só
"tem bye agora e já teve bye antes" e, com a busca exata achando "alternativa
melhor", marcava ``decision`` — que trava ``close_round``. Agora só acusa
quando o bye **atual** é PAB.
"""
from __future__ import annotations

import unittest

from src.services.pairing.diagnostics import pairing_diagnostics
from tests.support.core_service_base import CoreServiceTestCase


def _jogadores(quantos: int) -> list[dict]:
    return [{"id": numero, "name": f"J{numero}"} for numero in range(1, quantos + 1)]


def _rodada_com_bye(resultado_do_bye: str) -> list[dict]:
    """Mesas 2x3 e 4x5; o jogador 1 fica de bye com o código dado."""
    return [
        {"board_number": 1, "white_player_id": 2, "black_player_id": 3, "is_bye": 0},
        {"board_number": 2, "white_player_id": 4, "black_player_id": 5, "is_bye": 0},
        {"board_number": 3, "white_player_id": 1, "black_player_id": None, "is_bye": 1,
         "result": resultado_do_bye},
    ]


def _byes_repetidos(resultado_do_bye: str) -> list[dict]:
    pontos = {numero: {"points": 1.0} for numero in range(1, 6)}
    diagnosticos = pairing_diagnostics(
        _rodada_com_bye(resultado_do_bye),
        histories={},
        played_pairs=set(),
        bye_player_ids={1},  # o jogador 1 recebeu o PAB numa rodada anterior
        players=_jogadores(5),
        standings=pontos,
    )
    return [item for item in diagnosticos if item["kind"] == "bye_repeat"]


class ByeSolicitadoNaoERepeticaoTest(unittest.TestCase):
    def test_bye_solicitado_depois_de_pab_nao_e_bye_repetido(self) -> None:
        for codigo in ("Z", "H", "F"):
            with self.subTest(codigo=codigo):
                self.assertEqual([], _byes_repetidos(codigo))

    def test_pab_repetido_de_verdade_continua_bloqueando(self) -> None:
        for codigo in ("BYE", ""):
            with self.subTest(codigo=codigo):
                (repetido,) = _byes_repetidos(codigo)
                self.assertIs(True, repetido["avoidable"])
                self.assertEqual("decision", repetido["severity"])


class FechamentoComByeSolicitadoTest(CoreServiceTestCase):
    """Ponta a ponta com o motor próprio (o diagnóstico é o mesmo para os dois)."""

    def test_quem_teve_pab_e_pediu_bye_fecha_a_rodada(self) -> None:
        tid = self.db.create_tournament("RGS-17", rounds_count=4)
        self.db.save_tournament_settings(
            tid, {"pairing_system": "fide_dutch", "pairing_method": "swiss"}
        )
        for numero in range(5):
            self.db.create_player(tid, f"J{numero}", rating=2000 - 50 * numero, sex="m")

        r1 = self.service.generate_next_round(tid)
        (pab,) = [m for m in self.db.get_pairings_for_round(r1["id"]) if m["is_bye"]]
        for mesa in self.db.get_pairings_for_round(r1["id"]):
            if not mesa["is_bye"]:
                self.service.update_result(tid, mesa["id"], "1-0")
        self.service.close_round(tid, r1["id"])

        quem_teve_pab = int(pab["white_player_id"])
        self.service.request_bye(tid, quem_teve_pab, 2, "Z", reason="viagem")
        r2 = self.service.generate_next_round(tid)
        byes = [m for m in self.db.get_pairings_for_round(r2["id"]) if m["is_bye"]]
        self.assertEqual([quem_teve_pab], [int(m["white_player_id"]) for m in byes])
        self.assertEqual("Z", str(byes[0]["result"]).upper())
        for mesa in self.db.get_pairings_for_round(r2["id"]):
            if not mesa["is_bye"]:
                self.service.update_result(tid, mesa["id"], "1-0")

        self.service.close_round(tid, r2["id"])  # antes: AppError por "Bye repetido"
        self.assertEqual("closed", self.db.get_round(r2["id"])["status"])


if __name__ == "__main__":
    unittest.main()
