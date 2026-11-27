"""RG2-07a — guarda depois do pareamento suíço por equipes.

O motor de equipes trata "não repetir confronto" como custo, não como regra, e
escolhe o bye antes de testar se o resto pareia (o redesenho é o RG2-07b). Até
lá, a guarda recusa a rodada que repete confronto ou dá um segundo PAB
(FIDE C.04.1, critérios absolutos), em vez de gravá-la.

As sementes 0, 2, 5 e 7 são as do estresse da revisão (7 equipes × 6 rodadas):
nelas o motor repetia confronto.
"""
from __future__ import annotations

import random
import unittest

from src.services.constants import AppError
from src.services.pairing.team_swiss import team_round_violations
from tests.support.core_service_base import CoreServiceTestCase


def _confronto(numero: int, brancas: int, pretas: int | None) -> dict:
    return {
        "match_number": numero,
        "white_team_id": brancas,
        "black_team_id": pretas,
        "is_bye": 0 if pretas else 1,
    }


class GuardaPuraTest(unittest.TestCase):
    def test_rodada_sem_repeticao_passa(self) -> None:
        rodada = [_confronto(1, 1, 2), _confronto(2, 3, 4), _confronto(3, 5, None)]
        self.assertEqual([], team_round_violations(rodada, {frozenset((1, 3))}, {1}))

    def test_confronto_repetido_e_recusado(self) -> None:
        rodada = [_confronto(1, 1, 2), _confronto(2, 3, 4)]
        problemas = team_round_violations(rodada, {frozenset((2, 1))}, set())
        self.assertEqual(1, len(problemas))
        self.assertIn("1", problemas[0])
        self.assertIn("2", problemas[0])

    def test_segundo_pab_e_recusado(self) -> None:
        rodada = [_confronto(1, 1, 2), _confronto(2, 3, None)]
        self.assertEqual(1, len(team_round_violations(rodada, set(), {3})))


def _passou_sem_repetir(teste: CoreServiceTestCase, semente: int) -> tuple[int, list[str], str]:
    """Roda 6 rodadas; devolve (torneio, repetições gravadas, mensagem da recusa)."""
    sorteio = random.Random(semente)
    tid, _equipes = teste._create_team_tournament(teams_count=7, boards_count=2)
    with teste.db.connect() as conexao:
        conexao.execute("UPDATE tournaments SET rounds_count=6 WHERE id=?", (tid,))
    jogados: set[frozenset[int]] = set()
    pabs: set[int] = set()
    gravadas: list[str] = []
    for numero in range(1, 7):
        try:
            rodada = teste.service.generate_next_round(tid)
        except AppError as exc:
            return tid, gravadas, str(exc)
        rid = int(rodada["id"])
        for confronto in teste.db.list_team_matches_for_round(rid):
            brancas, pretas = confronto["white_team_id"], confronto["black_team_id"]
            if confronto.get("is_bye") or not pretas:
                if brancas in pabs:
                    gravadas.append(f"R{numero}: 2º PAB de {brancas}")
                pabs.add(brancas)
                continue
            par = frozenset((brancas, pretas))
            if par in jogados:
                gravadas.append(f"R{numero}: {brancas}×{pretas}")
            jogados.add(par)
            for tabuleiro in teste.db.list_team_boards(int(confronto["id"])):
                teste.service.update_result(
                    tid, int(tabuleiro["id"]), sorteio.choice(["1-0", "0-1", "1/2-1/2", "1-0", "0-1"])
                )
        teste.service.close_round(tid, rid)
    return tid, gravadas, ""


class GuardaNoServicoTest(CoreServiceTestCase):
    def test_sementes_que_repetiam_nao_gravam_repeticao(self) -> None:
        recusas = []
        for semente in (0, 2, 5, 7):
            with self.subTest(semente=semente):
                _tid, gravadas, recusa = _passou_sem_repetir(self, semente)
                self.assertEqual([], gravadas)
                if recusa:
                    self.assertIn("C.04.1", recusa)
                    recusas.append(semente)
        # Sem a guarda, estas sementes gravavam a repetição: ela tem de ter agido.
        self.assertTrue(recusas, "nenhuma semente chegou à guarda")

    def test_recusa_fica_na_auditoria_e_a_rodada_nao_e_criada(self) -> None:
        tid, _gravadas, recusa = _passou_sem_repetir(self, 0)
        self.assertTrue(recusa)
        eventos = self.db.list_audit_events(tid, action="team_pairing_refused", limit=10)
        self.assertEqual(1, len(eventos))
        rodadas = self.db.list_rounds(tid)
        self.assertTrue(all(str(r.get("status")) == "closed" for r in rodadas))

    def test_tres_equipes_quatro_rodadas_termina_em_erro_claro(self) -> None:
        tid, _equipes = self._create_team_tournament(teams_count=3, boards_count=2)
        with self.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET rounds_count=4 WHERE id=?", (tid,))
        with self.assertRaises(AppError) as erro:
            for _ in range(4):
                rodada = self.service.generate_next_round(tid)
                rid = int(rodada["id"])
                for confronto in self.db.list_team_matches_for_round(rid):
                    for tabuleiro in self.db.list_team_boards(int(confronto["id"])):
                        if not confronto.get("is_bye"):
                            self.service.update_result(tid, int(tabuleiro["id"]), "1-0")
                self.service.close_round(tid, rid)
        self.assertIn("C.04.1", str(erro.exception))
