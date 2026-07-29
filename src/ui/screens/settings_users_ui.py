from __future__ import annotations

from ..support import *
from ..components import Dialog, FormStack, actions_bar


class SettingsUsersMixin:
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

        self._remember_column_widths(self.plans_tree)
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
        dlg = Dialog(self, "Plano de Mensalidade" if plan else "Novo Plano", size=(420, 420))
        pilha = FormStack(dlg)

        pilha.section("Plano")
        name_entry = pilha.text("Nome do Plano", placeholder="Ex.: Mensal Padrão")
        amount_entry = pilha.text("Valor (R$)", placeholder="Ex.: 120,00")
        cycle_var = ctk.StringVar(value="monthly")
        cycle_menu = pilha.select(
            "Ciclo de Cobrança", ["monthly", "quarterly", "yearly"], variable=cycle_var
        )
        active_var = ctk.BooleanVar(value=True)
        active_cb = ctk.CTkCheckBox(dlg, text="Plano Ativo", variable=active_var)
        pilha.place(active_cb, "widget", sticky="w")

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
            dlg.close()

        actions_bar(dlg, primary=("Salvar", save), close_text="Cancelar")

    def _show_users_manager(self) -> None:
        if self.security_service.current_operator().get("role") != "admin":
            self._show_error("Apenas o administrador pode gerenciar usuários.")
            return

        # O "diálogo sem saída" do P3-10: ele nascia sem Fechar, sem Esc e sem
        # tratamento do X — quem entrasse aqui só saía fechando o app. E o
        # `grab_set` sem `transient` deixava a janela sumir atrás da principal.
        dlg = Dialog(self, "Gerenciar Usuários", size=(700, 500), stretch_rows=(1,))

        tree_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        tree_frame.grid(row=1, column=0, padx=SPACE_LG, pady=(0, SPACE_SM), sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        users_tree = self._make_tree(
            tree_frame,
            ["username", "role", "created_at"],
            {"username": "Usuário", "role": "Perfil", "created_at": "Criado em"},
            {"username": 200, "role": 150, "created_at": 150}
        )

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
            add_dlg = Dialog(dlg, "Novo Usuário", size=(400, 340))
            pilha = FormStack(add_dlg)
            pilha.section("Credenciais")
            user_entry = pilha.text("Nome de Usuário", placeholder="Ex.: arbitro01")
            # `show="*"` era o que faltava: a senha provisoria aparecia em
            # texto limpo, num dialogo aberto na tela do clube.
            pwd_entry = pilha.text("Senha Provisória", placeholder="Senha inicial", show="*")
            role_var = ctk.StringVar(value="teacher")
            role_combo = pilha.select(
                "Perfil", list(OPERATOR_ROLE_VALUES.keys()), variable=role_var
            )

            def save():
                try:
                    self.security_service.create_user(
                        username=user_entry.get().strip(),
                        password_raw=pwd_entry.get().strip(),
                        role=OPERATOR_ROLE_VALUES.get(role_var.get(), "teacher")
                    )
                    load_users()
                    add_dlg.close()
                except Exception as e:
                    self._show_error(str(e))

            actions_bar(add_dlg, primary=("Salvar", save), close_text="Cancelar")

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
            
            pwd_dlg = Dialog(dlg, "Redefinir Senha", size=(400, 240))
            pilha = FormStack(pwd_dlg)
            pilha.section("Nova senha")
            pwd_entry = pilha.text("Nova Senha", placeholder="Digite a nova senha", show="*")

            def save():
                try:
                    self.security_service.update_user_password(uid, pwd_entry.get().strip())
                    pwd_dlg.close()
                    self._show_toast("Senha atualizada.", kind="success")
                except Exception as e:
                    self._show_error(str(e))

            actions_bar(pwd_dlg, primary=("Salvar", save), close_text="Cancelar")

        actions_bar(
            dlg,
            row=0,
            primary=("Novo", add_user),
            danger=("Excluir", delete_user),
            secondary=[("Redefinir Senha", change_pwd)],
            close_text="Fechar",
        )
