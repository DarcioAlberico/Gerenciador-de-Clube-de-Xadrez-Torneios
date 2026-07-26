"""Contas de layout responsivo — puro, sem Tk (continuação da B-8).

Uma conta só, usada em dois lugares que a resolviam separado: a **barra do
torneio** (que a B-8 fez quebrar em linhas) e as **faixas de filtro** das telas
administrativas densas, que eram a razão de a sidebar precisar de 1.416px de
janela para aparecer inteira.

Puro de propósito: "quantos cabem em N pixels" é aritmética, e aritmética se
testa em milissegundos. O que precisa de Tk — medir a largura e re-`grid`ar — é
uma dúzia de linhas em [`components/wrap_row.py`](components/wrap_row.py).
"""
from __future__ import annotations

from collections.abc import Sequence

DEFAULT_PAD = 8


def column_widths(widths: Sequence[int], per_row: int) -> list[int]:
    """Largura de cada coluna quando os itens são distribuídos em ``per_row``.

    **É aqui que mora o detalhe que uma primeira versão errou.** O `grid` do Tk
    não empilha linhas independentes: a coluna 1 tem uma largura só, e ela é a
    do item mais largo que caiu nessa coluna — em qualquer linha. Uma conta que
    somasse cada linha por si concluiria que cabe, e a tela mostraria o último
    campo 1px fora da janela, esticado pelo vizinho de baixo.
    """
    return [max(widths[i] for i in range(coluna, len(widths), per_row)) for coluna in range(per_row)]


def wrap_positions(
    widths: Sequence[int],
    available: int,
    pad: int = DEFAULT_PAD,
    reserve: int = 0,
) -> list[tuple[int, int]]:
    """``(linha, coluna)`` de cada item, na ordem dada.

    ``reserve`` desconta o que já ocupa a faixa antes do primeiro item (o
    título da página, ao lado da barra do torneio).

    Escolhe o **maior** número de itens por linha que ainda cabe, medindo pelas
    colunas do `grid` (ver ``column_widths``). Três decisões que o código
    registra:

    - **Largura desconhecida vira linha única.** Antes do primeiro desenho todo
      widget mede 1px; quebrar com base nisso mostraria um layout errado que o
      próximo ``<Configure>`` desfaz — pisca à toa.
    - **Item que sozinho não cabe fica numa linha própria**, em vez de espremer.
      Encolher esconde rótulo; empurrar para fora da janela é exatamente o que
      esta função existe para evitar.
    - **A ordem dos itens é preservada.** Reordenar para empacotar melhor
      economizaria pixels e trocaria a ordem de leitura de um formulário, que
      vale mais.
    """
    total = len(widths)
    if total == 0:
        return []
    if available <= 1:
        return [(0, coluna) for coluna in range(total)]

    livre = max(0, available - reserve)
    por_linha = 1
    for candidato in range(total, 0, -1):
        colunas = column_widths(widths, candidato)
        if sum(colunas) + pad * (candidato - 1) <= livre:
            por_linha = candidato
            break
    return [(indice // por_linha, indice % por_linha) for indice in range(total)]


def rows_used(positions: Sequence[tuple[int, int]]) -> int:
    """Quantas linhas o arranjo ocupa. Vazio ocupa zero."""
    return max((linha for linha, _ in positions), default=-1) + 1
