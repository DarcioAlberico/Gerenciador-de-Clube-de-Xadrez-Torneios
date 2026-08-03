"""Mata-mata: quem avança, por quê, e o que a chave mostra — puro (PAR-03).

O que havia antes decidia o avanço com dois `if`: `1-0` passa as brancas, `0-1`
passa as pretas, **qualquer outra coisa** passa quem tem o melhor número inicial.
"Qualquer outra coisa" incluía o empate (o caso mais comum de um mata-mata!), a
dupla ausência, a mesa ainda em branco — e também o W.O. e o resultado por
decisão do árbitro (`1F-0F`, `1U-0U`), que têm vencedor claro e ainda assim eram
resolvidos pelo número inicial. Nada disso aparecia em lugar nenhum: o jogador
sumia da chave sem uma linha dizendo por quê.

Aqui o avanço tem três origens, e todas ficam registradas:

- **tabuleiro**: alguém fez mais pontos na mesa (inclui W.O. e decisão arbitral);
- **bye**: não havia adversário naquela fase;
- **decisão registrada**: empate, dupla ausência ou mesa sem resultado exigem que
  o árbitro diga QUEM passa e POR QUE (`ADVANCEMENT_CRITERIA`) antes da próxima
  fase ser gerada. O sistema não joga o desempate — ele o registra.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import RESULT_POINTS

# Como o desempate foi resolvido fora do tabuleiro. O sistema não arbitra
# nenhum deles: quem joga o blitz e o armagedom é a sala, e o que entra aqui é a
# ata do que aconteceu lá.
ADVANCEMENT_CRITERIA: dict[str, str] = {
    "mini_match": "Mini-match de desempate",
    "rapid": "Partidas rapidas",
    "blitz": "Blitz",
    "armageddon": "Armagedom",
    "regulation": "Criterio do regulamento (melhor colocado, sorteio previsto)",
    "arbiter": "Decisao do arbitro",
}

# Origens automáticas — não são escolha de ninguém, saem da própria mesa.
SOURCE_BOARD = "board"
SOURCE_BYE = "bye"

BOARD_LABEL = "Resultado no tabuleiro"
BYE_LABEL = "Bye (sem adversario na fase)"

# Motivo é obrigatório quando o critério não descreve sozinho o que houve.
CRITERIA_NEEDING_NOTES = frozenset({"regulation", "arbiter"})
MIN_NOTES_LENGTH = 5
MAX_NOTES_LENGTH = 200


def clean_notes(notes: Any) -> str:
    return " ".join(str(notes or "").split())[:MAX_NOTES_LENGTH]


def board_winner(pairing: Mapping[str, Any]) -> int | None:
    """Quem venceu NO TABULEIRO, ou None quando a mesa não decide sozinha.

    Usa os pontos do resultado, e não uma lista de códigos: W.O. e resultado por
    decisão do árbitro (ARB-02) têm vencedor tão claro quanto um `1-0`, e eram
    tratados como empate — o avanço caía no número inicial, em silêncio.
    """
    if pairing.get("is_bye"):
        return int(pairing["white_player_id"])
    black_id = pairing.get("black_player_id")
    if not black_id:
        return int(pairing["white_player_id"])
    pontos = RESULT_POINTS.get(str(pairing.get("result") or "").strip())
    if not pontos:
        return None
    brancas, pretas = pontos
    if brancas > pretas:
        return int(pairing["white_player_id"])
    if pretas > brancas:
        return int(black_id)
    return None


def advancement_source(pairing: Mapping[str, Any]) -> str:
    return SOURCE_BYE if pairing.get("is_bye") else SOURCE_BOARD


def criterion_label(criterion: str) -> str:
    codigo = str(criterion or "").strip()
    if codigo == SOURCE_BOARD:
        return BOARD_LABEL
    if codigo == SOURCE_BYE:
        return BYE_LABEL
    return ADVANCEMENT_CRITERIA.get(codigo, codigo or "Sem criterio")


def decision_error(
    *,
    criterion: str,
    notes: str,
    player_id: int,
    pairing: Mapping[str, Any] | None,
    round_closed: bool,
) -> str:
    """``""`` quando a decisão pode ser registrada."""
    if pairing is None:
        return "Mesa nao encontrada para o torneio selecionado."
    if str(criterion or "").strip() not in ADVANCEMENT_CRITERIA:
        return (
            "Criterio de avanco invalido. Use: "
            + ", ".join(sorted(ADVANCEMENT_CRITERIA))
            + "."
        )
    if pairing.get("is_bye"):
        return "Mesa de bye nao tem desempate: o jogador ja avanca sozinho."
    participantes = {
        int(pairing.get("white_player_id") or 0),
        int(pairing.get("black_player_id") or 0),
    }
    if int(player_id) not in participantes:
        return "O jogador escolhido nao esta nesta mesa."
    if board_winner(pairing) is not None:
        return (
            "Esta mesa foi decidida no tabuleiro. Corrija o resultado se ele "
            "estiver errado — um avanco registrado nao substitui o placar."
        )
    if not round_closed:
        return (
            "Feche a rodada antes de registrar o avanco: enquanto ela esta aberta "
            "o resultado ainda pode mudar."
        )
    if str(criterion).strip() in CRITERIA_NEEDING_NOTES and len(clean_notes(notes)) < MIN_NOTES_LENGTH:
        return (
            "Descreva o que decidiu o avanco (o criterio do regulamento aplicado, "
            "ou a decisao do arbitro). Sem isso a chave nao explica nada."
        )
    return ""


def undecided_boards(
    pairings: Sequence[Mapping[str, Any]],
    decisions_by_pairing: Mapping[int, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Mesas que não decidem sozinhas e ainda não têm decisão registrada."""
    pendentes = []
    for pairing in pairings:
        if board_winner(pairing) is not None:
            continue
        if int(pairing.get("id") or 0) in decisions_by_pairing:
            continue
        pendentes.append(pairing)
    return pendentes


