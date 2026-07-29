"""Bases oficiais de rating (FIDE, CBX, LBX e estrangeiras) — B-6.

Duas coisas diferentes moram aqui, e confundi-las custa caro:

- **importar uma lista** enche a base local do Albericus (não toca no torneio);
- **comparar/aplicar** leva o que está na base local para os **inscritos**.

A segunda passa por uma pré-visualização com seleção linha a linha, e isso é
deliberado: rating oficial que chega errado vira emparceiramento errado, e o
árbitro precisa ver o "antes → depois" de cada jogador antes de gravar.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ...components import neutral_button
from ...i18n import t
from ...support import THEME_TEXT_MAIN, THEME_TEXT_SUB, filedialog, font_section, font_subsection
from . import file_types
from .actions import ScreenActions, guarded
from .dialogs import actions_row, close_button, modal

def comparison_columns() -> dict[str, tuple[str, int]]:
    """Código → (título, largura) da tabela "antes → depois"."""
    return {
        "status": (t("players.preview.status"), 90),
        "player": (t("players.official.registered_player"), 210),
        "changes": (t("players.official.changed_fields"), 210),
        "before": (t("players.official.before"), 300),
        "after": (t("players.official.after"), 300),
    }


def unmatched_columns() -> dict[str, tuple[str, int]]:
    """Quem a base oficial não encontrou, com os três IDs para conferência."""
    return {
        "player": (t("players.official.player"), 300),
        "fide": (t("players.field.fide_id"), 150),
        "cbx": (t("players.field.cbx_id"), 150),
        "lbx": (t("players.field.lbx_id"), 150),
    }


class OfficialRatingActions(ScreenActions):
    def __init__(self, host: Any, on_changed: Callable[[], None] | None = None) -> None:
        super().__init__(host, on_changed)
        self.service = host.official_rating_service

    # ---- Encher a base local ---------------------------------------------- #

    @guarded
    def import_list(self, source: str) -> None:
        """Importa um CSV da lista oficial (FIDE/CBX/LBX) para a base local."""
        caminho = filedialog.askopenfilename(
            title=t("players.official.import_title", base=source),
            filetypes=file_types.csv_only(),
        )
        if not caminho:
            return

        def concluir(resultado: dict[str, Any]) -> None:
            self.host._show_info(
                self.with_errors(
                    t(
                        "players.official.imported",
                        quantidade=resultado["imported"],
                        base=source,
                    ),
                    resultado["errors"],
                )
            )

        self.background(
            lambda: self.service.import_official_csv(caminho, source),
            concluir,
            t("players.official.import_working", base=source),
        )

    @guarded
    def update_lbx_from_internet(self) -> None:
        def concluir(resultado: dict[str, Any]) -> None:
            self.host._show_info(
                self.with_errors(
                    t("players.official.lbx_downloaded", quantidade=resultado["imported"]),
                    resultado["errors"],
                )
            )

        self.background(
            self.service.import_lbx_lists_from_url,
            concluir,
            t("players.official.lbx_working"),
        )

    @guarded
    def import_foreign_list(self) -> None:
        """Lista de uma federação estrangeira, com cadastro embutido da federação."""
        federacoes = self.service.list_foreign_federations()
        opcoes = [
            f"{codigo} - {dados.get('name', codigo)}" for codigo, dados in sorted(federacoes.items())
        ]
        vazio = t("players.foreign.none")

        dialog = modal(self.host, t("players.foreign.title"), "480x300")

        ctk.CTkLabel(dialog, text=t("players.foreign.federation"), font=font_subsection()).grid(
            row=0, column=0, padx=16, pady=(16, 4), sticky="w"
        )
        seletor = ctk.CTkOptionMenu(dialog, values=opcoes or [vazio])
        seletor.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            dialog, text=t("players.foreign.add_hint"), text_color=THEME_TEXT_SUB
        ).grid(row=2, column=0, padx=16, pady=(0, 2), sticky="w")
        linha = ctk.CTkFrame(dialog, fg_color="transparent")
        linha.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="ew")
        linha.grid_columnconfigure(1, weight=1)
        codigo_entry = ctk.CTkEntry(linha, width=80, placeholder_text=t("players.foreign.code_hint"))
        codigo_entry.grid(row=0, column=0, padx=(0, 8))
        nome_entry = ctk.CTkEntry(linha, placeholder_text=t("players.foreign.name_hint"))
        nome_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        def adicionar() -> None:
            try:
                codigo = self.service.add_foreign_federation(codigo_entry.get(), nome_entry.get())
            except Exception as exc:  # noqa: BLE001 — código repetido/inválido vira recado
                self.host._show_error(exc)
                return
            self.host._show_toast(t("players.foreign.added", codigo=codigo), kind="success")
            dialog.close()
            self.import_foreign_list()

        ctk.CTkButton(
            linha, text=t("players.foreign.add"), width=100, command=adicionar
        ).grid(row=0, column=2)

        def importar() -> None:
            codigo = seletor.get().split(" - ", maxsplit=1)[0].strip()
            if not codigo or seletor.get() == vazio:
                self.host._show_warning(t("players.foreign.pick"))
                return
            caminho = filedialog.askopenfilename(
                title=t("players.foreign.file_title", codigo=codigo),
                filetypes=file_types.spreadsheets_flat(),
            )
            if not caminho:
                return
            dialog.close()

            def concluir(resultado: dict[str, Any]) -> None:
                self.host._show_info(
                    self.with_errors(
                        t(
                            "players.official.imported",
                            quantidade=resultado["imported"],
                            base=resultado["source"],
                        ),
                        resultado["errors"],
                        label=t("players.import.warnings"),
                    )
                )

            self.background(
                lambda: self.service.import_foreign_list(caminho, codigo),
                concluir,
                t("players.official.import_working", base=codigo),
            )

        faixa = actions_row(dialog, 4, pady=(8, 16))
        close_button(faixa, t("dialog.cancel"), dialog)
        ctk.CTkButton(faixa, text=t("players.foreign.import_file"), command=importar).pack(
            side="left"
        )

    # ---- Levar a base para os inscritos ----------------------------------- #

    @guarded
    def compare_with_players(self) -> None:
        tournament_id = self.tournament_id
        self.background(
            lambda: self.service.preview_tournament_player_updates(tournament_id),
            self.show_preview,
            t("players.official.comparing"),
        )

    def show_preview(self, result: dict[str, Any]) -> None:
        """"Antes → depois" por jogador, com as divergências já selecionadas."""
        dialog = modal(self.host, t("players.official.preview_title"), "1180x700", minsize=(920, 560))
        # A tabela de comparação vale o dobro da de "sem correspondência": é ela
        # que o árbitro lê linha a linha antes de confirmar.
        dialog.grid_rowconfigure(1, weight=2)
        dialog.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            dialog,
            text=t(
                "players.official.summary",
                inscritos=result["total"],
                correspondencias=result["matched"],
                alteracoes=result["changed"],
                sem_mudanca=result["unchanged"],
                sem_correspondencia=result["unmatched_count"],
            ),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        painel = ctk.CTkFrame(dialog, fg_color="transparent")
        painel.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(0, weight=1)
        tabela = self._tree(painel, comparison_columns(), visible_rows=12)
        tabela.configure(selectmode="extended")

        linhas_alteradas: dict[str, int] = {}
        for linha in result["rows"]:
            row_id = tabela.insert(
                "",
                "end",
                values=(
                    linha["status_label"],
                    linha["name"],
                    linha["changes_label"],
                    self._comparison_text(linha["before"]),
                    self._comparison_text(linha["after"]),
                ),
            )
            if linha["status"] == "changed":
                linhas_alteradas[row_id] = int(linha["player_id"])

        contador = ctk.CTkLabel(
            painel, text=t("players.official.selected", quantidade=0), text_color=THEME_TEXT_SUB
        )
        contador.grid(row=1, column=0, pady=(8, 0), sticky="w")

        ctk.CTkLabel(
            dialog,
            text=t("players.official.unmatched"),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=2, column=0, padx=16, pady=(0, 6), sticky="w")
        painel_sem = ctk.CTkFrame(dialog, fg_color="transparent")
        painel_sem.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        painel_sem.grid_columnconfigure(0, weight=1)
        painel_sem.grid_rowconfigure(0, weight=1)
        tabela_sem = self._tree(painel_sem, unmatched_columns(), visible_rows=5)
        for linha in result["unmatched"]:
            tabela_sem.insert(
                "",
                "end",
                values=(linha["name"], linha["fide_id"], linha["cbx_id"], linha["lbx_id"]),
            )

        faixa = actions_row(dialog, 4)

        def aplicar() -> None:
            escolhidos = [
                linhas_alteradas[row_id]
                for row_id in tabela.selection()
                if row_id in linhas_alteradas
            ]
            if not escolhidos:
                return
            dialog.close()
            tournament_id = self.tournament_id

            def concluir(resultado: dict[str, Any]) -> None:
                self.changed()
                self.host._show_info(
                    self.with_errors(
                        t("players.official.applied", quantidade=resultado["updated"]),
                        resultado["unmatched"],
                        limit=12,
                        label=t("players.official.unmatched_label"),
                    )
                )

            self.background(
                lambda: self.service.apply_tournament_player_updates(tournament_id, escolhidos),
                concluir,
                t("players.official.applying"),
            )

        def recontar(_evento: Any = None) -> None:
            selecionadas = sum(1 for row_id in tabela.selection() if row_id in linhas_alteradas)
            contador.configure(text=t("players.official.selected", quantidade=selecionadas))
            botao_aplicar.configure(state="normal" if selecionadas else "disabled")

        def selecionar_divergencias() -> None:
            tabela.selection_set(*linhas_alteradas)
            recontar()

        def limpar_selecao() -> None:
            tabela.selection_remove(*tabela.selection())
            recontar()

        close_button(faixa, t("dialog.cancel"), dialog)
        neutral_button(faixa, t("players.official.clear_selection"), limpar_selecao).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(
            faixa, text=t("players.official.select_changed"), command=selecionar_divergencias
        ).pack(side="left", padx=(0, 8))
        botao_aplicar = ctk.CTkButton(
            faixa, text=t("players.official.confirm"), command=aplicar
        )
        botao_aplicar.pack(side="left")
        tabela.bind("<<TreeviewSelect>>", recontar)
        selecionar_divergencias()

    # ---- Utilitários ------------------------------------------------------ #

    def _tree(self, parent: Any, columns: dict[str, tuple[str, int]], visible_rows: int) -> Any:
        return self.host._make_tree(
            parent,
            list(columns),
            {codigo: titulo for codigo, (titulo, _) in columns.items()},
            {codigo: largura for codigo, (_, largura) in columns.items()},
            visible_rows=visible_rows,
        )

    @staticmethod
    def _comparison_text(values: dict[str, Any]) -> str:
        """Uma linha só com o que muda: nome, clube, título e os três ratings."""
        return t(
            "players.official.row",
            nome=values["name"],
            clube=values["club"],
            titulo=values["title"],
            rating=values["rating"],
            nacional=values["national_rating"],
            internacional=values["international_rating"],
        )
