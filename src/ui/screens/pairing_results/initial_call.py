"""Chamada inicial: a lista de presença antes da primeira rodada (B-6).

É a **outra** tela que vivia dentro de `show_pairings`. Antes da primeira
rodada não há rodada para editar nem exportar, então a tela de Rodadas mostra
outra coisa inteira: quem está na sala. O `show_pairings` decidia isso com um
``if show_initial_call`` que aparecia **três vezes**, e as duas metades
compartilhavam só o painel.

Aqui ela é uma seção com dono: monta o painel, carrega a lista, alterna
presença e exporta. As regras (resumo, busca, qual status a alternância aplica)
são puras e moram em [`state`](state.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ...components import debounce, secondary_button
from ...i18n import t
from ...support import (
    AppError,
    PLAYER_STATUSES,
    SPACE_MD,
    SPACE_SM,
    THEME_TEXT_SUB,
    filedialog,
    font_section,
    player_full_name,
)
from .state import (
    initial_call_searchable,
    initial_call_summary,
    matches_initial_query,
    next_presence_status,
)

COLUNAS = ("start", "presence", "name", "rating", "club", "category", "status")
TITULOS = {
    "start": "Inicial",
    "presence": "Presença",
    "name": "Jogador",
    "rating": "Rating",
    "club": "Clube",
    "category": "Categoria",
    "status": "Status",
}
LARGURAS = {
    "start": 70,
    "presence": 90,
    "name": 280,
    "rating": 80,
    "club": 170,
    "category": 130,
    "status": 95,
}


class InitialCallSection:
    """A chamada inicial montada sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any) -> None:
        self.host = host
        self.tree: Any = None
        self.summary_label: Any = None
        self.search_entry: Any = None
        self.row_map: dict[str, int] = {}

    # ---- montagem --------------------------------------------------------- #

    def build(self, body: ctk.CTkFrame, row: int = 1) -> None:
        host = self.host
        painel = host._make_panel(body)
        painel.grid(row=row, column=0, sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(1, weight=1)

        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.grid(row=0, column=0, padx=SPACE_MD, pady=(SPACE_MD, 4), sticky="ew")
        cabecalho.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecalho, text=t("initial_call.title"), font=font_section(), anchor="w"
        ).grid(row=0, column=0, sticky="w")
        self.summary_label = ctk.CTkLabel(
            cabecalho, text="", text_color=THEME_TEXT_SUB, anchor="w"
        )
        self.summary_label.grid(row=1, column=0, pady=(2, 0), sticky="w")
        # Expostos no host porque e por eles que o smoke de janela le a tela —
        # o contrato externo nao muda so porque o interior ganhou dono.
        host.initial_call_summary_label = self.summary_label

        self.search_entry = ctk.CTkEntry(
            cabecalho, width=320, placeholder_text=t("initial_call.search.hint")
        )
        self.search_entry.grid(row=2, column=0, pady=(SPACE_SM, 0), sticky="w")
        self.search_debounced = debounce(self.search_entry, self.reload)
        self.search_entry.bind("<KeyRelease>", self.search_debounced)
        # A tela legada guardava este debounce no host (`initial_player_search_debounced`)
        # para o teste alcancar; segue exposto, agora com dono claro.
        host.initial_player_search_debounced = self.search_debounced
        host.initial_player_search_entry = self.search_entry

        secondary_button(cabecalho, t("initial_call.export"), self.export_list, width=110).grid(
            row=0, column=1, padx=(SPACE_SM, 0), sticky="e"
        )
        secondary_button(cabecalho, t("initial_call.print"), self.print_list, width=85).grid(
            row=0, column=2, padx=(SPACE_SM, 0), sticky="e"
        )

        suporte = ctk.CTkFrame(painel, fg_color="transparent")
        suporte.grid(row=1, column=0, padx=SPACE_MD, sticky="nsew")
        suporte.grid_columnconfigure(0, weight=1)
        suporte.grid_rowconfigure(0, weight=1)
        self.tree = host._make_tree(
            suporte, list(COLUNAS), dict(TITULOS), dict(LARGURAS), visible_rows=14
        )
        self.tree.configure(selectmode="extended")
        for sequencia in ("<Double-1>", "<space>"):
            self.tree.bind(sequencia, lambda _e: self.toggle_selected())
        host.initial_players_tree = self.tree

        acoes = ctk.CTkFrame(painel, fg_color="transparent")
        acoes.grid(row=2, column=0, padx=SPACE_MD, pady=(SPACE_SM, SPACE_MD), sticky="ew")
        for coluna in range(3):
            acoes.grid_columnconfigure(coluna, weight=1)
        # Rotulos resolvidos com `t("chave")` LITERAL: chave vinda de variavel e
        # invisivel para o `test_ui_i18n`, que cobra que toda chave do catalogo
        # tenha uso — e chave orfa hoje e texto perdido amanha.
        for coluna, (rotulo, comando) in enumerate(
            (
                (t("initial_call.all_present"), self.mark_all_present),
                (t("initial_call.present"), lambda: self.set_selected_status("active")),
                (t("initial_call.absent"), lambda: self.set_selected_status("absent")),
            )
        ):
            secondary_button(acoes, rotulo, comando).grid(
                row=0,
                column=coluna,
                padx=(0 if coluna == 0 else 6, 0 if coluna == 2 else 6),
                sticky="ew",
            )
        self.reload()

    # ---- dados ------------------------------------------------------------ #

    def reload(self, _event: Any = None) -> None:
        if self.tree is None or not self.tree.winfo_exists():
            return
        host = self.host
        self.tree.delete(*self.tree.get_children())
        self.row_map = {}
        host.initial_player_row_map = self.row_map

        jogadores = host.db.list_players(host.current_tournament_id, active_only=False)
        presentes, ausentes, total = initial_call_summary(jogadores)
        if self.summary_label is not None:
            self.summary_label.configure(
                text=t("initial_call.summary", presentes=presentes, ausentes=ausentes, total=total)
            )

        consulta = self.search_entry.get() if self.search_entry is not None else ""
        ordenados = host.export_service._initial_ranked_players(jogadores)
        for numero, jogador in enumerate(ordenados, start=1):
            nome = player_full_name(jogador)
            if not matches_initial_query(initial_call_searchable(jogador, nome), consulta):
                continue
            status = str(jogador.get("player_status", "active") or "active")
            item = self.tree.insert(
                "",
                "end",
                values=(
                    numero,
                    t("initial_call.yes") if status == "active" else t("initial_call.no"),
                    nome,
                    jogador.get("rating", ""),
                    jogador.get("club", ""),
                    jogador.get("category", ""),
                    PLAYER_STATUSES.get(status, status),
                ),
            )
            self.row_map[item] = int(jogador["id"])

    # ---- presença --------------------------------------------------------- #

    def locked(self) -> bool:
        """A chamada fecha quando a primeira rodada é gerada, e avisa por quê."""
        if self.host.db.list_rounds(self.host.current_tournament_id):
            self.host._show_warning(t("initial_call.locked"))
            return True
        return False

    def selected_ids(self) -> list[int]:
        if self.tree is None:
            return []
        return [
            self.row_map[item] for item in self.tree.selection() if item in self.row_map
        ]

    def set_status(self, player_ids: list[int], status: str) -> None:
        try:
            self.host.require_permission("tournament_write")
            if self.locked():
                return
            if not player_ids:
                raise AppError(t("initial_call.select_first"))
            # Pelo SERVICO (ARB-05): a chamada inicial e onde a ausencia da
            # rodada 1 nasce, e ela precisa entrar no historico como qualquer
            # outra — senao a ata nao sabe quem faltou desde o comeco.
            for player_id in player_ids:
                self.host.pairing_service.set_player_participation(
                    int(self.host.current_tournament_id), int(player_id), status
                )
            self.reload()
        except Exception as exc:
            self.host._show_error(exc)

    def set_selected_status(self, status: str) -> None:
        self.set_status(self.selected_ids(), status)

    def mark_all_present(self) -> None:
        self.set_status(list(self.row_map.values()), "active")

    def toggle_selected(self) -> str:
        try:
            if self.locked():
                return "break"
            ids = self.selected_ids()
            if not ids:
                return "break"
            jogadores = [self.host.db.get_player(player_id) for player_id in ids]
            self.set_status(ids, next_presence_status(jogadores))
            return "break"
        except Exception as exc:
            self.host._show_error(exc)
            return "break"

    # ---- exportação ------------------------------------------------------- #

    def _path(self, suffix: str = ".xlsx") -> Path:
        host = self.host
        torneio = (
            host.db.get_tournament(host.current_tournament_id)
            if host.current_tournament_id
            else None
        )
        nome = host._safe_filename(str(torneio.get("name") if torneio else "torneio"), "torneio")
        return host._default_export_dir() / f"{nome}_lista_inicial{suffix}"

    def export_list(self) -> None:
        host = self.host
        try:
            if not host.current_tournament_id:
                raise AppError(t("initial_call.no_tournament"))
            padrao = self._path()
            escolhido = filedialog.asksaveasfilename(
                title=t("initial_call.export.title"),
                initialdir=str(padrao.parent),
                initialfile=padrao.name,
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel", "*.xlsx"),
                    ("CSV", "*.csv"),
                    ("PDF", "*.pdf"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if not escolhido:
                return
            caminho = Path(escolhido)
            if caminho.suffix.lower() not in {".csv", ".xlsx", ".pdf"}:
                caminho = caminho.with_suffix(".xlsx")
            host._run_background(
                lambda: host.export_service.export_initial_player_list(
                    int(host.current_tournament_id), caminho
                ),
                lambda _r: host._show_info(t("initial_call.exported", caminho=caminho)),
                t("initial_call.exporting"),
            )
        except Exception as exc:
            host._show_error(exc)

    def print_list(self) -> None:
        host = self.host
        try:
            if not host.current_tournament_id:
                raise AppError(t("initial_call.no_tournament"))
            caminho = self._path(".pdf")
            host._run_background(
                lambda: host.export_service.export_initial_player_list(
                    int(host.current_tournament_id), caminho
                ),
                lambda _r: host._print_document(caminho),
                t("initial_call.printing"),
            )
        except Exception as exc:
            host._show_error(exc)
