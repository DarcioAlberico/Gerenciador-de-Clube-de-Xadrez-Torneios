"""Indicador de tarefa em andamento (barra indeterminada) para a statusbar.

Complementa a mensagem textual de status: enquanto houver trabalho rodando em
segundo plano, a barra fica visível e animada; ao terminar a última tarefa, ela
para e some (ESPEC_UI_UX §5.2 — toda ação longa tem indicador de progresso).

Conta as tarefas ativas, então **N** ações simultâneas mostram uma única barra e
só o fim da última a esconde — ``start``/``stop`` sempre em pares:

    indicador = BusyIndicator(statusbar)
    indicador.grid_config(row=0, column=3, padx=(0, 10))
    indicador.start()   # ... trabalho ...
    indicador.stop()
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..support import THEME_ACCENT


class BusyIndicator:
    """Barra indeterminada que aparece só enquanto há tarefa ativa.

    Não é um widget: encapsula um ``CTkProgressBar`` e o mostra/esconde via
    ``grid``/``grid_remove``. Tolerante a falhas de Tk (janela em destruição)
    para nunca derrubar o término de uma tarefa em background.
    """

    def __init__(self, parent: Any, width: int = 110, height: int = 6) -> None:
        self._active = 0
        self._grid_options: dict[str, Any] = {}
        self.bar = ctk.CTkProgressBar(
            parent,
            width=width,
            height=height,
            mode="indeterminate",
            progress_color=THEME_ACCENT,
        )

    # -- posicionamento ---------------------------------------------------

    def grid_config(self, **options: Any) -> None:
        """Guarda as opções de ``grid`` usadas quando a barra ficar visível."""
        self._grid_options = options

    # -- ciclo de vida ----------------------------------------------------

    @property
    def active_count(self) -> int:
        """Quantas tarefas seguram o indicador neste momento."""
        return self._active

    @property
    def is_running(self) -> bool:
        return self._active > 0

    def start(self) -> None:
        self._active += 1
        if self._active > 1:
            return
        try:
            self.bar.grid(**self._grid_options)
            self.bar.start()
        except Exception:
            pass

    def stop(self) -> None:
        if self._active == 0:
            return  # stop sem start: ignora em vez de zerar um contador alheio
        self._active -= 1
        if self._active > 0:
            return
        try:
            self.bar.stop()
            self.bar.set(0)
            self.bar.grid_remove()
        except Exception:
            pass

    def reset(self) -> None:
        """Zera o contador e esconde a barra (uso em teardown/troca de tela)."""
        self._active = 0
        try:
            self.bar.stop()
            self.bar.set(0)
            self.bar.grid_remove()
        except Exception:
            pass
