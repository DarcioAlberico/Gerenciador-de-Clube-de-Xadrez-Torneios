"""Regras puras da partida ADIADA (ARB-02).

Uma mesa adiada é uma pendência **esperada**: o árbitro sabe que ela está em
aberto e por quê. Sem a marca, ela é indistinguível da mesa que alguém esqueceu
de lançar — as duas travam a rodada do mesmo jeito e com o mesmo recado, e o
árbitro não tem como saber se está cobrando alguém ou aguardando um combinado.

Aqui só as regras e os textos; quem grava é o serviço, quem desenha é a tela.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import FINAL_RESULTS, player_pairing_name

# Nota do adiamento: cabe "sabado 14h" e "aguardando decisao de apelacao", e não
# cabe uma ata. O limite é da coluna, não da regra — texto maior é cortado pela
# tela antes de chegar aqui.
MAX_NOTE_LENGTH = 120


def clean_note(note: Any) -> str:
    return " ".join(str(note or "").split())[:MAX_NOTE_LENGTH]


def postpone_error(pairing: Mapping[str, Any] | None) -> str:
    """Por que ESTA mesa não pode ser adiada. ``""`` quando pode.

    Três recusas, todas por o adiamento não fazer sentido no estado em que a
    mesa está — e não por segurança: adiar é reversível e não move ponto nenhum.
    """
    if not pairing:
        return "Mesa nao encontrada para o torneio selecionado."
    if str(pairing.get("round_status") or "") == "closed":
        return (
            "A rodada esta fechada. Uma partida adiada e uma pendencia da rodada "
            "em andamento; para mexer numa rodada fechada, use a correcao com motivo."
        )
    if pairing.get("is_bye"):
        return "Um bye nao e partida: nao ha o que adiar."
    resultado = str(pairing.get("result") or "")
    if resultado and resultado in FINAL_RESULTS:
        return (
            "A mesa ja tem resultado lancado. Limpe o resultado antes de marcar "
            "a partida como adiada."
        )
    return ""


def resume_error(pairing: Mapping[str, Any] | None) -> str:
    """Por que ESTA mesa não pode voltar de adiada. ``""`` quando pode."""
    if not pairing:
        return "Mesa nao encontrada para o torneio selecionado."
    if not int(pairing.get("postponed") or 0):
        return "Esta mesa nao esta marcada como adiada."
    return ""


def describe_pairing(pairing: Mapping[str, Any]) -> str:
    """``"Mesa 4: Fulano x Sicrano"`` — o suficiente para achar a mesa no salão."""
    brancas = player_pairing_name(
        {
            "name": pairing.get("white_player_name"),
            "surname": pairing.get("white_player_surname"),
            "given_name": pairing.get("white_player_given_name"),
        }
    )
    pretas = player_pairing_name(
        {
            "name": pairing.get("black_player_name"),
            "surname": pairing.get("black_player_surname"),
            "given_name": pairing.get("black_player_given_name"),
        }
    )
    mesa = f"Mesa {pairing.get('board_number', '?')}"
    if not brancas and not pretas:
        return mesa
    return f"{mesa}: {brancas or '?'} x {pretas or '?'}"


def postponed_label(pairing: Mapping[str, Any]) -> str:
    """Rótulo curto para a coluna de contexto do painel."""
    nota = clean_note(pairing.get("postponed_note"))
    return f"Adiada — {nota}" if nota else "Adiada"


def blocking_message(postponed: Sequence[Mapping[str, Any]]) -> str:
    """Recado do fechamento quando há mesa adiada.

    Nomeia as mesas de propósito: o recado genérico "preencha todos os
    resultados" manda o árbitro procurar o que ele já sabe que está em aberto.
    """
    linhas = [describe_pairing(item) for item in postponed]
    detalhe = "; ".join(linhas)
    quantas = len(linhas)
    plural = "partida adiada" if quantas == 1 else "partidas adiadas"
    return (
        f"A rodada tem {quantas} {plural} e nao pode ser fechada: {detalhe}. "
        "Lance o resultado ou desfaca o adiamento."
    )


def issue_from_pairing(
    pairing: Mapping[str, Any],
    round_id: int,
    round_number: int,
) -> dict[str, Any]:
    """Pendência do painel para uma mesa adiada.

    ``severity="attention"``, e não ``"decision"``: a decisão o árbitro já tomou
    — foi ele quem adiou. O que impede o fechamento é a mesa sem resultado, com
    o recado próprio de `blocking_message`; marcar como bloqueante aqui faria a
    mesma coisa aparecer duas vezes, com dois textos diferentes.
    """
    nota = clean_note(pairing.get("postponed_note"))
    return {
        "issue_key": f"postponed:pairing:{int(pairing.get('id') or 0)}",
        "severity": "attention",
        "source": "postponed",
        "kind": "pairing",
        "title": describe_pairing(pairing) + (f" — {nota}" if nota else ""),
        "round_id": int(round_id),
        "round_number": int(round_number),
        "entity_id": int(pairing.get("id") or 0),
        "created_at": str(pairing.get("created_at") or ""),
    }
