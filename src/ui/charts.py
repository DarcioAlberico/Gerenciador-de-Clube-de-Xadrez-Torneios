"""Cache de figuras de gráfico — o que decide se um gráfico pode ser reaproveitado.

Módulo **puro**: não importa Tk, customtkinter nem matplotlib. Guarda objetos
opacos (as figuras) atrás de uma chave derivada dos dados e da paleta, e por
isso é testável sem abrir janela e sem desenhar nada.

Por que existe (P2-14): o Dashboard era remontado do zero a cada visita e a
cada F5, mesmo quando nada tinha mudado. Medido nesta máquina, com o backend
TkAgg, **por gráfico**:

===========================================  =========
``plt.subplots`` + embutir + destruir           321 ms
``Figure()`` (sem pyplot) + embutir              76 ms
``Figure()`` já pronta, vinda do cache           55 ms
===========================================  =========

Ou seja: o gasto grande era o *manager* global do pyplot (por isso o Dashboard
passou a construir ``Figure`` direto), e o cache raspa o que sobrou do desenho.
Com dois gráficos na tela, a visita repetida cai de ~640 ms para ~110 ms.

A **chave** é o contrato: tudo que entra no desenho tem de entrar nela, ou o
usuário vê número velho. É por isso que a paleta é um dataclass congelado com
as sete cores usadas, e não os três primeiros que a tela pedia — cor que o
gráfico usa mas a chave ignora vira gráfico do tema anterior.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import astuple, dataclass
from typing import Any, Callable, Hashable


@dataclass(frozen=True)
class ChartPalette:
    """Cores já resolvidas para a face (clara/escura) em vigor.

    Congelado e completo de propósito: entra inteiro na chave do cache, então
    trocar preset ou modo de aparência muda a chave e o gráfico é redesenhado.
    """

    panel: str
    text: str
    sub: str
    accent: str
    success: str
    warning: str
    danger: str


def members_chart_key(dashboard: dict[str, Any], palette: ChartPalette) -> Hashable:
    """Chave do gráfico de membros: os números desenhados + a paleta."""
    summary = dashboard.get("summary") or {}
    total = summary.get("total_members", 0)
    active = summary.get("active_members", 0)
    return (
        "members",
        total,
        active,
        dashboard.get("defaulters_count", 0),
        astuple(palette),
    )


def finance_chart_key(dashboard: dict[str, Any], palette: ChartPalette) -> Hashable:
    """Chave do gráfico financeiro: as três barras + a paleta."""
    finance = dashboard.get("finance_summary") or {}
    return (
        "finance",
        finance.get("paid_amount", 0),
        finance.get("pending_amount", 0),
        finance.get("late_amount", 0),
        astuple(palette),
    )


class FigureCache:
    """LRU minúsculo de figuras, com contadores para os testes.

    ``maxsize`` pequeno porque o interesse é a visita repetida, não histórico:
    dois gráficos vezes o tema atual e o anterior já cobre o uso real, e figura
    de tema abandonado sai sozinha em vez de ficar ocupando memória.
    """

    def __init__(self, maxsize: int = 4) -> None:
        if maxsize < 1:
            raise ValueError("maxsize precisa ser >= 1")
        self._maxsize = maxsize
        self._entries: OrderedDict[Hashable, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get_or_build(self, key: Hashable, build: Callable[[], Any]) -> Any:
        """Devolve a figura de ``key``, construindo-a só quando não houver."""
        if key in self._entries:
            self._entries.move_to_end(key)
            self.hits += 1
            return self._entries[key]

        self.misses += 1
        figure = build()
        self._entries[key] = figure
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)
        return figure

    def clear(self) -> None:
        """Esvazia o cache (troca de tema, janela fechando, teste)."""
        self._entries.clear()

    def reset_stats(self) -> None:
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._entries
