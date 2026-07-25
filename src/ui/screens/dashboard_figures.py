"""Montagem das figuras do Dashboard — matplotlib, sem Tk.

Separado da tela porque desenhar não é montar janela: aqui entra um dicionário
de dados e sai uma ``Figure``, o que roda no gate sem display. A tela
([dashboard.py](dashboard.py)) fica só com painéis, embutir e estados vazios.

Usa ``Figure`` direto, **não** ``pyplot``: o manager global do pyplot custava
~245 ms por gráfico (ver a tabela em [charts.py](../charts.py)) e ainda obrigava
a um ``plt.close()`` para não vazar — com ``Figure`` a coleta é a normal do
Python, o que é o que permite guardar a figura no cache sem medo.
"""
from __future__ import annotations

from typing import Any

from matplotlib.figure import Figure

from ..charts import ChartPalette
from ..theme import (
    THEME_ACCENT,
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_SUCCESS,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_WARNING,
    pick,
)

# Proporção dos dois painéis de gráfico do Dashboard, em polegadas.
FIGSIZE = (5.0, 3.0)


def current_palette() -> ChartPalette:
    """Resolve os tokens do tema para a face em vigor.

    ``pick`` porque o matplotlib só aceita **uma** cor — o par (claro, escuro)
    do token não serve. Todas as cores usadas no desenho passam por aqui, e é
    esta tupla que entra na chave do cache.
    """
    return ChartPalette(
        panel=pick(THEME_PANEL_BG),
        text=pick(THEME_TEXT_MAIN),
        sub=pick(THEME_TEXT_SUB),
        accent=pick(THEME_ACCENT),
        success=pick(THEME_SUCCESS),
        warning=pick(THEME_WARNING),
        danger=pick(THEME_DANGER),
    )


def _new_figure(palette: ChartPalette) -> tuple[Figure, Any]:
    figure = Figure(figsize=FIGSIZE, facecolor=palette.panel)
    axes = figure.add_subplot(111)
    axes.set_facecolor(palette.panel)
    return figure, axes


def build_members_figure(dashboard: dict[str, Any], palette: ChartPalette) -> Figure:
    """Pizza ativos × inativos, com o aviso de inadimplentes no título."""
    summary = dashboard.get("summary") or {}
    total = summary.get("total_members", 0)
    active = summary.get("active_members", 0)
    inactive = total - active
    defaulters = dashboard.get("defaulters_count", 0)

    figure, axes = _new_figure(palette)
    if total > 0:
        axes.pie(
            [active, inactive],
            labels=["Ativos", "Inativos"],
            autopct="%1.1f%%",
            colors=[palette.accent, palette.sub],
            textprops={"color": palette.text},
        )
    else:
        axes.text(0.5, 0.5, "Sem dados", ha="center", va="center", color=palette.sub)

    title = "Status dos Membros"
    if defaulters > 0:
        title += f"\n(Atenção: {defaulters} inadimplentes)"
    axes.set_title(title, color=palette.text)
    return figure


def build_finance_figure(dashboard: dict[str, Any], palette: ChartPalette) -> Figure:
    """Barras recebido / pendente / atrasado."""
    finance = dashboard.get("finance_summary") or {}

    figure, axes = _new_figure(palette)
    axes.bar(
        ["Recebido", "Pendente", "Atrasado"],
        [
            finance.get("paid_amount", 0),
            finance.get("pending_amount", 0),
            finance.get("late_amount", 0),
        ],
        color=[palette.success, palette.warning, palette.danger],
    )
    axes.set_title("Status Financeiro", color=palette.text)
    axes.tick_params(colors=palette.sub)
    for spine in axes.spines.values():
        spine.set_color(palette.sub)
    return figure
