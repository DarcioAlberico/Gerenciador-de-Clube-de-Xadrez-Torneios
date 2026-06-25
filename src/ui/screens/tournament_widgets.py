from __future__ import annotations

from ..support import *

from src.services.pairing.acceleration import acceleration_spec
from src.services.pairing import (
    DEFAULT_PLAYER_TIEBREAKS,
    DEFAULT_TEAM_TIEBREAKS,
    PLAYER_TIEBREAKS,
    TEAM_TIEBREAKS,
    parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
)
from src.services.prizes import PRIZE_POLICIES
from src.services.list_layouts import DEFAULT_STANDINGS_COLUMNS, STANDINGS_COLUMNS
from src.services.chess_results import normalize_results_url


class TiebreakSequenceEditor(ctk.CTkFrame):
    """Editor ordenável de critérios de desempate (spec E1/E2).

    Mantém uma lista ordenada de códigos de critério; expõe `get_sequence()` no
    formato persistido. A ordem aqui é aplicada DEPOIS dos pontos (sempre o
    primário) e ANTES dos critérios técnicos finais (rating/nome).
    """

    def __init__(
        self,
        master: Any,
        registry: dict[str, Any],
        default_codes: list[str],
        initial_codes: list[str] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._registry = registry
        self._default_codes = list(default_codes)
        self._codes = list(initial_codes) if initial_codes else list(default_codes)
        self.grid_columnconfigure(0, weight=1)
        self._render()

    def get_sequence(self) -> list[dict[str, Any]]:
        return [{"code": code, "params": {}} for code in self._codes]

    def _criterion_label(self, code: str) -> str:
        criterion = self._registry.get(code)
        return criterion.label if criterion is not None else code

    def _move(self, index: int, delta: int) -> None:
        target = index + delta
        if 0 <= target < len(self._codes):
            self._codes[index], self._codes[target] = self._codes[target], self._codes[index]
            self._render()

    def _remove(self, index: int) -> None:
        if len(self._codes) > 1 and 0 <= index < len(self._codes):
            del self._codes[index]
            self._render()

    def _add(self, code: str | None) -> None:
        if code and code in self._registry and code not in self._codes:
            self._codes.append(code)
            self._render()

    def _reset(self) -> None:
        self._codes = list(self._default_codes)
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        for index, code in enumerate(self._codes):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", pady=(0, 4))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"{index + 1}. {self._criterion_label(code)}", anchor="w").grid(
                row=0, column=0, sticky="ew"
            )
            up = ctk.CTkButton(row, text="↑", width=34, command=lambda i=index: self._move(i, -1))
            up.grid(row=0, column=1, padx=2)
            down = ctk.CTkButton(row, text="↓", width=34, command=lambda i=index: self._move(i, 1))
            down.grid(row=0, column=2, padx=2)
            remove = ctk.CTkButton(
                row, text="✕", width=34, fg_color=THEME_DANGER, hover_color=THEME_DANGER_HOVER,
                command=lambda i=index: self._remove(i),
            )
            remove.grid(row=0, column=3, padx=2)
            if index == 0:
                up.configure(state="disabled")
            if index == len(self._codes) - 1:
                down.configure(state="disabled")
            if len(self._codes) <= 1:
                remove.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=len(self._codes), column=0, sticky="ew", pady=(4, 0))
        footer.grid_columnconfigure(0, weight=1)

        available = [code for code in self._registry if code not in self._codes]
        if available:
            label_to_code = {self._criterion_label(code): code for code in available}
            add_menu = ctk.CTkOptionMenu(footer, values=list(label_to_code.keys()), width=230)
            add_menu.grid(row=0, column=0, sticky="w")
            add_menu.set(next(iter(label_to_code)))
            ctk.CTkButton(
                footer, text="Adicionar", width=110,
                command=lambda: self._add(label_to_code.get(add_menu.get())),
            ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            footer, text="Restaurar padrão FIDE", width=180, command=self._reset
        ).grid(row=0, column=2, padx=(8, 0))


