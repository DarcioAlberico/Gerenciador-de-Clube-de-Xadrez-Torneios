"""Véu de progresso sobre o painel em ação (F5.9 / P3-11).

O app já tinha indicador de tarefa longa: uma barra de **6px na statusbar**, no
rodapé da janela ([`busy.py`](busy.py)). Ela responde "há algo rodando", mas
duas coisas ficavam de fora:

1. **onde** — quem clicou "Importar lista CBX" no meio da tela procura a
   resposta ali, não a 700px de distância, no canto de baixo;
2. **o clique seguinte** — o ``busy_widget`` que desabilita o botão era
   *opcional* em ``_run_background``, e em 33 das 40 chamadas ninguém o
   passava. Sem ele, o segundo clique dispara a operação **de novo**: dois
   backups, duas importações, duas exportações para o mesmo arquivo.

O véu resolve os dois de uma vez, e o segundo **por construção**: ele é um
painel colocado por cima da área em ação, então o clique repetido acerta o véu,
não o botão. Não depende de ninguém lembrar de passar parâmetro.

Contagem por referência, como no ``BusyIndicator``: duas tarefas simultâneas
sobre o mesmo painel mostram um véu só, e é o fim da última que o retira —
``start``/``stop`` sempre em pares.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..theme import (
    SPACE_MD,
    THEME_ACCENT,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    font_subsection,
)


class ProgressOverlay:
    """Cobre ``target`` com mensagem + barra indeterminada enquanto há tarefa.

    Não é um widget: encapsula um ``CTkFrame`` posicionado com ``place`` sobre
    o alvo (``relwidth=1``/``relheight=1``) e o mostra/esconde. ``place`` e não
    ``grid`` de propósito — o alvo já tem o próprio grid montado, e o véu não
    pode disputar célula com o conteúdo que ele cobre.

    Tolerante a falhas de Tk (janela em destruição, alvo já removido) para
    nunca derrubar o término de uma tarefa em background.
    """

    def __init__(self, target: Any) -> None:
        self.target = target
        self._active = 0
        self._frame: ctk.CTkFrame | None = None
        self._label: ctk.CTkLabel | None = None
        self._bar: ctk.CTkProgressBar | None = None

    # -- ciclo de vida ----------------------------------------------------

    @property
    def active_count(self) -> int:
        """Quantas tarefas seguram o véu neste momento."""
        return self._active

    @property
    def is_running(self) -> bool:
        return self._active > 0

    def start(self, message: str = "") -> None:
        self._active += 1
        if self._active > 1:
            if message:
                self._set_message(message)
            return
        try:
            self._build()
            self._set_message(message)
            self._frame.place(relx=0, rely=0, relwidth=1, relheight=1)  # type: ignore[union-attr]
            self._frame.lift()  # type: ignore[union-attr]
            self._bar.start()  # type: ignore[union-attr]
        except Exception:
            pass

    def stop(self) -> None:
        if self._active == 0:
            return  # stop sem start: ignora em vez de zerar um contador alheio
        self._active -= 1
        if self._active > 0:
            return
        self._hide()

    def reset(self) -> None:
        """Zera o contador e retira o véu (uso em teardown/troca de tela)."""
        self._active = 0
        self._hide()

    # -- interno ----------------------------------------------------------

    def _hide(self) -> None:
        try:
            if self._bar is not None:
                self._bar.stop()
            if self._frame is not None:
                self._frame.place_forget()
        except Exception:
            pass

    def _set_message(self, message: str) -> None:
        if self._label is not None and message:
            try:
                self._label.configure(text=message)
            except Exception:
                pass

    def _build(self) -> None:
        if self._frame is not None and self._frame.winfo_exists():
            return
        frame = ctk.CTkFrame(self.target, fg_color=THEME_PANEL_BG, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure((0, 3), weight=1)

        self._label = ctk.CTkLabel(
            frame, text="", font=font_subsection(), text_color=THEME_TEXT_MAIN
        )
        self._label.grid(row=1, column=0, pady=(0, SPACE_MD))
        self._bar = ctk.CTkProgressBar(
            frame, width=220, height=6, mode="indeterminate", progress_color=THEME_ACCENT
        )
        self._bar.grid(row=2, column=0)

        # O ponto do véu: engolir o clique repetido. Sem isto ele seria só uma
        # decoração — o Tk entrega o evento ao widget de baixo se ninguém o
        # consumir, e o duplo clique voltaria a disparar a operação duas vezes.
        for evento in ("<Button-1>", "<Double-Button-1>", "<Button-3>", "<MouseWheel>"):
            frame.bind(evento, lambda _e: "break")
        self._frame = frame


_OVERLAY_ATTR = "_albericus_progress_overlay"


def overlay_of(target: Any) -> ProgressOverlay:
    """O véu do painel, criando-o na primeira chamada. Idempotente.

    Guardado no próprio widget, como o ``form_of``: dois véus sobre o mesmo
    painel teriam contadores independentes, e o primeiro a terminar retiraria
    a espera do outro. Quando a tela troca, o painel morre e leva o véu junto
    — e um véu novo nasce com o painel novo, sem contador velho pendurado.
    """
    veu = getattr(target, _OVERLAY_ATTR, None)
    if veu is None:
        veu = ProgressOverlay(target)
        setattr(target, _OVERLAY_ATTR, veu)
    return veu
