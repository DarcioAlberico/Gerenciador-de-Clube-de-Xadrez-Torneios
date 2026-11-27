"""RGS-31 — o laço de auto-atualização do painel do árbitro não pode morrer calado.

O painel se reagenda no fim da própria montagem (``panel.build`` →
``AutoRefresh.schedule``). Se uma montagem disparada pelo ``after`` levantava
exceção, o reagendamento nunca acontecia: o painel parava de se atualizar e
ninguém ficava sabendo por quê.

O ``AutoRefresh`` só conversa com o anfitrião por ``after``/``after_cancel`` e
alguns atributos, então o teste usa um anfitrião falso — sem Tk, determinístico.
"""
from __future__ import annotations

import logging
import unittest
from typing import Any, Callable

from src.ui.screens.pairing_arbitration.refresh import VIEW_METHOD, AutoRefresh


class _Anfitriao:
    """O mínimo da ``AlbericusApp`` que o ``AutoRefresh`` usa."""

    def __init__(self, montar: Callable[["_Anfitriao"], None]) -> None:
        self._arbitration_auto_refresh_enabled = True
        self._arbitration_refresh_interval_seconds = 15
        self._arbitration_refresh_job: str | None = None
        self._current_view_method = VIEW_METHOD
        self.agendados: list[tuple[int, Callable[[], None]]] = []
        self.cancelados: list[str] = []
        self._montar = montar
        self.montagens = 0

    def after(self, ms: int, func: Callable[[], None]) -> str:
        self.agendados.append((ms, func))
        return f"after#{len(self.agendados)}"

    def after_cancel(self, job: str) -> None:
        self.cancelados.append(job)

    # RG2-03: o tick pergunta se há diálogo aberto ou foco num campo.
    def winfo_children(self) -> list[Any]:
        return []

    def focus_get(self) -> None:
        return None

    def show_arbitration_panel(self) -> None:
        self.montagens += 1
        self._montar(self)


def _auto_refresh(anfitriao: _Anfitriao) -> AutoRefresh:
    return AutoRefresh(anfitriao, controller=None)


def _montagem_que_falha(_anfitriao: Any) -> None:
    raise RuntimeError("banco ocupado")


class TickComFalhaTest(unittest.TestCase):
    def test_tick_que_falha_registra_o_erro_e_agenda_o_proximo(self) -> None:
        anfitriao = _Anfitriao(_montagem_que_falha)
        refresh = _auto_refresh(anfitriao)

        with self.assertLogs("src.ui", level=logging.ERROR) as logs:
            refresh._tick()

        self.assertEqual(1, anfitriao.montagens)
        registro = logs.records[0]
        self.assertIsNotNone(registro.exc_info, "o log precisa levar o traceback")
        self.assertIsInstance(registro.exc_info[1], RuntimeError)
        self.assertEqual(1, len(anfitriao.agendados), "o próximo tick tem de estar agendado")
        self.assertEqual(15_000, anfitriao.agendados[0][0])
        self.assertIsNotNone(anfitriao._arbitration_refresh_job)

    def test_o_laco_sobrevive_a_varias_falhas_seguidas(self) -> None:
        anfitriao = _Anfitriao(_montagem_que_falha)
        refresh = _auto_refresh(anfitriao)

        with self.assertLogs("src.ui", level=logging.ERROR):
            refresh._tick()
            for _ in range(3):
                _ms, proximo = anfitriao.agendados[-1]
                proximo()

        self.assertEqual(4, anfitriao.montagens)
        self.assertEqual(4, len(anfitriao.agendados))


class TickSemFalhaTest(unittest.TestCase):
    """O que já funcionava continua igual."""

    def test_montagem_bem_sucedida_agenda_uma_vez_so(self) -> None:
        def montar(anfitriao: _Anfitriao) -> None:
            _auto_refresh(anfitriao).schedule()  # como o panel.build faz

        anfitriao = _Anfitriao(montar)
        _auto_refresh(anfitriao)._tick()

        self.assertEqual(1, anfitriao.montagens)
        self.assertEqual(1, len(anfitriao.agendados))

    def test_outra_tela_aberta_nao_monta_nem_reagenda(self) -> None:
        anfitriao = _Anfitriao(_montagem_que_falha)
        anfitriao._current_view_method = "show_pairings"
        _auto_refresh(anfitriao)._tick()

        self.assertEqual(0, anfitriao.montagens)
        self.assertEqual([], anfitriao.agendados)

    def test_auto_atualizacao_desligada_nao_reagenda_depois_de_falha(self) -> None:
        def montar(anfitriao: _Anfitriao) -> None:
            anfitriao._arbitration_auto_refresh_enabled = False
            raise RuntimeError("falhou depois de desligar")

        anfitriao = _Anfitriao(montar)
        with self.assertLogs("src.ui", level=logging.ERROR):
            _auto_refresh(anfitriao)._tick()

        self.assertEqual([], anfitriao.agendados)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
