"""Toasts: notificação não-bloqueante no canto inferior-direito da janela.

Empilha do rodapé para cima, some sozinho e — quando a ação permite voltar
atrás — carrega um botão de ação (``Desfazer``), que é o que a ESPEC_UI_UX §5.1
pede para exclusões reversíveis.

    toasts = ToastStack(app)
    toasts.show("Configuracoes salvas.", kind="success")
    toasts.show("Bye removido.", kind="success", action=("Desfazer", restaurar))

Um toast com ação vive mais tempo (``UNDO_DURATION_MS``): desfazer só faz
sentido se a pessoa tiver tempo de ler e clicar.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..theme import (
    SIZE_BODY,
    SPACE_SM,
    THEME_ACCENT,
    THEME_DANGER,
    THEME_SUCCESS,
    THEME_WARNING,
)

# Duração padrão e a maior, usada quando há ação para clicar.
DURATION_MS = 3500
UNDO_DURATION_MS = 8000

# kind -> (preenchimento, cor do texto sobre o preenchimento). As cores de texto
# são literais porque dependem do fundo do próprio toast, não do tema da janela;
# viram token na F3.3, junto com o resto da tokenização de cores.
_PALETTE: dict[str, tuple[Any, Any]] = {
    "info":    (THEME_ACCENT,  ("#FFFFFF", "#0B0F19")),
    "success": (THEME_SUCCESS, ("#FFFFFF", "#FFFFFF")),
    "warning": (THEME_WARNING, ("#0B0F19", "#0B0F19")),
    "error":   (THEME_DANGER,  ("#FFFFFF", "#FFFFFF")),
}

ToastAction = tuple[str, Callable[[], None]]


class ToastStack:
    """Pilha de toasts de uma janela. Uma instância por janela hospedeira."""

    def __init__(self, host: Any, *, margin: int = 20, bottom: int = 40, gap: int = 8) -> None:
        self._host = host
        self._margin = margin
        self._bottom = bottom
        self._gap = gap
        self._toasts: list[ctk.CTkFrame] = []

    @property
    def active(self) -> list[ctk.CTkFrame]:
        """Toasts na tela, do mais antigo para o mais recente."""
        return list(self._toasts)

    def show(
        self,
        message: str,
        *,
        kind: str = "info",
        duration_ms: int | None = None,
        action: ToastAction | None = None,
    ) -> ctk.CTkFrame:
        background, foreground = _PALETTE.get(kind, _PALETTE["info"])
        if duration_ms is None:
            duration_ms = UNDO_DURATION_MS if action else DURATION_MS

        toast = ctk.CTkFrame(self._host, fg_color=background, corner_radius=8)
        row = ctk.CTkFrame(toast, fg_color="transparent")
        row.pack(padx=14, pady=8)
        ctk.CTkLabel(
            row,
            text=message,
            text_color=foreground,
            font=ctk.CTkFont(size=SIZE_BODY),
            wraplength=320,
            justify="left",
        ).pack(side="left")

        if action is not None:
            label, callback = action
            ctk.CTkButton(
                row,
                text=label,
                width=90,
                height=26,
                fg_color="transparent",
                hover_color=background,
                text_color=foreground,
                border_width=1,
                border_color=foreground,
                font=ctk.CTkFont(size=SIZE_BODY, weight="bold"),
                command=lambda: self._fire(toast, callback),
            ).pack(side="left", padx=(SPACE_SM * 2, 0))

        self._toasts.append(toast)
        self.restack()
        try:
            toast.lift()
            self._host.after(duration_ms, lambda: self.dismiss(toast))
        except Exception:
            pass
        return toast

    def dismiss(self, toast: ctk.CTkFrame) -> None:
        """Tira um toast da pilha. Idempotente — o timer pode chegar depois do clique."""
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        try:
            toast.destroy()
        except Exception:
            pass
        self.restack()

    def clear(self) -> None:
        for toast in list(self._toasts):
            self.dismiss(toast)

    def restack(self) -> None:
        """Reposiciona os toasts ativos empilhados acima da statusbar."""
        offset = self._bottom
        for toast in reversed(self._toasts):
            try:
                toast.update_idletasks()
                height = toast.winfo_reqheight()
                toast.place(relx=1.0, rely=1.0, x=-self._margin, y=-offset, anchor="se")
                offset += height + self._gap
            except Exception:
                pass

    def _fire(self, toast: ctk.CTkFrame, callback: Callable[[], None]) -> None:
        """Clique na ação: fecha o toast antes de agir, para o callback poder
        abrir o seu próprio feedback sem disputar espaço com este."""
        self.dismiss(toast)
        callback()
