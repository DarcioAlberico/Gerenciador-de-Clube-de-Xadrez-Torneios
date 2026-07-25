"""Digitar num campo, de verdade, num teste de janela.

Existe porque três detalhes do Tk/customtkinter conspiram para um teste de busca
**passar sem nunca ter buscado** — foi o que aconteceu com
``test_arbitration_issues_filter_and_search_locate_table_without_mutation`` até
a B-4:

1. o ``CTkEntry`` é um frame com um ``tk.Entry`` dentro, e o ``bind`` vive no
   widget interno — gerar o evento no invólucro não dispara nada;
2. evento de tecla **sem ``keysym``** o Tk descarta em silêncio;
3. sem **foco** no campo, o evento também não é entregue.

Nenhum dos três levanta erro. O teste segue verde medindo a tabela não-filtrada.
"""
from __future__ import annotations

from typing import Any


def inner_entry(entry: Any) -> Any:
    """O ``tk.Entry`` de dentro de um ``CTkEntry`` (ou o próprio, se já for Tk)."""
    return getattr(entry, "_entry", entry)


def type_into(entry: Any, text: str, *, clear: bool = True) -> None:
    """Escreve ``text`` no campo e dispara ``<KeyRelease>`` como o usuário faria.

    Uma tecla só, e não uma por caractere: o que as telas escutam é o evento,
    não a sequência — e o campo já está com o texto completo quando ele chega.
    """
    if clear:
        entry.delete(0, "end")
    entry.insert(0, text)
    interno = inner_entry(entry)
    interno.focus_set()
    interno.update_idletasks()
    interno.event_generate("<KeyRelease>", keysym="a", when="now")
