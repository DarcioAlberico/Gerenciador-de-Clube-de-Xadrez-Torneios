"""Reestilização da árvore de widgets — trocar tema sem destruir a UI (P0-6).

Antes, aplicar um tema **destruía e recriava** `statusbar` e `content`: a tela
voltava para o começo, a seleção da tabela sumia, o scroll ia para o topo e o
foco se perdia. Aqui a troca vira `configure()` widget a widget, e nada é
recriado — por construção, foco, scroll e seleção continuam onde estavam.

Duas origens de cor precisam de tratamento diferente:

- **Tokens** (``THEME_*``): desde a F1.1 são listas mutadas no lugar, então o
  widget já segura o valor novo; falta só repintar, e ``configure`` faz isso.
- **Padrões do ``ThemeManager``** (o accent dos botões, por exemplo): foram
  *copiados* para dentro do widget quando ele nasceu. Para saber quem ainda
  seguia o padrão antigo — e não repintar por cima de quem tem cor própria,
  como um botão de perigo —, comparamos com um retrato tirado **antes** da
  troca (:func:`snapshot_defaults`).

    antes = snapshot_defaults()
    apply_accent_preset("emerald")
    restyle(janela, antes)
"""
from __future__ import annotations

import copy
import logging
from typing import Any

import customtkinter as ctk

logger = logging.getLogger("src.ui.restyle")

# Opções de cor por classe do customtkinter. Só o que existe na classe entra:
# `cget` de opção inválida levanta, e engolir isso em silêncio esconderia erro.
COLOR_OPTIONS: dict[str, tuple[str, ...]] = {
    "CTk": ("fg_color",),
    "CTkToplevel": ("fg_color",),
    "CTkFrame": ("fg_color", "border_color"),
    "CTkScrollableFrame": ("fg_color", "label_fg_color"),
    "CTkLabel": ("fg_color", "text_color"),
    "CTkButton": ("fg_color", "hover_color", "border_color", "text_color", "text_color_disabled"),
    "CTkEntry": ("fg_color", "border_color", "text_color", "placeholder_text_color"),
    "CTkTextbox": ("fg_color", "border_color", "text_color", "scrollbar_button_color"),
    "CTkOptionMenu": ("fg_color", "button_color", "button_hover_color", "text_color"),
    "CTkComboBox": ("fg_color", "border_color", "button_color", "button_hover_color", "text_color"),
    "CTkCheckBox": ("fg_color", "hover_color", "border_color", "text_color"),
    "CTkRadioButton": ("fg_color", "hover_color", "border_color", "text_color"),
    "CTkSwitch": ("fg_color", "progress_color", "button_color", "button_hover_color", "text_color"),
    "CTkSlider": ("fg_color", "progress_color", "button_color", "button_hover_color"),
    "CTkProgressBar": ("fg_color", "progress_color", "border_color"),
    "CTkSegmentedButton": ("fg_color", "selected_color", "selected_hover_color", "unselected_color", "text_color"),
    "CTkScrollbar": ("fg_color", "button_color", "button_hover_color"),
}


def snapshot_defaults() -> dict[str, dict[str, Any]]:
    """Retrato dos padrões do ``ThemeManager``, para comparar depois da troca."""
    try:
        return copy.deepcopy(ctk.ThemeManager.theme)
    except Exception:  # pragma: no cover - depende do interno do customtkinter
        logger.exception("Falha ao fotografar os padroes do ThemeManager")
        return {}


def _tk_children(widget: Any) -> list[Any]:
    """Filhos reais, incluindo os que o CTk esconde de ``winfo_children``."""
    try:
        caminhos = widget.tk.splitlist(widget.tk.call("winfo", "children", str(widget)))
    except Exception:
        return []
    filhos = []
    for caminho in caminhos:
        try:
            filhos.append(widget.nametowidget(caminho))
        except Exception:
            continue
    return filhos


def _resolve(widget: Any, option: str, previous: dict[str, dict[str, Any]], cls: str) -> Any:
    """Valor a aplicar: o novo padrão do tema, se o widget ainda seguia o antigo;
    senão o próprio valor atual (token já mutado, ou cor escolhida a dedo)."""
    atual = widget.cget(option)
    antigo = previous.get(cls, {}).get(option)
    novo = ctk.ThemeManager.theme.get(cls, {}).get(option)
    if antigo is not None and novo is not None and antigo != novo and atual == antigo:
        return novo
    return atual


def restyle(widget: Any, previous_defaults: dict[str, dict[str, Any]] | None = None) -> int:
    """Repinta ``widget`` e seus descendentes. Devolve quantos foram tocados.

    Nunca levanta por causa de um widget: uma tela com um caso esquisito não
    pode impedir o resto da janela de acompanhar o tema.
    """
    previous = previous_defaults or {}
    tocados = 0
    pilha = [widget]
    while pilha:
        atual = pilha.pop()
        pilha.extend(_tk_children(atual))
        opcoes = COLOR_OPTIONS.get(type(atual).__name__)
        if not opcoes:
            continue
        cls = type(atual).__name__
        mudancas: dict[str, Any] = {}
        for opcao in opcoes:
            try:
                mudancas[opcao] = _resolve(atual, opcao, previous, cls)
            except Exception:
                continue  # opcao inexistente nesta versao do customtkinter
        if not mudancas:
            continue
        try:
            atual.configure(**mudancas)
            tocados += 1
        except Exception:
            logger.exception("Falha ao reestilizar %s", cls)
    return tocados
