"""Auto-atualização do painel do árbitro — agendamento e preferências.

Numa mesa de arbitragem o painel fica aberto o tempo todo, e o que muda vem de
fora (resultado enviado por QR, evento de relógio). Por isso ele se reagenda
sozinho; por isso também o agendamento **só** dispara se o painel ainda for a
tela aberta — recarregar por baixo de outra tela seria roubar o foco de quem
está no meio de um lançamento.

Precisa de Tk (``after``/``after_cancel``), então mora na camada de view. A
política — quais intervalos valem, qual é o padrão — é dado puro e mora em
[`state`](state.py).
"""
from __future__ import annotations

from typing import Any

from .state import (
    INLINE_LIMIT_DEFAULT,
    INLINE_LIMIT_MAX,
    INLINE_LIMIT_MIN,
    REFRESH_INTERVAL_DEFAULT,
    REFRESH_INTERVAL_MAX,
    REFRESH_INTERVAL_MIN,
)

VIEW_METHOD = "show_arbitration_panel"


class AutoRefresh:
    """Reagenda o painel, e guarda a preferência de quem mexeu no intervalo."""

    def __init__(self, host: Any, controller: Any) -> None:
        self.host = host
        self.controller = controller

    # ---- Agendamento ------------------------------------------------------ #

    def schedule(self) -> None:
        self.cancel()
        if not self.host._arbitration_auto_refresh_enabled:
            return
        self.host._arbitration_refresh_job = self.host.after(
            self.host._arbitration_refresh_interval_seconds * 1000,
            self._tick,
        )

    def cancel(self) -> None:
        if self.host._arbitration_refresh_job is None:
            return
        try:
            self.host.after_cancel(self.host._arbitration_refresh_job)
        except Exception:  # noqa: BLE001 — job ja disparado ou raiz destruida
            pass
        self.host._arbitration_refresh_job = None

    def _tick(self) -> None:
        self.host._arbitration_refresh_job = None
        # A guarda é o ponto todo: sem ela, o painel se redesenharia por cima de
        # qualquer tela que o árbitro tivesse aberto nesse meio-tempo.
        if getattr(self.host, "_current_view_method", "") == VIEW_METHOD:
            self.host.show_arbitration_panel()

    # ---- Preferências ----------------------------------------------------- #

    def toggle(self) -> None:
        ligado = not self.host._arbitration_auto_refresh_enabled
        self.host._arbitration_auto_refresh_enabled = ligado
        self.controller.save_settings({"arbitration_auto_refresh_enabled": "1" if ligado else "0"})
        if ligado:
            self.schedule()
        else:
            self.cancel()

    def set_interval(self, value: str) -> None:
        segundos = self.host._bounded_int_setting(
            {"value": value},
            "value",
            default=REFRESH_INTERVAL_DEFAULT,
            minimum=REFRESH_INTERVAL_MIN,
            maximum=REFRESH_INTERVAL_MAX,
        )
        self.host._arbitration_refresh_interval_seconds = segundos
        self.controller.save_settings({"arbitration_refresh_interval_seconds": str(segundos)})
        if self.host._arbitration_auto_refresh_enabled:
            self.schedule()

    def set_inline_limit(self, value: str) -> None:
        limite = self.host._bounded_int_setting(
            {"value": value},
            "value",
            default=INLINE_LIMIT_DEFAULT,
            minimum=INLINE_LIMIT_MIN,
            maximum=INLINE_LIMIT_MAX,
        )
        self.host._arbitration_inline_tables_limit = limite
        self.controller.save_settings({"arbitration_inline_tables_limit": str(limite)})
        # Mudar quantas mesas cabem na lista muda o que a consulta pede, então a
        # tela precisa ser remontada — não basta reagendar.
        self.host.show_arbitration_panel()
