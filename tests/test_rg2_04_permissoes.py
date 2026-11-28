"""RG2-04 — a permissão mora no serviço, lendo o operador do banco.

Só ``SecurityService`` checava permissão; a tela fazia o resto, handler a
handler, e o painel do árbitro, os ajustes e o QR gravavam sem checar nada.
Logado como ``viewer``, a sonda da R4 lançou 1-0, adiou mesa e criou ajuste de
+1 ponto.

A varredura descobre por AST os métodos públicos de ``src/services`` que
gravam (chamam ``self.db.(create|update|delete|replace|save|add|close|set)_*``,
abrem ``self.db.transaction()`` ou são ``@atomic``) e reprova o que não tem
``@requires(...)``, não chama ``require_permission`` nem está isento com motivo.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from src.core.operator import Operator
from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase

SERVICOS = Path(__file__).resolve().parents[1] / "src" / "services"
VERBO = re.compile(r"^(create|update|delete|replace|save|add|close|set)_")
ISENTOS = {
    "column_layout_service.py::ColumnLayoutService.remember": "largura de coluna: preferência de tela do próprio usuário",
    "security_service.py::SecurityService.audit": "é a própria trilha de auditoria (inclusive da recusa)",
    "qr_result_service.py::QRResultService.submit_result": "entrada pública do QR, autorizada pelo token da mesa",
    "pairing_service.py::PairingService.tiebreak_report": "relatório: grava só o cache dos componentes de desempate",
}


def _grava(metodo: ast.FunctionDef) -> bool:
    if any(isinstance(d, ast.Name) and d.id == "atomic" for d in metodo.decorator_list):
        return True
    for no in ast.walk(metodo):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            alvo = no.func.value
            if (
                isinstance(alvo, ast.Attribute) and alvo.attr == "db"
                and isinstance(alvo.value, ast.Name) and alvo.value.id == "self"
                and (VERBO.match(no.func.attr) or no.func.attr == "transaction")
            ):
                return True
    return False


def _checa(metodo: ast.FunctionDef) -> bool:
    for decorador in metodo.decorator_list:
        if isinstance(decorador, ast.Call) and isinstance(decorador.func, ast.Name) and decorador.func.id == "requires":
            return True
    return any(
        isinstance(no, ast.Call)
        and (
            (isinstance(no.func, ast.Name) and no.func.id == "require_permission")
            or (isinstance(no.func, ast.Attribute) and no.func.attr == "require_permission")
        )
        for no in ast.walk(metodo)
    )


def gravam_sem_checar() -> list[str]:
    achados = []
    for arquivo in sorted(SERVICOS.rglob("*.py")):
        if "gacrux" in arquivo.parts:
            continue
        for classe in (n for n in ast.parse(arquivo.read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef)):
            for metodo in classe.body:
                if isinstance(metodo, ast.FunctionDef) and not metodo.name.startswith("_") and _grava(metodo) and not _checa(metodo):
                    achados.append(f"{arquivo.relative_to(SERVICOS).as_posix()}::{classe.name}.{metodo.name}")
    return achados


class VarreduraTest(unittest.TestCase):
    def test_todo_metodo_que_grava_checa_permissao(self) -> None:
        self.assertEqual([], [m for m in gravam_sem_checar() if m not in ISENTOS])

    def test_isencao_que_nao_precisa_mais_sai_da_lista(self) -> None:
        self.assertEqual(set(), set(ISENTOS) - set(gravam_sem_checar()), "a isenção só encolhe")


class _ComPapel(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jogadores = self._create_players(4)
        self.rodada = self.service.generate_next_round(self.tournament_id)
        self.mesa = next(p for p in self.db.get_pairings_for_round(self.rodada["id"]) if not p["is_bye"])

    def _como(self, papel: str) -> None:
        self.db.set_operator(Operator(user_id=9, name=f"u_{papel}", role=papel))


class ViewerNaoGravaTest(_ComPapel):
    def _recusa(self, chamada) -> None:
        with self.assertRaisesRegex(AppError, "Permissão negada"):
            chamada()

    def test_resultado_e_adiamento(self) -> None:
        self._como("viewer")
        self._recusa(lambda: self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0"))
        self._recusa(lambda: self.service.postpone_pairing(self.tournament_id, int(self.mesa["id"]), "chuva"))
        mesa = next(p for p in self.db.get_pairings_for_round(self.rodada["id"]) if p["id"] == self.mesa["id"])
        self.assertEqual("", mesa["result"] or "")
        self.assertFalse(mesa.get("postponed"))

    def test_aprovar_qr(self) -> None:
        token = self.qr_result_service.result_url_for_pairing(self.tournament_id, int(self.mesa["id"]))
        envio = self.qr_result_service.submit_result(token["token"], "1-0", submitter="Mesa 1")
        self._como("viewer")
        self._recusa(lambda: self.qr_result_service.approve_submission(int(envio["id"])))
        self.assertEqual("submitted", self.db.get_result_submission(int(envio["id"]))["status"])

    def test_excluir_torneio_e_lancamento(self) -> None:
        lancamento = self.finance_service.save_transaction(
            {"transaction_type": "income", "description": "Inscrição", "amount": "50", "transaction_date": "2026-11-01"}
        )
        self._como("viewer")
        self._recusa(lambda: self.tournament_service.delete_tournament(self.tournament_id))
        self._recusa(lambda: self.finance_service.delete_transaction(lancamento))
        self.assertIsNotNone(self.db.get_tournament(self.tournament_id))
        self.assertIn(lancamento, [t["id"] for t in self.finance_service.list_transactions()])

    def test_a_recusa_fica_na_auditoria_global(self) -> None:
        self._como("viewer")
        self._recusa(lambda: self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0"))
        (registro,) = self.db.list_audit_logs(action="permission_denied")
        self.assertEqual(("u_viewer", "viewer"), (registro["actor"], registro["role"]))
        self.assertIn("tournament_write", registro["description"])


class ArbitroTest(_ComPapel):
    def test_arbitro_exclui_rodada_mas_nao_o_torneio(self) -> None:
        self._como("arbiter")
        self.service.delete_generated_round(self.tournament_id, int(self.rodada["id"]))
        self.assertEqual([], self.db.list_rounds(self.tournament_id))
        with self.assertRaisesRegex(AppError, "Permissão negada"):
            self.tournament_service.delete_tournament(self.tournament_id)

    def test_arbitro_lanca_resultado(self) -> None:
        self._como("arbiter")
        self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0")


if __name__ == "__main__":
    unittest.main()
