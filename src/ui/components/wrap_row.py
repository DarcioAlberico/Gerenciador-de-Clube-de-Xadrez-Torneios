"""Faixa de widgets que quebra em quantas linhas couberem (continuação da B-8).

A B-8 fez isso à mão para a barra do torneio e provou que funciona: quebrar
custa ~38px de altura, que sobra; insistir numa linha custa um botão
inacessível, que não tem substituto visível. Aqui a mesma ideia vira componente,
para as **faixas de filtro** das telas administrativas densas — que eram quem
obrigava a sidebar a exigir 1.416px de janela para aparecer inteira.

    faixa = WrapRow(painel)
    faixa.grid(row=0, column=0, sticky="ew")
    busca = faixa.add(ctk.CTkEntry(faixa.frame), width=240, grow=True)
    faixa.add(botao_filtrar, width=100)
    faixa.bind_to(self.content)   # arranja agora e a cada mudança de largura

A conta mora em [`layout.py`](../layout.py), que não importa Tk. Aqui fica só o
que precisa de janela: medir e re-``grid``ar — e **não** re-``grid``ar quando o
arranjo não mudou, senão cada pixel de arrasto redesenharia a faixa inteira.

**A medida vem do ``content``, nunca da própria faixa.** Tentar o contrário
parece mais elegante e não funciona: no grid, um container fica tão largo quanto
o que ele pede, então uma faixa montada em linha única *empurra* o painel para
a largura dela — e aí ela nunca "vê" uma largura menor para justificar a quebra.
O ``content`` tem largura própria (vem da janela) e sobrevive à troca de tela.

O preço dessa escolha é o ouvinte no ``content``, que **não** morre com a tela;
por isso a faixa se desliga sozinha no ``<Destroy>`` do próprio frame. Sem isso,
cada visita à tela deixaria mais um ouvinte falando com widget destruído.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk
from customtkinter import ScalingTracker

from ..layout import DEFAULT_PAD, wrap_positions


class WrapRow:
    """Gerencia o posicionamento dos filhos de um frame em linhas que cabem."""

    # Margem à direita da faixa (padding do corpo + do painel, em pixels reais).
    # O que fica à **esquerda** — um painel de formulário, por exemplo — não
    # precisa ser declarado: é medido pela posição da própria faixa.
    DEFAULT_MARGIN = 40

    # Folga por item. Medido: um item ocupa ~3px a mais do que pede — borda do
    # frame que o embrulha. Três pixels não parecem nada; com sete itens viram
    # vinte, e vinte foi o suficiente para o último campo da tela Relatórios
    # ficar **1px** fora da janela. Errar para o lado da quebra é barato: custa
    # altura, que sobra.
    ITEM_SLACK = 6

    def __init__(self, master: Any, pad: int = DEFAULT_PAD, margin: int = DEFAULT_MARGIN) -> None:
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self._pad = pad
        self._margin = margin
        self._items: list[tuple[Any, int, bool]] = []
        self._arranjo: list[tuple[int, int]] | None = None
        self._fonte: Any = None
        self._escuta: Any = None
        self._funcid: str | None = None
        self._agendado: Any = None

    # ---- Montagem --------------------------------------------------------- #

    def add(self, widget: Any, width: int, grow: bool = False) -> Any:
        """Acrescenta um item com a largura mínima que ele precisa.

        ``grow=True`` marca o item elástico da linha (a caixa de busca): ele
        absorve a sobra, os demais ficam no tamanho pedido.
        """
        self._items.append((widget, width, grow))
        return widget

    def add_field(self, label: str, build: Any, width: int, grow: bool = False) -> Any:
        """Campo rotulado (rótulo em cima, controle embaixo) como **um** item.

        A faixa move o par junto: rótulo separado do seu controle numa quebra de
        linha é pior que não quebrar. Devolve o controle, que é o que a tela usa.
        """
        caixa = ctk.CTkFrame(self.frame, fg_color="transparent")
        caixa.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(caixa, text=label).grid(row=0, column=0, sticky="w", pady=(0, 2))
        controle = build(caixa)
        controle.grid(row=1, column=0, sticky="ew")
        self.add(caixa, width, grow)
        return controle

    def grid(self, **kwargs: Any) -> None:
        """Posiciona a própria faixa no pai. Aceita o mesmo que ``grid``."""
        self.frame.grid(**kwargs)

    def bind_to(self, source: Any) -> None:
        """Arranja agora e sempre que ``source`` mudar de largura.

        Chame depois de acrescentar todos os itens: é esta chamada que os põe no
        grid pela primeira vez. Sem ela os widgets existiriam sem posição —
        criados e invisíveis.
        """
        self._fonte = source
        # Escuta o canvas interno do CTkFrame, e não o frame. Motivo prático:
        # `CTkFrame.bind` **não devolve** o funcid e `CTkFrame.unbind` recusa
        # receber um — só sabe apagar todas as ligações da sequência, o que
        # levaria junto as internas do customtkinter. Sem funcid não há como se
        # desligar, e sem desligar cada visita à tela deixa um ouvinte morto.
        self._escuta = getattr(source, "_canvas", source)
        self._funcid = self._escuta.bind("<Configure>", self._on_configure, add="+")
        self.frame.bind("<Destroy>", self._on_destroy, add="+")
        self.relayout()
        # E de novo quando a geometria assentar: só então a faixa sabe onde
        # começa (há um painel de formulário à esquerda em quase toda tela
        # densa) e quanto cada item de fato pede. Roda dentro do mesmo
        # `update()`, antes de a tela aparecer — o usuário não vê o intervalo.
        try:
            self._agendado = self.frame.after_idle(self._on_configure)
        except Exception:  # noqa: BLE001 — sem laço de eventos (teste puro)
            pass

    # ---- Layout ----------------------------------------------------------- #

    def available(self) -> int:
        """Espaço útil da faixa, em pixels reais.

        Largura do ``content`` menos o que fica à esquerda (medido: o painel de
        formulário das telas densas) e menos a margem da direita.
        """
        if self._fonte is None:
            return 0
        try:
            largura = int(self._fonte.winfo_width())
        except Exception:  # noqa: BLE001 — fonte destruida entre eventos
            return 0
        if largura <= 1:
            return largura  # antes do primeiro desenho: a conta trata como linha única
        try:
            deslocamento = max(0, self.frame.winfo_rootx() - self._fonte.winfo_rootx())
        except Exception:  # noqa: BLE001
            deslocamento = 0
        return max(1, largura - deslocamento - self._margin)

    def _real_widths(self) -> list[int]:
        """Larguras em pixels de **tela**, que é a unidade de ``winfo_width``.

        Detalhe que custou uma medição: ``CTkEntry(width=190)`` não ocupa 190px.
        O customtkinter multiplica pela escala de UI (120% por padrão), e o
        widget desenha 228. Comparar largura pedida (lógica) com espaço
        disponível (real) faz a conta concluir que cabe — e o último item sai da
        janela, que é exatamente o defeito que esta faixa existe para evitar.

        ``winfo_reqwidth`` já vem em pixels reais e sabe de rótulo mais largo que
        o controle; antes do primeiro desenho ele ainda é 1, e aí vale a largura
        declarada, escalada.
        """
        escala = self._scaling()
        reais = []
        for widget, largura, _cresce in self._items:
            try:
                pedida = int(widget.winfo_reqwidth())
            except Exception:  # noqa: BLE001 — widget destruido no meio da troca
                pedida = 0
            reais.append(max(int(largura * escala), pedida) + self.ITEM_SLACK)
        return reais

    def _scaling(self) -> float:
        try:
            return float(ScalingTracker.get_widget_scaling(self.frame))
        except Exception:  # noqa: BLE001 — sem tracker (teste puro), 1:1 serve
            return 1.0

    def relayout(self) -> None:
        """Re-``grid``a os itens, se e só se o arranjo mudou."""
        larguras = self._real_widths()
        # Sem `reserve` aqui: `available()` ja desconta margem e deslocamento.
        arranjo = wrap_positions(larguras, self.available(), self._pad)
        if arranjo == self._arranjo:
            return
        self._arranjo = arranjo
        elasticas = set()
        for (linha, coluna), (widget, _largura, cresce) in zip(arranjo, self._items):
            widget.grid(
                row=linha,
                column=coluna,
                padx=(0 if coluna == 0 else self._pad, 0),
                pady=(0, 4),
                sticky="ew" if cresce else "w",
            )
            if cresce:
                elasticas.add(coluna)
        # Só a coluna do item elástico estica; as demais voltam a peso zero para
        # a faixa não distribuir sobra entre botões, que ficariam gigantes.
        for coluna in range(len(self._items)):
            self.frame.grid_columnconfigure(coluna, weight=1 if coluna in elasticas else 0)

    # ---- Ciclo de vida ---------------------------------------------------- #

    def _on_configure(self, _event: Any = None) -> None:
        self._agendado = None
        if not self._alive():
            self._unbind()
            return
        self.relayout()

    def _on_destroy(self, _event: Any = None) -> None:
        # Sem checar `event.widget`: `CTkFrame.bind` registra no canvas interno,
        # então quem chega aqui é o `<Destroy>` do canvas — que só acontece
        # quando o frame inteiro morre, que é exatamente o gatilho desejado.
        self._cancel_pending()
        self._unbind()

    def _cancel_pending(self) -> None:
        """Descarta o arranjo agendado que já não tem para quem falar.

        Trocar de tela destrói a faixa antes de o ``after_idle`` do ``bind_to``
        rodar. Sem este cancelamento o Tcl dispara um callback cujo comando
        acabou de ser apagado junto com o frame — erro no console a cada visita
        rápida a uma tela densa. Cancelar **pelo próprio frame** é o que mantém
        a contabilidade de comandos com quem é dono dela.
        """
        if self._agendado is None:
            return
        try:
            self.frame.after_cancel(self._agendado)
        except Exception:  # noqa: BLE001 — ja disparado ou raiz destruida
            pass
        self._agendado = None

    def _alive(self) -> bool:
        try:
            return bool(self.frame.winfo_exists())
        except Exception:
            return False

    def _unbind(self) -> None:
        if self._escuta is None or not self._funcid:
            return
        try:
            self._escuta.unbind("<Configure>", self._funcid)
        except Exception:  # noqa: BLE001 — fonte ja destruida: nada a desligar
            pass
        self._funcid = None
