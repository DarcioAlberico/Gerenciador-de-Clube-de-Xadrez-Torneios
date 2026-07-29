"""Importação de jogadores: planilha, inscrições online e mapeamento (B-6).

Três caminhos para o mesmo fim — encher a lista de inscritos — e o que muda
entre eles é só a origem:

- **planilha padrão** (`Modelo jogadores`): colunas conhecidas, importa direto;
- **inscrições online**: passa por uma pré-visualização, porque vem de gente
  digitando em formulário e duplicata é regra, não exceção;
- **mapeamento**: planilha alheia, o operador diz qual coluna é o quê.

Arquivo e link (Google Sheets/Forms publicado em CSV) são a mesma coisa daqui
para baixo: os serviços aceitam caminho ou URL como "origem".
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

from ...components import neutral_button
from ...i18n import t
from ...support import THEME_TEXT_MAIN, THEME_TEXT_SUB, filedialog, font_section
from . import file_types
from .actions import ScreenActions, guarded
from .dialogs import actions_row, close_button, modal

# Nome sugerido do arquivo de modelo. É dado, não texto de interface: o
# operador reconhece o arquivo pelo nome, e traduzi-lo quebraria a rotina de
# quem já guarda "modelo_jogadores.xlsx" numa pasta.
TEMPLATE_FILENAMES = {
    "players": "modelo_jogadores.xlsx",
    "online": "modelo_inscricoes_online.xlsx",
}

def preview_columns() -> dict[str, tuple[str, int]]:
    """Colunas da pré-visualização: código → (título, largura).

    Função e não constante: o título sai do catálogo, e resolver no *import*
    congelaria o idioma. Chamadas literais de ``t()`` também são o que torna
    cada chave visível para o teste do catálogo.
    """
    return {
        "line": (t("players.preview.line"), 60),
        "status": (t("players.preview.status"), 90),
        "name": (t("players.field.name"), 210),
        "birth": (t("players.field.birth_date"), 100),
        "rating": (t("players.field.rating"), 80),
        "club": (t("players.field.club"), 150),
        "category": (t("players.field.category"), 110),
        "message": (t("players.preview.message"), 260),
    }


class PlayerImportActions(ScreenActions):
    """Ações de importação. O host dá arquivo, background e diálogo."""

    def __init__(self, host: Any, on_changed: Callable[[], None] | None = None) -> None:
        super().__init__(host, on_changed)
        self.import_service = host.import_service
        self.export_service = host.export_service

    # ---- Modelos ---------------------------------------------------------- #

    @guarded
    def export_template(self, kind: str) -> None:
        """Salva a planilha-modelo (jogadores ou inscrições online)."""
        caminho = filedialog.asksaveasfilename(
            title=t("players.import.template.title"),
            initialdir=str(self.host._default_export_dir()),
            initialfile=TEMPLATE_FILENAMES[kind],
            defaultextension=".xlsx",
            filetypes=file_types.excel_or_csv(),
        )
        if not caminho:
            return
        destino = Path(caminho)
        if destino.suffix.lower() not in {".csv", ".xlsx"}:
            # O usuário pode apagar a extensão sugerida; sem isto o exportador
            # receberia um arquivo sem formato e escolheria por conta.
            destino = destino.with_suffix(".xlsx")
        exportar = (
            self.export_service.export_online_registration_template
            if kind == "online"
            else self.export_service.export_player_import_template
        )
        self.background(
            lambda: exportar(destino),
            lambda _resultado: self.host._show_info(
                t("players.import.template.saved", caminho=destino)
            ),
            t("players.import.template.working"),
        )

    # ---- Planilha padrão -------------------------------------------------- #

    @guarded
    def import_spreadsheet(self) -> None:
        caminho = filedialog.askopenfilename(
            title=t("players.import.spreadsheet.title"),
            filetypes=file_types.spreadsheets(),
        )
        if not caminho:
            return
        tournament_id = self.tournament_id

        def concluir(resultado: dict[str, Any]) -> None:
            self.changed()
            self.host._show_info(
                self.with_errors(
                    t("players.import.spreadsheet.done", quantidade=resultado["imported"]),
                    resultado["errors"],
                )
            )

        self.background(
            lambda: self.import_service.import_players(tournament_id, caminho),
            concluir,
            t("players.import.spreadsheet.working"),
        )

    # ---- Inscrições online ------------------------------------------------ #

    @guarded
    def import_online_file(self) -> None:
        caminho = filedialog.askopenfilename(
            title=t("players.import.online.title"),
            filetypes=file_types.spreadsheets(),
        )
        if caminho:
            self._preview_online(caminho)

    @guarded
    def import_online_url(self) -> None:
        link = self.host._ask_string(
            t("players.import.online.title"), t("players.import.url.prompt")
        )
        if link and link.strip():
            self._preview_online(link.strip())

    def _preview_online(self, source: str) -> None:
        """Lê a origem e abre a pré-visualização; só depois importa de fato."""
        tournament_id = self.tournament_id
        self.background(
            lambda: self.import_service.preview_online_registrations(tournament_id, source),
            lambda resultado: self.show_online_preview(
                resultado,
                lambda: self.import_service.import_online_registrations(tournament_id, source),
            ),
            t("players.import.online.reading"),
        )

    def show_online_preview(
        self, result: dict[str, Any], importer: Callable[[], dict[str, Any]]
    ) -> None:
        """Confere antes de gravar: quantas estão prontas, duplicadas e com erro.

        Também é o destino do caminho com mapeamento — daí receber o
        ``importer`` pronto em vez de montar a chamada aqui.
        """
        dialog = modal(
            self.host,
            t("players.import.online.title"),
            "980x560",
            minsize=(860, 460),
            stretch_rows=(1,),
        )

        ctk.CTkLabel(
            dialog,
            text=t(
                "players.preview.summary",
                total=result["total"],
                prontas=result["ready"],
                duplicadas=result["duplicate"],
                erros=result["error"],
            ),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        painel = ctk.CTkFrame(dialog, fg_color="transparent")
        painel.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(0, weight=1)
        colunas = preview_columns()
        tabela = self.host._make_tree(
            painel,
            list(colunas),
            {codigo: titulo for codigo, (titulo, _) in colunas.items()},
            {codigo: largura for codigo, (_, largura) in colunas.items()},
            visible_rows=13,
        )
        for linha in result["rows"]:
            tabela.insert(
                "",
                "end",
                values=(
                    linha["line"],
                    linha["status_label"],
                    linha["name"],
                    linha["birth_date"],
                    linha["rating"],
                    linha["club"],
                    linha["category"],
                    linha["message"],
                ),
            )

        faixa = actions_row(dialog, 2)

        def importar() -> None:
            dialog.close()

            def concluir(resultado: dict[str, Any]) -> None:
                self.changed()
                self.host._show_info(
                    self.with_errors(
                        t(
                            "players.import.online.done",
                            importadas=resultado["imported"],
                            ignoradas=resultado["skipped"],
                        ),
                        resultado["errors"],
                    )
                )

            self.background(importer, concluir, t("players.import.online.working"))

        close_button(faixa, t("dialog.cancel"), dialog)
        botao = ctk.CTkButton(faixa, text=t("players.preview.import_ready"), command=importar)
        botao.pack(side="left")
        if result["ready"] <= 0:
            botao.configure(state="disabled")

    # ---- Mapeamento de colunas -------------------------------------------- #

    @guarded
    def import_mapped_file(self) -> None:
        caminho = filedialog.askopenfilename(
            title=t("players.mapping.file_title"),
            filetypes=file_types.spreadsheets(),
        )
        if caminho:
            self._inspect(caminho)

    @guarded
    def import_mapped_url(self) -> None:
        link = self.host._ask_string(t("players.mapping.title"), t("players.import.url.prompt"))
        if link and link.strip():
            self._inspect(link.strip())

    def _inspect(self, source: str) -> None:
        self.background(
            lambda: self.import_service.inspect_source(source),
            lambda inspecao: self.show_mapping_dialog(inspecao, source),
            t("players.mapping.reading"),
        )

    def show_mapping_dialog(self, inspection: dict[str, Any], source: str) -> None:
        """Associa cada campo do Albericus a uma coluna da planilha alheia."""
        cabecalhos = list(inspection["headers"])
        campos = list(inspection["fields"])
        ignorar = t("players.mapping.ignore")
        opcoes = [ignorar, *cabecalhos]

        dialog = modal(
            self.host,
            t("players.mapping.title"),
            "760x640",
            minsize=(640, 520),
            stretch_rows=(3,),
        )

        ctk.CTkLabel(
            dialog,
            text=t("players.mapping.header", origem=source, linhas=inspection["total_rows"]),
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
            justify="left",
            wraplength=720,
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(
            dialog,
            text=self._reference_text(cabecalhos, inspection["sample_rows"]),
            text_color=THEME_TEXT_SUB,
            justify="left",
            wraplength=720,
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        escolhas: dict[str, ctk.StringVar] = {}

        def aplicar(mapeamento: dict[str, str]) -> None:
            for campo in campos:
                escolhido = mapeamento.get(campo["key"], "")
                escolhas[campo["key"]].set(escolhido if escolhido in cabecalhos else ignorar)

        def mapeamento_atual() -> dict[str, str]:
            return {
                campo["key"]: escolhas[campo["key"]].get()
                for campo in campos
                if escolhas[campo["key"]].get() not in ("", ignorar)
            }

        self._build_profiles_row(dialog, aplicar, mapeamento_atual)

        seletores = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        seletores.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="nsew")
        seletores.grid_columnconfigure(1, weight=1)
        for indice, campo in enumerate(campos):
            rotulo = campo["label"] + (" *" if campo["required"] else "")
            ctk.CTkLabel(seletores, text=rotulo).grid(
                row=indice, column=0, padx=(0, 10), pady=4, sticky="w"
            )
            variavel = ctk.StringVar(value=ignorar)
            escolhas[campo["key"]] = variavel
            ctk.CTkOptionMenu(seletores, values=opcoes, variable=variavel, width=320).grid(
                row=indice, column=1, pady=4, sticky="ew"
            )
        aplicar(inspection["suggested_mapping"])

        faixa = actions_row(dialog, 4)

        def continuar() -> None:
            mapeamento = mapeamento_atual()
            if not mapeamento.get("name"):
                self.host._show_error(self._app_error(t("players.mapping.name_required")))
                return
            tournament_id = self.tournament_id
            dialog.close()
            self.background(
                lambda: self.import_service.preview_mapped_registrations(
                    tournament_id, source, mapeamento
                ),
                lambda resultado: self.show_online_preview(
                    resultado,
                    lambda: self.import_service.import_mapped_registrations(
                        tournament_id, source, mapeamento
                    ),
                ),
                t("players.mapping.checking"),
            )

        close_button(faixa, t("dialog.cancel"), dialog)
        ctk.CTkButton(faixa, text=t("players.mapping.continue"), command=continuar).pack(side="left")

    @staticmethod
    def _reference_text(headers: list[str], sample_rows: list[dict[str, Any]]) -> str:
        """Colunas detectadas e a primeira linha — a régua de quem está mapeando."""
        texto = t("players.mapping.detected", colunas=", ".join(headers))
        amostra = sample_rows[0] if sample_rows else {}
        if amostra:
            valores = " | ".join(
                f"{cabecalho}={str(amostra.get(cabecalho, '')).strip()}" for cabecalho in headers
            )
            texto += "\n\n" + t("players.mapping.first_row", valores=valores)
        return texto

    def _build_profiles_row(
        self,
        dialog: ctk.CTkToplevel,
        apply_mapping: Callable[[dict[str, str]], None],
        current_mapping: Callable[[], dict[str, str]],
    ) -> None:
        """Perfis salvos: a mesma planilha volta todo mês, o mapeamento também."""
        vazio = t("players.mapping.profile.none")
        faixa = ctk.CTkFrame(dialog, fg_color="transparent")
        faixa.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="ew")
        perfis = self.import_service.list_mapping_profiles()
        escolhido = ctk.StringVar(value=next(iter(perfis), "") if perfis else "")
        ctk.CTkLabel(faixa, text=t("players.mapping.profile")).pack(side="left", padx=(0, 6))
        menu = ctk.CTkOptionMenu(
            faixa, values=list(perfis) or [vazio], variable=escolhido, width=200
        )
        menu.pack(side="left", padx=(0, 6))

        def recarregar(selecionado: str) -> None:
            valores = list(self.import_service.list_mapping_profiles()) or [vazio]
            menu.configure(values=valores)
            escolhido.set(selecionado if selecionado in valores else valores[0])

        def usar() -> None:
            salvo = self.import_service.list_mapping_profiles().get(escolhido.get())
            if salvo:
                apply_mapping(salvo)

        def salvar() -> None:
            nome = self.host._ask_string(
                t("players.mapping.profile.title"), t("players.mapping.profile.prompt")
            )
            if not nome:
                return
            try:
                self.import_service.save_mapping_profile(nome, current_mapping())
            except Exception as exc:  # noqa: BLE001 — nome invalido/duplicado vira recado
                self.host._show_error(exc)
                return
            recarregar(nome)
            self.host._show_info(t("players.mapping.profile.saved", nome=nome))

        def excluir() -> None:
            nome = escolhido.get()
            if not nome or nome == vazio:
                return
            self.import_service.delete_mapping_profile(nome)
            recarregar("")

        ctk.CTkButton(faixa, text=t("players.mapping.profile.apply"), width=80, command=usar).pack(
            side="left", padx=4
        )
        ctk.CTkButton(
            faixa, text=t("players.mapping.profile.save"), width=80, command=salvar
        ).pack(side="left", padx=4)
        neutral_button(
            faixa, t("players.mapping.profile.delete"), excluir, width=80
        ).pack(side="left", padx=4)

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
