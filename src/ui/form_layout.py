"""Ritmo vertical do formulário — a parte que decide *espaço*, sem abrir widget.

Camada pura da F5.4 (molde da F1.5): aqui moram as regras de espaçamento e a
largura do painel de formulário; o [`components/form.py`](components/form.py)
só as aplica no grid. Nada nesta linha cria widget, então o ritmo é testável
sem janela — e, mais importante, é **um lugar só** para mudá-lo.

Por que existir (P3-12): os formulários do app usavam três padrões — grid com
aritmética manual de linhas (``row=index * 2 + 1``), o ``_settings_stack`` da
Config. do torneio e ``pack`` solto — e, entre eles, mais de dez combinações de
``pady``. O resultado visível era o ritmo mudar de tela para tela e formulários
de 14 a 25 campos sem nenhuma divisão: uma coluna única de rótulos, do primeiro
ao último, sem onde o olho descansar.

As regras abaixo são poucas de propósito:

- **campo** carrega o próprio respiro de cima (``SPACE_SM``) e nada embaixo — a
  linha de mensagem do ``labeled_field`` já ocupa o rodapé do campo;
- **seção** abre com ``SPACE_XL``, o dobro do maior espaço entre campos: é essa
  diferença que faz o grupo ser lido como grupo, e não a régua nem a cor;
- a **primeira** linha do painel nunca recebe respiro de cima — margem dupla no
  topo é o defeito clássico de empilhar sem olhar para a posição.
"""
from __future__ import annotations

from typing import Literal

from .theme import SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XL, SPACE_XS

# Largura única do painel de formulário (P3-12): antes eram 272, 280, 292, 300 e
# 302 — cinco medidas para a mesma coluna, nascidas de ajuste no olho, tela a
# tela. 300 é a escolhida por caber o campo padrão (FIELD_MD=240) mais as duas
# margens de FORM_PADX com folga para a barra de rolagem do CTkScrollableFrame.
FORM_PANEL_WIDTH = 300

# Margem lateral de todas as linhas do formulário.
FORM_PADX = SPACE_LG

RowKind = Literal["field", "section", "widget", "note"]

_TOP = {
    "field": SPACE_SM,
    "section": SPACE_XL,
    "widget": SPACE_SM,
    "note": SPACE_XS,
}
_BOTTOM = {
    "field": 0,  # a linha de mensagem do labeled_field ja e o rodape do campo
    "section": SPACE_XS,
    "widget": SPACE_XS,
    "note": SPACE_SM,
}


def row_padding(kind: RowKind, *, first: bool = False) -> tuple[int, int]:
    """``pady`` de uma linha do formulário: ``(topo, base)``.

    ``first`` é a linha inicial do painel — o respiro de cima já vem da margem
    do próprio painel, então somá-lo aqui dobraria a distância só no topo.
    """
    topo = 0 if first else _TOP[kind]
    return topo, _BOTTOM[kind]


def section_gap() -> int:
    """Distância que separa duas seções — o que define o agrupamento visual."""
    return SPACE_XL


def field_gap() -> int:
    """Distância entre dois campos da mesma seção."""
    return SPACE_SM


def panel_padding() -> tuple[int, int]:
    """``padx``/``pady`` internos do painel de formulário."""
    return FORM_PADX, SPACE_MD
