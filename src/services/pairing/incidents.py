"""Registro disciplinar de incidentes (ARB-03).

Não existia módulo nenhum: celular tocando (art. 11.3.2), lance ilegal (7.5),
atraso além do tempo de tolerância (6.7) e conduta (12.x) eram anotados no PAPEL,
na tabela do manual operacional. `point_adjustments` já existia, mas sem catálogo
de infrações e sem vínculo com o jogador reincidente — dedução de ponto ficava
como um número com um texto livre ao lado.

Aqui vive o CATÁLOGO e as regras; quem grava é o serviço. O catálogo é o que
transforma "anotei no papel" em "o sistema sabe que este é o segundo celular do
mesmo jogador".

Uma decisão de escopo: o catálogo nomeia o artigo, e não a sanção. A FIDE deixa
a sanção a cargo do árbitro (11.3.2 é a exceção histórica — perda da partida —,
e mesmo ela tem redação com margem em torneios rápidos). Então cada infração
traz a sanção SUGERIDA, e o árbitro escolhe; o que o sistema garante é que a
escolha fique registrada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# Decisões do árbitro
# ---------------------------------------------------------------------------

DECISION_WARNING = "warning"
DECISION_LOSS = "loss"
DECISION_DEDUCTION = "deduction"
DECISION_EXPULSION = "expulsion"
DECISION_NONE = "none"

INCIDENT_DECISIONS: dict[str, str] = {
    DECISION_WARNING: "Advertencia",
    DECISION_LOSS: "Partida perdida",
    DECISION_DEDUCTION: "Deducao de pontos",
    DECISION_EXPULSION: "Expulsao do torneio",
    DECISION_NONE: "Sem sancao (registrado)",
}

# Decisões que MEXEM em pontuação e por isso exigem o resto do formulário.
DECISION_NEEDS_PAIRING = frozenset({DECISION_LOSS})
DECISION_NEEDS_POINTS = frozenset({DECISION_DEDUCTION})


@dataclass(frozen=True)
class Infraction:
    """Uma entrada do catálogo: o artigo, o que é, e o que se costuma decidir."""

    code: str
    article: str
    label: str
    suggested: str


INFRACTIONS: dict[str, Infraction] = {
    "mobile_phone": Infraction(
        "mobile_phone", "11.3.2", "Telefone celular / dispositivo eletronico", DECISION_LOSS
    ),
    "illegal_move": Infraction(
        "illegal_move", "7.5", "Lance ilegal", DECISION_WARNING
    ),
    "default_time": Infraction(
        "default_time", "6.7", "Atraso alem do tempo de tolerancia", DECISION_LOSS
    ),
    "conduct": Infraction(
        "conduct", "12.2", "Conduta / perturbacao do adversario", DECISION_WARNING
    ),
    "notation": Infraction(
        "notation", "8.1", "Anotacao incompleta ou ausente", DECISION_WARNING
    ),
    "agreed_result": Infraction(
        "agreed_result", "11.1", "Resultado combinado / falta de esforco", DECISION_EXPULSION
    ),
    "flag_fall": Infraction(
        "flag_fall", "6.2", "Queda de seta contestada", DECISION_NONE
    ),
    "other": Infraction("other", "-", "Outro (descrever nas observacoes)", DECISION_NONE),
}

MAX_NOTES_LENGTH = 500


def clean_notes(notes: Any) -> str:
    return " ".join(str(notes or "").split())[:MAX_NOTES_LENGTH]


def infraction_label(code: str) -> str:
    """``"Telefone celular / dispositivo eletronico (art. 11.3.2)"``."""
    item = INFRACTIONS.get(str(code or "").strip())
    if item is None:
        return str(code or "")
    return f"{item.label} (art. {item.article})" if item.article != "-" else item.label


def decision_label(code: str) -> str:
    return INCIDENT_DECISIONS.get(str(code or "").strip(), str(code or ""))


def register_error(
    *,
    infraction: str,
    decision: str,
    player_id: int | None,
    pairing_id: int | None,
    deduction_points: float,
    notes: str,
) -> str:
    """Por que ESTE incidente não pode ser registrado. ``""`` quando pode."""
    if str(infraction or "").strip() not in INFRACTIONS:
        return "Infracao invalida. Escolha uma do catalogo."
    if str(decision or "").strip() not in INCIDENT_DECISIONS:
        return "Decisao invalida. Escolha uma das opcoes."
    if not player_id:
        return "Informe o jogador envolvido no incidente."
    if str(infraction).strip() == "other" and not clean_notes(notes):
        return (
            "A infracao \"Outro\" exige descricao nas observacoes: e ela que a ata "
            "vai citar no lugar do artigo."
        )
    if str(decision).strip() in DECISION_NEEDS_PAIRING and not pairing_id:
        return (
            "Partida perdida precisa da MESA: e nela que o resultado sera lancado. "
            "Se o incidente nao e de uma partida, use advertencia ou deducao."
        )
    if str(decision).strip() in DECISION_NEEDS_POINTS and not deduction_points:
        return "Deducao de pontos precisa de um valor diferente de zero."
    return ""


def forfeit_result(is_white: bool) -> str:
    """Resultado da mesa quando a decisão é PARTIDA PERDIDA.

    W.O. (`1F-0F`/`0F-1F`), e não o resultado por decisão do árbitro (`1U-0U`,
    da ARB-02): quem perde por regulamento **não jogou aquela partida** aos olhos
    da FIDE — e é por isso que ela não conta como vitória do adversário no
    tabuleiro nem entra no rating.
    """
    return "0F-1F" if is_white else "1F-0F"


def repeat_count(
    incidents: Sequence[Mapping[str, Any]],
    player_id: int,
    infraction: str | None = None,
) -> int:
    """Quantos incidentes o jogador já tem (opcionalmente, da mesma infração).

    É o número que o catálogo existe para produzir: a segunda advertência do
    mesmo artigo é outra conversa, e no papel ninguém a encontrava.
    """
    return sum(
        1
        for item in incidents
        if int(item.get("player_id") or 0) == int(player_id)
        and (infraction is None or str(item.get("infraction") or "") == str(infraction))
    )


def repeat_offenders(incidents: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    """``{player_id: quantidade}`` para quem tem MAIS DE UM incidente."""
    contagem: dict[int, int] = {}
    for item in incidents:
        player_id = int(item.get("player_id") or 0)
        if player_id:
            contagem[player_id] = contagem.get(player_id, 0) + 1
    return {player_id: total for player_id, total in contagem.items() if total > 1}


def describe(incident: Mapping[str, Any]) -> str:
    """Uma linha para a ata e para a pendência do painel."""
    partes = [infraction_label(str(incident.get("infraction") or ""))]
    rodada = int(incident.get("round_number") or 0)
    if rodada:
        partes.append(f"R{rodada}")
    mesa = int(incident.get("board_number") or 0)
    if mesa:
        partes.append(f"mesa {mesa}")
    partes.append(decision_label(str(incident.get("decision") or "")))
    return " — ".join(partes)


# ---------------------------------------------------------------------------
# Alertas de relógio que viram decisão pendente
# ---------------------------------------------------------------------------

# Eventos de relógio que a FIDE não deixa passar sem decisão do árbitro: a seta
# caiu (quem ganha? houve reclamação?) e a ausência (6.7 — perde a partida?).
# Enquanto não houver incidente registrado apontando para eles, a rodada não
# fecha. O aviso de tempo crítico continua sendo só aviso.
DECISION_REQUIRED_CLOCK_EVENTS = frozenset({"flag_fall", "absence"})


def clock_event_needs_decision(event_type: Any) -> bool:
    return str(event_type or "").strip() in DECISION_REQUIRED_CLOCK_EVENTS


def decided_clock_event_ids(incidents: Sequence[Mapping[str, Any]]) -> set[int]:
    """Ids de eventos de relógio que já têm incidente registrado."""
    return {
        int(item["clock_event_id"])
        for item in incidents
        if item.get("clock_event_id")
    }