def pending_decision_message(boards: Sequence[int]) -> str:
    mesas = ", ".join(str(board) for board in boards)
    return (
        f"Mata-mata: a(s) mesa(s) {mesas} terminaram sem vencedor no tabuleiro. "
        "Registre quem avanca e por que criterio (mini-match, rapidas, blitz, "
        "armagedom, regulamento ou decisao do arbitro) antes de gerar a proxima "
        "fase. Antes, o melhor colocado passava em silencio."
    )


def advancement(
    pairing: Mapping[str, Any],
    decisions_by_pairing: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Quem avançou nesta mesa e por quê. ``None`` enquanto não há decisão."""
    vencedor = board_winner(pairing)
    if vencedor is not None:
        return {
            "player_id": vencedor,
            "criterion": advancement_source(pairing),
            "notes": "",
        }
    decisao = decisions_by_pairing.get(int(pairing.get("id") or 0))
    if not decisao:
        return None
    return {
        "player_id": int(decisao["player_id"]),
        "criterion": str(decisao.get("criterion") or "arbiter"),
        "notes": str(decisao.get("notes") or ""),
    }


def advancing_player_ids(
    pairings: Sequence[Mapping[str, Any]],
    decisions_by_pairing: Mapping[int, Mapping[str, Any]],
) -> list[int]:
    ids = []
    for pairing in pairings:
        passou = advancement(pairing, decisions_by_pairing)
        if passou:
            ids.append(int(passou["player_id"]))
    return ids


def third_place_pairing(
    previous_pairings: Sequence[Mapping[str, Any]],
    decisions_by_pairing: Mapping[int, Mapping[str, Any]],
    board_number: int,
) -> dict[str, Any] | None:
    """Mesa do 3º lugar: os dois que perderam a semifinal.

    Só existe quando a fase anterior teve exatamente duas mesas com dois
    jogadores cada — a semifinal. Com bye na semi não há dois perdedores, e
    inventar um terceiro lugar ali seria premiar quem não jogou.
    """
    perdedores: list[int] = []
    for pairing in previous_pairings:
        if pairing.get("is_bye") or not pairing.get("black_player_id"):
            return None
        passou = advancement(pairing, decisions_by_pairing)
        if not passou:
            return None
        lados = {int(pairing["white_player_id"]), int(pairing["black_player_id"])}
        perdedores.extend(lados - {int(passou["player_id"])})
    if len(perdedores) != 2:
        return None
    return {
        "board_number": int(board_number),
        "white_player_id": perdedores[0],
        "black_player_id": perdedores[1],
        "result": "",
        "is_bye": 0,
    }


def bracket(
    rounds: Sequence[Mapping[str, Any]],
    pairings_by_round: Mapping[int, Sequence[Mapping[str, Any]]],
    decisions_by_pairing: Mapping[int, Mapping[str, Any]],
    names_by_player: Mapping[int, str],
) -> list[dict[str, Any]]:
    """A chave, fase a fase, com o motivo de cada avanço.

    É esta lista que responde "por que este jogador está na próxima fase?" —
    a pergunta que antes não tinha resposta em lugar nenhum do sistema.
    """
    fases: list[dict[str, Any]] = []
    for round_data in rounds:
        numero = int(round_data.get("number") or 0)
        mesas = []
        for pairing in pairings_by_round.get(numero, []):
            passou = advancement(pairing, decisions_by_pairing)
            branca = int(pairing.get("white_player_id") or 0)
            preta = int(pairing.get("black_player_id") or 0)
            mesas.append(
                {
                    "board_number": int(pairing.get("board_number") or 0),
                    "white_player_id": branca,
                    "white_name": names_by_player.get(branca, str(branca)),
                    "black_player_id": preta or None,
                    "black_name": "BYE" if pairing.get("is_bye") else names_by_player.get(preta, ""),
                    "result": str(pairing.get("result") or ""),
                    "advanced_player_id": passou["player_id"] if passou else None,
                    "advanced_name": (
                        names_by_player.get(int(passou["player_id"]), "") if passou else ""
                    ),
                    "criterion": passou["criterion"] if passou else "",
                    "criterion_label": criterion_label(passou["criterion"]) if passou else "",
                    "notes": passou["notes"] if passou else "",
                    "pending": passou is None,
                }
            )
        fases.append(
            {
                "round_number": numero,
                "round_status": str(round_data.get("status") or ""),
                "boards": mesas,
                "pending": sum(1 for mesa in mesas if mesa["pending"]),
            }
        )
    return fases
