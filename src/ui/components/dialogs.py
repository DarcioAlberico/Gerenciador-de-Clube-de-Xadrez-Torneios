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
    report_dialog(parent, "Desempates", corpo_longo)        -> None
"""
from __future__ import annotations

from typing import Any, Sequence

import customtkinter as ctk

from ..i18n import t
from ..theme import (
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_WARNING_TEXT,
    font_section,
)
from .buttons import danger_button, neutral_button, primary_button, secondary_button
from .fields import text_area

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
    confirm_text: str | None = None,
    cancel_text: str | None = None,
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
            (cancel_text or t("dialog.no"), False, "secondary"),
            (confirm_text or t("dialog.yes"), True, "danger" if danger else "primary"),
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
    yes_text: str | None = None,
    no_text: str | None = None,
    cancel_text: str | None = None,
) -> bool | None:
    """Escolha de três vias (equivalente a ``askyesnocancel``): retorna ``True``
    (Sim), ``False`` (Não) ou ``None`` (Cancelar / Esc / fechar)."""
    dialog = _ModalDialog(
        parent,
        title,
        message,
        [
            (cancel_text or t("dialog.cancel"), None, "secondary"),
            (no_text or t("dialog.no"), False, "secondary"),
            (yes_text or t("dialog.yes"), True, "primary"),
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
    ok_text: str | None = None,
) -> None:
    """Alerta bloqueante com um único botão (OK). ``kind`` ∈
    {info, success, warning, error} apenas colore o título."""
    _ModalDialog(
        parent,
        title,
        message,
        [(ok_text or t("dialog.ok"), None, "primary")],
        default=None,
        title_color=_TITLE_COLOR.get(kind, THEME_TEXT_MAIN),
    )


class _ReportDialog(ctk.CTkToplevel):
    """Relatório longo: corpo rolável, selecionável e com ``Copiar`` (F5.7).

    Existe porque o toast é o canal errado para conteúdo que se **lê** e se
    **copia**: 320px de largura, sem rolagem, e some em 3,5 segundos. Aqui o
    corpo é um campo de texto somente-leitura — o usuário rola, seleciona um
    trecho, ou leva tudo com um clique.
    """

    def __init__(self, parent: Any, title: str, body: str, *, kind: str = "info") -> None:
        super().__init__(parent)
        try:
            self._previous_grab = self.grab_current()
        except Exception:
            self._previous_grab = None

        self.title(title)
        self.configure(fg_color=THEME_PANEL_BG)

        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=SPACE_XL, pady=SPACE_LG)
        ctk.CTkLabel(
            wrapper,
            text=title,
            font=font_section(),
            text_color=_TITLE_COLOR.get(kind, THEME_TEXT_MAIN),
            justify="left",
        ).pack(anchor="w")

        # Altura pelo conteúdo, com teto: um relatório de 60 linhas não pode
        # nascer maior que a tela (os diálogos de tamanho fixo do P3-10 são
        # justamente o que não se quer repetir).
        linhas = max(6, min(24, body.count("\n") + 2))
        self.corpo = text_area(wrapper, height=linhas * 18, width=560)
        self.corpo.pack(fill="both", expand=True, pady=(SPACE_SM, SPACE_MD))
        self.corpo.insert("1.0", body)
        # Somente leitura, mas ainda selecionável com o mouse/teclado.
        self.corpo.configure(state="disabled")

        bar = ctk.CTkFrame(wrapper, fg_color="transparent")
        bar.pack(anchor="e")
        self.copy_button = neutral_button(bar, t("dialog.copy"), self._copy)
        self.copy_button.pack(side="left", padx=(0, SPACE_SM))
        primary_button(bar, t("dialog.close"), self._close).pack(side="left")

        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._center_over(parent)
        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.grab_set()
        self._body = body

    def _copy(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self._body)
            self.copy_button.configure(text=t("dialog.copied"))
        except Exception:  # pragma: no cover - area de transferencia indisponivel
            pass

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
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


def report_dialog(parent: Any, title: str, body: str, *, kind: str = "info") -> None:
    """Mostra ``body`` num diálogo rolável com ``Copiar``. Bloqueia até fechar."""
    dialog = _ReportDialog(parent, title, body, kind=kind)
    dialog.wait_window()
