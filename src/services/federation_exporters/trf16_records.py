"""Registros e checagens do dialeto TRF16 — funções puras (FED-03).

O TRF16 "de facto" (o que JaVaFo, Swiss-Manager e Chess-Results trocam entre si)
tem extensões que não são registros numerados: `XXR` (total de rodadas) e `XXC`
(cor do tabuleiro 1 na primeira rodada). O exportador emitia `142` no lugar do
`XXR` — que é registro **TRF25** —, então quem lê o dialeto TRF16 ficava sem
saber quantas rodadas o torneio tem.

Sobre o `XXA` (aceleração), que a auditoria pedia junto: ele **não é emitido**, de
propósito. O parser da implementação de referência (Otto Milvang, o motor que
este projeto usa para parear) monta os valores do `XXA` com as chaves
`matchScore`/`gameScore` e depois os lê como `matchResult`/`gameResult` —
`KeyError` garantido em qualquer torneio que traga o registro. A aceleração sai no
registro **250**, que o mesmo parser lê corretamente e que a PAR-02 já usa para
alimentar o motor.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.services.trf_layout import (
    CELL_COLOR,
    CELL_OPPONENT,
    CELL_RESULT,
    NAME,
    START_RANK,
    cell_blocks,
    field,
)

# Texto do registro 092 (tipo de torneio). O que havia era proprietário
# ("Individual: Suico (Standard)"); estes são os termos que Swiss-Manager e
# Chess-Results usam e reconhecem.
TOURNAMENT_TYPE_TEXTS: dict[str, str] = {
    "swiss": "Swiss-System",
    "round_robin": "Round Robin",
    "knockout": "Knock-Out",
    "scheveningen": "Scheveningen",
}

WHITE_FIRST = "white1"
BLACK_FIRST = "black1"


def record_xxr(rounds: int) -> str:
    """`XXR` — total de rodadas do torneio (dialeto TRF16)."""
    return f"XXR {int(rounds)}"


def record_xxe(event_id: Any) -> str:
    """`XXE` — FIDE Event-ID. `""` quando o torneio não tem.

    **Nenhum dos dois dialetos tem campo para o Event-ID**: nem o TRF16 nem o
    TRF25 reservam registro para ele, e a FIDE o pede no portal, fora do arquivo.
    Ele era exigido na validação do cadastro e não saía em lugar nenhum — quem
    recebe o arquivo não conseguia amarrá-lo ao evento.

    A saída é a família `XX*`, que é o espaço de extensão de facto (`XXR`, `XXC`,
    `XXZ`): quem não conhece o código ignora a linha — conferido contra o parser
    da implementação de referência, que só a registra como chave desconhecida.
    """
    identificador = str(event_id or "").strip()
    return f"XXE {identificador}" if identificador else ""


def record_xxc(initial_color: str) -> str:
    """`XXC` — cor do tabuleiro 1 na rodada 1 (`white1` ou `black1`)."""
    cor = str(initial_color or "").strip().lower()
    return f"XXC {cor if cor in (WHITE_FIRST, BLACK_FIRST) else WHITE_FIRST}"


def initial_color(first_round_pairings: Sequence[Mapping[str, Any]], start_ranks: Mapping[int, int]) -> str:
    """Cor do tabuleiro 1 na primeira rodada, lida do que foi pareado.

    Sem rodada gerada assume `white1`, que e o que o proprio motor faz quando
    monta a rodada 1 — declarar o contrario seria descrever um torneio diferente
    do que vai acontecer.
    """
    for pairing in first_round_pairings:
        if pairing.get("is_bye") or not pairing.get("black_player_id"):
            continue
        branca = start_ranks.get(int(pairing["white_player_id"]), 0)
        preta = start_ranks.get(int(pairing["black_player_id"]), 0)
        if branca and preta:
            return WHITE_FIRST if branca < preta else BLACK_FIRST
    return WHITE_FIRST


def tournament_type_text(competition_type: str, pairing_method: str, *, fide_rated: bool) -> str:
    """Texto do 092 no vocabulário que os programas da federação entendem."""
    sistema = TOURNAMENT_TYPE_TEXTS.get(str(pairing_method or "swiss"), TOURNAMENT_TYPE_TEXTS["swiss"])
    escopo = "Team" if str(competition_type) == "team" else "Individual"
    sufixo = " (FIDE-rated)" if fide_rated else ""
    return f"{escopo}: {sistema}{sufixo}"


def arbiter_text(name: str, fide_id: Any = "") -> str:
    """Árbitro nos registros 102/112, com o FIDE ID quando existe.

    O ID era validado no cadastro e nunca saía no arquivo — quem recebe a
    submissão precisa dele para identificar o árbitro.
    """
    limpo = str(name or "").strip()
    identificador = str(fide_id or "").strip()
    if limpo and identificador:
        return f"{limpo} ({identificador})"
    return limpo


def reciprocity_errors(lines: Sequence[str]) -> list[str]:
    """Confere que cada mesa aparece igual nas DUAS linhas 001 (FED-03).

    Se o jogador 5 diz "rodada 3, adversario 12, brancas", a linha do 12 tem de
    dizer "rodada 3, adversario 5, pretas". Uma divergencia aqui e arquivo
    corrompido — o validador da federacao recusa, e o arbitro descobre depois do
    envio. E a checagem que so se pode fazer sobre o ARQUIVO PRONTO.
    """
    celulas: dict[int, list[str]] = {}
    nomes: dict[int, str] = {}
    for line in lines:
        if not line.startswith("001"):
            continue
        rank = _int(field(line, START_RANK))
        if not rank:
            continue
        celulas[rank] = cell_blocks(line)
        nomes[rank] = field(line, NAME)

    erros: list[str] = []
    for rank, blocos in sorted(celulas.items()):
        for rodada, bloco in enumerate(blocos, start=1):
            adversario = _int(bloco[CELL_OPPONENT[0]:CELL_OPPONENT[1]])
            if not adversario:
                continue
            cor = bloco[CELL_COLOR:CELL_COLOR + 1].strip().lower()
            outro = celulas.get(adversario)
            if outro is None or len(outro) < rodada:
                erros.append(
                    f"Rodada {rodada}: {nomes.get(rank, rank)} aponta o adversario "
                    f"{adversario}, que nao tem essa rodada no arquivo."
                )
                continue
            bloco_oposto = outro[rodada - 1]
            volta = _int(bloco_oposto[CELL_OPPONENT[0]:CELL_OPPONENT[1]])
            cor_oposta = bloco_oposto[CELL_COLOR:CELL_COLOR + 1].strip().lower()
            if volta != rank:
                erros.append(
                    f"Rodada {rodada}: {nomes.get(rank, rank)} joga com {adversario}, "
                    f"mas {adversario} aponta {volta or 'ninguem'}."
                )
            elif cor and cor_oposta and cor == cor_oposta:
                erros.append(
                    f"Rodada {rodada}: {nomes.get(rank, rank)} e {adversario} estao "
                    f"os dois com '{cor}'."
                )
    return erros


def pending_result_cells(lines: Sequence[str]) -> list[str]:
    """Mesas pareadas que sairam SEM resultado (celula em branco)."""
    pendentes: list[str] = []
    for line in lines:
        if not line.startswith("001"):
            continue
        for rodada, bloco in enumerate(cell_blocks(line), start=1):
            if not _int(bloco[CELL_OPPONENT[0]:CELL_OPPONENT[1]]):
                continue
            resultado = bloco[CELL_RESULT:CELL_RESULT + 1].strip()
            if not resultado:
                pendentes.append(f"Rodada {rodada}: {field(line, NAME)} sem resultado.")
    return pendentes


def duplicate_fide_ids(players: Iterable[Mapping[str, Any]]) -> list[str]:
    """IDs FIDE repetidos — o mesmo jogador entrando duas vezes no arquivo."""
    vistos: dict[str, list[str]] = {}
    for player in players:
        fide_id = str(player.get("fide_id") or "").strip()
        if not fide_id:
            continue
        vistos.setdefault(fide_id, []).append(str(player.get("name") or "").strip())
    return [
        f"FIDE ID {fide_id} repetido em: {', '.join(nomes)}."
        for fide_id, nomes in sorted(vistos.items())
        if len(nomes) > 1
    ]


def submission_message(blockers: Sequence[str]) -> str:
    lista = "\n".join(f"- {item}" for item in blockers)
    return (
        "Modo submissao: o arquivo NAO foi gerado porque ha pendencia que a "
        "federacao recusaria.\n"
        f"{lista}\n"
        "Resolva as pendencias ou exporte no modo normal (que gera o arquivo com "
        "os avisos)."
    )


def _int(text: str) -> int:
    try:
        return int(str(text).strip() or 0)
    except ValueError:
        return 0
