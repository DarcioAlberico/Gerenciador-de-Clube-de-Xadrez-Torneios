from __future__ import annotations

from ..support import *


# Cores PADRAO do modelo de diploma: sao DADO do template (vao para o banco e
# para o PDF), nao cor da interface — por isso nao seguem o tema.
DIPLOMA_COR_PRIMARIA_PADRAO = "#1E3A8A"
DIPLOMA_COR_DESTAQUE_PADRAO = "#93C5FD"


class SettingsCertificatesMixin:
    def _build_certificate_style_controls(self, parent: Any) -> tuple[Any, Any, Any]:
        """Cria o frame de controles de estilo/marca d'agua dos diplomas.

        Devolve (frame, style_payload, load_style): o frame para posicionar, uma
        funcao que le os controles num dict de payload, e outra que carrega um
        modelo nos controles. Isola os mapas estilo/paleta/peca da tela.
        """
        from src.services.certificates.palettes import PALETTES
        from src.services.certificates.styles import STYLE_PRESETS

        style_by_label = {preset.name: preset.key for preset in STYLE_PRESETS.values()}
        label_by_style = {key: label for label, key in style_by_label.items()}
        palette_by_label = {"Automatica (cores acima)": ""}
        for palette in PALETTES.values():
            palette_by_label[palette.name] = palette.key
        label_by_palette = {key: label for label, key in palette_by_label.items()}
        wm_by_label = {
            "Padrão do estilo": "", "Peca de xadrez": "piece", "Tabuleiro": "board",
            "Numeral": "numeral", "Imagem importada": "image", "Nenhuma": "none",
        }
        label_by_wm = {key: label for label, key in wm_by_label.items()}
        piece_by_label = {"Cavalo": "knight", "Torre": "rook", "Dama": "queen", "Rei": "king", "Peao": "pawn"}
        label_by_piece = {key: label for label, key in piece_by_label.items()}
        kind_by_label = {"Gerado (estilo)": "generated", "Imagem com campos": "image_overlay"}
        label_by_kind = {key: label for label, key in kind_by_label.items()}

        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text="Estilo do diploma").grid(row=0, column=0, padx=10, pady=(8, 6), sticky="w")
        style_option = ctk.CTkOptionMenu(frame, values=list(style_by_label), width=250)
        style_option.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(frame, text="Paleta de cores").grid(row=2, column=0, padx=10, pady=(2, 4), sticky="w")
        palette_option = ctk.CTkOptionMenu(frame, values=list(palette_by_label), width=250)
        palette_option.grid(row=3, column=0, padx=10, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(frame, text="Marca d'agua").grid(row=4, column=0, padx=10, pady=(2, 4), sticky="w")
        watermark_kind_option = ctk.CTkOptionMenu(frame, values=list(wm_by_label), width=250)
        watermark_kind_option.grid(row=5, column=0, padx=10, pady=(0, 6), sticky="ew")
        watermark_piece_option = ctk.CTkOptionMenu(frame, values=list(piece_by_label), width=250)
        watermark_piece_option.grid(row=6, column=0, padx=10, pady=(0, 6), sticky="ew")
        watermark_image_entry = ctk.CTkEntry(frame, width=250, placeholder_text="Imagem da marca d'agua (opcional)")
        watermark_image_entry.grid(row=7, column=0, padx=10, pady=(0, 6), sticky="ew")

        def choose_watermark() -> None:
            file_path = filedialog.askopenfilename(
                title="Escolher imagem da marca d'agua", initialdir=str(BASE_DIR),
                filetypes=[("Imagens", "*.png *.jpg *.jpeg"), ("Todos os arquivos", "*.*")],
            )
            if file_path:
                watermark_image_entry.delete(0, "end")
                watermark_image_entry.insert(0, file_path)

        ctk.CTkButton(frame, text="Escolher imagem da marca d'agua", command=choose_watermark).grid(
            row=8, column=0, padx=10, pady=(0, 8), sticky="ew")
        seal_switch = ctk.CTkSwitch(frame, text="Selo / medalha")
        seal_switch.grid(row=9, column=0, padx=10, pady=(0, 4), sticky="w")
        watermark_switch = ctk.CTkSwitch(frame, text="Marca d'agua ligada")
        watermark_switch.grid(row=10, column=0, padx=10, pady=(0, 4), sticky="w")
        medal_switch = ctk.CTkSwitch(frame, text="Medalha por colocacao")
        medal_switch.grid(row=11, column=0, padx=10, pady=(0, 8), sticky="w")
        for switch in (seal_switch, watermark_switch, medal_switch):
            switch.select()
        ctk.CTkLabel(frame, text="Modo do diploma").grid(row=12, column=0, padx=10, pady=(2, 4), sticky="w")
        kind_option = ctk.CTkOptionMenu(frame, values=list(kind_by_label), width=250)
        kind_option.grid(row=13, column=0, padx=10, pady=(0, 8), sticky="ew")

        def style_payload() -> dict[str, Any]:
            return {
                "style_preset": style_by_label.get(style_option.get(), "classic"),
                "palette_key": palette_by_label.get(palette_option.get(), ""),
                "watermark_kind": wm_by_label.get(watermark_kind_option.get(), ""),
                "watermark_piece": piece_by_label.get(watermark_piece_option.get(), ""),
                "watermark_image_path": watermark_image_entry.get().strip(),
                "seal_enabled": 1 if seal_switch.get() else 0,
                "watermark_enabled": 1 if watermark_switch.get() else 0,
                "medal_by_placement": 1 if medal_switch.get() else 0,
                "template_kind": kind_by_label.get(kind_option.get(), "generated"),
            }

        def load_style(template: dict[str, Any]) -> None:
            style_option.set(label_by_style.get(str(template.get("style_preset") or "classic"), "Clássico"))
            palette_option.set(label_by_palette.get(str(template.get("palette_key") or ""), "Automatica (cores acima)"))
            watermark_kind_option.set(label_by_wm.get(str(template.get("watermark_kind") or ""), "Padrão do estilo"))
            watermark_piece_option.set(label_by_piece.get(str(template.get("watermark_piece") or "rook"), "Cavalo"))
            watermark_image_entry.delete(0, "end")
            watermark_image_entry.insert(0, str(template.get("watermark_image_path") or ""))
            for switch, key in (
                (seal_switch, "seal_enabled"), (watermark_switch, "watermark_enabled"),
                (medal_switch, "medal_by_placement"),
            ):
                switch.select() if int(template.get(key, 1) or 0) else switch.deselect()
            kind_option.set(label_by_kind.get(str(template.get("template_kind") or "generated"), "Gerado (estilo)"))

        return frame, style_payload, load_style

    def show_certificates(self) -> None:
        tournament = (
            self.db.get_tournament(self.current_tournament_id)
            if getattr(self, "current_tournament_id", None)
            else None
        )
        self._clear_content()
        self._page_title(
            "Diplomas",
            f"Torneio atual: {tournament['name']}" if tournament else "Gere certificados e diplomas por contexto.",
        )
        if tournament:
            self._build_tournament_nav("certificates")

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form_panel = self._make_scrollable_panel(body, width=360)
        form_panel.grid(row=0, column=0, padx=(0, 14), sticky="nsw")

        table_panel = self._make_panel(body)
        table_panel.grid(row=0, column=1, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)

        context_values = [
            "Torneio",
            "Membros/alunos",
            "Aula/turma",
            "Evento",
            "Ranking interno",
        ]
        context_keys = {
            "Torneio": "tournament",
            "Membros/alunos": "members",
            "Aula/turma": "training",
            "Evento": "event",
            "Ranking interno": "ranking",
        }
        context_default_types = {
            "tournament": "participation",
            "members": "member_certificate",
            "training": "training_participation",
            "event": "event_participation",
            "ranking": "internal_ranking",
        }
        source_labels = {
            "tournament": "Torneio",
            "members": "Origem",
            "training": "Aula/turma",
            "event": "Evento",
            "ranking": "Origem",
        }
        history_context_labels = {
            "tournament": "Torneio",
            "members": "Membros",
            "training": "Aula",
            "event": "Evento",
            "ranking": "Ranking",
        }
        recipient_modes = {
            "tournament": ["Todos", "Top N geral", "Top N por categoria", "Selecionados na lista"],
            "members": ["Todos", "Selecionados na lista"],
            "training": ["Todos", "Selecionados na lista"],
            "event": ["Todos", "Selecionados na lista"],
            "ranking": ["Todos", "Top N geral", "Selecionados na lista"],
        }
        type_labels = {value: label for label, value in CERTIFICATE_TYPE_VALUES.items()}
        orientation_labels = {value: label for label, value in CERTIFICATE_ORIENTATION_VALUES.items()}
        templates = self.certificate_service.list_templates(active_only=True)
        template_map = {str(template["name"]): template for template in templates}
        template_values = list(template_map) or ["Sem modelo"]
        selected_template_id: dict[str, int | None] = {
            "value": int(templates[0]["id"]) if templates else None,
        }
        source_map: dict[str, int] = {}
        recipient_row_map: dict[str, int] = {}

        ctk.CTkLabel(form_panel, text="Contexto").grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        context_option = ctk.CTkOptionMenu(form_panel, values=context_values, width=290)
        context_option.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        source_label = ctk.CTkLabel(form_panel, text="Torneio")
        source_label.grid(row=2, column=0, padx=16, pady=(2, 4), sticky="w")
        source_option = ctk.CTkOptionMenu(form_panel, values=["Nenhum registro"], width=290)
        source_option.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Modelo salvo").grid(row=4, column=0, padx=16, pady=(2, 4), sticky="w")
        template_option = ctk.CTkOptionMenu(form_panel, values=template_values, width=290)
        template_option.grid(row=5, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Nome do modelo").grid(row=6, column=0, padx=16, pady=(2, 4), sticky="w")
        template_name_entry = ctk.CTkEntry(form_panel, width=290)
        template_name_entry.grid(row=7, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Tipo").grid(row=8, column=0, padx=16, pady=(2, 4), sticky="w")
        type_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_TYPE_VALUES.keys()), width=290)
        type_option.grid(row=9, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Orientacao").grid(row=10, column=0, padx=16, pady=(2, 4), sticky="w")
        orientation_option = ctk.CTkOptionMenu(form_panel, values=list(CERTIFICATE_ORIENTATION_VALUES.keys()), width=290)
        orientation_option.grid(row=11, column=0, padx=16, pady=(0, 10), sticky="ew")

        assets_frame = ctk.CTkFrame(form_panel, fg_color="transparent")
        assets_frame.grid(row=12, column=0, padx=16, pady=(2, 10), sticky="ew")
        assets_frame.grid_columnconfigure(0, weight=1)

        def choose_image(entry: ctk.CTkEntry, title: str) -> None:
            file_path = filedialog.askopenfilename(
                title=title,
                initialdir=str(BASE_DIR),
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if file_path:
                entry.delete(0, "end")
                entry.insert(0, file_path)
                update_count()

        ctk.CTkLabel(assets_frame, text="Logo principal").grid(row=0, column=0, pady=(0, 4), sticky="w")
        logo_entry = ctk.CTkEntry(assets_frame, width=290)
        logo_entry.grid(row=1, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo principal",
            command=lambda: choose_image(logo_entry, "Escolher logo principal"),
        ).grid(row=2, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Logo secundario").grid(row=3, column=0, pady=(0, 4), sticky="w")
        secondary_logo_entry = ctk.CTkEntry(assets_frame, width=290)
        secondary_logo_entry.grid(row=4, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher logo secundario",
            command=lambda: choose_image(secondary_logo_entry, "Escolher logo secundario"),
        ).grid(row=5, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Imagem de fundo").grid(row=6, column=0, pady=(0, 4), sticky="w")
        background_image_entry = ctk.CTkEntry(assets_frame, width=290)
        background_image_entry.grid(row=7, column=0, pady=(0, 6), sticky="ew")
        ctk.CTkButton(
            assets_frame,
            text="Escolher fundo",
            command=lambda: choose_image(background_image_entry, "Escolher imagem de fundo"),
        ).grid(row=8, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(assets_frame, text="Opacidade do fundo").grid(row=9, column=0, pady=(0, 4), sticky="w")
        background_opacity_entry = ctk.CTkEntry(assets_frame, width=90)
        background_opacity_entry.grid(row=10, column=0, pady=(0, 0), sticky="w")
        background_opacity_entry.insert(0, "0.18")

        ctk.CTkLabel(form_panel, text="Cor principal").grid(row=15, column=0, padx=16, pady=(2, 4), sticky="w")
        primary_color_entry = ctk.CTkEntry(form_panel, width=140)
        primary_color_entry.grid(row=16, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Cor de destaque").grid(row=17, column=0, padx=16, pady=(2, 4), sticky="w")
        accent_color_entry = ctk.CTkEntry(form_panel, width=140)
        accent_color_entry.grid(row=18, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do titulo").grid(row=19, column=0, padx=16, pady=(2, 4), sticky="w")
        title_font_entry = ctk.CTkEntry(form_panel, width=80)
        title_font_entry.grid(row=20, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do texto").grid(row=21, column=0, padx=16, pady=(2, 4), sticky="w")
        body_font_entry = ctk.CTkEntry(form_panel, width=80)
        body_font_entry.grid(row=22, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Fonte do rodape").grid(row=23, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_font_entry = ctk.CTkEntry(form_panel, width=80)
        footer_font_entry.grid(row=24, column=0, padx=16, pady=(0, 10), sticky="w")

        ctk.CTkLabel(form_panel, text="Título").grid(row=25, column=0, padx=16, pady=(2, 4), sticky="w")
        title_entry = ctk.CTkEntry(form_panel, width=290)
        title_entry.grid(row=26, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Texto principal").grid(row=27, column=0, padx=16, pady=(2, 4), sticky="w")
        body_textbox = ctk.CTkTextbox(form_panel, width=290, height=110)
        body_textbox.grid(row=28, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Rodape").grid(row=29, column=0, padx=16, pady=(2, 4), sticky="w")
        footer_entry = ctk.CTkEntry(form_panel, width=290)
        footer_entry.grid(row=30, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura esquerda").grid(row=31, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_left_entry = ctk.CTkEntry(form_panel, width=290)
        signature_left_entry.grid(row=32, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Assinatura direita").grid(row=33, column=0, padx=16, pady=(2, 4), sticky="w")
        signature_right_entry = ctk.CTkEntry(form_panel, width=290)
        signature_right_entry.grid(row=34, column=0, padx=16, pady=(0, 14), sticky="ew")

        ctk.CTkLabel(form_panel, text="Destinatarios").grid(row=35, column=0, padx=16, pady=(4, 4), sticky="w")
        recipient_option = ctk.CTkOptionMenu(form_panel, values=recipient_modes["tournament"], width=250)
        recipient_option.grid(row=36, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Limite").grid(row=37, column=0, padx=16, pady=(2, 4), sticky="w")
        top_entry = ctk.CTkEntry(form_panel, width=120)
        top_entry.grid(row=38, column=0, padx=16, pady=(0, 10), sticky="w")
        top_entry.insert(0, "3")

        ctk.CTkLabel(form_panel, text="Categoria").grid(row=39, column=0, padx=16, pady=(2, 4), sticky="w")
        category_option = ctk.CTkOptionMenu(form_panel, values=["Todas"], width=250)
        category_option.grid(row=40, column=0, padx=16, pady=(0, 10), sticky="ew")

        count_label = ctk.CTkLabel(form_panel, text="", text_color=THEME_TEXT_SUB, wraplength=270, justify="left")
        count_label.grid(row=41, column=0, padx=16, pady=(0, 14), sticky="w")

        style_frame, style_payload, load_style = self._build_certificate_style_controls(form_panel)
        style_frame.grid(row=42, column=0, padx=16, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(form_panel, text="Código de verificacao").grid(row=43, column=0, padx=16, pady=(2, 4), sticky="w")
        verification_code_entry = ctk.CTkEntry(form_panel, width=250)
        verification_code_entry.grid(row=44, column=0, padx=16, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(
            table_panel,
            text="Selecione destinatarios na lista apenas quando usar destinatarios selecionados.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        tree_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        tree_holder.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        tree_holder.grid_columnconfigure(0, weight=1)
        tree_holder.grid_rowconfigure(0, weight=1)

        tree = self._make_tree(
            tree_holder,
            ["pos", "name", "category", "points", "status"],
            {
                "pos": "Pos",
                "name": "Nome",
                "category": "Categoria",
                "points": "Pts",
                "status": "Status",
            },
            {
                "pos": 60,
                "name": 280,
                "category": 140,
                "points": 80,
                "status": 130,
            },
            visible_rows=16,
        )
        tree.configure(selectmode="extended")

        ctk.CTkLabel(
            table_panel,
            text="Histórico recente de emissoes",
            text_color=THEME_TEXT_SUB,
        ).grid(row=2, column=0, padx=16, pady=(0, 8), sticky="w")

        history_holder = ctk.CTkFrame(table_panel, fg_color="transparent")
        history_holder.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        history_holder.grid_columnconfigure(0, weight=1)
        history_holder.grid_rowconfigure(0, weight=1)
        history_tree = self._make_tree(
            history_holder,
            ["issued_at", "recipient", "context", "code", "status"],
            {
                "issued_at": "Emissao",
                "recipient": "Destinatario",
                "context": "Contexto",
                "code": "Código",
                "status": "Status",
            },
            {
                "issued_at": 130,
                "recipient": 240,
                "context": 90,
                "code": 130,
                "status": 90,
            },
            visible_rows=5,
        )
        history_row_map: dict[str, dict[str, Any]] = {}

        def context_key() -> str:
            return context_keys.get(context_option.get(), "tournament")

        def selected_source_id() -> int | None:
            return source_map.get(source_option.get())

        def source_id_required(label: str) -> int:
            source_id = selected_source_id()
            if not source_id:
                raise AppError(f"Selecione {label}.")
            return source_id

        def selected_recipient_ids() -> list[int]:
            return [recipient_row_map[item_id] for item_id in tree.selection() if item_id in recipient_row_map]

        def selected_category() -> str:
            return "" if category_option.get() == "Todas" else category_option.get()

        def set_entry(entry: ctk.CTkEntry, value: Any) -> None:
            entry.delete(0, "end")
            entry.insert(0, str(value or ""))

        def set_textbox(textbox: ctk.CTkTextbox, value: Any) -> None:
            textbox.delete("1.0", "end")
            textbox.insert("1.0", str(value or ""))

        def textbox_value(textbox: ctk.CTkTextbox) -> str:
            return textbox.get("1.0", "end").strip()

        def current_template_payload() -> dict[str, Any]:
            return {
                "name": template_name_entry.get().strip(),
                "certificate_type": CERTIFICATE_TYPE_VALUES[type_option.get()],
                "orientation": CERTIFICATE_ORIENTATION_VALUES[orientation_option.get()],
                "title_template": title_entry.get().strip(),
                "body_template": textbox_value(body_textbox),
                "footer_template": footer_entry.get().strip(),
                "signature_left": signature_left_entry.get().strip(),
                "signature_right": signature_right_entry.get().strip(),
                "logo_path": logo_entry.get().strip(),
                "background_image_path": background_image_entry.get().strip(),
                "background_opacity": background_opacity_entry.get().strip(),
                "secondary_logo_path": secondary_logo_entry.get().strip(),
                "primary_color": primary_color_entry.get().strip(),
                "accent_color": accent_color_entry.get().strip(),
                "title_font_size": title_font_entry.get().strip(),
                "body_font_size": body_font_entry.get().strip(),
                "footer_font_size": footer_font_entry.get().strip(),
                "active": 1,
                **style_payload(),
            }

        def load_template_fields(template: dict[str, Any]) -> None:
            selected_template_id["value"] = int(template["id"])
            set_entry(template_name_entry, template.get("name", ""))
            type_option.set(type_labels.get(template.get("certificate_type"), "Participacao"))
            orientation_option.set(orientation_labels.get(template.get("orientation"), "Paisagem"))
            set_entry(title_entry, template.get("title_template", ""))
            set_textbox(body_textbox, template.get("body_template", ""))
            set_entry(footer_entry, template.get("footer_template", ""))
            set_entry(signature_left_entry, template.get("signature_left", ""))
            set_entry(signature_right_entry, template.get("signature_right", ""))
            set_entry(logo_entry, template.get("logo_path", ""))
            set_entry(background_image_entry, template.get("background_image_path", ""))
            set_entry(background_opacity_entry, template.get("background_opacity", 0.18))
            set_entry(secondary_logo_entry, template.get("secondary_logo_path", ""))
            set_entry(primary_color_entry, template.get("primary_color", DIPLOMA_COR_PRIMARIA_PADRAO))
            set_entry(accent_color_entry, template.get("accent_color", DIPLOMA_COR_DESTAQUE_PADRAO))
            set_entry(title_font_entry, template.get("title_font_size", 32))
            set_entry(body_font_entry, template.get("body_font_size", 18))
            set_entry(footer_font_entry, template.get("footer_font_size", 10))
            load_style(template)

        def select_template_for_type(certificate_type: str) -> None:
            selected = next(
                (template for template in templates if template.get("certificate_type") == certificate_type),
                templates[0] if templates else None,
            )
            if selected:
                template_option.set(str(selected["name"]))
                load_template_fields(selected)

        def reload_templates(select_id: int | None = None) -> None:
            nonlocal templates, template_map
            templates = self.certificate_service.list_templates(active_only=True)
            template_map = {str(template["name"]): template for template in templates}
            values = list(template_map) or ["Sem modelo"]
            template_option.configure(values=values)
            selected = next(
                (template for template in templates if select_id and int(template["id"]) == select_id),
                None,
            )
            if not selected:
                selected = next(
                    (
                        template
                        for template in templates
                        if template.get("certificate_type") == context_default_types[context_key()]
                    ),
                    templates[0] if templates else None,
                )
            if selected:
                template_option.set(str(selected["name"]))
                load_template_fields(selected)
                update_count()

        def on_template_select(value: str) -> None:
            template = template_map.get(value)
            if template:
                load_template_fields(template)
                update_count()

        def source_label_for(record: dict[str, Any], title_key: str, date_key: str = "") -> str:
            title = str(record.get(title_key) or f"Registro {record.get('id')}")
            date_value = str(record.get(date_key) or "").strip() if date_key else ""
            prefix = f"{date_value} - " if date_value else ""
            return f"{prefix}{title} (#{record.get('id')})"

        def reload_sources() -> None:
            source_map.clear()
            current_context = context_key()
            source_label.configure(text=source_labels[current_context])
            if current_context == "tournament":
                records = self.db.list_tournaments()
                values = [source_label_for(item, "name") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = getattr(self, "current_tournament_id", None)
            elif current_context == "training":
                records = self.db.list_training_sessions()
                values = [source_label_for(item, "title", "session_date") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = None
            elif current_context == "event":
                records = self.db.list_club_events()
                values = [source_label_for(item, "title", "event_date") for item in records]
                for label, item in zip(values, records, strict=False):
                    source_map[label] = int(item["id"])
                selected_id = None
            else:
                values = ["Todos os membros"]
                source_map["Todos os membros"] = 0
                selected_id = 0

            if not values:
                values = ["Nenhum registro"]
            source_option.configure(values=values)
            selected_label = next(
                (label for label, item_id in source_map.items() if selected_id and item_id == selected_id),
                values[0],
            )
            source_option.set(selected_label)

        def configure_recipient_modes() -> None:
            values = recipient_modes[context_key()]
            recipient_option.configure(values=values)
            if recipient_option.get() not in values:
                recipient_option.set("Top N geral" if context_key() == "ranking" else values[0])

        def refresh_category_values() -> None:
            current_context = context_key()
            categories: list[str] = []
            try:
                if current_context == "tournament" and selected_source_id():
                    categories = self.certificate_service.tournament_categories(source_id_required("um torneio"))
                elif current_context == "ranking":
                    categories = sorted(
                        {
                            str(member.get("category") or "").strip()
                            for member in self.db.list_members(active_only=True)
                            if str(member.get("category") or "").strip()
                        },
                        key=lambda value: value.casefold(),
                    )
            except Exception:
                categories = []
            values = ["Todas"] + categories if categories else ["Todas"]
            current = category_option.get()
            category_option.configure(values=values)
            category_option.set(current if current in values else "Todas")

        def update_tree_headings() -> None:
            headings = {
                "tournament": ("Pos", "Nome", "Categoria", "Pts", "Status"),
                "members": ("#", "Nome", "Turma", "Rating", "Status"),
                "training": ("#", "Nome", "Turma", "Presenca", "Status"),
                "event": ("#", "Nome", "Clube", "Categoria", "Status"),
                "ranking": ("Pos", "Nome", "Categoria", "Rating", "Jogos"),
            }[context_key()]
            for column, text in zip(("pos", "name", "category", "points", "status"), headings, strict=False):
                tree.heading(column, text=text)

        def clear_recipient_table() -> None:
            recipient_row_map.clear()
            for item_id in tree.get_children():
                tree.delete(item_id)

        def add_recipient_row(values: tuple[Any, Any, Any, Any, Any], recipient_id: int) -> None:
            item_id = tree.insert("", "end", values=values)
            recipient_row_map[item_id] = recipient_id

        def issuance_status_label(item: dict[str, Any]) -> str:
            return "Revogado" if item.get("revoked") else "Valido"

        def issuance_context_label(item: dict[str, Any]) -> str:
            return history_context_labels.get(str(item.get("context_type") or ""), str(item.get("context_type") or ""))

        def refresh_history() -> None:
            history_row_map.clear()
            for item_id in history_tree.get_children():
                history_tree.delete(item_id)
            for item in self.certificate_service.list_issuances(limit=40):
                row_id = history_tree.insert(
                    "",
                    "end",
                    values=(
                        item.get("issued_at", ""),
                        item.get("recipient_name", ""),
                        issuance_context_label(item),
                        item.get("verification_code", ""),
                        issuance_status_label(item),
                    ),
                )
                history_row_map[row_id] = item

        def selected_history_issuance() -> dict[str, Any] | None:
            selection = history_tree.selection()
            if not selection:
                return None
            return history_row_map.get(selection[0])

        def fill_verification_from_history(_event: Any | None = None) -> None:
            issuance = selected_history_issuance()
            if not issuance:
                return
            verification_code_entry.delete(0, "end")
            verification_code_entry.insert(0, str(issuance.get("verification_code") or ""))

        def verify_certificate_code() -> None:
            try:
                code = verification_code_entry.get().strip()
                if not code:
                    issuance = selected_history_issuance()
                    code = str(issuance.get("verification_code") or "") if issuance else ""
                if not code:
                    raise AppError("Informe ou selecione um codigo de verificacao.")
                issuance = self.certificate_service.verify_issuance(code)
                status = issuance_status_label(issuance)
                self._show_info(
                    "Diploma encontrado:\n"
                    f"Codigo: {issuance['verification_code']}\n"
                    f"Status: {status}\n"
                    f"Destinatario: {issuance['recipient_name']}\n"
                    f"Contexto: {issuance_context_label(issuance)}\n"
                    f"Origem: {issuance.get('source_title') or ''}\n"
                    f"Arquivo: {issuance.get('file_path') or ''}"
                )
            except Exception as exc:
                self._show_error(exc)

        def export_verification_site() -> None:
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Exportar verificador de diplomas",
                    initialdir=str(self._default_export_dir()),
                    initialfile="verificador_diplomas.html",
                    defaultextension=".html",
                    filetypes=[
                        ("HTML", "*.html"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != ".html":
                    path = path.with_suffix(".html")
                self._run_background(
                    lambda: self.certificate_service.export_verification_site(path),
                    lambda result_path: self._show_info(f"Verificador exportado:\n{result_path}"),
                    "Exportando verificador...",
                )
            except Exception as exc:
                self._show_error(exc)

        def refresh_recipient_table(_value: str | None = None) -> None:
            clear_recipient_table()
            update_tree_headings()
            try:
                current_context = context_key()
                if current_context == "tournament":
                    tournament_id = source_id_required("um torneio")
                    selected_tournament = self.db.get_tournament(tournament_id)
                    if selected_tournament and selected_tournament.get("competition_type") == "team":
                        count_label.configure(text="Diplomas por equipes ficam para uma etapa futura.")
                        return
                    for item in self.pairing_service.standings(tournament_id):
                        add_recipient_row(
                            (
                                item.get("position", ""),
                                item.get("name", ""),
                                item.get("category", ""),
                                item.get("points", 0),
                                PLAYER_STATUSES.get(item.get("player_status", "active"), "Ativo"),
                            ),
                            int(item["player_id"]),
                        )
                elif current_context == "members":
                    for index, recipient in enumerate(self.certificate_service.member_recipients(), start=1):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("class_name", ""),
                                recipient.get("rating", ""),
                                recipient.get("status", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                elif current_context == "training":
                    session_id = source_id_required("uma aula/turma")
                    for index, recipient in enumerate(
                        self.certificate_service.training_recipients(session_id, present_only=False),
                        start=1,
                    ):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("class_name", ""),
                                recipient.get("status", ""),
                                recipient.get("type_label", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                elif current_context == "event":
                    event_id = source_id_required("um evento")
                    for index, recipient in enumerate(self.certificate_service.event_recipients(event_id), start=1):
                        add_recipient_row(
                            (
                                index,
                                recipient.get("name", ""),
                                recipient.get("club", ""),
                                recipient.get("category", ""),
                                recipient.get("status", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                else:
                    for recipient in self.certificate_service.ranking_recipients(top_n=0):
                        add_recipient_row(
                            (
                                recipient.get("position", ""),
                                recipient.get("name", ""),
                                recipient.get("category", ""),
                                recipient.get("rating", ""),
                                recipient.get("games", ""),
                            ),
                            int(recipient["member_id"]),
                        )
                update_count()
            except Exception as exc:
                count_label.configure(text=str(exc))

        def tournament_payload() -> dict[str, Any]:
            certificate_type = CERTIFICATE_TYPE_VALUES[type_option.get()]
            recipient_mode = recipient_option.get()
            category = selected_category()
            top_n = top_entry.get().strip()
            if recipient_mode == "Todos":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": 0,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N geral":
                return {
                    "certificate_type": certificate_type,
                    "category": "",
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": False,
                }
            if recipient_mode == "Top N por categoria":
                return {
                    "certificate_type": certificate_type,
                    "category": category,
                    "top_n": top_n,
                    "player_ids": None,
                    "by_category": True,
                }
            player_ids = selected_recipient_ids()
            if not player_ids:
                raise AppError("Selecione ao menos um destinatario na lista.")
            return {
                "certificate_type": certificate_type,
                "category": "",
                "top_n": 0,
                "player_ids": player_ids,
                "by_category": False,
            }

        def context_payload() -> dict[str, Any]:
            recipient_mode = recipient_option.get()
            selected_ids = selected_recipient_ids() if recipient_mode == "Selecionados na lista" else None
            if recipient_mode == "Selecionados na lista" and not selected_ids:
                raise AppError("Selecione ao menos um destinatario na lista.")
            current_context = context_key()
            if current_context == "members":
                return {"member_ids": selected_ids, "class_id": None}
            if current_context == "training":
                return {
                    "session_id": source_id_required("uma aula/turma"),
                    "member_ids": selected_ids,
                    "present_only": False,
                }
            if current_context == "event":
                return {"event_id": source_id_required("um evento"), "member_ids": selected_ids}
            if current_context == "ranking":
                return {
                    "member_ids": selected_ids,
                    "category": "" if selected_ids else selected_category(),
                    "top_n": 0 if recipient_mode == "Todos" or selected_ids else top_entry.get().strip(),
                }
            raise AppError("Contexto de diploma invalido.")

        def current_recipients() -> list[dict[str, Any]]:
            current_context = context_key()
            if current_context == "tournament":
                return self.certificate_service.tournament_recipients(
                    source_id_required("um torneio"),
                    **tournament_payload(),
                )
            payload = context_payload()
            if current_context == "members":
                return self.certificate_service.member_recipients(**payload)
            if current_context == "training":
                session_id = int(payload.pop("session_id"))
                return self.certificate_service.training_recipients(session_id, **payload)
            if current_context == "event":
                event_id = int(payload.pop("event_id"))
                return self.certificate_service.event_recipients(event_id, **payload)
            if current_context == "ranking":
                return self.certificate_service.ranking_recipients(**payload)
            raise AppError("Contexto de diploma invalido.")

        def update_count(_value: str | None = None) -> None:
            try:
                recipients = current_recipients()
                preview = self.certificate_service.preview_template_recipient(
                    current_template_payload(),
                    recipients[0],
                )
                count_label.configure(text=f"{len(recipients)} diploma(s). Preview: {preview['title']}")
            except Exception as exc:
                count_label.configure(text=str(exc))

        def apply_type_defaults(_value: str | None = None) -> None:
            current_context = context_key()
            model = CERTIFICATE_TYPE_VALUES[type_option.get()]
            values = recipient_modes[current_context]
            if current_context == "tournament":
                if model == "participation":
                    recipient_option.set("Todos")
                elif model == "overall_award":
                    recipient_option.set("Top N geral")
                else:
                    recipient_option.set("Top N por categoria")
            elif current_context == "ranking" and "Top N geral" in values:
                recipient_option.set("Top N geral")
            else:
                recipient_option.set(values[0])
            update_count()

        def on_source_select(_value: str | None = None) -> None:
            if context_key() == "tournament" and selected_source_id():
                self.current_tournament_id = selected_source_id()
            refresh_category_values()
            refresh_recipient_table()

        def on_context_select(_value: str | None = None) -> None:
            reload_sources()
            configure_recipient_modes()
            refresh_category_values()
            select_template_for_type(context_default_types[context_key()])
            apply_type_defaults()
            refresh_recipient_table()

        def default_filename() -> str:
            context_name = self._safe_filename(context_option.get(), "diplomas")
            source_name = self._safe_filename(source_option.get(), context_name)
            model_name = self._safe_filename(template_name_entry.get(), "modelo")
            return f"{context_name}_{source_name}_{model_name}.pdf"

        def save_template() -> None:
            try:
                template_id = selected_template_id["value"]
                if not template_id:
                    raise AppError("Selecione um modelo.")
                self.certificate_service.update_template(template_id, current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo salvo.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def save_template_as_new() -> None:
            try:
                template_id = self.certificate_service.create_template(current_template_payload())
                reload_templates(template_id)
                self._show_toast("Modelo criado.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def preview_template() -> None:
            try:
                import tempfile
                import webbrowser

                out = Path(tempfile.gettempdir()) / "previa_diploma.pdf"
                self.certificate_service.preview_template_pdf(current_template_payload(), out)
                webbrowser.open(out.resolve().as_uri())
            except Exception as exc:
                self._show_error(exc)

        def generate_gallery() -> None:
            try:
                result = self.certificate_service.seed_gallery()
                reload_templates()
                self._show_toast(f"Galeria: {result['created']} novos modelos prontos.", kind="success")
            except Exception as exc:
                self._show_error(exc)

        def export_art_guide() -> None:
            try:
                orientation = CERTIFICATE_ORIENTATION_VALUES[orientation_option.get()]
                file_path = filedialog.asksaveasfilename(
                    title="Exportar guia de arte",
                    initialdir=str(self._default_export_dir()),
                    initialfile="guia_arte_diploma.pdf",
                    defaultextension=".pdf",
                    filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
                )
                if not file_path:
                    return
                result = self.certificate_service.export_art_guide(file_path, orientation)
                self._show_info(f"Guia de arte exportado:\n{result}")
            except Exception as exc:
                self._show_error(exc)

        def export_certificates() -> None:
            try:
                template_payload = current_template_payload()
                export_context = context_key()
                export_source_id: int | None = None
                export_kwargs: dict[str, Any]
                if export_context == "tournament":
                    export_source_id = source_id_required("um torneio")
                    export_kwargs = tournament_payload()
                else:
                    export_kwargs = context_payload()
                    if export_context == "training":
                        export_source_id = int(export_kwargs.pop("session_id"))
                    elif export_context == "event":
                        export_source_id = int(export_kwargs.pop("event_id"))

                file_path = filedialog.asksaveasfilename(
                    title="Gerar diplomas",
                    initialdir=str(self._default_export_dir()),
                    initialfile=default_filename(),
                    defaultextension=".pdf",
                    filetypes=[
                        ("PDF", "*.pdf"),
                        ("Todos os arquivos", "*.*"),
                    ],
                )
                if not file_path:
                    return
                path = Path(file_path)
                if path.suffix.lower() != ".pdf":
                    path = path.with_suffix(".pdf")

                def write_export() -> dict[str, Any]:
                    if export_context == "tournament":
                        return self.certificate_service.export_tournament_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "members":
                        return self.certificate_service.export_member_certificates(
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "training":
                        return self.certificate_service.export_training_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "event":
                        return self.certificate_service.export_event_certificates(
                            int(export_source_id or 0),
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    if export_context == "ranking":
                        return self.certificate_service.export_ranking_certificates(
                            path,
                            template_data=template_payload,
                            **export_kwargs,
                        )
                    raise AppError("Contexto de diploma invalido.")

                def export_done(result: dict[str, Any]) -> None:
                    refresh_history()
                    codes = result.get("verification_codes") or []
                    code_preview = ", ".join(str(code) for code in codes[:3])
                    if len(codes) > 3:
                        code_preview = f"{code_preview}..."
                    suffix = f"\nCodigos: {code_preview}" if code_preview else ""
                    self._show_info(
                        f"{result['exported']} diploma(s) exportados:\n{result['path']}{suffix}"
                    )

                self._run_background(
                    write_export,
                    export_done,
                    "Gerando diplomas...",
                )
            except Exception as exc:
                self._show_error(exc)

        context_option.configure(command=on_context_select)
        source_option.configure(command=on_source_select)
        template_option.configure(command=on_template_select)
        type_option.configure(command=apply_type_defaults)
        orientation_option.configure(command=update_count)
        recipient_option.configure(command=update_count)
        category_option.configure(command=update_count)
        tree.bind("<<TreeviewSelect>>", update_count)
        history_tree.bind("<<TreeviewSelect>>", fill_verification_from_history)

        context_option.set("Torneio")
        on_context_select("Torneio")
        refresh_history()

        ctk.CTkButton(form_panel, text="Consultar codigo", command=verify_certificate_code).grid(
            row=45,
            column=0,
            padx=16,
            pady=(0, 8),
            sticky="ew",
        )

        self._grid_form_buttons(
            form_panel,
            [
                ("Pré-visualizar", preview_template),
                ("Gerar galeria (50 modelos)", generate_gallery),
                ("Exportar guia de arte", export_art_guide),
                ("Salvar modelo", save_template),
                ("Salvar como novo", save_template_as_new),
                ("Gerar PDF", export_certificates),
                ("Exportar verificador", export_verification_site),
            ],
            start_row=46,
        )
