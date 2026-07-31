"""Histórico de participação: quem saiu, quando, e se voltou (ARB-05).

`players.player_status` é um campo ÚNICO: guarda o estado de agora e apaga o
anterior. `withdrawn` e `absent` produziam o mesmo efeito (`active = 0`) e não
sobrava rastro de "saiu na rodada 3, voltou na 5" — nem para a ata, nem para
explicar por que um jogador some do pareamento no meio do evento.

Este módulo é a parte pura: o que cada estado significa, qual vale numa rodada,
e como isso vira texto. Quem grava é o serviço; a tabela `player_status_events`
é append-only, e o campo do jogador continua existindo como o "estado de agora".

Sobre o TRF: ele não tem código para separar "desistiu" de "faltou". As duas
viram `0000 - Z` (não pareado, zero ponto), e isso está certo — o que a FIDE
distingue é `Z` (não pareado) de `-` (pareado e não compareceu, que é forfeit e
exige mesa). A diferença entre desistência e ausência é do REGULAMENTO, não do
arquivo, e por isso ela vive na ata.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# Estados de participação. `active` é a volta — a "reentrada" da espec.
STATUS_ACTIVE = "active"
STATUS_WITHDRAWN = "withdrawn"
STATUS_ABSENT = "absent"
STATUS_INACTIVE = "inactive"

PARTICIPATION_STATUSES: dict[str, str] = {
    STATUS_ACTIVE: "Ativo",
    STATUS_WITHDRAWN: "Desistente",
    STATUS_ABSENT: "Ausente",
    STATUS_INACTIVE: "Nao emparceirado",
}

# Estados que tiram o jogador do pareamento.
OUT_STATUSES = frozenset({STATUS_WITHDRAWN, STATUS_ABSENT, STATUS_INACTIVE})

# Quem desistiu não volta pela mesma porta que quem faltou: a reentrada de um
# desistente é decisão arbitral e costuma exigir registro na ata. Os dois são
# reversíveis aqui — o que muda é o texto, e é o texto que o árbitro lê.
REENTRY_NEEDS_REASON = frozenset({STATUS_WITHDRAWN})

MAX_REASON_LENGTH = 200


def clean_reason(reason: Any) -> str:
    return " ".join(str(reason or "").split())[:MAX_REASON_LENGTH]


def is_out(status: Any) -> bool:
    return str(status or STATUS_ACTIVE).strip() in OUT_STATUSES


def status_error(status: Any) -> str:
    """``""`` quando o estado existe. Estado inventado nao entra no historico."""
    if str(status or "").strip() not in PARTICIPATION_STATUSES:
        return (
            "Estado de participacao invalido. Use: "
            + ", ".join(sorted(PARTICIPATION_STATUSES))
            + "."
        )
    return ""


def change_error(
    *,
    new_status: str,
    current_status: str,
    reason: str,
) -> str:
    """Por que ESTA mudança não pode ser registrada. ``""`` quando pode."""
    erro = status_error(new_status)
    if erro:
        return erro
    if str(new_status).strip() == str(current_status or STATUS_ACTIVE).strip():
        return f"O jogador ja esta como \"{PARTICIPATION_STATUSES[new_status]}\"."
    if (
        str(new_status).strip() == STATUS_ACTIVE
        and str(current_status or "").strip() in REENTRY_NEEDS_REASON
        and not clean_reason(reason)
    ):
        return (
            "A reentrada de um jogador que DESISTIU e decisao arbitral: descreva o "
            "motivo, que vai para a ata e para a auditoria."
        )
    return ""


def effective_round(latest_round: Mapping[str, Any] | None) -> int:
    """A partir de qual rodada a mudança vale.

    A rodada em andamento JÁ FOI pareada: tirar alguém agora não desfaz a mesa
    dele — isso é resultado (W.O.) ou correção. Então a mudança vale da PRÓXIMA
    rodada em diante, que é também a leitura do salão ("a partir da 4 ele não
    joga mais"). Sem rodada nenhuma, vale da primeira.
    """
    if not latest_round:
        return 1
    return int(latest_round.get("number") or 0) + 1


def status_at_round(events: Sequence[Mapping[str, Any]], round_number: int) -> str:
    """Estado em vigor NA rodada pedida, pelo histórico.

    O último evento cuja rodada de vigência é menor ou igual à pedida. Sem
    evento, `active`: o jogador que nunca teve mudança sempre jogou.
    """
    vigente = STATUS_ACTIVE
    for evento in sorted(events, key=lambda item: (int(item.get("round_number") or 0), int(item.get("id") or 0))):
        if int(evento.get("round_number") or 0) <= int(round_number):
            vigente = str(evento.get("status") or STATUS_ACTIVE)
    return vigente


def absence_rounds(
    events: Sequence[Mapping[str, Any]],
    rounds_total: int,
) -> list[int]:
    """Rodadas em que o jogador estava fora, do histórico."""
    return [
        rodada
        for rodada in range(1, int(rounds_total or 0) + 1)
        if is_out(status_at_round(events, rodada))
    ]


def history_lines(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Uma linha por evento, na ordem: ``"R3 — Desistente: viagem"``."""
    linhas: list[str] = []
    for evento in sorted(
        events, key=lambda item: (int(item.get("round_number") or 0), int(item.get("id") or 0))
    ):
        rotulo = PARTICIPATION_STATUSES.get(
            str(evento.get("status") or ""), str(evento.get("status") or "")
        )
        motivo = clean_reason(evento.get("reason"))
        linha = f"R{int(evento.get('round_number') or 0)} — {rotulo}"
        linhas.append(f"{linha}: {motivo}" if motivo else linha)
    return linhas


def summarize(events: Sequence[Mapping[str, Any]], rounds_total: int) -> str:
    """Resumo de uma linha para a ata: saídas, voltas e rodadas de fora."""
    if not events:
        return ""
    fora = absence_rounds(events, rounds_total)
    if not fora:
        return "; ".join(history_lines(events))
    faixas = _ranges(fora)
    return "Fora " + ", ".join(faixas) + " — " + "; ".join(history_lines(events))


def _ranges(numbers: Sequence[int]) -> list[str]:
    """``[3, 4, 5, 8]`` -> ``["R3-R5", "R8"]``."""
    if not numbers:
        return []
    faixas: list[str] = []
    inicio = anterior = numbers[0]
    for atual in list(numbers)[1:]:
        if atual == anterior + 1:
            anterior = atual
            continue
        faixas.append(f"R{inicio}" if inicio == anterior else f"R{inicio}-R{anterior}")
        inicio = anterior = atual
    faixas.append(f"R{inicio}" if inicio == anterior else f"R{inicio}-R{anterior}")
    return faixas
