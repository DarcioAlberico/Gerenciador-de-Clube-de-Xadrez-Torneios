from __future__ import annotations

from ..support import *
from ..components import danger_button, debounce


# Verde da marca WhatsApp: nao acompanha o tema — e identidade de terceiro.
WHATSAPP_VERDE = "#25D366"
WHATSAPP_VERDE_HOVER = "#128C7E"


class ClubMembersMixin:
    def show_members(self, initial_class_id: int | None = None) -> None:
        self._clear_content()
        self._page_title(
            "Membros",
            "Cadastre socios, alunos, visitantes e convidados do clube.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tabview = ctk.CTkTabview(body, width=320)
        tabview.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        
        tab_dados = tabview.add("Dados Pessoais")
        tab_freq = tabview.add("Frequência")
        tab_titles = tabview.add("Títulos")
        tab_deslig = tabview.add("Desligamentos")
        tab_patrimonio = tabview.add("Patrimônio (Empréstimos)")
        tab_integracao = tabview.add("Integração")
        tab_contato = tabview.add("Contato")

        form = self._make_scrollable_panel(tab_dados, width=300)
        form.pack(fill="both", expand=True)

        financial_alert_label = ctk.CTkLabel(
            form, 
            text="", 
            text_color=THEME_DANGER,
            font=ctk.CTkFont(size=SIZE_PAGE_SUBTITLE, weight="bold")
        )
        financial_alert_label.grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 0), sticky="ew")
        financial_alert_label.grid_remove()  # Oculta por padrao

        entries: dict[str, Any] = {}
        fields = [
            ("name", "Nome"),
            ("surname", "Sobrenome"),
            ("rating", "Rating"),
            ("category", "Categoria"),
            ("city", "Cidade"),
            ("phone", "Telefone"),
            ("email", "E-mail"),
            ("document", "Documento"),
            ("birth_date", "Nascimento"),
            ("guardian_name", "Responsável"),
            ("guardian_phone", "Telefone resp."),
            ("notes", "Observações"),
        ]
        for index, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=index * 2, column=0, padx=16, pady=(8, 0), sticky="w")
            if key == "birth_date":
                entry = self._make_date_entry(form, width=30)
            elif key == "category":
                from ..support import FIDE_CATEGORIES
                entry = ctk.CTkOptionMenu(form, values=FIDE_CATEGORIES, width=250)
                entry.set("")
            else:
                entry = ctk.CTkEntry(form, width=250)
            entry.grid(row=index * 2 + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry

        option_row = len(fields) * 2
        ctk.CTkLabel(form, text="Tipo").grid(row=option_row, column=0, padx=16, pady=(8, 0), sticky="w")
        member_type_option = ctk.CTkOptionMenu(form, values=list(MEMBER_TYPE_VALUES.keys()), width=250)
        member_type_option.grid(row=option_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Status").grid(row=option_row + 2, column=0, padx=16, pady=(8, 0), sticky="w")
        status_option = ctk.CTkOptionMenu(form, values=list(MEMBER_STATUS_VALUES.keys()), width=250)
        status_option.grid(row=option_row + 3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Clube/Escola").grid(row=option_row + 4, column=0, padx=16, pady=(8, 0), sticky="w")
        club_option = ctk.CTkOptionMenu(form, values=[""], width=250)
        club_option.grid(row=option_row + 5, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Turma").grid(row=option_row + 6, column=0, padx=16, pady=(8, 0), sticky="w")
        class_option = ctk.CTkOptionMenu(form, values=["Sem turma"], width=250)
        class_option.grid(row=option_row + 7, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Nível de aprendizagem").grid(
            row=option_row + 8,
            column=0,
            padx=16,
            pady=(8, 0),
            sticky="w",
        )
        learning_level_option = ctk.CTkOptionMenu(form, values=["Sem nivel"], width=250)
        learning_level_option.grid(row=option_row + 9, column=0, padx=16, pady=(2, 0), sticky="ew")

        selected_member_id: dict[str, int | None] = {"value": None}
        club_option_map: dict[str, int] = {}
        class_option_map: dict[str, int | None] = {"Sem turma": None}
        class_filter_map: dict[str, int] = {}
        learning_level_option_map: dict[str, int | None] = {"Sem nivel": None}
        learning_level_filter_map: dict[str, int] = {}

        # Frequência Tab
        freq_frame = ctk.CTkFrame(tab_freq, fg_color="transparent")
        freq_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        freq_tree = ttk.Treeview(freq_frame, columns=("id", "data", "evento"), show="headings", height=8)
        freq_tree.heading("id", text="ID")
        freq_tree.heading("data", text="Data")
        freq_tree.heading("evento", text="Evento")
        freq_tree.column("id", width=30)
        freq_tree.column("data", width=80)
        freq_tree.column("evento", width=120)
        self._remember_column_widths(freq_tree)
        freq_tree.pack(fill="x", pady=5)

        freq_date_entry = self._make_date_entry(freq_frame, width=200)
        freq_date_entry.pack(pady=2)
        freq_date_entry.insert(0, "DD/MM/AAAA")
        freq_event_entry = ctk.CTkEntry(freq_frame, placeholder_text="Evento/Aula", width=200)
        freq_event_entry.pack(pady=2)
        
        def add_presence():
            mid = selected_member_id["value"]
            if not mid: return
            d = freq_date_entry.get().strip()
            e = freq_event_entry.get().strip()
            if d and e:
                self.member_service.register_presence(mid, d, e)
                load_freq()
                freq_event_entry.delete(0, "end")
        
        def delete_presence():
            sel = freq_tree.selection()
            if sel:
                pid = int(freq_tree.item(sel[0])["values"][0])
                self.member_service.remove_presence(pid)
                load_freq()

        freq_btns = ctk.CTkFrame(freq_frame, fg_color="transparent")
        freq_btns.pack(pady=5)
        ctk.CTkButton(freq_btns, text="Add", width=80, command=add_presence).pack(side="left", padx=2)
        danger_button(freq_btns, "Del", delete_presence, width=80).pack(side="left", padx=2)

        def load_freq():
            freq_tree.delete(*freq_tree.get_children())
            mid = selected_member_id["value"]
            if not mid: return
            for p in self.member_service.list_presences(mid):
                freq_tree.insert("", "end", values=(p["id"], p["presence_date"], p["event_type"]))

        # Títulos Tab
        titles_frame = ctk.CTkFrame(tab_titles, fg_color="transparent")
        titles_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        titles_tree = ttk.Treeview(titles_frame, columns=("id", "titulo", "data"), show="headings", height=8)
        titles_tree.heading("id", text="ID")
        titles_tree.heading("titulo", text="Título")
        titles_tree.heading("data", text="Data")
        titles_tree.column("id", width=30)
        titles_tree.column("titulo", width=120)
        titles_tree.column("data", width=80)
        self._remember_column_widths(titles_tree)
        titles_tree.pack(fill="x", pady=5)

        title_name_entry = ctk.CTkEntry(titles_frame, placeholder_text="Título", width=200)
        title_name_entry.pack(pady=2)
        title_date_entry = self._make_date_entry(titles_frame, width=200)
        title_date_entry.pack(pady=2)
        title_date_entry.insert(0, "DD/MM/AAAA")
        title_issuer_entry = ctk.CTkEntry(titles_frame, placeholder_text="Emissor", width=200)
        title_issuer_entry.pack(pady=2)

        def add_title_action():
            mid = selected_member_id["value"]
            if not mid: return
            n = title_name_entry.get().strip()
            d = title_date_entry.get().strip()
            i = title_issuer_entry.get().strip()
            if n:
                self.member_service.add_title(mid, n, d, i)
                load_titles()
                title_name_entry.delete(0, "end")
                title_issuer_entry.delete(0, "end")

        def delete_title_action():
            sel = titles_tree.selection()
            if sel:
                tid = int(titles_tree.item(sel[0])["values"][0])
                self.member_service.remove_title(tid)
                load_titles()

        titles_btns = ctk.CTkFrame(titles_frame, fg_color="transparent")
        titles_btns.pack(pady=5)
        ctk.CTkButton(titles_btns, text="Add", width=80, command=add_title_action).pack(side="left", padx=2)
        danger_button(titles_btns, "Del", delete_title_action, width=80).pack(side="left", padx=2)

        def load_titles():
            titles_tree.delete(*titles_tree.get_children())
            mid = selected_member_id["value"]
            if not mid: return
            for t in self.member_service.list_titles(mid):
                titles_tree.insert("", "end", values=(t["id"], t["title_name"], t["date_earned"]))

        # Desligamentos Tab
        deslig_frame = ctk.CTkFrame(tab_deslig, fg_color="transparent")
        deslig_frame.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(deslig_frame, text="Data de Desligamento").pack(anchor="w", pady=(5,0))
        deslig_date = self._make_date_entry(deslig_frame, width=250)
        deslig_date.pack(fill="x")
        
        ctk.CTkLabel(deslig_frame, text="Motivo").pack(anchor="w", pady=(10,0))
        deslig_reason = ctk.CTkEntry(deslig_frame, width=250)
        deslig_reason.pack(fill="x")
        
        ctk.CTkLabel(deslig_frame, text="Notas (Transferência)").pack(anchor="w", pady=(10,0))
        deslig_notes = ctk.CTkEntry(deslig_frame, width=250)
        deslig_notes.pack(fill="x")

        def do_deactivate():
            mid = selected_member_id["value"]
            if not mid: return
            try:
                self.member_service.deactivate_member(
                    mid,
                    reason=deslig_reason.get().strip(),
                    date=deslig_date.get().strip(),
                    notes=deslig_notes.get().strip()
                )
                self._show_toast("Membro desligado com sucesso.", kind="success")
                load_members()
            except Exception as e:
                self._show_error(str(e))

        danger_button(deslig_frame, "Desligar Membro", do_deactivate).pack(pady=20)

        def load_deslig(member: dict[str, Any]):
            deslig_date.delete(0, "end")
            deslig_reason.delete(0, "end")
            deslig_notes.delete(0, "end")
            deslig_date.insert(0, str(member.get("departure_date") or ""))
            deslig_reason.insert(0, str(member.get("departure_reason") or ""))
            deslig_notes.insert(0, str(member.get("transfer_notes") or ""))

        # TAB PATRIMONIO
        pat_holder = self._make_panel(tab_patrimonio)
        pat_holder.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        pat_holder.grid_rowconfigure(0, weight=1)
        pat_holder.grid_columnconfigure(0, weight=1)
        pat_tree = self._make_tree(
            pat_holder,
            ["id", "item", "qty", "loan", "due", "status"],
            {
                "id": "ID",
                "item": "Item",
                "qty": "Qtd",
                "loan": "Data Empréstimo",
                "due": "Data Devolução",
                "status": "Status",
            },
            {"id": 40, "item": 180, "qty": 40, "loan": 90, "due": 90, "status": 90},
        )
        def load_patrimonio(member_id: int):
            pat_tree.delete(*pat_tree.get_children())
            if not member_id:
                return
            loans = self.db.list_inventory_loans(member_id=member_id)
            for loan in loans:
                pat_tree.insert(
                    "",
                    "end",
                    values=(
                        loan["id"],
                        loan.get("item_name") or "",
                        loan["quantity"],
                        loan.get("loan_date") or "",
                        loan.get("due_date") or "",
                        INVENTORY_LOAN_STATUS_LABELS.get(loan["status"], loan["status"]),
                    ),
                )

        # Integração Online Tab
        integracao_frame = self._make_scrollable_panel(tab_integracao, width=300)
        integracao_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(integracao_frame, text="Lichess Username").grid(row=0, column=0, padx=16, pady=(16, 0), sticky="w")
        lichess_entry = ctk.CTkEntry(integracao_frame, width=250)
        lichess_entry.grid(row=1, column=0, padx=16, pady=(2, 0), sticky="ew")
        entries["lichess_username"] = lichess_entry

        ctk.CTkLabel(integracao_frame, text="Chess.com Username").grid(row=2, column=0, padx=16, pady=(16, 0), sticky="w")
        chesscom_entry = ctk.CTkEntry(integracao_frame, width=250)
        chesscom_entry.grid(row=3, column=0, padx=16, pady=(2, 0), sticky="ew")
        entries["chesscom_username"] = chesscom_entry

        ctk.CTkLabel(integracao_frame, text="Rating Online Blitz").grid(row=4, column=0, padx=16, pady=(16, 0), sticky="w")
        blitz_entry = ctk.CTkEntry(integracao_frame, width=150)
        blitz_entry.grid(row=5, column=0, padx=16, pady=(2, 0), sticky="w")
        entries["online_blitz_rating"] = blitz_entry

        ctk.CTkLabel(integracao_frame, text="Rating Online Rapid").grid(row=6, column=0, padx=16, pady=(16, 0), sticky="w")
        rapid_entry = ctk.CTkEntry(integracao_frame, width=150)
        rapid_entry.grid(row=7, column=0, padx=16, pady=(2, 16), sticky="w")
        entries["online_rapid_rating"] = rapid_entry

        def sync_online_ratings():
            lichess_user = lichess_entry.get().strip()
            chesscom_user = chesscom_entry.get().strip()
            if not lichess_user and not chesscom_user:
                self._show_info("Informe pelo menos um username (Lichess ou Chess.com).")
                return
            
            def fetch_ratings() -> tuple[int, int]:
                """Consulta as plataformas (rede) — fora da thread da UI."""
                from src.services.integration_service import IntegrationService
                service = IntegrationService()

                blitz_max = 0
                rapid_max = 0
                if lichess_user:
                    l_ratings = service.fetch_lichess_ratings(lichess_user)
                    blitz_max = max(blitz_max, l_ratings["blitz"])
                    rapid_max = max(rapid_max, l_ratings["rapid"])
                if chesscom_user:
                    c_ratings = service.fetch_chesscom_ratings(chesscom_user)
                    blitz_max = max(blitz_max, c_ratings["blitz"])
                    rapid_max = max(rapid_max, c_ratings["rapid"])
                return blitz_max, rapid_max

            def apply_ratings(ratings: tuple[int, int]) -> None:
                blitz_max, rapid_max = ratings
                blitz_entry.delete(0, "end")
                blitz_entry.insert(0, str(blitz_max))
                rapid_entry.delete(0, "end")
                rapid_entry.insert(0, str(rapid_max))
                self._show_info(
                    f"Sincronizacao concluida!\nBlitz: {blitz_max} | Rapid: {rapid_max}\n"
                    "(Clique em Salvar para persistir)"
                )

            self._run_background(
                fetch_ratings,
                on_success=apply_ratings,
                busy_message="Consultando Lichess/Chess.com...",
                busy_widget=sync_button,
            )

        sync_button = ctk.CTkButton(
            integracao_frame, text="Sincronizar Rating Online", command=sync_online_ratings, fg_color=THEME_ACCENT
        )
        sync_button.grid(row=8, column=0, padx=16, pady=16, sticky="ew")

        # Contato Tab
        contato_frame = self._make_scrollable_panel(tab_contato, width=300)
        contato_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(contato_frame, text="Acoes Rapidas", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        def open_whatsapp():
            phone = entries.get("phone")
            if not phone:
                return
            num = "".join(filter(str.isdigit, phone.get()))
            if not num:
                self._show_info("Membro nao possui telefone valido.")
                return
            if not num.startswith("55"):
                num = "55" + num
            import webbrowser
            webbrowser.open(f"https://wa.me/{num}")

        def open_email():
            email_field = entries.get("email")
            if not email_field:
                return
            email = email_field.get().strip()
            if not email:
                self._show_info("Membro nao possui email.")
                return
            import webbrowser
            webbrowser.open(f"mailto:{email}")

        ctk.CTkButton(contato_frame, text=" Abrir WhatsApp", command=open_whatsapp, fg_color=WHATSAPP_VERDE, hover_color=WHATSAPP_VERDE_HOVER).grid(
            row=1, column=0, padx=16, pady=8, sticky="ew"
        )
        ctk.CTkButton(contato_frame, text=" Enviar E-mail", command=open_email).grid(
            row=2, column=0, padx=16, pady=8, sticky="ew"
        )

        list_panel = self._make_panel(body)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(1, weight=2)
        list_panel.grid_rowconfigure(3, weight=1)

        controls = ctk.CTkFrame(list_panel, fg_color="transparent")
        controls.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por nome, telefone, e-mail ou categoria")
        search_entry.grid(row=0, column=0, columnspan=2, pady=(0, 8), sticky="ew")

        type_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos os tipos"] + list(MEMBER_TYPE_VALUES.keys()),
            width=150,
        )
        type_filter.grid(row=1, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")

        status_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos os status"] + list(MEMBER_STATUS_VALUES.keys()),
            width=150,
        )
        status_filter.grid(row=1, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")

        category_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todas as categorias"],
            width=170,
        )
        category_filter.grid(row=2, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")

        club_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos clubes"],
            width=180,
        )
        club_filter.grid(row=2, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")

        class_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todas turmas"],
            width=170,
        )
        class_filter.grid(row=3, column=0, columnspan=2, sticky="ew")

        learning_level_filter = ctk.CTkOptionMenu(
            controls,
            values=["Todos niveis"],
            width=170,
        )
        learning_level_filter.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        tree_holder = ctk.CTkFrame(list_panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            tree_holder,
            [
                "id",
                "name",
                "surname",
                "club",
                "class",
                "learning_level",
                "type",
                "status",
                "rating",
                "category",
                "age_category",
                "rating_category",
                "tags",
                "phone",
                "email",
            ],
            {
                "id": "ID",
                "name": "Nome",
                "surname": "Sobrenome",
                "club": "Clube/Escola",
                "class": "Turma",
                "learning_level": "Nível",
                "type": "Tipo",
                "status": "Status",
                "rating": "Rating",
                "category": "Categoria",
                "age_category": "Idade",
                "rating_category": "Rating cat.",
                "tags": "Tags",
                "phone": "Telefone",
                "email": "E-mail",
            },
            {
                "id": 55,
                "name": 170,
                "surname": 150,
                "club": 160,
                "class": 140,
                "learning_level": 140,
                "type": 90,
                "status": 80,
                "rating": 70,
                "category": 110,
                "age_category": 85,
                "rating_category": 95,
                "tags": 150,
                "phone": 120,
                "email": 180,
            },
        )

        history_header = ctk.CTkFrame(list_panel, fg_color="transparent")
        history_header.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
        history_header.grid_columnconfigure(0, weight=1)
        self._section_title(history_header, "Historico de torneios do membro selecionado").grid(
            row=0, column=0, sticky="w"
        )

        history_holder = ctk.CTkFrame(list_panel, fg_color="transparent")
        history_holder.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        history_holder.grid_columnconfigure(0, weight=1)
        history_holder.grid_rowconfigure(0, weight=1)
        history_tree = self._make_tree(
            history_holder,
            ["tournament", "status", "points", "position", "rounds", "record", "last"],
            {
                "tournament": "Torneio",
                "status": "Status",
                "points": "Pts",
                "position": "Pos",
                "rounds": "Rodadas",
                "record": "V/E/D/B",
                "last": "Ultimo",
            },
            {
                "tournament": 260,
                "status": 90,
                "points": 60,
                "position": 55,
                "rounds": 75,
                "record": 90,
                "last": 90,
            },
        )
        history_tournament_map: dict[str, int] = {}

        def club_label(club: dict[str, Any]) -> str:
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            return f"{club['id']} - {club['name']} ({kind})"

        def load_club_options(selected_id: int | None = None) -> None:
            club_option_map.clear()
            values = []
            for club in self.db.list_clubs(active_only=True):
                label = club_label(club)
                values.append(label)
                club_option_map[label] = int(club["id"])
            if not values:
                values = ["1 - Clube padrao (Clube)"]
                club_option_map[values[0]] = 1
            club_option.configure(values=values)
            chosen = next(
                (label for label, club_id in club_option_map.items() if club_id == selected_id),
                values[0],
            )
            club_option.set(chosen)
            load_class_options(club_option_map[chosen], None)

            filter_values = ["Todos clubes"] + values
            current_filter = club_filter.get()
            club_filter.configure(values=filter_values)
            club_filter.set(current_filter if current_filter in filter_values else "Todos clubes")
            load_class_filter_options()

        def load_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            class_option_map.clear()
            class_option_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    class_option_map[label] = int(class_data["id"])
            class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in class_option_map.items() if class_id == selected_id),
                "Sem turma",
            )
            class_option.set(chosen)

        def load_class_filter_options(club_id: int | None = None, initial_set_id: int | None = None) -> None:
            class_filter_map.clear()
            values = ["Todas turmas"]
            chosen = "Todas turmas"
            for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                label = f"{class_data['id']} - {class_data['name']}"
                values.append(label)
                class_filter_map[label] = int(class_data["id"])
                if initial_set_id == int(class_data["id"]):
                    chosen = label
            current_filter = class_filter.get()
            class_filter.configure(values=values)
            if initial_set_id is not None:
                class_filter.set(chosen)
            else:
                class_filter.set(current_filter if current_filter in values else "Todas turmas")

        def load_learning_level_options(selected_id: int | None = None) -> None:
            learning_level_option_map.clear()
            learning_level_option_map["Sem nivel"] = None
            values = ["Sem nivel"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                learning_level_option_map[label] = int(level["id"])
            learning_level_option.configure(values=values)
            chosen = next(
                (label for label, level_id in learning_level_option_map.items() if level_id == selected_id),
                "Sem nivel",
            )
            learning_level_option.set(chosen)

        def load_learning_level_filter_options() -> None:
            learning_level_filter_map.clear()
            values = ["Todos niveis"]
            for level in self.db.list_learning_levels(active_only=True):
                label = f"{level['id']} - {level['name']}"
                values.append(label)
                learning_level_filter_map[label] = int(level["id"])
            current_filter = learning_level_filter.get()
            learning_level_filter.configure(values=values)
            learning_level_filter.set(current_filter if current_filter in values else "Todos niveis")

        def on_club_option_change(_value: str) -> None:
            load_class_options(club_option_map.get(club_option.get()), None)

        def member_payload() -> dict[str, Any]:
            payload = {key: entry.get() for key, entry in entries.items()}
            payload["member_type"] = MEMBER_TYPE_VALUES[member_type_option.get()]
            payload["status"] = MEMBER_STATUS_VALUES[status_option.get()]
            payload["club_id"] = club_option_map.get(club_option.get(), 1)
            payload["class_id"] = class_option_map.get(class_option.get())
            payload["learning_level_id"] = learning_level_option_map.get(learning_level_option.get())
            return payload

        def load_member_history(member_id: int | None = None) -> None:
            history_tree.delete(*history_tree.get_children())
            history_tournament_map.clear()
            if not member_id:
                return
            for item in self.member_service.tournament_history(member_id):
                record = f"{item['wins']}/{item['draws']}/{item['losses']}/{item['byes']}"
                row_id = history_tree.insert(
                    "",
                    "end",
                    values=(
                        item["name"],
                        item["status"],
                        item["points"],
                        item["position"],
                        item["rounds_played"],
                        record,
                        item["last_result"],
                    ),
                )
                history_tournament_map[row_id] = int(item["tournament_id"])

        def show_history_details(_event: Any = None) -> None:
            member_id = selected_member_id["value"]
            selected = history_tree.selection()
            if not member_id or not selected:
                return
            tournament_id = history_tournament_map.get(selected[0])
            if not tournament_id:
                return
            results = self.member_service.tournament_results(member_id, tournament_id)
            if not results:
                self._show_info("Este membro ainda nao possui resultados neste torneio.")
                return
            lines = []
            for result in results:
                points = "" if result["points"] is None else f"{result['points']:g} pt"
                raw_result = result["result"] or "Pendente"
                lines.append(
                    "Rodada {round_number}, mesa {board_number}: {color} x {opponent} - "
                    "{result} ({outcome}{points})".format(
                        round_number=result["round_number"],
                        board_number=result["board_number"],
                        color=result["color"],
                        opponent=result["opponent"],
                        result=raw_result,
                        outcome=result["outcome"],
                        points=f", {points}" if points else "",
                    )
                )
            self._show_info("\n".join(lines))

        def clear_form() -> None:
            selected_member_id["value"] = None
            financial_alert_label.grid_remove()
            for key, entry in entries.items():
                if isinstance(entry, ctk.CTkOptionMenu):
                    entry.set("")
                elif hasattr(entry, "delete"):
                    entry.delete(0, "end")
            member_type_option.set(MEMBER_TYPE_LABELS["socio"])
            status_option.set(MEMBER_STATUS_LABELS["active"])
            load_club_options()
            load_learning_level_options()
            load_member_history()

        def load_members() -> None:
            tree.delete(*tree.get_children())
            query = search_entry.get().strip().casefold()
            type_value = type_filter.get()
            status_value = status_filter.get()
            category_value = category_filter.get()
            club_value = club_filter.get()
            class_value = class_filter.get()
            learning_level_value = learning_level_filter.get()
            for member in self.db.list_members(active_only=False):
                if type_value != "Todos os tipos" and member["member_type"] != MEMBER_TYPE_VALUES[type_value]:
                    continue
                if status_value != "Todos os status" and member["status"] != MEMBER_STATUS_VALUES[status_value]:
                    continue
                if category_value != "Todas as categorias" and member["category"] != category_value:
                    continue
                if club_value != "Todos clubes" and member.get("club_id") != club_option_map.get(club_value):
                    continue
                if class_value != "Todas turmas" and member.get("active_class_id") != class_filter_map.get(class_value):
                    continue
                if (
                    learning_level_value != "Todos niveis"
                    and member.get("learning_level_id") != learning_level_filter_map.get(learning_level_value)
                ):
                    continue
                searchable = " ".join(
                    [
                        str(member["name"] or ""),
                        str(member.get("surname") or ""),
                        str(member.get("club_name") or ""),
                        str(member.get("active_class_name") or ""),
                        str(member.get("learning_level_name") or ""),
                        str(member["phone"] or ""),
                        str(member["email"] or ""),
                        str(member["category"] or ""),
                        str(member.get("age_category") or ""),
                        str(member.get("rating_category") or ""),
                        str(member.get("prize_tags") or ""),
                        str(member["member_type"] or ""),
                        str(member["status"] or ""),
                    ]
                ).casefold()
                if query and query not in searchable:
                    continue
                tree.insert(
                    "",
                    "end",
                    values=(
                        member["id"],
                        member["name"],
                        member.get("surname") or "",
                        member.get("club_name") or "",
                        member.get("active_class_name") or "",
                        member.get("learning_level_name") or "",
                        MEMBER_TYPE_LABELS.get(member["member_type"], member["member_type"]),
                        MEMBER_STATUS_LABELS.get(member["status"], member["status"]),
                        member["rating"],
                        member["category"],
                        member.get("age_category", ""),
                        member.get("rating_category", ""),
                        member.get("prize_tags", ""),
                        member["phone"],
                        member["email"],
                    ),
                )

        def load_category_filter() -> None:
            selected = category_filter.get()
            categories = sorted(
                {
                    str(member["category"]).strip()
                    for member in self.db.list_members(active_only=False)
                    if str(member["category"]).strip()
                }
            )
            values = ["Todas as categorias"] + categories
            category_filter.configure(values=values)
            category_filter.set(selected if selected in values else "Todas as categorias")

        def selected_member() -> dict[str, Any] | None:
            selected = tree.selection()
            if not selected:
                return None
            member_id = int(tree.item(selected[0], "values")[0])
            return self.db.get_member(member_id)

        def show_rating_history() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                history = self.internal_rating_service.member_rating_history(int(member["id"]))
                if not history:
                    self._show_info("Este membro ainda nao possui historico de rating interno.")
                    return
                lines = []
                for item in history:
                    old_rating = int(item["old_rating"] or 0)
                    new_rating = int(item["new_rating"] or 0)
                    delta = new_rating - old_rating
                    sign = "+" if delta >= 0 else ""
                    tournament_name = item.get("tournament_name") or "Torneio removido"
                    lines.append(
                        "{created_at} - {tournament}: {old} -> {new} ({sign}{delta}), "
                        "perf. {performance}, {games} partidas, {points:g} pts".format(
                            created_at=item["created_at"],
                            tournament=tournament_name,
                            old=old_rating,
                            new=new_rating,
                            sign=sign,
                            delta=delta,
                            performance=item["performance"],
                            games=item["games"],
                            points=float(item["points"] or 0.0),
                        )
                    )
                self._show_info("\n".join(lines))
            except Exception as exc:
                self._show_error(exc)

        def export_evolution() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                safe_name = self._safe_filename(str(member["name"]), "membro")
                file_path = filedialog.asksaveasfilename(
                    title="Exportar evolucao do membro",
                    initialdir=str(self._default_export_dir()),
                    initialfile=f"{safe_name}_evolucao.xlsx",
                    defaultextension=".xlsx",
                    filetypes=[
                        ("Excel", "*.xlsx"),
                        ("CSV", "*.csv"),
                        ("PDF", "*.pdf"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() not in {".csv", ".xlsx", ".pdf"}:
                    path = path.with_suffix(".xlsx")
                member_id = int(member["id"])
                self._run_background(
                    lambda: self.export_service.export_member_evolution(member_id, path),
                    lambda _result: self._show_info(f"Relatorio exportado:\n{path}"),
                    "Exportando evolucao do membro...",
                )
            except Exception as exc:
                self._show_error(exc)

        def on_select(_event: Any = None) -> None:
            member = selected_member()
            if not member:
                return
            selected_member_id["value"] = member["id"]
            for key, entry in entries.items():
                if isinstance(entry, ctk.CTkOptionMenu):
                    entry.set(str(member.get(key) or ""))
                elif hasattr(entry, "delete"):
                    entry.delete(0, "end")
                    entry.insert(0, str(member.get(key) or ""))
            member_type_option.set(MEMBER_TYPE_LABELS.get(member["member_type"], MEMBER_TYPE_LABELS["socio"]))
            status_option.set(MEMBER_STATUS_LABELS.get(member["status"], MEMBER_STATUS_LABELS["active"]))
            
            fin_status = self.finance_service.member_financial_status(member["id"])
            if fin_status["status"] == "late":
                financial_alert_label.configure(text=f"ÔÜá INADIMPLENTE: R$ {fin_status['late_amount']:.2f} atrasado")
                financial_alert_label.grid()
            else:
                financial_alert_label.grid_remove()
                
            load_club_options(int(member.get("club_id") or 1))
            load_class_options(int(member.get("club_id") or 1), member.get("active_class_id"))
            load_learning_level_options(member.get("learning_level_id"))
            load_member_history(member["id"])
            load_freq()
            load_titles()
            load_deslig(member)
            load_patrimonio(member["id"])

        def add_member() -> None:
            try:
                self.member_service.create_member(member_payload())
                clear_form()
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        def update_member() -> None:
            try:
                member_id = selected_member_id["value"]
                if not member_id:
                    raise AppError("Selecione um membro.")
                self.member_service.update_member(member_id, member_payload())
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        def toggle_member() -> None:
            try:
                member = selected_member()
                if not member:
                    raise AppError("Selecione um membro.")
                self.member_service.toggle_member_status(member["id"])
                clear_form()
                load_category_filter()
                load_members()
            except Exception as exc:
                self._show_error(exc)

        tree.bind("<<TreeviewSelect>>", on_select)
        history_tree.bind("<Double-1>", show_history_details)
        search_entry.bind("<KeyRelease>", debounce(search_entry, load_members))
        type_filter.configure(command=lambda _value: load_members())
        status_filter.configure(command=lambda _value: load_members())
        category_filter.configure(command=lambda _value: load_members())
        club_filter.configure(command=lambda _value: load_members())
        class_filter.configure(command=lambda _value: load_members())
        learning_level_filter.configure(command=lambda _value: load_members())
        club_option.configure(command=on_club_option_change)

        def import_ratings() -> None:
            file_path = filedialog.askopenfilename(
                title="Importar lista de Rating",
                initialdir=str(self._default_export_dir()),
                filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return

            dialog = ctk.CTkToplevel(self)
            dialog.title("Tipo de Rating")
            dialog.geometry("320x150")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Selecione o tipo de rating do arquivo CSV:").pack(pady=(20, 10))
            
            def do_import(rating_type: str) -> None:
                dialog.destroy()
                try:
                    result = self.import_service.import_rating_list_csv(file_path, rating_type)
                    msg = (
                        f"Importacao de rating ({rating_type.upper()}) concluida.\n"
                        f"Membros atualizados: {result['updated']}\n"
                        f"Linhas ignoradas: {result['skipped']}\n"
                        f"Erros encontrados: {len(result['errors'])}"
                    )
                    self._show_info(msg)
                    if result['errors']:
                        logger.warning("Erros na importacao de rating: %s", result['errors'])
                    load_members()
                except Exception as exc:
                    self._show_error(exc)


            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack(pady=10)
            ctk.CTkButton(btn_frame, text="FIDE", command=lambda: do_import("fide"), width=100).pack(side="left", padx=10)
            ctk.CTkButton(btn_frame, text="CBX", command=lambda: do_import("cbx"), width=100).pack(side="left", padx=10)

        def import_members() -> None:
            try:
                file_path = filedialog.askopenfilename(
                    title="Importar membros/alunos",
                    initialdir=str(self._default_export_dir()),
                    filetypes=[
                        ("Planilhas e CSV", "*.csv;*.xls;*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Excel", "*.xls;*.xlsx"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return

                def show_import_result(result: dict[str, Any]) -> None:
                    load_category_filter()
                    load_learning_level_filter_options()
                    load_class_filter_options()
                    load_members()
                    message = (
                        f"{result['imported']} membros/alunos importados.\n"
                        f"{result['skipped']} linhas ignoradas."
                    )
                    if result["errors"]:
                        message += "\n\nErros:\n" + "\n".join(result["errors"][:12])
                    self._show_info(message)

                self._run_background(
                    lambda: self.import_service.import_members(file_path),
                    show_import_result,
                    "Importando membros/alunos...",
                )
            except Exception as exc:
                self._show_error(exc)

        def export_member_import_template() -> None:
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Salvar modelo de membros/alunos",
                    initialdir=str(self._default_export_dir()),
                    initialfile="modelo_membros_alunos.xlsx",
                    defaultextension=".xlsx",
                    filetypes=[
                        ("Excel", "*.xlsx"),
                        ("CSV", "*.csv"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() not in {".csv", ".xlsx"}:
                    path = path.with_suffix(".xlsx")
                self._run_background(
                    lambda: self.export_service.export_member_import_template(path),
                    lambda _result: self._show_info(f"Modelo salvo:\n{path}"),
                    "Gerando modelo...",
                )
            except Exception as exc:
                self._show_error(exc)

        buttons = [
            ("Adicionar", add_member),
            ("Atualizar", update_member),
            ("Ativar/Inativar", toggle_member),
            ("Hist. rating", show_rating_history),
            ("Exportar evolucao", export_evolution),
            ("Modelo CSV/Excel", export_member_import_template),
            ("Importar CSV/Excel", import_members),
            ("Importar Ratings", import_ratings),
            ("Limpar", clear_form),
        ]
        self._grid_form_buttons(form, buttons, option_row + 10)

        clear_form()
        type_filter.set("Todos os tipos")
        status_filter.set("Todos os status")
        load_category_filter()
        load_learning_level_filter_options()
        def initialize_filters() -> None:
            if initial_class_id:
                cls_data = self.db.get_class(initial_class_id)
                if cls_data:
                    club_id = int(cls_data["club_id"])
                    # Find club label
                    club_label_str = next((label for label, cid in club_option_map.items() if cid == club_id), None)
                    if club_label_str:
                        club_filter.set(club_label_str)
                    load_class_filter_options(club_id, initial_set_id=initial_class_id)
                    load_members()
                    return
            load_class_filter_options()
            load_members()

        initialize_filters()
