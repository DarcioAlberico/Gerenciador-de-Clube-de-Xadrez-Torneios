"""Dois defeitos de alta severidade no financeiro, achados na auditoria.

O financeiro nunca tinha sido auditado, e os dois achados mexem em dinheiro:

1. **A aba "Fluxo de Caixa" não tinha botão nenhum.** `save_trans` e
   `delete_trans` estavam definidas e nunca ligadas a widget, e não havia outro
   caminho no aplicativo para criar uma transação. O tesoureiro preenchia o
   formulário inteiro e não tinha onde clicar: `financial_transactions` ficava
   sempre vazia, os cards de despesa mostravam R$ 0,00 e o DRE em PDF saía com
   "TOTAL DE DESPESAS R$ 0,00" — prestação de contas com número errado.
2. **Lançamento de plano inativo perdia o `plan_id` ao ser salvo.** O seletor só
   listava planos ativos, então abrir uma cobrança cujo plano foi inativado caía
   em "Sem plano" e qualquer "Salvar lançamento" gravava `NULL` sem aviso.

O segundo custa mais do que parece. A trava anti-duplicação de mensalidade é
`(member_id, plan_id, reference_period)`: com a cobrança órfã ela não reconhece
o que já existe. **Reproduzido**: inativar o plano, salvar a cobrança (que perde
o plano) e reativar o plano depois faz a geração criar uma SEGUNDA cobrança da
mesma referência para o mesmo sócio.

A sequência importa e o achado original a descrevia sem ela: gerar mensalidade
RECUSA plano inativo (`"Selecione um plano ativo"`), então a duplicata só
aparece depois que o plano volta a ser ativo.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.services.finance_plan_options import (
    NO_PLAN_LABEL,
    plan_options,
    selected_label,
)
from tests.support.core_service_base import CoreServiceTestCase

ATIVOS = [
    {"id": 1, "name": "Mensal", "amount": 80.0},
    {"id": 2, "name": "Trimestral", "amount": 210.0},
]
INATIVO = {"id": 9, "name": "Mensal antigo", "amount": 60.0}


class OpcoesDePlanoTest(unittest.TestCase):
    def test_planos_ativos_entram_com_sem_plano_na_frente(self) -> None:
        rotulos, mapa = plan_options(ATIVOS)
        self.assertEqual(NO_PLAN_LABEL, rotulos[0])
        self.assertEqual([None, 1, 2], [mapa[r] for r in rotulos])

    def test_plano_do_lancamento_entra_mesmo_inativo(self) -> None:
        """Era aqui que o `plan_id` sumia."""
        rotulos, mapa = plan_options(ATIVOS, INATIVO)
        self.assertIn(9, mapa.values())
        rotulo = next(r for r, pid in mapa.items() if pid == 9)
        self.assertIn("(inativo)", rotulo)
        self.assertIn(rotulo, rotulos)

    def test_plano_ativo_do_lancamento_nao_duplica(self) -> None:
        rotulos, mapa = plan_options(ATIVOS, ATIVOS[0])
        self.assertEqual(len(rotulos), len(set(rotulos)))
        self.assertEqual(1, sum(1 for pid in mapa.values() if pid == 1))
        self.assertNotIn("(inativo)", " ".join(rotulos))

    def test_rotulo_selecionado_aponta_o_plano_do_lancamento(self) -> None:
        _rotulos, mapa = plan_options(ATIVOS, INATIVO)
        self.assertIn("(inativo)", selected_label(mapa, 9))
        self.assertEqual(NO_PLAN_LABEL, selected_label(mapa, None))
        # Plano que nao esta no mapa nao inventa rotulo.
        self.assertEqual(NO_PLAN_LABEL, selected_label(mapa, 404))

    def test_sem_plano_nenhum_a_lista_nao_fica_vazia(self) -> None:
        rotulos, mapa = plan_options([])
        self.assertEqual([NO_PLAN_LABEL], rotulos)
        self.assertEqual({NO_PLAN_LABEL: None}, mapa)


class CobrancaOrfaDuplicaTest(CoreServiceTestCase):
    """O custo real de perder o `plan_id`: mensalidade cobrada duas vezes."""

    BASE = {"name": "Mensal", "amount": "80", "billing_cycle": "monthly"}

    def setUp(self) -> None:
        super().setUp()
        self.member_service.create_member({"name": "Socio", "status": "active"})
        self.plan_id = self.finance_service.save_plan({**self.BASE, "active": 1})

    def _gerar(self) -> dict:
        return self.finance_service.generate_recurring_payments(
            self.plan_id, "2026-08", "2026-08-10"
        )

    def _cobrancas_de_agosto(self) -> list[dict]:
        return [p for p in self.db.list_payments() if p["reference_period"] == "2026-08"]

    def test_trava_anti_duplicacao_funciona_com_o_plano_preservado(self) -> None:
        self.assertEqual(1, self._gerar()["created"])
        self.assertEqual(0, self._gerar()["created"])
        self.assertEqual(1, len(self._cobrancas_de_agosto()))

    def test_gerar_mensalidade_recusa_plano_inativo(self) -> None:
        """Detalhe que muda a sequencia do defeito: inativo nao gera."""
        from src.services.constants import AppError

        self._gerar()
        self.finance_service.save_plan({**self.BASE, "active": 0}, self.plan_id)
        with self.assertRaises(AppError):
            self._gerar()

    def test_cobranca_sem_plano_deixa_de_ser_reconhecida(self) -> None:
        """Reproducao do estrago, com a reativacao que o cenario exige."""
        self._gerar()
        cobranca = self._cobrancas_de_agosto()[0]
        self.finance_service.save_payment(
            {
                "member_id": cobranca["member_id"],
                "plan_id": None,  # o que a tela gravava sozinha
                "reference_period": cobranca["reference_period"],
                "amount": cobranca["amount"],
                "due_date": cobranca["due_date"],
                "status": cobranca["status"],
            },
            int(cobranca["id"]),
        )
        self.assertIsNone(self._cobrancas_de_agosto()[0]["plan_id"])

        self.assertEqual(1, self._gerar()["created"])
        self.assertEqual(2, len(self._cobrancas_de_agosto()))

    def test_com_o_plano_preservado_a_segunda_cobranca_nao_nasce(self) -> None:
        """O mesmo caminho, agora com o `plan_id` que a correcao mantem."""
        self._gerar()
        cobranca = self._cobrancas_de_agosto()[0]
        self.finance_service.save_payment(
            {
                "member_id": cobranca["member_id"],
                "plan_id": self.plan_id,
                "reference_period": cobranca["reference_period"],
                "amount": cobranca["amount"],
                "due_date": "2026-08-20",
                "status": cobranca["status"],
            },
            int(cobranca["id"]),
        )
        self.assertEqual(0, self._gerar()["created"])
        self.assertEqual(1, len(self._cobrancas_de_agosto()))


class FluxoDeCaixaTemBotaoTest(unittest.TestCase):
    """A aba montava o formulario inteiro e nao tinha onde clicar.

    A tela e coberta pelo `test_ui_layout`; o que se fixa aqui e que as tres
    acoes estao LIGADAS a um widget. Ler a fonte e proposital: `save_trans` e
    uma closure dentro de `show_finance()` e so existe com a janela de pe.
    """

    FONTE = Path("src/ui/screens/admin_training_finance.py").read_text(encoding="utf-8")

    def test_as_tres_acoes_do_caixa_estao_ligadas(self) -> None:
        for comando in ("command=save_trans", "command=clear_trans_form", "delete_trans)"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.FONTE)

    def test_a_aba_de_patrocinios_continua_com_os_dela(self) -> None:
        """Guarda: era a aba vizinha que mostrava o que faltava no caixa."""
        for comando in ("command=save_spon", "command=clear_spon_form", "delete_spon)"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.FONTE)


class TransacaoPersisteTest(CoreServiceTestCase):
    """O servico por tras do botao que faltava."""

    def test_despesa_lancada_entra_no_fluxo(self) -> None:
        self.finance_service.save_transaction(
            {
                "type": "expense",
                "description": "Aluguel do salao",
                "amount": "1200,00",
                "transaction_date": "2026-08-01",
                "category": "Estrutura",
                "payment_method": "pix",
                "notes": "",
            }
        )
        transacoes = self.db.list_financial_transactions()
        self.assertEqual(1, len(transacoes))
        self.assertEqual(1200.0, float(transacoes[0]["amount"]))
        self.assertEqual("expense", transacoes[0]["type"])
