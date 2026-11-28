"""RG2-25 — operação de várias gravações entra inteira ou não entra.

Extensão do RGS-08 (``Database.transaction()``). Os métodos públicos de
serviço que gravam duas vezes ou mais são **descobertos por AST**, não listados
à mão: o teste reprova o que grava fora de ``with self.db.transaction():`` (ou
sem ``@atomic``). Gravação é ``self.db.<verbo>_...(...)`` — create, update,
delete, save, set, add, mark… —, contada no pior caminho (um ``if`` vale o
ramo mais pesado; dentro de laço, vale duas). ``backup``/``backup_before`` não
contam: o backup é de propósito antes da transação.

Limite declarado: gravação feita por um método auxiliar (``self._x()``) não é
vista — a varredura pega o caso comum, o teste de comportamento pega o resto.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path
from unittest import mock

from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase

SERVICOS = Path(__file__).resolve().parents[1] / "src" / "services"
VERBO = re.compile(
    r"^(create|update|delete|save|set|replace|add|close|insert|remove|mark|apply|record|upsert|clear|reset|"
    r"reopen|archive|approve|reject|register|enqueue|store|write|import|merge|move|swap|toggle|link|unlink|"
    r"assign|cancel)_"
)
NAO_CONTA = {"backup", "backup_before"}
ISENTOS = {
    "sync_service.py::SyncService.sync_pending": (
        "rede entre as gravações: cada item da fila marca o próprio status ao voltar do servidor, "
        "e uma transação seguraria o banco durante o envio"
    ),
}


def _e_transacao(no: ast.With) -> bool:
    return any(
        isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Attribute)
        and item.context_expr.func.attr == "transaction"
        for item in no.items
    )


def _e_gravacao(no: ast.AST) -> bool:
    if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
        return False
    alvo = no.func.value
    return (
        isinstance(alvo, ast.Attribute) and alvo.attr == "db"
        and isinstance(alvo.value, ast.Name) and alvo.value.id == "self"
        and bool(VERBO.match(no.func.attr)) and no.func.attr not in NAO_CONTA
    )


def _soma(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    return (a[0] + b[0], a[1] + b[1])


def _conta(no: ast.AST, dentro: bool) -> tuple[int, int]:
    """(gravações, gravações fora de transação) no pior caminho."""
    if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return (0, 0)
    if isinstance(no, ast.With) and _e_transacao(no):
        dentro = True
    if isinstance(no, ast.If):
        return _soma(_conta(no.test, dentro), max(_bloco(no.body, dentro), _bloco(no.orelse, dentro)))
    if isinstance(no, ast.IfExp):
        return _soma(_conta(no.test, dentro), max(_conta(no.body, dentro), _conta(no.orelse, dentro)))
    if isinstance(no, (ast.For, ast.AsyncFor, ast.While)):
        corpo = _bloco(no.body, dentro)
        cabeca = _conta(no.test if isinstance(no, ast.While) else no.iter, dentro)
        return _soma(_soma((corpo[0] * 2, corpo[1] * 2), _bloco(no.orelse, dentro)), cabeca)
    total = (1, 0 if dentro else 1) if _e_gravacao(no) else (0, 0)
    for filho in ast.iter_child_nodes(no):
        total = _soma(total, _conta(filho, dentro))
    return total


def _bloco(nos: list[ast.stmt], dentro: bool) -> tuple[int, int]:
    total = (0, 0)
    for indice, no in enumerate(nos):
        if isinstance(no, ast.If) and not no.orelse and no.body and isinstance(no.body[-1], (ast.Return, ast.Raise)):
            # `if x: ...; return` — o resto do bloco é o "senão" implícito.
            resto = _bloco(nos[indice + 1:], dentro)
            return _soma(total, _soma(_conta(no.test, dentro), max(_bloco(no.body, dentro), resto)))
        total = _soma(total, _conta(no, dentro))
    return total


def _atomico(metodo: ast.FunctionDef) -> bool:
    return any(isinstance(d, ast.Name) and d.id == "atomic" for d in metodo.decorator_list)


def gravam_fora_de_transacao() -> dict[str, tuple[int, int]]:
    achados: dict[str, tuple[int, int]] = {}
    for arquivo in sorted(SERVICOS.rglob("*.py")):
        if "gacrux" in arquivo.parts:
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for classe in (n for n in arvore.body if isinstance(n, ast.ClassDef)):
            for metodo in classe.body:
                if not isinstance(metodo, ast.FunctionDef) or metodo.name.startswith("_") or _atomico(metodo):
                    continue
                total, fora = _bloco(metodo.body, False)
                if total >= 2 and fora:
                    achados[f"{arquivo.relative_to(SERVICOS).as_posix()}::{classe.name}.{metodo.name}"] = (total, fora)
    return achados


class VarreduraPorAstTest(unittest.TestCase):
    def test_nenhum_metodo_publico_grava_duas_vezes_fora_de_transacao(self) -> None:
        achados = {k: v for k, v in gravam_fora_de_transacao().items() if k not in ISENTOS}
        self.assertEqual({}, achados, "use @atomic ou `with self.db.transaction():` (RG2-25)")

    def test_isencao_que_nao_precisa_mais_sai_da_lista(self) -> None:
        sobrando = set(ISENTOS) - set(gravam_fora_de_transacao())
        self.assertEqual(set(), sobrando, "a isenção só encolhe: tire da lista o que já está numa transação")

    def test_a_varredura_reconhece_os_casos(self) -> None:
        def contar(fonte: str) -> tuple[int, int]:
            return _bloco(ast.parse(fonte).body[0].body, False)  # type: ignore[attr-defined]

        self.assertEqual((2, 2), contar("def f(self):\n    self.db.set_x()\n    self.db.create_y()\n"))
        self.assertEqual((2, 0), contar(
            "def f(self):\n    with self.db.transaction():\n        self.db.set_x()\n        self.db.create_y()\n"
        ))
        self.assertEqual((1, 1), contar(
            "def f(self, i):\n    if i:\n        self.db.update_x(i)\n        return i\n    return self.db.create_x()\n"
        ))
        self.assertEqual((2, 2), contar("def f(self, xs):\n    for x in xs:\n        self.db.update_x(x)\n"))
        self.assertEqual((1, 1), contar("def f(self):\n    self.db.backup_before('a')\n    self.db.create_x()\n"))


class SemEstadoParcialTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jogadores = self._create_players(4)

    def test_participacao_com_falha_na_auditoria_nao_muda_o_status(self) -> None:
        with mock.patch.object(self.db, "create_audit_event", side_effect=RuntimeError("falha injetada")):
            with self.assertRaises(RuntimeError):
                self.service.set_player_participation(self.tournament_id, self.jogadores[0], "absent")
        self.assertEqual("active", self.db.get_player(self.jogadores[0])["player_status"])
        self.assertEqual([], self.service.participation_history(self.tournament_id, self.jogadores[0]))

    def test_geracao_com_falha_na_auditoria_nao_deixa_rodada(self) -> None:
        original = self.db.create_audit_event

        def falha_no_evento_da_rodada(*args, **kwargs):
            if kwargs.get("action") == "round_generated":
                raise RuntimeError("falha injetada")
            return original(*args, **kwargs)

        with mock.patch.object(self.db, "create_audit_event", side_effect=falha_no_evento_da_rodada):
            with self.assertRaises(RuntimeError):
                self.service.generate_next_round(self.tournament_id)
        self.assertEqual([], self.db.list_rounds(self.tournament_id))
        self.assertEqual("draft", self.db.get_tournament(self.tournament_id)["status"])


class TodosPresentesTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jogadores = self._create_players(4)
        for jogador in self.jogadores[1:]:
            self.db.set_player_status(jogador, "absent")
        self.service.set_player_participation(self.tournament_id, self.jogadores[0], "withdrawn", reason="viajou")

    def test_pula_o_desistente_e_ativa_os_demais(self) -> None:
        resultado = self.service.set_players_participation(
            self.tournament_id, self.jogadores, "active", skip_withdrawn=True
        )
        self.assertEqual({"changed": 3, "skipped_withdrawn": 1}, resultado)
        estados = [self.db.get_player(j)["player_status"] for j in self.jogadores]
        self.assertEqual(["withdrawn", "active", "active", "active"], estados)

    def test_falha_no_meio_nao_deixa_metade_aplicada(self) -> None:
        original = self.db.add_player_status_event
        chamadas = {"n": 0}

        def falha_no_segundo(*args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise RuntimeError("falha injetada")
            return original(*args, **kwargs)

        with mock.patch.object(self.db, "add_player_status_event", side_effect=falha_no_segundo):
            with self.assertRaises(RuntimeError):
                self.service.set_players_participation(
                    self.tournament_id, self.jogadores, "active", skip_withdrawn=True
                )
        self.assertEqual(
            ["withdrawn", "absent", "absent", "absent"],
            [self.db.get_player(j)["player_status"] for j in self.jogadores],
        )

    def test_sem_pular_o_desistente_e_recusado_e_nada_muda(self) -> None:
        with self.assertRaises(AppError):
            self.service.set_players_participation(self.tournament_id, self.jogadores, "active")
        self.assertEqual("absent", self.db.get_player(self.jogadores[1])["player_status"])


if __name__ == "__main__":
    unittest.main()
