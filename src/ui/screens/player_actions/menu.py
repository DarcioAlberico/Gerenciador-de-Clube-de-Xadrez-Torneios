"""Menu da linha do jogador e a porta de entrada dos diálogos (RGS-22/23/24).

``PlayerActions`` é o que as telas usam: Jogadores, Classificação e a chamada
da tela de Rodadas ligam a tabela delas com ``bind_tree`` e passam a ter, no
clique direito (ou Shift+F10 / tecla Menu), o mesmo menu:

    Bye na próxima rodada… (H ½ / Z 0)
    Faltar só à rodada N…
    ─────────────
    Retirar do torneio…
    Reintegrar…

``menu_items`` devolve a mesma lista que o menu desenha — é por ela que o
teste conta as ações e é por ela que outra tela (o menu de mesa da tela de
Rodadas, por exemplo) pode oferecer as ações de um dos dois jogadores.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from ...theme import THEME_ACCENT, THEME_PANEL_BG, THEME_TEXT_MAIN, THEME_TEXT_SUB
from .controller import PlayerActionsController
from .dialogs import ByeDialog, ReinstateDialog, WithdrawDialog
from .late_entry import LateEntryDialog
from .state import (
    ACTION_BYE,
    ACTION_MISS_ROUND,
    ACTION_REINSTATE,
    ACTION_WITHDRAW,
    SCOPE_WITHDRAWN,
    player_menu,
)

MenuItems = list[tuple[str, Callable[[], Any] | None] | None]


class PlayerActions:
    """Ações sobre um jogador, a partir de qualquer tela que o mostre."""

    def __init__(self, host: Any, on_changed: Callable[[], None] | None = None) -> None:
        self.host = host
        self.on_changed = on_changed
        self.controller = PlayerActionsController(host.db, host.pairing_service)
        self.last_dialog: Any = None

    # ---- Menu ------------------------------------------------------------- #

    def menu_items(self, player_id: int) -> MenuItems:
        """``(rótulo, comando)`` por item; comando ``None`` = item inativo."""
        jogador = self.controller.player(player_id)
        rodada = self.controller.absence_round(int(jogador["tournament_id"]), int(player_id))
        abrir = {
            ACTION_BYE: lambda: self.open_bye(player_id),
            ACTION_MISS_ROUND: lambda: self.open_miss_round(player_id),
            ACTION_WITHDRAW: lambda: self.open_withdraw(player_id),
            ACTION_REINSTATE: lambda: self.open_reinstate(player_id),
        }
        itens: MenuItems = []
        for entrada in player_menu(jogador, absence_round=rodada):
            if entrada is None:
                itens.append(None)
                continue
            itens.append((entrada.label, abrir[entrada.key] if entrada.enabled else None))
        return itens

    def popup(self, widget: Any, player_id: int, x: int, y: int) -> None:
        try:
            itens = self.menu_items(player_id)
        except Exception as exc:  # noqa: BLE001 — erro vira recado, nunca traceback
            self.host._show_error(exc)
            return
        face = 1 if ctk.get_appearance_mode() == "Dark" else 0
        menu = tk.Menu(
            widget,
            tearoff=0,
            bd=0,
            activeborderwidth=0,
            bg=THEME_PANEL_BG[face],
            fg=THEME_TEXT_MAIN[face],
            activebackground=THEME_ACCENT[face],
            activeforeground=THEME_PANEL_BG[face],
            disabledforeground=THEME_TEXT_SUB[face],
        )
        for item in itens:
            if item is None:
                menu.add_separator()
                continue
            rotulo, comando = item
            menu.add_command(
                label=rotulo, command=comando, state="normal" if comando else "disabled"
            )
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def bind_tree(self, tree: Any, player_id_of: Callable[[str], int | None]) -> None:
        """Clique direito, Shift+F10 e a tecla Menu abrem o menu da linha."""

        def pelo_mouse(evento: Any) -> str:
            linha = tree.identify_row(evento.y)
            if not linha:
                return "break"
            tree.selection_set(linha)
            tree.focus(linha)
            player_id = player_id_of(linha)
            if player_id:
                self.popup(tree, int(player_id), evento.x_root, evento.y_root)
            return "break"

        def pelo_teclado(_evento: Any = None) -> str:
            selecionadas = tree.selection()
            linha = tree.focus() or (selecionadas[0] if selecionadas else "")
            if not linha:
                return "break"
            player_id = player_id_of(linha)
            if not player_id:
                return "break"
            caixa = tree.bbox(linha) or (0, 0, 0, 0)
            x = tree.winfo_rootx() + int(caixa[0]) + 24
            y = tree.winfo_rooty() + int(caixa[1]) + int(caixa[3])
            self.popup(tree, int(player_id), x, y)
            return "break"

        tree.bind("<Button-3>", pelo_mouse, add="+")
        for sequencia in ("<Shift-F10>", "<App>"):
            try:
                tree.bind(sequencia, pelo_teclado, add="+")
            except tk.TclError:  # pragma: no cover - tecla inexistente na plataforma
                continue

    # ---- Diálogos --------------------------------------------------------- #

    def _allowed(self) -> bool:
        try:
            self.host.require_permission("tournament_write")
            return True
        except Exception as exc:  # noqa: BLE001 — sem permissão vira recado
            self.host._show_error(exc)
            return False

    def _changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()

    def _open(self, factory: Callable[[], Any]) -> Any:
        if not self._allowed():
            return None
        try:
            self.last_dialog = factory()
        except Exception as exc:  # noqa: BLE001
            self.host._show_error(exc)
            return None
        return self.last_dialog

    def open_bye(self, player_id: int, *, bye_type: str = "H", round_number: int | None = None) -> Any:
        return self._open(
            lambda: ByeDialog(
                self.host,
                self.controller,
                self.controller.player(player_id),
                bye_type=bye_type,
                round_number=round_number,
                on_done=self._changed,
            )
        )

    def open_miss_round(self, player_id: int) -> Any:
        """"Faltar só à rodada N…": o mesmo diálogo, já em Z e na rodada da falta."""
        jogador = self.controller.player(player_id)
        rodada = self.controller.absence_round(int(jogador["tournament_id"]), int(player_id))
        return self.open_bye(player_id, bye_type="Z", round_number=rodada)

    def open_withdraw(self, player_id: int, *, scope: str = SCOPE_WITHDRAWN) -> Any:
        return self._open(
            lambda: WithdrawDialog(
                self.host,
                self.controller,
                self.controller.player(player_id),
                scope=scope,
                on_done=self._changed,
            )
        )

    def open_reinstate(self, player_id: int) -> Any:
        return self._open(
            lambda: ReinstateDialog(
                self.host, self.controller, self.controller.player(player_id), on_done=self._changed
            )
        )

    def open_late_entry(self, tournament_id: int) -> Any:
        return self._open(
            lambda: LateEntryDialog(
                self.host, self.controller, int(tournament_id), on_done=self._changed
            )
        )
