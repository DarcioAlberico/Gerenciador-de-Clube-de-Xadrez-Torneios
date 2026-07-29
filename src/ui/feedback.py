"""Para onde vai cada recado da interface (F5.7 / P3-8).

Módulo **puro** (não importa Tk): entra a mensagem, sai o canal.

A F2.2 acertou ao tirar os 26 ``messagebox`` nativos do caminho, mas mandou
tudo para o mesmo lugar: ``_show_info`` vira toast de 320px que some em 3,5
segundos. Serve para "Torneio salvo"; **não** serve para o que o usuário
precisa ler com calma ou copiar — a URL do servidor QR, o caminho do backup, a
narrativa completa de um desempate. Nesses casos o toast é pior do que o
``messagebox`` que substituiu: o antigo pelo menos esperava um clique.

A regra olha o **formato** da mensagem, porque é o formato que denuncia a
intenção:

- uma linha → confirmação; toast, como sempre;
- duas linhas → quase sempre "fiz isto:" + um caminho/endereço; toast, mas com
  ação **Copiar** (o dado inteiro vai para a área de transferência);
- três ou mais → é relatório; abre em diálogo rolável e copiável.

Erro e aviso não entram na regra: são curtos, e ``_show_error`` já manda o
inesperado para um modal com código e caminho do log.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FeedbackPlan", "REPORT_MIN_LINES", "plan_feedback"]

# A partir de quantas linhas a mensagem deixa de caber num toast.
REPORT_MIN_LINES = 3

TOAST = "toast"
REPORT = "report"


@dataclass(frozen=True)
class FeedbackPlan:
    """Canal escolhido e se o recado leva ação de copiar."""

    channel: str
    copyable: bool = False


def line_count(message: str) -> int:
    """Linhas não vazias — uma linha em branco separa blocos, não conta como conteúdo."""
    return len([linha for linha in str(message).splitlines() if linha.strip()])


def plan_feedback(message: str, kind: str = "success") -> FeedbackPlan:
    """Decide entre toast (com ou sem Copiar) e diálogo de relatório."""
    if kind in ("error", "warning"):
        return FeedbackPlan(TOAST)
    linhas = line_count(message)
    if linhas >= REPORT_MIN_LINES:
        return FeedbackPlan(REPORT)
    return FeedbackPlan(TOAST, copyable=linhas == 2)
