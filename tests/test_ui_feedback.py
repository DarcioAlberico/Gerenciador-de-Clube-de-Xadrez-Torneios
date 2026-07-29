"""Roteamento de feedback (``src/ui/feedback.py`` — F5.7 / P3-8).

A regra é pura: entra mensagem, sai canal. Testá-la sem janela é o que permite
cobrar o comportamento que motivou a tarefa — que a URL do servidor QR e a
narrativa de desempate **não** saiam num toast de 3,5 segundos.
"""
from __future__ import annotations

import unittest

from src.ui.feedback import REPORT, REPORT_MIN_LINES, TOAST, line_count, plan_feedback


class ContagemDeLinhasTest(unittest.TestCase):
    def test_linha_em_branco_separa_blocos_e_nao_conta(self) -> None:
        self.assertEqual(2, line_count("Servidor ativo:\n\nhttp://192.168.0.5:8765"))

    def test_texto_vazio_nao_tem_linhas(self) -> None:
        self.assertEqual(0, line_count("   \n  \n"))


class RoteamentoTest(unittest.TestCase):
    def test_confirmacao_curta_continua_no_toast(self) -> None:
        plano = plan_feedback("Torneio salvo.")
        self.assertEqual(TOAST, plano.channel)
        self.assertFalse(plano.copyable)

    def test_duas_linhas_ganham_acao_de_copiar(self) -> None:
        """O caso "fiz isto:" + caminho — curto, mas o dado precisa ser levado."""
        plano = plan_feedback("Relatorio exportado:\nC:/tmp/relatorio.pdf")
        self.assertEqual(TOAST, plano.channel)
        self.assertTrue(plano.copyable)

    def test_relatorio_longo_vai_para_dialogo(self) -> None:
        narrativa = "\n".join(f"Criterio {i}: valor" for i in range(12))
        self.assertEqual(REPORT, plan_feedback(narrativa).channel)

    def test_limiar_e_de_tres_linhas(self) -> None:
        duas = "linha 1\nlinha 2"
        tres = "linha 1\nlinha 2\nlinha 3"
        self.assertEqual(3, REPORT_MIN_LINES)
        self.assertEqual(TOAST, plan_feedback(duas).channel)
        self.assertEqual(REPORT, plan_feedback(tres).channel)

    def test_erro_e_aviso_nunca_viram_relatorio(self) -> None:
        """São curtos e recuperáveis; o inesperado já tem modal próprio."""
        longo = "\n".join(["detalhe"] * 10)
        for kind in ("error", "warning"):
            with self.subTest(kind=kind):
                plano = plan_feedback(longo, kind)
                self.assertEqual(TOAST, plano.channel)
                self.assertFalse(plano.copyable)


class CasosReaisTest(unittest.TestCase):
    """As mensagens concretas citadas no achado P3-8."""

    def test_url_do_servidor_qr_nao_sai_em_toast_efemero(self) -> None:
        msg = "http://192.168.0.5:8765\n\nUse este endereco na mesma rede local."
        self.assertTrue(plan_feedback(msg).copyable)

    def test_narrativa_de_desempate_abre_dialogo(self) -> None:
        msg = (
            "Ana Silva - 4.0 pontos\n"
            "Buchholz: 18.5\n"
            "Sonneborn-Berger: 12.25\n"
            "\n"
            "- Detalhes tecnicos -\n"
            "Adversarios: Bruno, Carla, Diego"
        )
        self.assertEqual(REPORT, plan_feedback(msg).channel)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
