"""Agrupamento de ações de formulário — hierarquia antes de densidade (F5.6 / P3-7).

O ``_grid_form_buttons`` empilha ``(rótulo, comando)`` em coluna, com todos os
botões do mesmo peso. Funciona para meia dúzia de ações; com 25 (tela de
Jogadores) vira um muro em que nada se destaca e a ação destrutiva tem o mesmo
peso visual de "Modelo jogadores".

Este módulo dá **vocabulário** para a tela declarar hierarquia sem saber desenhar:

- ``(rótulo, comando)`` — botão comum, como antes;
- :class:`ActionGroup` — vira um ``menu_button`` ("Importar ▾") com as ações
  recolhidas;
- :class:`DangerAction` — vira ``danger_button``, sempre por último e separado.

É o mesmo molde que a F2.1 provou na barra de Rodadas, agora disponível para as
16 chamadas de ``_grid_form_buttons``.

O módulo é **puro** (não importa Tk): quem desenha é o ``_grid_form_buttons``.
Isso deixa a decisão de agrupamento — que é a parte que se discute e se revisa —
testável sem abrir janela.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple, Union

__all__ = ["ActionGroup", "DangerAction", "FormAction", "visible_controls", "flatten_actions"]

# Item de menu: ``(rótulo, comando)``; ``None`` no lugar do item vira separador.
MenuEntry = Optional[Tuple[str, Optional[Callable[[], None]]]]


@dataclass(frozen=True)
class ActionGroup:
    """Ações de apoio recolhidas atrás de um gatilho ``"label ▾"``."""

    label: str
    items: Sequence[MenuEntry] = field(default_factory=tuple)
    tip: str = ""


@dataclass(frozen=True)
class DangerAction:
    """Ação destrutiva: cor de perigo e posição isolada do resto."""

    label: str
    command: Callable[[], None]
    tip: str = ""


# O que uma tela pode declarar numa lista de ações.
FormAction = Union[Tuple[str, Callable[[], None]], ActionGroup, DangerAction]


def visible_controls(actions: Sequence[FormAction]) -> int:
    """Quantos alvos clicáveis a tela mostra no mesmo nível.

    A métrica do aceite da F5.6 (ESPEC_UI_UX §10.11: no máximo ~8): um grupo
    conta como **um** controle, não como o tamanho do menu.
    """
    return len(actions)


def flatten_actions(actions: Sequence[FormAction]) -> list[str]:
    """Todos os rótulos alcançáveis, inclusive os de dentro dos menus.

    Serve para provar que reagrupar não **perdeu** nenhuma ação — que é o risco
    real de mexer num muro de 25 botões.
    """
    rotulos: list[str] = []
    for acao in actions:
        if isinstance(acao, ActionGroup):
            rotulos.extend(item[0] for item in acao.items if item is not None)
        elif isinstance(acao, DangerAction):
            rotulos.append(acao.label)
        else:
            rotulos.append(acao[0])
    return rotulos
