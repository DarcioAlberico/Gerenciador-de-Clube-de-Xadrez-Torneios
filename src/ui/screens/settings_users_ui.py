from __future__ import annotations

from ..support import *


class SettingsUsersMixin:
    def _open_user_management_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Gerenciar Usuários")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()

        tree = self._make_tree(
            dialog,
            ["id", "username", "role", "created_at"],
            {"id": "ID", "username": "Usuário", "role": "Perfil", "created_at": "Criado em"},
            {"id": 40, "username": 150, "role": 120, "created_at": 150},
            visible_rows=10,
        )
        tree.pack(fill="both", expand=True, padx=20, pady=20)

        def load_users():
            tree.delete(*tree.get_children())
            for u in self.security_service.list_users():
                tree.insert("", "end", values=(u["id"], u["username"], OPERATOR_ROLES.get(u["role"], u["role"]), u["created_at"]))

        load_users()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        def create_user():
            add_dlg = ctk.CTkToplevel(dialog)
            add_dlg.title("Novo Usuário")
            add_dlg.geometry("300x350")
            add_dlg.transient(dialog)
            add_dlg.grab_set()

            ctk.CTkLabel(add_dlg, text="Usuário:").pack(pady=(10, 0))
            u_entry = ctk.CTkEntry(add_dlg)
            u_entry.pack(pady=5)

            ctk.CTkLabel(add_dlg, text="Senha:").pack(pady=(10, 0))
            p_entry = ctk.CTkEntry(add_dlg, show="*")
            p_entry.pack(pady=5)

            ctk.CTkLabel(add_dlg, text="Perfil:").pack(pady=(10, 0))
            r_option = ctk.CTkOptionMenu(add_dlg, values=list(OPERATOR_ROLE_VALUES.keys()))
            r_option.pack(pady=5)

            def save():
                try:
                    role_val = OPERATOR_ROLE_VALUES[r_option.get()]
                    self.security_service.create_user(u_entry.get().strip(), p_entry.get(), role_val)
                    load_users()
                    add_dlg.destroy()
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(add_dlg, text="Salvar", command=save).pack(pady=20)

        def delete_user():
            sel = tree.selection()
            if not sel:
                return
            uid = tree.item(sel[0])["values"][0]
            try:
                self.security_service.delete_user(int(uid))
                load_users()
            except Exception as e:
                self._show_error(str(e))

        ctk.CTkButton(btn_frame, text="Novo Usuário", command=create_user).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deletar Usuário", command=delete_user, fg_color="red").pack(side="left", padx=5)

    def show_membership_plans(self) -> None:
        self._clear_content()
        self._page_title(
            "Planos de Mensalidade",
            "Cadastre e gerencie os planos de mensalidade oferecidos pelo clube.",
        )

        top_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        top_frame.grid(row=1, column=0, padx=22, pady=(0, 10), sticky="ew")

        btn_new = ctk.CTkButton(
            top_frame,
            text="Novo Plano",
            command=self._show_plan_form,
        )
        btn_new.pack(side="left")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=2, column=0, padx=22, pady=(0, 22), sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        columns = ("id", "nome", "valor", "ciclo", "status")
        self.plans_tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            style="App.Treeview",
        )
        self.plans_tree.heading("id", text="ID")
        self.plans_tree.heading("nome", text="Nome do Plano")
        self.plans_tree.heading("valor", text="Valor (R$)")
        self.plans_tree.heading("ciclo", text="Ciclo")
        self.plans_tree.heading("status", text="Status")
        
        self.plans_tree.column("id", width=50, anchor="center")
        self.plans_tree.column("nome", width=300, anchor="w")
        self.plans_tree.column("valor", width=100, anchor="e")
        self.plans_tree.column("ciclo", width=100, anchor="center")
        self.plans_tree.column("status", width=100, anchor="center")

        self.plans_tree.pack(fill="both", expand=True)
        self.plans_tree.bind("<Double-1>", lambda e: self._on_plan_double_click())

        self._load_plans()

    def _load_plans(self) -> None:
        for row in self.plans_tree.get_children():
            self.plans_tree.delete(row)
        plans = self.db.list_membership_plans(active_only=False)
        for p in plans:
            status_text = "Ativo" if p["active"] else "Inativo"
            cycle_map = {"monthly": "Mensal", "yearly": "Anual", "quarterly": "Trimestral"}
            cycle_text = cycle_map.get(p["billing_cycle"], p["billing_cycle"])
            self.plans_tree.insert(
                "",
                "end",
                values=(
                    p["id"],
                    p["name"],
                    f"{p['amount']:.2f}",
                    cycle_text,
                    status_text
                ),
            )

    def _on_plan_double_click(self) -> None:
        sel = self.plans_tree.selection()
        if not sel:
            return
        plan_id = int(self.plans_tree.item(sel[0])["values"][0])
        plan = self.db.get_membership_plan(plan_id)
        if plan:
            self._show_plan_form(plan)

    def _show_plan_form(self, plan: dict[str, Any] | None = None) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Plano de Mensalidade" if plan else "Novo Plano")
        dlg.geometry("400x450")
        dlg.transient(self)
        dlg.grab_set()

        frame = ctk.CTkFrame(dlg)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nome do Plano:").pack(anchor="w", pady=(0, 5))
        name_entry = ctk.CTkEntry(frame)
        name_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(frame, text="Valor (R$):").pack(anchor="w", pady=(0, 5))
        amount_entry = ctk.CTkEntry(frame)
        amount_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(frame, text="Ciclo de Cobrança:").pack(anchor="w", pady=(0, 5))
        cycle_var = ctk.StringVar(value="monthly")
        cycle_menu = ctk.CTkOptionMenu(
            frame,
            variable=cycle_var,
            values=["monthly", "quarterly", "yearly"]
        )
        cycle_menu.pack(fill="x", pady=(0, 15))

        active_var = ctk.BooleanVar(value=True)
        active_cb = ctk.CTkCheckBox(frame, text="Plano Ativo", variable=active_var)
        active_cb.pack(anchor="w", pady=(0, 15))

        if plan:
            name_entry.insert(0, plan["name"])
            amount_entry.insert(0, str(plan["amount"]))
            cycle_var.set(plan["billing_cycle"])
            active_var.set(bool(plan["active"]))

        def save():
            try:
                amount = float(amount_entry.get().replace(",", "."))
            except ValueError:
                self._show_error("Valor inválido.")
                return

            name = name_entry.get().strip()
            if not name:
                self._show_error("Nome é obrigatório.")
                return

            if plan:
                self.db.update_membership_plan(
                    plan["id"],
                    name=name,
                    amount=amount,
                    billing_cycle=cycle_var.get(),
                    active=int(active_var.get()),
                    notes=""
                )
            else:
                self.db.create_membership_plan(
                    name=name,
                    amount=amount,
                    billing_cycle=cycle_var.get(),
                    notes=""
                )
            self._load_plans()
            dlg.destroy()

        ctk.CTkButton(frame, text="Salvar", command=save).pack(pady=20)

    def _show_users_manager(self) -> None:
        if self.security_service.current_operator().get("role") != "admin":
            self._show_error("Apenas o administrador pode gerenciar usuários.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Gerenciar Usuários")
        dlg.geometry("700x500")
        dlg.grab_set()

        frame = ctk.CTkFrame(dlg)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        top_bar = ctk.CTkFrame(frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))

        tree_frame = ctk.CTkFrame(frame)
        tree_frame.pack(fill="both", expand=True)

        users_tree = self._make_tree(
            tree_frame,
            ["username", "role", "created_at"],
            {"username": "Usuário", "role": "Perfil", "created_at": "Criado em"},
            {"username": 200, "role": 150, "created_at": 150}
        )
        users_tree.pack(fill="both", expand=True)

        user_ids = {}

        def load_users():
            users_tree.delete(*users_tree.get_children())
            user_ids.clear()
            for user in self.security_service.list_users():
                row_id = users_tree.insert("", "end", values=(
                    user["username"],
                    OPERATOR_ROLES.get(user["role"], user["role"]),
                    user["created_at"]
                ))
                user_ids[row_id] = user["id"]

        load_users()

        def add_user():
            add_dlg = ctk.CTkToplevel(dlg)
            add_dlg.title("Novo Usuário")
            add_dlg.geometry("400x400")
            add_dlg.grab_set()

            ctk.CTkLabel(add_dlg, text="Nome de Usuário").pack(pady=(20, 5))
            user_entry = ctk.CTkEntry(add_dlg, width=250)
            user_entry.pack()

            ctk.CTkLabel(add_dlg, text="Senha Provisória").pack(pady=(15, 5))
            pwd_entry = ctk.CTkEntry(add_dlg, width=250)
            pwd_entry.pack()

            ctk.CTkLabel(add_dlg, text="Perfil").pack(pady=(15, 5))
            role_var = ctk.StringVar(value="teacher")
            role_combo = ctk.CTkOptionMenu(add_dlg, variable=role_var, values=list(OPERATOR_ROLE_VALUES.keys()))
            role_combo.pack()

            def save():
                try:
                    self.security_service.create_user(
                        username=user_entry.get().strip(),
                        password_raw=pwd_entry.get().strip(),
                        role=OPERATOR_ROLE_VALUES.get(role_var.get(), "teacher")
                    )
                    load_users()
                    add_dlg.destroy()
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(add_dlg, text="Salvar", command=save).pack(pady=30)

        def delete_user():
            selected = users_tree.selection()
            if not selected:
                return
            uid = user_ids[selected[0]]
            try:
                self.security_service.delete_user(uid)
                load_users()
            except Exception as e:
                self._show_error(str(e))

        def change_pwd():
            selected = users_tree.selection()
            if not selected:
                return
            uid = user_ids[selected[0]]
            
            pwd_dlg = ctk.CTkToplevel(dlg)
            pwd_dlg.title("Redefinir Senha")
            pwd_dlg.geometry("400x250")
            pwd_dlg.grab_set()

            ctk.CTkLabel(pwd_dlg, text="Nova Senha").pack(pady=(20, 5))
            pwd_entry = ctk.CTkEntry(pwd_dlg, width=250)
            pwd_entry.pack()

            def save():
                try:
                    self.security_service.update_user_password(uid, pwd_entry.get().strip())
                    pwd_dlg.destroy()
                    self._show_toast("Senha atualizada.", kind="success")
                except Exception as e:
                    self._show_error(str(e))

            ctk.CTkButton(pwd_dlg, text="Salvar", command=save).pack(pady=30)

        ctk.CTkButton(top_bar, text="Novo", command=add_user).pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Excluir", command=delete_user, fg_color="red").pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Redefinir Senha", command=change_pwd).pack(side="left", padx=5)