class PrizeEditor(ctk.CTkFrame):
    """Editor de prêmios em linhas dinâmicas (spec E4).

    Cada linha é um prêmio (tipo, rótulo, categoria, faixa de colocação, valor).
    `get_rows()` devolve os prêmios atuais para o PrizeService persistir.
    """

    KIND_LABELS = {
        "overall": "Geral",
        "category": "Categoria",
        "special": "Especial",
        "board": "Tabuleiro",
    }

    def __init__(self, master: Any, initial_rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self._kind_by_label = {label: code for code, label in self.KIND_LABELS.items()}
        self._data = [self._normalize(prize) for prize in (initial_rows or [])]
        self._widgets: list[dict[str, Any]] = []
        self.grid_columnconfigure(0, weight=1)
        self._render()

    @staticmethod
    def _normalize(prize: dict[str, Any]) -> dict[str, str]:
        amount = prize.get("amount")
        return {
            "kind": str(prize.get("kind") or "overall"),
            "label": str(prize.get("label") or ""),
            "category": str(prize.get("category") or ""),
            "rank_from": str(prize.get("rank_from") or 1),
            "rank_to": str(prize.get("rank_to") or prize.get("rank_from") or 1),
            "amount": "" if amount in (None, "") else str(amount),
        }

    def _sync(self) -> None:
        for data, widgets in zip(self._data, self._widgets):
            data["kind"] = self._kind_by_label.get(widgets["kind"].get(), "overall")
            data["label"] = widgets["label"].get().strip()
            data["category"] = widgets["category"].get().strip()
            data["rank_from"] = widgets["rank_from"].get().strip()
            data["rank_to"] = widgets["rank_to"].get().strip()
            data["amount"] = widgets["amount"].get().strip()

    def get_rows(self) -> list[dict[str, Any]]:
        self._sync()
        return [dict(data) for data in self._data]

    def _add(self) -> None:
        self._sync()
        self._data.append(self._normalize({}))
        self._render()

    def _remove(self, index: int) -> None:
        self._sync()
        if 0 <= index < len(self._data):
            del self._data[index]
            self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._widgets = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="w", pady=(0, 2))
        columns = [("Tipo", 110), ("Premio", 170), ("Categoria", 120), ("De", 46), ("Ate", 46), ("Valor", 90), ("", 36)]
        for index, (text, width) in enumerate(columns):
            ctk.CTkLabel(header, text=text, width=width, anchor="w").grid(row=0, column=index, padx=2, sticky="w")

        for index, data in enumerate(self._data):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.grid(row=index + 1, column=0, sticky="w", pady=1)
            kind = ctk.CTkOptionMenu(row, values=list(self.KIND_LABELS.values()), width=110)
            kind.set(self.KIND_LABELS.get(data["kind"], "Geral"))
            kind.grid(row=0, column=0, padx=2)
            label = ctk.CTkEntry(row, width=170)
            label.insert(0, data["label"])
            label.grid(row=0, column=1, padx=2)
            category = ctk.CTkEntry(row, width=120)
            category.insert(0, data["category"])
            category.grid(row=0, column=2, padx=2)
            rank_from = ctk.CTkEntry(row, width=46)
            rank_from.insert(0, data["rank_from"])
            rank_from.grid(row=0, column=3, padx=2)
            rank_to = ctk.CTkEntry(row, width=46)
            rank_to.insert(0, data["rank_to"])
            rank_to.grid(row=0, column=4, padx=2)
            amount = ctk.CTkEntry(row, width=90)
            amount.insert(0, data["amount"])
            amount.grid(row=0, column=5, padx=2)
            ctk.CTkButton(
                row, text="✕", width=36, fg_color=THEME_DANGER, hover_color=THEME_DANGER_HOVER,
                command=lambda i=index: self._remove(i),
            ).grid(row=0, column=6, padx=2)
            self._widgets.append(
                {"kind": kind, "label": label, "category": category,
                 "rank_from": rank_from, "rank_to": rank_to, "amount": amount}
            )

        ctk.CTkButton(self, text="Adicionar premio", width=160, command=self._add).grid(
            row=len(self._data) + 1, column=0, sticky="w", pady=(6, 0)
        )


