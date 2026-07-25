"""Testes da tela de Árbitros — o piloto de View/Controller/State (F1.5).

Nenhum teste aqui abre janela nem toca banco: é exatamente esse o aceite da
tarefa. O serviço é um dublê, e o que se verifica é a **regra da tela** — o que
vai para o payload, o que volta para o formulário, e quando é criação ou edição.
"""
from __future__ import annotations

import unittest
from typing import Any

from src.ui.screens.referees import RefereeForm, RefereeRow, RefereesController
from src.ui.screens.referees.state import CAMPOS_TEXTO, CATEGORIA_PADRAO


class ServicoFalso:
    """Dublê do RefereeService: guarda o que foi pedido, sem banco."""

    def __init__(self, registros: list[dict[str, Any]] | None = None) -> None:
        self.registros = registros or []
        self.criados: list[dict[str, Any]] = []
        self.atualizados: list[tuple[int, dict[str, Any]]] = []
        self.pediu_active_only: list[bool] = []

    def list_referees(self, active_only: bool = True) -> list[dict[str, Any]]:
        self.pediu_active_only.append(active_only)
        return list(self.registros)

    def create_referee(self, data: dict[str, Any]) -> int:
        self.criados.append(data)
        return 42

    def update_referee(self, referee_id: int, data: dict[str, Any]) -> None:
        self.atualizados.append((referee_id, data))


class LeitorFalso:
    def __init__(self, por_id: dict[int, dict[str, Any]] | None = None) -> None:
        self.por_id = por_id or {}

    def get_referee(self, referee_id: int) -> dict[str, Any] | None:
        return self.por_id.get(int(referee_id))


REGISTRO = {
    "id": 7,
    "name": "Ana Arbitra",
    "federation_id": "FPX-1",
    "fide_id": "12345",
    "cbx_id": "999",
    "phone": "11 99999-0000",
    "email": "ana@clube.org",
    "notes": "Disponivel aos sabados",
    "category": "AR",
    "active": 1,
}


class RefereeFormTest(unittest.TestCase):
    def test_nasce_vazio_e_novo(self) -> None:
        form = RefereeForm()
        self.assertTrue(form.is_new)
        self.assertEqual("", form.name)
        self.assertEqual(CATEGORIA_PADRAO, form.category)
        self.assertTrue(form.active)

    def test_from_record_preenche_todos_os_campos(self) -> None:
        form = RefereeForm.from_record(REGISTRO)
        self.assertEqual(7, form.selected_id)
        self.assertFalse(form.is_new)
        self.assertEqual("Ana Arbitra", form.name)
        self.assertEqual("AR", form.category)
        self.assertTrue(form.active)

    def test_campo_nulo_vira_string_vazia(self) -> None:
        """O formulário mostrava a palavra 'None' quando o campo vinha nulo."""
        form = RefereeForm.from_record({**REGISTRO, "phone": None, "notes": None})
        self.assertEqual("", form.phone)
        self.assertEqual("", form.notes)

    def test_categoria_ausente_cai_no_padrao(self) -> None:
        form = RefereeForm.from_record({**REGISTRO, "category": None})
        self.assertEqual(CATEGORIA_PADRAO, form.category)

    def test_to_payload_manda_active_como_inteiro(self) -> None:
        """O banco guarda 0/1; mandar True/False mudaria o tipo da coluna."""
        self.assertEqual(1, RefereeForm(active=True).to_payload()["active"])
        self.assertEqual(0, RefereeForm(active=False).to_payload()["active"])

    def test_payload_tem_exatamente_os_campos_do_formulario(self) -> None:
        payload = RefereeForm.from_record(REGISTRO).to_payload()
        esperados = {chave for chave, _ in CAMPOS_TEXTO} | {"category", "active"}
        self.assertEqual(esperados, set(payload))
        self.assertNotIn("selected_id", payload, "id nao vai no payload")

    def test_with_values_nao_muda_o_original(self) -> None:
        original = RefereeForm.from_record(REGISTRO)
        alterado = original.with_values(name="Outro nome")
        self.assertEqual("Ana Arbitra", original.name)
        self.assertEqual("Outro nome", alterado.name)
        self.assertEqual(7, alterado.selected_id, "editar campo nao perde o id")

    def test_cleared_volta_para_cadastro_novo(self) -> None:
        limpo = RefereeForm.from_record(REGISTRO).cleared()
        self.assertTrue(limpo.is_new)
        self.assertEqual("", limpo.name)


