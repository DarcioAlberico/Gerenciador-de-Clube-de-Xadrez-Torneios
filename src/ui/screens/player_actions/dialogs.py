"""Diálogos das ações na linha do jogador (RGS-22, RGS-23).

Três diálogos curtos sobre a mesma casca (``Dialog`` canônico: Esc fecha, cabe
na tela, Enter confirma). O alvo da espec é contado em ações — **bye: menu,
tipo, motivo, Enter; retirar/reintegrar: menu, escopo, motivo, Enter** — e
cada diálogo foi desenhado para isso: o tipo/escopo já vem marcado pelo item
de menu escolhido, o foco nasce no motivo e o Enter grava.

Os diálogos NÃO bloqueiam (sem ``wait_window``): quem abre recebe o objeto e
o teste dirige os widgets como o árbitro faria. O recado de erro aparece no
próprio diálogo, sem fechá-lo — fechar apagaria o motivo já digitado.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from src.services.constants import player_full_name
from src.services.pairing.participation import (
    PARTICIPATION_STATUSES,
    STATUS_WITHDRAWN,
    status_description,
)

from ...components import Dialog, actions_bar
from ...i18n import t
from ...theme import SPACE_LG, SPACE_SM, SPACE_XS, THEME_DANGER, THEME_TEXT_SUB, THEME_WARNING_TEXT
from .controller import PlayerActionsController
from .state import (
    SCOPE_ROUND,
    SCOPE_WITHDRAWN,
    bye_type_labels,
    scope_labels,
)

WRAP = 470


class PlayerDialog:
    """Casca comum: título, linhas de texto, motivo, recado de erro e rodapé."""

    size = (560, 400)

    def __init__(
        self,
        host: Any,
        controller: PlayerActionsController,
        player: dict[str, Any],
        *,
        title: str,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self.host = host
        self.controller = controller
        self.player = player
        self.player_id = int(player["id"])
        self.tournament_id = int(player["tournament_id"])
        self.name = player_full_name(player)
        self.on_done = on_done
        self.done = False
        self.window = Dialog(host, title, size=self.size)
        self._row = 0
        self.reason: Any = None
        self.error_label: Any = None
        self.primary_button: Any = None

    # ---- Montagem --------------------------------------------------------- #

    def _place(self, widget: Any, *, pady: tuple[int, int] = (SPACE_SM, 0), sticky: str = "ew") -> Any:
        widget.grid(row=self._row, column=0, padx=SPACE_LG, pady=pady, sticky=sticky)
        self._row += 1
        return widget

    def _text(self, text: str = "", *, color: Any = THEME_TEXT_SUB) -> ctk.CTkLabel:
        return self._place(
            ctk.CTkLabel(
                self.window, text=text, text_color=color, anchor="w", justify="left", wraplength=WRAP
            )
        )

    def _segmented(self, values: list[str], initial: str, command: Callable[[str], Any] | None = None) -> Any:
        seletor = ctk.CTkSegmentedButton(self.window, values=values, command=command)
        seletor.set(initial)
        return self._place(seletor, sticky="w")

    def _finish(self, primary_text: str, reason_hint: str) -> None:
        """Motivo, recado de erro e rodapé — sempre nesta ordem, no fim."""
        self.reason = self._place(ctk.CTkEntry(self.window, placeholder_text=reason_hint), pady=(SPACE_LG, 0))
        self.error_label = self._place(
            ctk.CTkLabel(self.window, text="", text_color=THEME_DANGER, anchor="w", justify="left", wraplength=WRAP),
            pady=(SPACE_XS, 0),
        )
        barra = actions_bar(
            self.window,
            row=self._row,
            primary=(primary_text, self.confirm),
            secondary=[(t("dialog.cancel"), self.window.close)],
        )
        self.primary_button = barra.winfo_children()[-1]
        # O foco nasce no motivo: o tipo/escopo já veio marcado pelo menu, e o
        # que falta é escrever e dar Enter (as 4 ações da espec).
        self.reason.focus_set()

    # ---- Ação ------------------------------------------------------------- #

    def reason_text(self) -> str:
        return " ".join(str(self.reason.get() if self.reason is not None else "").split())

    def apply(self) -> str:
        """Grava e devolve o recado de sucesso. Levanta ``AppError`` com o motivo."""
        raise NotImplementedError

    def confirm(self) -> None:
        if self.primary_button is not None and str(self.primary_button.cget("state")) == "disabled":
            return
        try:
            mensagem = self.apply()
        except Exception as exc:  # noqa: BLE001 — o recado fica no diálogo, que segue aberto
            if self.error_label is not None:
                self.error_label.configure(text=str(exc))
            return
        self.done = True
        self.window.close()
        self.host._show_toast(mensagem, kind="success")
        if self.on_done is not None:
            self.on_done()


class ByeDialog(PlayerDialog):
    """Bye solicitado (H ½ / Z 0) com o saldo da política — e o W.O. quando a
    rodada escolhida já foi gerada (RGS-22 "Faltar só à rodada N", RGS-23)."""

    def __init__(
        self,
        host: Any,
        controller: PlayerActionsController,
        player: dict[str, Any],
        *,
        bye_type: str = "H",
        round_number: int | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            host, controller, player, title=t("player_actions.bye.title", nome=player_full_name(player)), on_done=on_done
        )
        self.mode = "bye"
        self.situation: dict[str, Any] = {}
        rodadas = controller.bye_rounds(self.tournament_id, self.player_id)
        self.round_labels = {t("player_actions.round", rodada=numero): numero for numero in rodadas}
        escolhida = int(round_number or (rodadas[0] if rodadas else controller.next_round(self.tournament_id)))
        if escolhida not in self.round_labels.values():
            self.round_labels[t("player_actions.round", rodada=escolhida)] = escolhida
        self.type_labels = bye_type_labels()
        self.type_codes = {rotulo: codigo for codigo, rotulo in self.type_labels.items()}

        self.balance_label = self._text(
            t("player_actions.bye.balance", saldo=controller.bye_balance(self.tournament_id, self.player_id))
        )
        self.round_option = self._place(
            ctk.CTkOptionMenu(
                self.window,
                values=list(self.round_labels),
                command=lambda _valor: self.refresh_mode(),
            ),
            sticky="w",
        )
        self.round_option.set(
            next(rotulo for rotulo, numero in self.round_labels.items() if numero == escolhida)
        )
        self.type_selector = self._segmented(
            list(self.type_labels.values()), self.type_labels.get(bye_type.upper(), self.type_labels["H"])
        )
        self.info_label = self._text(color=THEME_WARNING_TEXT)
        self._finish(t("player_actions.bye.confirm"), t("player_actions.reason.hint"))
        self.refresh_mode()

    @property
    def round_number(self) -> int:
        return int(self.round_labels[self.round_option.get()])

    @property
    def bye_type(self) -> str:
        return self.type_codes.get(self.type_selector.get(), "H")

    def refresh_mode(self) -> None:
        """Bye (rodada por gerar), W.O. (gerada, mesa sem resultado) ou nada."""
        self.situation = self.controller.situation(self.tournament_id, self.player_id, self.round_number)
        situacao = self.situation
        texto_primario = t("player_actions.bye.confirm")
        estado = "normal"
        info = ""
        if situacao["round_status"] is None:
            self.mode = "bye"
        elif (
            situacao["round_status"] != "closed"
            and situacao["pairing_id"]
            and not situacao["is_bye"]
            and not situacao["has_result"]
        ):
            self.mode = "walkover"
            info = t(
                "player_actions.bye.generated_walkover",
                rodada=self.round_number,
                mesa=situacao["board_number"],
            )
            texto_primario = t("player_actions.bye.walkover", mesa=situacao["board_number"])
        else:
            self.mode = "blocked"
            info = t("player_actions.bye.generated_blocked", rodada=self.round_number)
            estado = "disabled"
        self.type_selector.configure(state="normal" if self.mode == "bye" else "disabled")
        self.info_label.configure(text=info)
        if self.primary_button is not None:
            self.primary_button.configure(text=texto_primario, state=estado)

    def apply(self) -> str:
        if self.mode == "walkover":
            feito = self.controller.forfeit(
                self.tournament_id, self.player_id, self.round_number, self.reason_text()
            )
            return t("player_actions.done.walkover", mesa=feito["board_number"], resultado=feito["result"])
        self.controller.request_bye(
            self.tournament_id, self.player_id, self.round_number, self.bye_type, self.reason_text()
        )
        return t("player_actions.done.bye", nome=self.name, rodada=self.round_number, tipo=self.bye_type)


class WithdrawDialog(PlayerDialog):
    """Retirar: só uma rodada (bye Z) ou mudança de estado com histórico (RGS-22)."""

    def __init__(
        self,
        host: Any,
        controller: PlayerActionsController,
        player: dict[str, Any],
        *,
        scope: str = SCOPE_WITHDRAWN,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            host,
            controller,
            player,
            title=t("player_actions.withdraw.title", nome=player_full_name(player)),
            on_done=on_done,
        )
        self.next_round = controller.next_round(self.tournament_id)
        self.scope_labels = scope_labels(self.next_round)
        self.scope_codes = {rotulo: codigo for codigo, rotulo in self.scope_labels.items()}
        self.scope_selector = self._segmented(
            list(self.scope_labels.values()),
            self.scope_labels.get(scope, self.scope_labels[SCOPE_WITHDRAWN]),
            command=lambda _valor: self.refresh_info(),
        )
        self.info_label = self._text()
        self._finish(t("player_actions.withdraw.confirm"), t("player_actions.reason.hint"))
        self.refresh_info()

    @property
    def scope(self) -> str:
        return self.scope_codes.get(self.scope_selector.get(), SCOPE_WITHDRAWN)

    def refresh_info(self) -> None:
        if self.scope == SCOPE_ROUND:
            texto = t("player_actions.withdraw.info.round", rodada=self.next_round)
        else:
            texto = t(
                "player_actions.withdraw.info.status",
                rodada=self.next_round,
                descricao=status_description(self.scope),
            )
        self.info_label.configure(text=texto)

    def apply(self) -> str:
        motivo = self.reason_text()
        if self.scope == STATUS_WITHDRAWN and not motivo:
            raise _app_error(t("player_actions.withdraw.reason_required"))
        rodada = self.controller.withdraw(self.tournament_id, self.player_id, self.scope, motivo)
        if self.scope == SCOPE_ROUND:
            return t("player_actions.done.bye", nome=self.name, rodada=rodada, tipo="Z")
        return t(
            "player_actions.done.status",
            nome=self.name,
            status=PARTICIPATION_STATUSES.get(self.scope, self.scope),
            rodada=rodada,
        )


class ReinstateDialog(PlayerDialog):
    """Reintegrar: motivo e "volta na rodada N" — a saída que não existia (RGS-22)."""

    size = (560, 320)

    def __init__(
        self,
        host: Any,
        controller: PlayerActionsController,
        player: dict[str, Any],
        *,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            host,
            controller,
            player,
            title=t("player_actions.reinstate.title", nome=player_full_name(player)),
            on_done=on_done,
        )
        status = str(player.get("player_status") or "")
        self.next_round = controller.next_round(self.tournament_id)
        self.info_label = self._text(
            t(
                "player_actions.reinstate.info",
                status=PARTICIPATION_STATUSES.get(status, status),
                descricao=status_description(status),
                rodada=self.next_round,
            )
        )
        dica = (
            t("player_actions.reinstate.reason_required")
            if status == STATUS_WITHDRAWN
            else t("player_actions.reason.hint")
        )
        self._finish(t("player_actions.reinstate.confirm"), dica)

    def apply(self) -> str:
        rodada = self.controller.reinstate(self.tournament_id, self.player_id, self.reason_text())
        return t("player_actions.done.reinstate", nome=self.name, rodada=rodada)


def _app_error(message: str) -> Exception:
    from src.services.constants import AppError

    return AppError(message)
