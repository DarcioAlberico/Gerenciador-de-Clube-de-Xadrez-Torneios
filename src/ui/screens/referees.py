from __future__ import annotations

import customtkinter as ctk
from typing import Any
from ..support import AppError


class RefereePagesMixin:
    def show_referees(self) -> None:
        self._clear_content()
        self._page_title(
            "Arbitros",
            "Gerenciamento da equipe de arbitragem.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(body, width=292)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_id: dict[str, int | None] = {"value": None}
        entries: dict[str, ctk.CTkEntry] = {}
        
        fields = [
            ("name", "Nome"),
            ("federation_id", "ID Federacao"),
            ("fide_id", "FIDE ID"),
            ("cbx_id", "CBX ID"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("notes", "Observacoes")
        ]
        
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index*2, column=0, padx=16, pady=(12, 0), sticky="w")
            entry = ctk.CTkEntry(form, width=270)
            entry.grid(row=index*2+1, column=0, padx=16, pady=(4, 2), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Categoria").grid(row=option_row, column=0, padx=16, pady=(12, 0), sticky="w")
        category_option = ctk.CTkOptionMenu(form, values=["AN", "AR", "AF", "AI", "Outro"], width=270)
        category_option.grid(row=option_row + 1, column=0, padx=16, pady=(4, 2), sticky="ew")
        
        active_check = ctk.CTkCheckBox(form, text="Ativo")
        active_check.grid(row=option_row + 2, column=0, padx=16, pady=(10, 2), sticky="w")
        active_check.select()

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            list_panel,
            ["id", "name", "category", "fide_id", "cbx_id", "active"],
            {"id": "ID", "name": "Nome", "category": "Cat.", "fide_id": "FIDE", "cbx_id": "CBX", "active": "Ativo"},
            {"id": 50, "name": 200, "category": 60, "fide_id": 80, "cbx_id": 80, "active": 60}
        )
        tree.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        def clear_form() -> None:
            selected_id["value"] = None
            for entry in entries.values():
                entry.delete(0, "end")
            category_option.set("AN")
            active_check.select()

        def load_list() -> None:
            tree.delete(*tree.get_children())
            for item in self.referee_service.list_referees(active_only=False):
                tree.insert(
                    "", "end", values=(
                        item["id"],
                        item["name"],
                        item["category"],
                        item["fide_id"],
                        item["cbx_id"],
                        "Sim" if item["active"] else "Nao"
                    )
                )

        def on_select(_event: Any = None) -> None:
            selected = tree.selection()
            if not selected:
                return
            ref_id = int(tree.item(selected[0], "values")[0])
            ref = self.db.get_referee(ref_id)
            if not ref:
                return
            selected_id["value"] = ref_id
            for key, entry in entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(ref.get(key) or ""))
            category_option.set(ref.get("category") or "AN")
            active_check.select() if ref.get("active") else active_check.deselect()

        def save_form() -> None:
            try:
                payload = {key: entry.get() for key, entry in entries.items()}
                payload["category"] = category_option.get()
                payload["active"] = active_check.get()
                
                if selected_id["value"]:
                    self.referee_service.update_referee(selected_id["value"], payload)
                else:
                    self.referee_service.create_referee(payload)
                
                clear_form()
                load_list()
                self._show_toast("Arbitro salvo com sucesso.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Novo arbitro", clear_form),
            ("Salvar arbitro", save_form),
        ]
        self._grid_form_buttons(form, buttons, option_row + 3)

        tree.bind("<<TreeviewSelect>>", on_select)
        load_list()
