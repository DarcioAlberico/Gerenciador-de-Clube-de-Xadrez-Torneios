"""Testes do adiamento de refiltro (B-4 / P2-13).

Sem janela: o agendamento entra por parâmetro, então o relógio aqui é uma lista
de tarefas que o teste dispara na mão. Testar debounce com ``sleep`` seria
trocar uma suíte determinística por uma suíte lenta e intermitente.
"""
from __future__ import annotations

import unittest

from src.ui.components.debounce import DEFAULT_DELAY_MS, Debounced


class RelogioFalso:
    """Agenda tarefas e só executa quando o teste manda."""

    def __init__(self) -> None:
        self.tarefas: dict[int, object] = {}
        self.atrasos: list[int] = []
        self._proximo = 0

    def schedule(self, delay_ms: int, fn: object) -> int:
        self._proximo += 1
        self.tarefas[self._proximo] = fn
        self.atrasos.append(delay_ms)
        return self._proximo

    def cancel(self, token: int) -> None:
        self.tarefas.pop(token, None)

    def avancar(self) -> None:
        """Executa tudo que está agendado."""
        for fn in list(self.tarefas.values()):
            fn()  # type: ignore[operator]
        self.tarefas.clear()


class DebouncedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.relogio = RelogioFalso()
        self.execucoes: list[int] = []
        self.adiado = Debounced(
            lambda: self.execucoes.append(1), self.relogio.schedule, self.relogio.cancel
        )

    def test_uma_tecla_nao_executa_na_hora(self) -> None:
        self.adiado()
        self.assertEqual([], self.execucoes)
        self.assertTrue(self.adiado.is_pending)

    def test_dez_teclas_seguidas_viram_uma_execucao(self) -> None:
        """O ponto da tarefa: com 6.000 linhas, cada tecla custava ~50 ms."""
        for _ in range(10):
            self.adiado()
        self.assertEqual(1, len(self.relogio.tarefas), "so um agendamento vivo por vez")
        self.relogio.avancar()
        self.assertEqual(1, self.adiado.runs)
        self.assertEqual(1, len(self.execucoes))

    def test_pausa_entre_rajadas_executa_duas_vezes(self) -> None:
        self.adiado()
        self.relogio.avancar()
        self.adiado()
        self.relogio.avancar()
        self.assertEqual(2, len(self.execucoes))

    def test_flush_executa_agora(self) -> None:
        self.adiado()
        self.adiado.flush()
        self.assertEqual(1, len(self.execucoes))
        self.assertFalse(self.adiado.is_pending)

    def test_flush_sem_nada_pendente_nao_executa(self) -> None:
        """Enter num campo intocado não pode refiltrar do nada."""
        self.adiado.flush()
        self.assertEqual([], self.execucoes)

    def test_flush_nao_repete_o_que_ja_rodou(self) -> None:
        self.adiado()
        self.adiado.flush()
        self.relogio.avancar()  # o agendamento ja tinha sido cancelado
        self.assertEqual(1, len(self.execucoes))

    def test_cancelar_descarta_o_pendente(self) -> None:
        self.adiado()
        self.adiado.cancel()
        self.relogio.avancar()
        self.assertEqual([], self.execucoes)

    def test_cancelamento_que_falha_nao_derruba_a_digitacao(self) -> None:
        """Widget destruído no meio: ``after_cancel`` levanta, e não pode subir."""
        def cancel_quebrado(_token: object) -> None:
            raise RuntimeError("widget ja morreu")

        adiado = Debounced(lambda: None, self.relogio.schedule, cancel_quebrado)
        adiado()
        adiado.cancel()  # nao pode levantar
        self.assertFalse(adiado.is_pending)

    def test_usa_o_atraso_padrao_e_aceita_outro(self) -> None:
        self.adiado()
        self.assertEqual([DEFAULT_DELAY_MS], self.relogio.atrasos)

        relogio = RelogioFalso()
        Debounced(lambda: None, relogio.schedule, relogio.cancel, delay_ms=50)()
        self.assertEqual([50], relogio.atrasos)

    def test_atraso_negativo_vira_zero(self) -> None:
        relogio = RelogioFalso()
        Debounced(lambda: None, relogio.schedule, relogio.cancel, delay_ms=-5)()
        self.assertEqual([0], relogio.atrasos)

    def test_serve_direto_como_callback_de_bind(self) -> None:
        """O ``bind`` entrega um evento; o adiado tem de aceitá-lo e ignorá-lo."""
        self.adiado("<evento falso>")
        self.relogio.avancar()
        self.assertEqual(1, len(self.execucoes))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