class ColumnLayoutEditor(ctk.CTkFrame):
    """Editor de colunas de lista: mostrar/ocultar + ordem + largura (spec E7 / Fase F).

    Aceita `initial` como lista de códigos ou de {"key","width"}. `get_columns()`
    devolve specs [{"key","width"}] (largura 0 = automática).
    """

    def __init__(
        self,
        master: Any,
        columns: dict[str, str],
        default_keys: list[str],
        initial: list[Any] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._columns = dict(columns)
        self._default = list(default_keys)
        self._keys: list[str] = []
        self._widths: dict[str, int] = {}
        for entry in initial or []:
            if isinstance(entry, dict):
                key = str(entry.get("key") or "").strip()
                width = int(entry.get("width") or 0)
            else:
                key, width = str(entry).strip(), 0
            if key in self._columns and key not in self._keys:
                self._keys.append(key)
                self._widths[key] = max(0, width)
        if not self._keys:
            self._keys = list(default_keys)
        self._width_widgets: list[Any] = []
        self.grid_columnconfigure(0, weight=1)
        self._render()

    def get_columns(self) -> list[dict[str, Any]]:
        self._sync()
        return [{"key": key, "width": self._widths.get(key, 0)} for key in self._keys]

    def _label(self, key: str) -> str:
        return self._columns.get(key, key)

    def _sync(self) -> None:
        for key, widget in zip(self._keys, self._width_widgets):
            raw = widget.get().strip()
            try:
                self._widths[key] = max(0, int(raw)) if raw else 0
            except ValueError:
                self._widths[key] = 0

    def _move(self, index: int, delta: int) -> None:
        self._sync()
        target = index + delta
        if 0 <= target < len(self._keys):
            self._keys[index], self._keys[target] = self._keys[target], self._keys[index]
            self._render()

    def _remove(self, index: int) -> None:
        self._sync()
        if len(self._keys) > 1 and 0 <= index < len(self._keys):
            del self._keys[index]
            self._render()

    def _add(self, key: str | None) -> None:
        self._sync()
        if key and key in self._columns and key not in self._keys:
            self._keys.append(key)
            self._render()

    def _reset(self) -> None:
        self._keys = list(self._default)
        self._widths = {}
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._width_widgets = []
        for index, key in enumerate(self._keys):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", pady=(0, 3))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"{index + 1}. {self._label(key)}", anchor="w").grid(
                row=0, column=0, sticky="ew"
            )
            width_entry = ctk.CTkEntry(row, width=64, placeholder_text="auto")
            current_width = self._widths.get(key, 0)
            if current_width:
                width_entry.insert(0, str(current_width))
            width_entry.grid(row=0, column=1, padx=2)
            self._width_widgets.append(width_entry)
            up = ctk.CTkButton(row, text="↑", width=34, command=lambda i=index: self._move(i, -1))
            up.grid(row=0, column=2, padx=2)
            down = ctk.CTkButton(row, text="↓", width=34, command=lambda i=index: self._move(i, 1))
            down.grid(row=0, column=3, padx=2)
            remove = ctk.CTkButton(
                row, text="✕", width=34, fg_color=THEME_DANGER, hover_color=THEME_DANGER_HOVER,
                command=lambda i=index: self._remove(i),
            )
            remove.grid(row=0, column=4, padx=2)
            if index == 0:
                up.configure(state="disabled")
            if index == len(self._keys) - 1:
                down.configure(state="disabled")
            if len(self._keys) <= 1:
                remove.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=len(self._keys), column=0, sticky="ew", pady=(4, 0))
        footer.grid_columnconfigure(0, weight=1)
        available = [key for key in self._columns if key not in self._keys]
        if available:
            label_to_key = {self._label(key): key for key in available}
            add_menu = ctk.CTkOptionMenu(footer, values=list(label_to_key.keys()), width=210)
            add_menu.grid(row=0, column=0, sticky="w")
            add_menu.set(next(iter(label_to_key)))
            ctk.CTkButton(
                footer, text="Adicionar coluna", width=150,
                command=lambda: self._add(label_to_key.get(add_menu.get())),
            ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(footer, text="Restaurar padrao", width=150, command=self._reset).grid(
            row=0, column=2, padx=(8, 0)
        )
