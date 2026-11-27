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

import logging
import tkinter
from dataclasses import dataclass
from tkinter import ttk
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

logger = logging.getLogger("src.ui.screens.pairing_arbitration")

# Onde a tecla é do campo, não do atalho da mesa.
CAIXAS_DE_TEXTO = (tkinter.Entry, tkinter.Text, tkinter.Spinbox, ttk.Entry)


@dataclass(frozen=True)
class RefreshState:
    """O painel como o árbitro o deixou, para a remontagem do tick (RG2-03).

    ``None`` em ``host._arbitration_refresh_state`` quer dizer que quem monta é
    o árbitro (abriu o painel, buscou, lançou): aí vale a primeira mesa e o
    foco na tabela.
    """

    pairing_id: int | None
    foco_na_tabela: bool
    rascunho: str | None


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
        if getattr(self.host, "_current_view_method", "") != VIEW_METHOD:
            return
        # RG2-03: com um diálogo aberto ou o cursor num campo, o árbitro está no
        # meio de algo; remontar agora trocaria a mesa-alvo ou levaria o foco
        # para a tabela, onde o próximo "1" vira 1-0. Espera o ciclo seguinte.
        if self._arbitro_ocupado():
            self.schedule()
            return
        self.host._arbitration_refresh_state = self._capturar_estado()
        try:
            self.host.show_arbitration_panel()
        except Exception:
            # RGS-31: quem reagenda é a própria montagem do painel; se ela
            # falhava, o laço morria calado. O erro vai ao log com o traceback
            # e não sobe ao Tk — um diálogo a cada ciclo travaria a mesa.
            logger.exception(
                "Falha na auto-atualização do painel do árbitro; nova tentativa no próximo ciclo"
            )
        finally:
            self.host._arbitration_refresh_state = None
            # Religa só se a montagem não chegou a agendar (o caminho feliz já
            # agendou; ``schedule`` respeita a auto-atualização desligada).
            if self.host._arbitration_refresh_job is None:
                self.schedule()

    def _arbitro_ocupado(self) -> bool:
        """Diálogo aberto (janela filha visível) ou foco num campo de texto."""
        host = self.host
        for filho in host.winfo_children():
            if isinstance(filho, tkinter.Toplevel) and filho.winfo_exists() and filho.winfo_viewable():
                return True
        try:
            foco = host.focus_get()
        except (KeyError, tkinter.TclError):  # foco num widget que o Tk já soltou
            return False
        return isinstance(foco, CAIXAS_DE_TEXTO)

    def _capturar_estado(self) -> RefreshState:
        """O que a remontagem do tick precisa devolver ao árbitro como estava."""
        host = self.host
        tabela = getattr(host, "arbitration_pending_tree", None)
        pairing_id = None
        foco_na_tabela = False
        if tabela is not None and tabela.winfo_exists():
            selecionado = tabela.selection()
            if selecionado:
                pairing_id = host.arbitration_pending_row_map.get(selecionado[0])
            try:
                foco_na_tabela = host.focus_get() == tabela
            except (KeyError, tkinter.TclError):
                foco_na_tabela = False
        busca = getattr(host, "arbitration_pending_query_entry", None)
        rascunho = busca.get() if busca is not None and busca.winfo_exists() else None
        return RefreshState(pairing_id=pairing_id, foco_na_tabela=foco_na_tabela, rascunho=rascunho)

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