class RefereeRowTest(unittest.TestCase):
    def test_valores_na_ordem_das_colunas(self) -> None:
        linha = RefereeRow.from_record(REGISTRO)
        self.assertEqual((7, "Ana Arbitra", "AR", "12345", "999", "Sim"), linha.as_values())

    def test_inativo_aparece_como_nao(self) -> None:
        linha = RefereeRow.from_record({**REGISTRO, "active": 0})
        self.assertEqual("Não", linha.as_values()[-1])


class ControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.servico = ServicoFalso([REGISTRO, {**REGISTRO, "id": 8, "name": "Bruno", "active": 0}])
        self.leitor = LeitorFalso({7: REGISTRO})
        self.controller = RefereesController(self.servico, self.leitor)

    def test_lista_inclui_inativos(self) -> None:
        """A tela mostra ativos e inativos — quem filtra é o olho, não a query."""
        linhas = self.controller.rows()
        self.assertEqual([7, 8], [linha.id for linha in linhas])
        self.assertEqual([False], self.servico.pediu_active_only)

    def test_load_devolve_formulario_preenchido(self) -> None:
        form = self.controller.load(7)
        self.assertIsNotNone(form)
        self.assertEqual("Ana Arbitra", form.name)

    def test_load_de_id_inexistente_devolve_none(self) -> None:
        self.assertIsNone(self.controller.load(999))

    def test_save_sem_id_cria(self) -> None:
        novo_id = self.controller.save(RefereeForm(name="Novo"))
        self.assertEqual(42, novo_id)
        self.assertEqual(1, len(self.servico.criados))
        self.assertEqual([], self.servico.atualizados)
        self.assertEqual("Novo", self.servico.criados[0]["name"])

    def test_save_com_id_atualiza(self) -> None:
        form = self.controller.load(7).with_values(name="Ana Editada")
        salvo = self.controller.save(form)
        self.assertEqual(7, salvo)
        self.assertEqual([], self.servico.criados)
        self.assertEqual(1, len(self.servico.atualizados))
        referee_id, payload = self.servico.atualizados[0]
        self.assertEqual(7, referee_id)
        self.assertEqual("Ana Editada", payload["name"])

    def test_erro_do_servico_sobe_para_a_tela(self) -> None:
        """A validação é do serviço; o controlador não repete regra de negócio."""
        class ServicoQueRecusa(ServicoFalso):
            def create_referee(self, data: dict[str, Any]) -> int:
                raise ValueError("Nome do arbitro e obrigatorio.")

        controller = RefereesController(ServicoQueRecusa(), self.leitor)
        with self.assertRaises(ValueError):
            controller.save(RefereeForm())


class SemDependenciaDeTkTest(unittest.TestCase):
    def test_state_e_controller_nao_importam_tk(self) -> None:
        """É o aceite da F1.5: a regra da tela roda sem janela."""
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "ui" / "screens" / "referees"
        for arquivo in ("state.py", "controller.py"):
            codigo = (raiz / arquivo).read_text(encoding="utf-8")
            self.assertNotIn("customtkinter", codigo, f"{arquivo} nao pode depender de Tk")
            self.assertNotIn("import tkinter", codigo, f"{arquivo} nao pode depender de Tk")

    def test_tela_nao_usa_mais_dicionario_de_estado(self) -> None:
        """P0-3: o id selecionado saiu do `{"value": None}`."""
        import pathlib

        view = (
            pathlib.Path(__file__).resolve().parents[1]
            / "src" / "ui" / "screens" / "referees" / "view.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('{"value"', view)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
