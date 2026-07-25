"""Liberação de janelas customtkinter dos trackers globais após ``destroy()``.

O customtkinter registra cada janela (``CTk``/``CTkToplevel``) em containers de
classe globais — ``ScalingTracker.window_dpi_scaling_dict`` /
``window_widgets_dict`` e ``AppearanceModeTracker.app_list`` /
``callback_list`` — e **não** as remove em ``destroy()``. Criar e destruir muitas
janelas no mesmo processo (como nos testes de UI, que constroem uma
``AlbericusApp`` inteira por teste) retém todas elas na memória e ainda deixa
callbacks ``after`` órfãos disparando ``invalid command name`` no Tcl. Esta
função desfaz esse registro para as janelas já destruídas.

Mantida como utilitário puro de suporte a testes (não toca o código de
produção), tolerante a falhas: nunca deve derrubar um ``tearDown``.
"""
from __future__ import annotations

try:
    from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker import (
        AppearanceModeTracker,
    )
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
except Exception:  # pragma: no cover - depende da estrutura interna do customtkinter
    AppearanceModeTracker = None
    ScalingTracker = None


def _is_dead(window) -> bool:
    """True se a janela/widget já foi destruída (ou o interpretador Tcl morreu)."""
    try:
        return not bool(window.winfo_exists())
    except Exception:
        return True


def _callback_owner_dead(callback) -> bool:
    owner = getattr(callback, "__self__", None)
    if owner is None:
        return False  # função solta, sem janela associada: preservar
    return _is_dead(owner)


def cancel_pending_callbacks(window) -> None:
    """Cancela todos os ``after`` pendentes de uma janela, antes do ``destroy()``.

    Callbacks órfãos (a animação da barra de progresso, o ``check_dpi_scaling``
    interno do customtkinter) continuam agendados no interpretador Tcl depois da
    janela morrer e chegam a atrapalhar a criação da raiz seguinte. Tolerante a
    falhas: nunca deve derrubar um ``tearDown``.
    """
    try:
        jobs = window.tk.call("after", "info")
    except Exception:
        return
    for job in jobs:
        try:
            window.after_cancel(job)
        except Exception:
            pass


def release_dead_ctk_windows() -> None:
    """Remove dos trackers globais do customtkinter as janelas já destruídas.

    Idempotente. Deve ser chamada **após** ``window.destroy()``.
    """
    if ScalingTracker is not None:
        for window in list(ScalingTracker.window_dpi_scaling_dict):
            if _is_dead(window):
                ScalingTracker.window_dpi_scaling_dict.pop(window, None)
        for window in list(ScalingTracker.window_widgets_dict):
            if _is_dead(window):
                ScalingTracker.window_widgets_dict.pop(window, None)

    if AppearanceModeTracker is not None:
        AppearanceModeTracker.app_list[:] = [
            window for window in AppearanceModeTracker.app_list if not _is_dead(window)
        ]
        AppearanceModeTracker.callback_list[:] = [
            callback
            for callback in AppearanceModeTracker.callback_list
            if not _callback_owner_dead(callback)
        ]
