from __future__ import annotations

import json
from typing import Any

import customtkinter as ctk

from src.services.constants import OPERATOR_ROLES

class AuditPagesMixin:
    def show_audit_logs(self) -> None:
        self.require_permission("settings_write")
        self._clear_content()
        self._page_title(
            "Auditoria Completa",
            "Consulte e filtre os registros completos de auditoria do sistema.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        filter_panel = ctk.CTkFrame(body, fg_color="transparent")
        filter_panel.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        for col in range(6):
            filter_panel.grid_columnconfigure(col, weight=0)

        ctk.CTkLabel(filter_panel, text="Data Inicial").grid(row=0, column=0, padx=(0, 8), pady=(0, 4), sticky="w")
        start_date = self._make_date_entry(filter_panel, width=15)
        start_date.grid(row=1, column=0, padx=(0, 16), sticky="w")

        ctk.CTkLabel(filter_panel, text="Data Final").grid(row=0, column=1, padx=(0, 8), pady=(0, 4), sticky="w")
        end_date = self._make_date_entry(filter_panel, width=15)
        end_date.grid(row=1, column=1, padx=(0, 16), sticky="w")

        ctk.CTkLabel(filter_panel, text="Operador").grid(row=0, column=2, padx=(0, 8), pady=(0, 4), sticky="w")
        operator_entry = ctk.CTkEntry(filter_panel, width=150, placeholder_text="Nome do operador...")
        operator_entry.grid(row=1, column=2, padx=(0, 16), sticky="w")

        ctk.CTkLabel(filter_panel, text="Ação").grid(row=0, column=3, padx=(0, 8), pady=(0, 4), sticky="w")
        action_entry = ctk.CTkEntry(filter_panel, width=150, placeholder_text="Ex: login, payment...")
        action_entry.grid(row=1, column=3, padx=(0, 16), sticky="w")

        ctk.CTkLabel(filter_panel, text="Entidade").grid(row=0, column=4, padx=(0, 8), pady=(0, 4), sticky="w")
        entity_entry = ctk.CTkEntry(filter_panel, width=150, placeholder_text="Ex: member, backup...")
        entity_entry.grid(row=1, column=4, padx=(0, 16), sticky="w")

        table_panel = self._make_panel(body)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            table_panel,
            ["id", "created", "actor", "role", "action", "entity", "description"],
            {
                "id": "ID",
                "created": "Data",
                "actor": "Operador",
                "role": "Perfil",
                "action": "Ação",
                "entity": "Entidade",
                "description": "Descrição",
            },
            {
                "id": 50,
                "created": 150,
                "actor": 150,
                "role": 120,
                "action": 150,
                "entity": 120,
                "description": 300,
            }
        )
        tree.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        metadata_cache: dict[int, str] = {}

        def load_logs() -> None:
            tree.delete(*tree.get_children())
            metadata_cache.clear()
            try:
                op = operator_entry.get().strip()
                act = action_entry.get().strip()
                ent = entity_entry.get().strip()
                
                rows = self.security_service.list_audit_logs(
                    limit=1000,
                    action=act,
                    entity_type=ent,
                    start_date=start_date.get(),
                    end_date=end_date.get(),
                )
                
                if op:
                    rows = [r for r in rows if op.lower() in (r.get("actor") or "").lower()]

                for row in rows:
                    row_id = row["id"]
                    metadata_cache[row_id] = row.get("metadata_json") or "{}"
                    tree.insert(
                        "",
                        "end",
                        iid=str(row_id),
                        values=(
                            row_id,
                            row["created_at"],
                            row.get("actor") or "",
                            OPERATOR_ROLES.get(row.get("role"), row.get("role") or ""),
                            row["action"],
                            row.get("entity_type") or "",
                            row.get("description") or "",
                        ),
                    )
            except Exception as exc:
                self._show_error(exc)

        def view_metadata(_event: Any = None) -> None:
            selected = tree.selection()
            if not selected:
                return
            row_id_str = selected[0]
            row_id = int(row_id_str)
            meta_json = metadata_cache.get(row_id, "{}")
            
            try:
                parsed = json.loads(meta_json)
                formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                formatted = meta_json

            modal = ctk.CTkToplevel(self)
            modal.title(f"Metadados - Log #{row_id}")
            modal.geometry("500x400")
            modal.grab_set()
            
            ctk.CTkLabel(modal, text="JSON Metadados", font=ctk.CTkFont(weight="bold")).pack(pady=10, padx=10, anchor="w")
            
            text = ctk.CTkTextbox(modal, wrap="none")
            text.pack(expand=True, fill="both", padx=10, pady=(0, 10))
            text.insert("1.0", formatted)
            text.configure(state="disabled")

        tree.bind("<Double-1>", view_metadata)
        
        btn_search = ctk.CTkButton(filter_panel, text="Buscar", command=load_logs)
        btn_search.grid(row=1, column=5, padx=(16, 0), sticky="w")
        
        ctk.CTkLabel(filter_panel, text="Dica: Clique duplo num registro para inspecionar os dados técnicos.").grid(row=2, column=0, columnspan=6, pady=(8, 0), sticky="w")

        load_logs()
