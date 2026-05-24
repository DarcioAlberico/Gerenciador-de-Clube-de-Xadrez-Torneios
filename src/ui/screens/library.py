import customtkinter as ctk
from typing import Any
import tkinter as tk

from ..support import UIBuilderMixin

class LibraryMixin:
    def show_library(self) -> None:
        self._clear_content()
        self._page_title(
            "Biblioteca Pedagógica",
            "Acervo de exercícios e textos para o professor gerar apostilas e PDFs.",
        )

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tabview = ctk.CTkTabview(body)
        tabview.grid(row=0, column=0, sticky="nsew")
        
        tab_acervo = tabview.add("Acervo")
        tab_apostilas = tabview.add("Apostilas")
        tab_importador = tabview.add("Importador PGN")
        tab_historico = tabview.add("Histórico de Envio")

        self._build_acervo_tab(tab_acervo)
        self._build_apostilas_tab(tab_apostilas)
        self._build_importador_tab(tab_importador)
        self._build_historico_tab(tab_historico)

    def _build_acervo_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # PAINEL ESQUERDO: Cadastro / Edição
        form = self._make_scrollable_panel(parent, width=320)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_item_id: dict[str, int | None] = {"value": None}
        entries: dict[str, Any] = {}

        fields = [
            ("title", "Título"),
            ("fen_pgn", "FEN / PGN"),
            ("solution", "Solução / Gabarito"),
            ("tags", "Tags"),
            ("author", "Fonte / Autor"),
        ]
        
        ctk.CTkLabel(form, text="Tipo").grid(row=0, column=0, padx=16, pady=(8, 0), sticky="w")
        type_option = ctk.CTkOptionMenu(form, values=["exercise", "text"], width=280)
        type_option.grid(row=1, column=0, padx=16, pady=(2, 0), sticky="ew")
        
        ctk.CTkLabel(form, text="Fase do Jogo").grid(row=2, column=0, padx=16, pady=(8, 0), sticky="w")
        phase_option = ctk.CTkOptionMenu(form, values=["general", "opening", "middlegame", "endgame"], width=280)
        phase_option.grid(row=3, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Nível").grid(row=4, column=0, padx=16, pady=(8, 0), sticky="w")
        level_option = ctk.CTkOptionMenu(form, values=["", "beginner", "intermediate", "advanced"], width=280)
        level_option.grid(row=5, column=0, padx=16, pady=(2, 0), sticky="ew")
        
        current_row = 6
        for key, label in fields:
            ctk.CTkLabel(form, text=label).grid(row=current_row, column=0, padx=16, pady=(8, 0), sticky="w")
            if key == "fen_pgn":
                entry = ctk.CTkTextbox(form, width=280, height=80)
                entry.grid(row=current_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            else:
                entry = ctk.CTkEntry(form, width=280)
                entry.grid(row=current_row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
            entries[key] = entry
            current_row += 2

        # PAINEL DIREITO: Busca e Listagem
        right_panel = ctk.CTkFrame(parent, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        
        search_entry = ctk.CTkEntry(controls, placeholder_text="Buscar por título ou tag...")
        search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        list_holder = self._make_panel(right_panel)
        list_holder.grid(row=1, column=0, sticky="nsew")
        list_holder.grid_columnconfigure(0, weight=1)
        list_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            list_holder,
            ["id", "type", "phase", "level", "title", "tags"],
            {
                "id": "ID",
                "type": "Tipo",
                "phase": "Fase",
                "level": "Nível",
                "title": "Título",
                "tags": "Tags",
            },
            {"id": 40, "type": 80, "phase": 100, "level": 100, "title": 250, "tags": 150},
        )

        def clear_form() -> None:
            selected_item_id["value"] = None
            type_option.set("exercise")
            phase_option.set("general")
            level_option.set("")
            for key, entry in entries.items():
                if isinstance(entry, ctk.CTkTextbox):
                    entry.delete("1.0", "end")
                else:
                    entry.delete(0, "end")

        def load_items() -> None:
            tree.delete(*tree.get_children())
            search_query = search_entry.get().strip()
            items = self.library_service.list_items(search=search_query)
            for item in items:
                tree.insert(
                    "",
                    "end",
                    values=(
                        item["id"],
                        item["item_type"],
                        item["phase"],
                        item["level"],
                        item["title"],
                        item["tags"],
                    ),
                )

        def on_select(_event: Any = None) -> None:
            selected = tree.selection()
            if not selected:
                return
            item_id = int(tree.item(selected[0])["values"][0])
            items = self.library_service.list_items()
            target = next((i for i in items if i["id"] == item_id), None)
            if not target:
                return
            clear_form()
            selected_item_id["value"] = item_id
            type_option.set(target["item_type"])
            phase_option.set(target["phase"] or "general")
            level_option.set(target["level"] or "")
            for key, entry in entries.items():
                val = str(target.get(key) or "")
                if isinstance(entry, ctk.CTkTextbox):
                    entry.insert("1.0", val)
                else:
                    entry.insert(0, val)

        def save_item() -> None:
            title_val = entries["title"].get().strip()
            if not title_val:
                self._show_warning("O título é obrigatório.")
                return
            
            payload = {
                "title": title_val,
                "item_type": type_option.get(),
                "phase": phase_option.get(),
                "level": level_option.get(),
                "fen_pgn": entries["fen_pgn"].get("1.0", "end-1c").strip(),
                "solution": entries["solution"].get().strip(),
                "tags": entries["tags"].get().strip(),
                "author": entries["author"].get().strip(),
            }
            try:
                self.library_service.save_item(payload, selected_item_id["value"])
                self._show_info("Item salvo com sucesso na biblioteca!")
                load_items()
                clear_form()
            except Exception as exc:
                self._show_error(exc)

        def delete_item() -> None:
            if not selected_item_id["value"]:
                return
            if self._confirm_action("Apagar item", "Tem certeza que deseja apagar este conteúdo do acervo?"):
                try:
                    self.library_service.delete_item(selected_item_id["value"])
                    load_items()
                    clear_form()
                except Exception as exc:
                    self._show_error(exc)

        def print_item() -> None:
            if not selected_item_id["value"]:
                self._show_warning("Selecione um exercício ou texto da lista primeiro.")
                return
            try:
                export_dir = self._default_export_dir()
                path = self.library_service.export_to_html(selected_item_id["value"], export_dir)
                self._print_document(path)
            except Exception as exc:
                self._show_error(exc)
        
        def add_to_collection() -> None:
            if not selected_item_id["value"]:
                self._show_warning("Selecione um item.")
                return
            cols = self.library_service.list_collections()
            if not cols:
                self._show_warning("Nenhuma apostila criada ainda.")
                return
            
            dialog = ctk.CTkToplevel(self)
            dialog.title("Adicionar à Apostila")
            dialog.geometry("400x200")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Selecione a apostila:").pack(pady=10)
            col_map = {c["name"]: c["id"] for c in cols}
            col_opt = ctk.CTkOptionMenu(dialog, values=list(col_map.keys()))
            col_opt.pack(pady=10)

            def do_add() -> None:
                c_id = col_map[col_opt.get()]
                c_data = self.library_service.get_collection(c_id)
                if c_data:
                    items = c_data["items"]
                    if selected_item_id["value"] not in items:
                        items.append(selected_item_id["value"])
                        self.library_service.save_collection({"name": c_data["name"], "description": c_data["description"], "items": items}, c_id)
                        self._show_info("Adicionado com sucesso!")
                dialog.destroy()

            ctk.CTkButton(dialog, text="Adicionar", command=do_add).pack(pady=10)

        tree.bind("<<TreeviewSelect>>", on_select)
        search_entry.bind("<Return>", lambda e: load_items())
        
        ctk.CTkButton(controls, text="Buscar", width=80, command=load_items).grid(row=0, column=1, padx=(0, 4))
        
        self._grid_form_buttons(
            form,
            [
                ("Salvar", save_item),
                ("Limpar", clear_form),
                ("Apagar", delete_item),
                ("Imprimir Único", print_item),
                ("Add à Apostila", add_to_collection),
            ],
            start_row=current_row
        )

        load_items()

    def _build_apostilas_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        form = self._make_scrollable_panel(parent, width=320)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        selected_col_id: dict[str, int | None] = {"value": None}
        
        ctk.CTkLabel(form, text="Nome da Apostila").grid(row=0, column=0, padx=16, pady=(8, 0), sticky="w")
        name_entry = ctk.CTkEntry(form, width=280)
        name_entry.grid(row=1, column=0, padx=16, pady=(2, 0), sticky="ew")

        ctk.CTkLabel(form, text="Descrição").grid(row=2, column=0, padx=16, pady=(8, 0), sticky="w")
        desc_entry = ctk.CTkEntry(form, width=280)
        desc_entry.grid(row=3, column=0, padx=16, pady=(2, 0), sticky="ew")

        list_panel = self._make_panel(parent)
        list_panel.grid(row=0, column=1, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            list_panel,
            ["id", "name", "desc"],
            {"id": "ID", "name": "Nome", "desc": "Descrição"},
            {"id": 50, "name": 200, "desc": 300}
        )

        def clear_form() -> None:
            selected_col_id["value"] = None
            name_entry.delete(0, "end")
            desc_entry.delete(0, "end")

        def load_cols() -> None:
            tree.delete(*tree.get_children())
            for c in self.library_service.list_collections():
                tree.insert("", "end", values=(c["id"], c["name"], c["description"]))

        def on_select(_e: Any) -> None:
            sel = tree.selection()
            if not sel: return
            cid = int(tree.item(sel[0])["values"][0])
            c_data = self.library_service.get_collection(cid)
            if c_data:
                clear_form()
                selected_col_id["value"] = cid
                name_entry.insert(0, str(c_data["name"]))
                desc_entry.insert(0, str(c_data["description"]))

        def save_col() -> None:
            name = name_entry.get().strip()
            if not name: return
            payload = {"name": name, "description": desc_entry.get().strip()}
            if selected_col_id["value"]:
                c_data = self.library_service.get_collection(selected_col_id["value"])
                payload["items"] = c_data["items"] if c_data else []
            self.library_service.save_collection(payload, selected_col_id["value"])
            load_cols()
            clear_form()

        def del_col() -> None:
            if selected_col_id["value"]:
                self.library_service.delete_collection(selected_col_id["value"])
                load_cols()
                clear_form()

        def print_col(for_student: bool) -> None:
            if not selected_col_id["value"]:
                return
            try:
                export_dir = self._default_export_dir()
                path = self.library_service.export_collection_pdf(selected_col_id["value"], export_dir, for_student=for_student)
                self._print_document(path)
            except Exception as e:
                self._show_error(e)

        def print_student() -> None: print_col(True)
        def print_teacher() -> None: print_col(False)

        tree.bind("<<TreeviewSelect>>", on_select)
        
        self._grid_form_buttons(
            form,
            [
                ("Salvar", save_col),
                ("Limpar", clear_form),
                ("Apagar", del_col),
                ("PDF Aluno", print_student),
                ("PDF Professor", print_teacher),
            ],
            start_row=4
        )
        load_cols()

    def _build_importador_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="Cole o texto PGN completo abaixo. As posições marcadas com '!' ou '!!' serão convertidas em exercícios.", anchor="w").grid(row=0, column=0, padx=16, pady=8, sticky="ew")
        
        pgn_text = ctk.CTkTextbox(parent)
        pgn_text.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")

        def do_import() -> None:
            content = pgn_text.get("1.0", "end-1c").strip()
            if not content:
                self._show_warning("Cole o texto PGN.")
                return
            try:
                count = self.library_service.import_pgn(content)
                self._show_info(f"{count} posições foram importadas com sucesso!")
                pgn_text.delete("1.0", "end")
            except Exception as e:
                self._show_error(e)

        btn = ctk.CTkButton(parent, text="Extrair PGN e Salvar na Biblioteca", command=do_import)
        btn.grid(row=2, column=0, padx=16, pady=(8, 16), sticky="ew")

    def _build_historico_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=16, pady=(0, 8))

        classes_opt = ctk.CTkOptionMenu(controls, values=["Selecionar turma..."])
        classes_opt.pack(side="left", padx=(0, 8))
        
        class_map: dict[str, int] = {}
        for cl in self.db.list_classes():
            label = f"{cl['name']} ({cl.get('club_name', '')})"
            class_map[label] = cl["id"]
        
        if class_map:
            classes_opt.configure(values=list(class_map.keys()))
            classes_opt.set(list(class_map.keys())[0])

        tree = self._make_tree(
            parent,
            ["id", "class", "collection", "item", "date", "notes"],
            {"id": "ID", "class": "Turma", "collection": "Apostila", "item": "Exercício Avulso", "date": "Data de Envio", "notes": "Notas"},
            {"id": 40, "class": 150, "collection": 150, "item": 150, "date": 100, "notes": 150}
        )
        tree.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")

        def load_hist() -> None:
            tree.delete(*tree.get_children())
            for h in self.library_service.list_history():
                tree.insert("", "end", values=(h["id"], h.get("class_name"), h.get("collection_name"), h.get("item_name"), h.get("sent_date"), h.get("notes")))

        def registrar() -> None:
            sel_class = classes_opt.get()
            if sel_class not in class_map: return
            cid = class_map[sel_class]
            
            # Perguntar o que registrar (simplificado)
            dialog = ctk.CTkInputDialog(text="ID da Apostila a registrar:", title="Registrar Histórico")
            col_id_str = dialog.get_input()
            if col_id_str and col_id_str.isdigit():
                col_id = int(col_id_str)
                # Check for 183 days repetition
                repeated = self.library_service.check_repetition(class_id=cid, collection_id=col_id)
                if repeated:
                    msg = "Atenção: Os seguintes exercícios já foram aplicados nesta turma nos últimos 6 meses:\n\n"
                    msg += "\n".join(f"- {title}" for title in repeated)
                    msg += "\n\nDeseja registrar o envio mesmo assim?"
                    if not self._confirm_action("Repetição Detectada", msg):
                        return
                        
                self.library_service.record_history(class_id=cid, collection_id=col_id, notes="Enviado pelo sistema")
                load_hist()

        ctk.CTkButton(controls, text="Registrar Envio Manual", command=registrar).pack(side="left")
        ctk.CTkButton(controls, text="Atualizar", command=load_hist).pack(side="left", padx=8)

        load_hist()
