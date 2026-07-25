"""Diálogos modais temáticos: confirmação, escolha tri-estado e alerta.

Substituem os ``messagebox`` nativos do SO (ver ESPEC_UI_UX §4.4 / §5.1): seguem
o tema, centralizam sobre a janela (ou sobre o modal já aberto), respondem a
``Esc``/``Enter`` e devolvem o resultado de forma **bloqueante** (``wait_window``)
— o chamador usa o retorno como faria com ``askyesno``/``askyesnocancel``.

Preservam e restauram o *grab* anterior, então podem ser abertos por cima de
outro modal sem quebrar a modalidade do pai.

    confirm_dialog(parent, "Excluir?", "...", danger=True)  -> bool
    tri_state_dialog(parent, "...", "...")                  -> True | False | None
    alert_dialog(parent, "Erro", "...", kind="error")       -> None
"""
from __future__ import annotations

from typing import Any, Sequence

import customtkinter as ctk

from ..support import (
    SPACE_LG,
    SPACE_SM,
    SPACE_XL,
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_WARNING_TEXT,
    font_section,
)
from .buttons import danger_button, primary_button, secondary_button

# kind do alerta -> cor do título (demais ficam na cor de texto principal)
_TITLE_COLOR = {
    "error": THEME_DANGER,
    "warning": THEME_WARNING_TEXT,
}

_FACTORY = {
    "primary": primary_button,
    "secondary": secondary_button,
    "danger": danger_button,
}

# Cada botão: (rótulo, valor_retornado, estilo)
ButtonSpec = tuple[str, Any, str]


class _ModalDialog(ctk.CTkToplevel):
    """Casca de modal com cabeçalho/corpo/rodapé. Uso interno — prefira as
    funções ``confirm_dialog`` / ``tri_state_dialog`` / ``alert_dialog``."""

    def __init__(
        self,
        parent: Any,
        title: str,
        message: str,
        buttons: Sequence[ButtonSpec],
        *,
        default: Any,
        title_color: Any = THEME_TEXT_MAIN,
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.result = default
        self._default = default
        # preserva o grab atual (ex.: outro modal aberto) para restaurar ao fechar
        try:
            self._previous_grab = self.grab_current()
        except Exception:
            self._previous_grab = None

        self.title(title)
        self.configure(fg_color=THEME_PANEL_BG)
        self.resizable(False, False)

        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=SPACE_XL, pady=SPACE_LG)
        ctk.CTkLabel(
            wrapper,
            text=title,
            font=font_section(),
            text_color=title_color,
            wraplength=440,
            justify="left",
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrapper,
            text=message,
            text_color=THEME_TEXT_SUB,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(SPACE_SM, SPACE_LG))

        bar = ctk.CTkFrame(wrapper, fg_color="transparent")
        bar.pack(anchor="e")
        main_button = None
        safe_button = None
        for text, value, style in buttons:
            factory = _FACTORY[style]
            button = factory(bar, text, lambda v=value: self._choose(v))
            button.pack(side="left", padx=(SPACE_SM, 0))
            if style in ("primary", "danger"):
                main_button = button
            if value == default and safe_button is None:
                safe_button = button

        # Em diálogo destrutivo o Enter **não** confirma: evita apagar algo com um
        # Enter reflexo (ESPEC_UI_UX §6). O foco também aponta para a saída segura,
        # mas hoje isso é só intenção — ``focus_set`` em ``CTkButton`` não retém o
        # foco (o Tk devolve o próprio toplevel), então a proteção real é o binding.
        enter_value = self._default if danger else buttons[-1][1]
        self.bind("<Escape>", lambda _e: self._choose(self._default))
        self.bind("<Return>", lambda _e: self._choose(enter_value))
        self.protocol("WM_DELETE_WINDOW", lambda: self._choose(self._default))

        self._center_over(parent)
        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.grab_set()
        focus_button = (safe_button or main_button) if danger else main_button
        if focus_button is not None:
            focus_button.focus_set()
        self.wait_window()

    def _choose(self, value: Any) -> None:
        self.result = value
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        # devolve o grab ao modal pai, se havia um
        if self._previous_grab is not None:
            try:
                self._previous_grab.grab_set()
            except Exception:
                pass

    def _center_over(self, parent: Any) -> None:
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            owner = self.grab_current() or parent
            px, py = owner.winfo_rootx(), owner.winfo_rooty()
            pw, ph = owner.winfo_width(), owner.winfo_height()
            x = px + max((pw - width) // 2, 0)
            y = py + max((ph - height) // 3, 0)
        except Exception:
            x = y = 120
        self.geometry(f"+{x}+{y}")


def confirm_dialog(
    parent: Any,
    title: str,
    message: str,
    *,
    danger: bool = False,
    confirm_text: str = "Sim",
    cancel_text: str = "Não",
) -> bool:
    """Confirmação Sim/Não temática. Retorna ``True`` se confirmado (``Esc``,
    fechar a janela ou Não retornam ``False``). Com ``danger=True`` o botão de
    confirmação usa a cor de perigo do tema (o rótulo segue sendo ``confirm_text``,
    então serve tanto para excluir quanto para outras ações arriscadas) e o teclado
    passa a favorecer a saída segura — ver ``_ModalDialog``."""
    dialog = _ModalDialog(
        parent,
        title,
        message,
        [
            (cancel_text, False, "secondary"),
            (confirm_text, True, "danger" if danger else "primary"),
        ],
        default=False,
        title_color=THEME_DANGER if danger else THEME_TEXT_MAIN,
        danger=danger,
    )
    return bool(dialog.result)


def tri_state_dialog(
    parent: Any,
    title: str,
    message: str,
    *,
    yes_text: str = "Sim",
    no_text: str = "Não",
    cancel_text: str = "Cancelar",
) -> bool | None:
    """Escolha de três vias (equivalente a ``askyesnocancel``): retorna ``True``
    (Sim), ``False`` (Não) ou ``None`` (Cancelar / Esc / fechar)."""
    dialog = _ModalDialog(
        parent,
        title,
        message,
        [
            (cancel_text, None, "secondary"),
            (no_text, False, "secondary"),
            (yes_text, True, "primary"),
        ],
        default=None,
    )
    return dialog.result


def alert_dialog(
    parent: Any,
    title: str,
    message: str,
    *,
    kind: str = "info",
    ok_text: str = "OK",
) -> None:
    """Alerta bloqueante com um único botão (OK). ``kind`` ∈
    {info, success, warning, error} apenas colore o título."""
    _ModalDialog(
        parent,
        title,
        message,
        [(ok_text, None, "primary")],
        default=None,
        title_color=_TITLE_COLOR.get(kind, THEME_TEXT_MAIN),
    )
