"""Assistente de entrada tardia — uma tela (RGS-24).

Nome, rating (com a busca na base oficial FIDE/CBX que o app já importa),
"entra na rodada N" e os pontos por rodada perdida. As rodadas 1…N−1 do
entrante são células DERIVADAS no TRF (Z/H/F a partir dos pontos iniciais):
nada é gravado em rodada fechada, o limite de bye não é consumido e a
`bye_policy` fica como está.

Substitui o aviso antigo ("foge ao regulamento", sem acento), que dizia uma
coisa imprecisa e não mostrava o que de fato ia acontecer.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from src.services.pairing.player_round import LATE_ENTRY_CELL_POINTS

from ...components import Dialog, actions_bar, secondary_button
from ...i18n import t
from ...theme import SPACE_LG, SPACE_SM, SPACE_XS, THEME_DANGER, THEME_TEXT_SUB
from .controller import PlayerActionsController
from .state import points_text

WRAP = 470


def _per_round_label(value: float) -> str:
    return t("late_entry.per_round", pontos=points_text(value))


class LateEntryDialog:
    """Uma tela: identificação, rating, rodada de entrada e pontos."""

    def __init__(
        self,
        host: Any,
        controller: PlayerActionsController,
        tournament_id: int,
        *,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self.host = host
        self.controller = controller
        self.tournament_id = int(tournament_id)
        self.on_done = on_done
        self.result: dict[str, Any] | None = None
        self._found: dict[str, Any] = {}
        self.window = Dialog(host, t("late_entry.title"), size=(580, 520))
        self._row = 0

        plano = controller.late_entry_plan(self.tournament_id)
        self.points_labels = {_per_round_label(valor): valor for valor in LATE_ENTRY_CELL_POINTS}

        busca = ctk.CTkFrame(self.window, fg_color="transparent")
        busca.grid_columnconfigure(0, weight=1)
        self.official_id = ctk.CTkEntry(busca, placeholder_text=t("late_entry.official_id.hint"))
        self.official_id.grid(row=0, column=0, sticky="ew")
        secondary_button(busca, t("late_entry.lookup"), self.lookup, width=90).grid(
            row=0, column=1, padx=(SPACE_SM, 0)
        )
        self._label(t("late_entry.official_id"))
        self._place(busca)
        self.lookup_label = self._place(self._muted(""), pady=(SPACE_XS, 0))

        self._label(t("late_entry.name"))
        self.name = self._place(ctk.CTkEntry(self.window, placeholder_text=t("late_entry.name.hint")))
        self._label(t("late_entry.rating"))
        self.rating = self._place(ctk.CTkEntry(self.window, placeholder_text="0"))

        self._label(t("late_entry.points"))
        inicial = next(
            (rotulo for rotulo, valor in self.points_labels.items() if abs(valor - plano.per_round_points) < 1e-9),
            "",
        )
        self.points_selector = self._place(
            ctk.CTkSegmentedButton(
                self.window, values=list(self.points_labels), command=lambda _v: self.refresh_plan()
            ),
            sticky="w",
        )
        if inicial:
            self.points_selector.set(inicial)
        self.plan_label = self._place(self._muted(""), pady=(SPACE_SM, 0))
        self.error_label = self._place(
            ctk.CTkLabel(self.window, text="", text_color=THEME_DANGER, anchor="w", justify="left", wraplength=WRAP),
            pady=(SPACE_XS, 0),
        )
        barra = actions_bar(
            self.window,
            row=self._row,
            primary=(t("late_entry.confirm"), self.confirm),
            secondary=[(t("dialog.cancel"), self.window.close)],
        )
        self.primary_button = barra.winfo_children()[-1]
        self.refresh_plan()
        self.name.focus_set()

    # ---- Montagem --------------------------------------------------------- #

    def _place(self, widget: Any, *, pady: tuple[int, int] = (SPACE_XS, 0), sticky: str = "ew") -> Any:
        widget.grid(row=self._row, column=0, padx=SPACE_LG, pady=pady, sticky=sticky)
        self._row += 1
        return widget

    def _label(self, text: str) -> None:
        self._place(ctk.CTkLabel(self.window, text=text, anchor="w"), pady=(SPACE_SM, 0))

    def _muted(self, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            self.window, text=text, text_color=THEME_TEXT_SUB, anchor="w", justify="left", wraplength=WRAP
        )

    # ---- Estado ----------------------------------------------------------- #

    @property
    def per_round_points(self) -> float | None:
        return self.points_labels.get(self.points_selector.get())

    def refresh_plan(self) -> None:
        """Rodada de entrada e o que as anteriores valem — antes de gravar."""
        pontos = self.per_round_points
        if pontos is None:
            configurado = self.controller.late_entry_plan(self.tournament_id)
            self.plan_label.configure(text="")
            self.error_label.configure(text=configurado.error or t("late_entry.points.choose"))
            self.primary_button.configure(state="disabled")
            return
        plano = self.controller.late_entry_plan(self.tournament_id, pontos)
        if plano.error:
            self.plan_label.configure(text="")
            self.error_label.configure(text=plano.error)
            self.primary_button.configure(state="disabled")
            return
        if len(plano.missed_rounds) == 1:
            texto = t(
                "late_entry.plan.one",
                rodada=plano.entry_round,
                cada=points_text(plano.per_round_points),
                total=points_text(plano.starting_points),
            )
        elif plano.missed_rounds:
            texto = t(
                "late_entry.plan",
                rodada=plano.entry_round,
                ultima=plano.entry_round - 1,
                cada=points_text(plano.per_round_points),
                total=points_text(plano.starting_points),
            )
        else:
            texto = t("late_entry.plan.first_round")
        self.plan_label.configure(text=texto)
        self.error_label.configure(text="")
        self.primary_button.configure(state="normal")

    def lookup(self) -> None:
        """Preenche nome e rating a partir da base oficial importada (FIDE/CBX)."""
        achado = self.controller.official_lookup(self.official_id.get())
        if not achado:
            self.lookup_label.configure(text=t("late_entry.lookup.none"))
            return
        nome = str(achado.get("name") or achado.get("surname") or "").strip()
        rating = (
            achado.get("standard_rating")
            or achado.get("international_rating")
            or achado.get("national_rating")
            or 0
        )
        if nome:
            self.name.delete(0, "end")
            self.name.insert(0, nome)
        if rating:
            self.rating.delete(0, "end")
            self.rating.insert(0, str(rating))
        self.lookup_label.configure(text=t("late_entry.lookup.found", nome=nome, rating=rating or "-"))
        self._found = achado

    def payload(self) -> dict[str, Any]:
        bruto = self.rating.get().strip()
        try:
            rating = int(bruto) if bruto else 0
        except ValueError as exc:
            raise _app_error(t("late_entry.rating.invalid")) from exc
        dados: dict[str, Any] = {"name": self.name.get(), "rating": rating}
        achado = self._found
        for chave in ("fide_id", "cbx_id", "surname", "given_name", "title", "sex", "birth_date"):
            if achado.get(chave):
                dados[chave] = str(achado[chave])
        for chave in ("national_rating", "international_rating"):
            if achado.get(chave):
                dados[chave] = int(achado[chave] or 0)
        return dados

    def confirm(self) -> None:
        if str(self.primary_button.cget("state")) == "disabled":
            return
        try:
            self.result = dict(
                self.controller.register_late_entry(
                    self.tournament_id, self.payload(), float(self.per_round_points or 0.0)
                )
            )
        except Exception as exc:  # noqa: BLE001 — recado no próprio diálogo
            self.error_label.configure(text=str(exc))
            return
        nome = " ".join(self.name.get().split())
        self.window.close()
        self.host._show_toast(
            t(
                "late_entry.done",
                nome=nome,
                rodada=self.result["entry_round"],
                pontos=points_text(float(self.result["starting_points"])),
            ),
            kind="success",
        )
        if self.on_done is not None:
            self.on_done()


def _app_error(message: str) -> Exception:
    from src.services.constants import AppError

    return AppError(message)
