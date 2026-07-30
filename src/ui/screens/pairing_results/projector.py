"""Modo Projetor: as mesas da rodada na parede da sala (B-6).

Módulo próprio porque é uma **tela inteira** dentro da tela de Rodadas — 290
linhas num único método, com nove closures e um dicionário de estado. Ela não
compartilha nada com o lançamento de resultados a não ser a lista de mesas.

Duas decisões que ficam registradas aqui:

- **as cores são fixas, alheias ao tema**: quem vê é a sala, na parede, e não
  faz sentido a projeção seguir a preferência de cor de quem opera. São
  constantes nomeadas (permitido pelo lint) e não tokens;
- **a paginação é pura** e mora em [`state`](state.py): quantas páginas, o que
  cabe em cada uma e o que vai em cada coluna. Era o que decidia se a última
  mesa aparecia na parede, escondido em três closures.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...theme import SIZE_PAGE_SUBTITLE
from .state import (
    is_bye_row,
    projector_capacity,
    projector_column_items,
    projector_page_items,
    projector_total_pages,
)

# ---------------------------------------------------------------------------
# Contraste FIXO, alheio ao tema (ver o cabeçalho do módulo).
# ---------------------------------------------------------------------------
PROJETOR_FUNDO        = "#000000"
PROJETOR_BARRA        = "#111111"
PROJETOR_TEXTO        = "#FFFFFF"
PROJETOR_TEXTO_SUAVE  = "#94A3B8"
PROJETOR_DESTAQUE     = "#FBBF24"
PROJETOR_MESA         = "#F59E0B"
PROJETOR_LINHA_PAR    = "#1E293B"
PROJETOR_LINHA_IMPAR  = "#0F172A"
PROJETOR_BOTAO        = "#334155"
PROJETOR_BOTAO_HOVER  = "#475569"
PROJETOR_TABULEIRO    = "#D97706"

_FONTE = "Segoe UI"
_TAMANHO_MIN = 12
_TAMANHO_MAX = 48
_COLUNAS = {"1 Coluna": 1, "2 Colunas": 2, "3 Colunas": 3, "4 Colunas": 4}
_LINHAS = ("10", "15", "20", "25", "30")
_INTERVALOS = ("5s", "8s", "10s", "12s", "15s", "20s")


class ProjectorWindow:
    """A janela de projeção. Uma instância por abertura; fecha-se sozinha.

    O ``after`` do slideshow é o único recurso que precisa de desmontagem, e
    ele é cancelado nos **dois** caminhos de saída (botão/X e Esc) — um
    ``after`` órfão num Toplevel destruído é ``invalid command name`` no Tcl.
    """

    def __init__(self, host: Any, rows: list[dict[str, str]]) -> None:
        self.host = host
        self.rows = rows
        self.pagina = 0
        self.tamanho_fonte = 24
        self.colunas = 2
        self.linhas_por_coluna = 15
        self.slideshow = True
        self.intervalo_ms = 10_000
        self.tela_cheia = False
        self._after: str | None = None

        self.dialog = ctk.CTkToplevel(host)
        self.dialog.title(t("projector.title"))
        self.dialog.configure(fg_color=PROJETOR_FUNDO)
        self.dialog.transient(host)
        self.dialog.grab_set()
        self.dialog.after(10, lambda: self.dialog.state("zoomed"))

        self.controles = ctk.CTkFrame(
            self.dialog, fg_color=PROJETOR_BARRA, corner_radius=0, height=60
        )
        self.controles.pack(fill="x", side="top")
        self.conteudo = ctk.CTkFrame(self.dialog, fg_color=PROJETOR_FUNDO, corner_radius=0)
        self.conteudo.pack(fill="both", expand=True, padx=20, pady=20)

        self._build_controls()
        self.dialog.bind("<Escape>", self._on_escape)
        self.dialog.bind("<F11>", self._toggle_fullscreen)
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)

        self.draw()
        self._reset_timer()

    # ---- paginação -------------------------------------------------------- #

    @property
    def capacidade(self) -> int:
        return projector_capacity(self.colunas, self.linhas_por_coluna)

    @property
    def total_paginas(self) -> int:
        return projector_total_pages(len(self.rows), self.capacidade)

    # ---- controles -------------------------------------------------------- #

    def _rotulo(self, texto: str) -> ctk.CTkLabel:
        rotulo = ctk.CTkLabel(
            self.controles,
            text=texto,
            text_color=PROJETOR_TEXTO,
            font=ctk.CTkFont(family=_FONTE, size=13, weight="bold"),
        )
        rotulo.pack(side="left", padx=(15, 5))
        return rotulo

    def _botao(self, texto: str, comando: Any, largura: int = 30) -> ctk.CTkButton:
        botao = ctk.CTkButton(
            self.controles,
            text=texto,
            width=largura,
            height=28,
            fg_color=PROJETOR_BOTAO,
            hover_color=PROJETOR_BOTAO_HOVER,
            command=comando,
        )
        botao.pack(side="left", padx=2)
        return botao

    def _build_controls(self) -> None:
        self._rotulo(t("projector.font"))
        for texto, delta in (("-", -2), ("+", 2)):
            ctk.CTkButton(
                self.controles,
                text=texto,
                width=30,
                height=28,
                font=ctk.CTkFont(size=SIZE_PAGE_SUBTITLE, weight="bold"),
                command=lambda d=delta: self._change_font(d),
            ).pack(side="left", padx=2)

        self._rotulo(t("projector.columns"))
        menu_colunas = ctk.CTkOptionMenu(
            self.controles,
            values=list(_COLUNAS),
            width=110,
            height=28,
            command=self._on_columns,
        )
        menu_colunas.pack(side="left", padx=2)
        menu_colunas.set("2 Colunas")

        self._rotulo(t("projector.rows"))
        menu_linhas = ctk.CTkOptionMenu(
            self.controles, values=list(_LINHAS), width=80, height=28, command=self._on_rows
        )
        menu_linhas.pack(side="left", padx=2)
        menu_linhas.set("15")

        self.btn_play = self._botao(t("projector.pause"), self._toggle_slideshow, largura=100)
        self._botao("<", lambda: self._step(-1))
        self._botao(">", lambda: self._step(1))

        menu_intervalo = ctk.CTkOptionMenu(
            self.controles,
            values=list(_INTERVALOS),
            width=75,
            height=28,
            command=self._on_interval,
        )
        menu_intervalo.pack(side="left", padx=5)
        menu_intervalo.set("10s")

        self.lbl_pagina = ctk.CTkLabel(
            self.controles,
            text="",
            text_color=PROJETOR_DESTAQUE,
            font=ctk.CTkFont(family=_FONTE, size=13, weight="bold"),
        )
        self.lbl_pagina.pack(side="left", padx=(15, 10))

        # Saida explicita: o projetor abre maximizado e, em tela cheia, some com
        # a barra de titulo — sem este botao a unica saida era adivinhar o Esc.
        ctk.CTkButton(
            self.controles,
            text=t("projector.exit"),
            width=100,
            height=28,
            fg_color=PROJETOR_BOTAO,
            hover_color=PROJETOR_BOTAO_HOVER,
            command=self.close,
        ).pack(side="right", padx=(0, 15))
        ctk.CTkButton(
            self.controles,
            text=t("projector.fullscreen"),
            width=120,
            height=28,
            fg_color=PROJETOR_BOTAO,
            hover_color=PROJETOR_BOTAO_HOVER,
            command=self._toggle_fullscreen,
        ).pack(side="right", padx=15)

    # ---- reações ---------------------------------------------------------- #

    def _change_font(self, delta: int) -> None:
        self.tamanho_fonte = max(_TAMANHO_MIN, min(_TAMANHO_MAX, self.tamanho_fonte + delta))
        self.draw()

    def _on_columns(self, valor: str) -> None:
        self.colunas = _COLUNAS.get(valor, 2)
        self.pagina = 0
        self.draw()
        self._reset_timer()

    def _on_rows(self, valor: str) -> None:
        self.linhas_por_coluna = int(valor)
        self.pagina = 0
        self.draw()
        self._reset_timer()

    def _on_interval(self, valor: str) -> None:
        self.intervalo_ms = int(valor.replace("s", "")) * 1000
        self._reset_timer()

    def _step(self, delta: int) -> None:
        self.pagina = (self.pagina + delta) % self.total_paginas
        self.draw()
        self._reset_timer()

    def _toggle_slideshow(self) -> None:
        self.slideshow = not self.slideshow
        self.btn_play.configure(
            text=t("projector.pause") if self.slideshow else t("projector.play")
        )
        self._reset_timer()
        self._update_page_label()

    def _toggle_fullscreen(self, _event: Any = None) -> None:
        self.tela_cheia = not self.tela_cheia
        self.dialog.attributes("-fullscreen", self.tela_cheia)
        if self.tela_cheia:
            self.controles.pack_forget()
            self.host._show_toast(t("projector.fullscreen.hint"), kind="info", duration_ms=2500)
        else:
            self._show_controls()

    def _on_escape(self, _event: Any = None) -> None:
        """Esc em dois passos: sai da tela cheia; se já estava fora, fecha.

        Antes o segundo Esc não fazia nada, e a janela maximizada sem barra de
        título visível virava o "modal sem saída" do P3-10 para quem não achasse
        o botão Sair.
        """
        if self.tela_cheia:
            self.tela_cheia = False
            self.dialog.attributes("-fullscreen", False)
            self._show_controls()
        else:
            self.close()

    def _show_controls(self) -> None:
        self.controles.pack(fill="x", side="top")
        self.controles.pack_configure(before=self.conteudo)

    # ---- slideshow -------------------------------------------------------- #

    def _reset_timer(self) -> None:
        self._cancel_timer()
        if self.slideshow:
            self._after = self.dialog.after(self.intervalo_ms, self._auto_advance)

    def _cancel_timer(self) -> None:
        if self._after is not None:
            try:
                self.dialog.after_cancel(self._after)
            except Exception:  # pragma: no cover - janela em destruicao
                pass
            self._after = None

    def _auto_advance(self) -> None:
        if self.total_paginas > 1:
            self.pagina = (self.pagina + 1) % self.total_paginas
            self.draw()
        self._reset_timer()

    def close(self) -> None:
        self._cancel_timer()
        try:
            self.dialog.destroy()
        except Exception:  # pragma: no cover
            pass

    # ---- desenho ---------------------------------------------------------- #

    def _update_page_label(self) -> None:
        estado = t("projector.state.slide") if self.slideshow else t("projector.state.paused")
        self.lbl_pagina.configure(
            text=t(
                "projector.page",
                pagina=self.pagina + 1,
                total=self.total_paginas,
                estado=estado,
            )
        )

    def draw(self) -> None:
        for filho in self.conteudo.winfo_children():
            filho.destroy()

        if self.pagina >= self.total_paginas:
            self.pagina = 0
        self._update_page_label()

        da_pagina = projector_page_items(self.rows, self.pagina, self.capacidade)
        fonte_cabecalho = ctk.CTkFont(family=_FONTE, size=self.tamanho_fonte + 2, weight="bold")
        fonte_nome = ctk.CTkFont(family=_FONTE, size=self.tamanho_fonte, weight="bold")
        fonte_mesa = ctk.CTkFont(family=_FONTE, size=self.tamanho_fonte + 8, weight="bold")

        for coluna in range(self.colunas):
            self.conteudo.grid_columnconfigure(coluna, weight=1, uniform="equal")
        self.conteudo.grid_rowconfigure(0, weight=1)

        for coluna in range(self.colunas):
            itens = projector_column_items(da_pagina, coluna, self.linhas_por_coluna)
            if not itens and coluna > 0:
                continue
            quadro = ctk.CTkFrame(self.conteudo, fg_color="transparent")
            quadro.grid(row=0, column=coluna, sticky="nsew", padx=10)
            quadro.grid_columnconfigure(0, weight=1)
            self._draw_header(quadro, fonte_cabecalho)
            for indice, linha in enumerate(itens):
                self._draw_row(quadro, indice, linha, fonte_mesa, fonte_nome)

    @staticmethod
    def _tres_colunas(quadro: ctk.CTkFrame) -> None:
        quadro.grid_columnconfigure(0, weight=1)
        quadro.grid_columnconfigure(1, weight=3)
        quadro.grid_columnconfigure(2, weight=3)

    def _draw_header(self, coluna: ctk.CTkFrame, fonte: Any) -> None:
        cabecalho = ctk.CTkFrame(coluna, fg_color=PROJETOR_LINHA_PAR, corner_radius=4)
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._tres_colunas(cabecalho)
        for indice, (texto, cor) in enumerate(
            (
                (t("projector.column.board"), PROJETOR_MESA),
                (t("projector.column.white"), PROJETOR_TEXTO),
                (t("projector.column.black"), PROJETOR_TEXTO),
            )
        ):
            ctk.CTkLabel(cabecalho, text=texto, font=fonte, text_color=cor).grid(
                row=0, column=indice, padx=8, pady=8, sticky="" if indice == 0 else "w"
            )

    def _draw_row(
        self,
        coluna: ctk.CTkFrame,
        indice: int,
        linha: dict[str, str],
        fonte_mesa: Any,
        fonte_nome: Any,
    ) -> None:
        bye = is_bye_row(linha)
        fundo = PROJETOR_LINHA_PAR if indice % 2 == 0 else PROJETOR_LINHA_IMPAR
        cor_texto = PROJETOR_TEXTO_SUAVE if bye else PROJETOR_TEXTO
        cor_mesa = PROJETOR_TABULEIRO if bye else PROJETOR_DESTAQUE

        quadro = ctk.CTkFrame(coluna, fg_color=fundo, corner_radius=4)
        quadro.grid(row=indice + 1, column=0, sticky="ew", pady=2)
        self._tres_colunas(quadro)
        ctk.CTkLabel(
            quadro, text=linha["board"], font=fonte_mesa, text_color=cor_mesa
        ).grid(row=0, column=0, padx=8, pady=6)
        for posicao, chave in ((1, "white"), (2, "black")):
            ctk.CTkLabel(
                quadro, text=linha[chave], font=fonte_nome, text_color=cor_texto, anchor="w"
            ).grid(row=0, column=posicao, padx=8, pady=6, sticky="w")
