"""Ritmo de jogo: leitura do texto e classificação FIDE (puro).

O ritmo é digitado como texto no cadastro do torneio, na gramática que o
construtor de ritmo gera: ``"10 min"``, ``"15 min + 10 s"``,
``"90 min / 40 lances + 30 min"`` e a combinação com incremento. Duas partes do
sistema precisam entender esse texto — o registro 222 do TRF25 e a
classificação standard/rapid/blitz do relatório de rating — e é por isso que a
leitura mora **aqui**, num módulo só: dois interpretadores acabariam
discordando, e o arquivo da federação diria um ritmo enquanto o relatório
calcularia por outro.

Classificação (Leis do Xadrez / B.02): conta-se o tempo total mais 60 vezes o
incremento, ou seja, o tempo de uma partida de 60 lances.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STANDARD = "standard"
RAPID = "rapid"
BLITZ = "blitz"

SPEED_LABELS = {
    STANDARD: "Standard (clássico)",
    RAPID: "Rápido",
    BLITZ: "Blitz",
}

# Lances de referência da fórmula FIDE ("tempo + 60 vezes o incremento").
REFERENCE_MOVES = 60

# Fronteiras em segundos: >= 60 min é standard, > 10 min é rápido, o resto é
# blitz. Abaixo de 3 minutos a FIDE não rata nem como blitz.
STANDARD_FLOOR_SECONDS = 60 * 60
RAPID_FLOOR_SECONDS = 10 * 60
BLITZ_FLOOR_SECONDS = 3 * 60

# B.02 — tempo mínimo para a partida valer rating STANDARD, pelo rating do
# jogador mais forte da mesa.
STANDARD_MINIMUM_SECONDS = ((2400, 120 * 60), (1800, 90 * 60), (0, 60 * 60))


@dataclass(frozen=True)
class TimePeriod:
    """Um período do ritmo. `moves = 0` significa "até o fim da partida"."""

    moves: int
    seconds: int
    increment: int


_INCREMENT = re.compile(r"\+\s*(\d+)\s*(?:s|seg|segundos?)\b")
_MULTI = re.compile(r"(\d+)\s*min\s*/\s*(\d+)\s*lances\s*\+\s*(\d+)\s*min")
_SINGLE = re.compile(r"(\d+)\s*min")

# Grafia internacional (ORG-03): `90'+30"` é como o edital e o cartaz escrevem,
# e o programa não a reconhecia — o TRF25 omitia o registro 222 e o relatório de
# rating não sabia classificar o evento. A conversão para a gramática interna é
# textual de propósito: um interpretador só continua sendo um só.
_MINUTES_MARK = re.compile(r"(\d+)\s*(?:'|’|min\b)")
_SECONDS_MARK = re.compile(r"(\d+)\s*(?:\"|”|''|s\b)")
# `40/90` = 40 lances em 90 minutos (forma compacta da FIDE).
_COMPACT_MOVES = re.compile(r"^(\d+)\s*/\s*(\d+)(?![\d/])")
# `90+30` sem marca nenhuma: convenção universal de minutos + incremento.
_BARE_PAIR = re.compile(r"^(\d+)\s*\+\s*(\d+)$")


def normalized_text(value: object) -> str:
    """Traduz as grafias comuns para a gramática interna (`min`/`s`/`lances`).

    Aceita `90'+30"`, `90+30`, `40/90+30` e o que o construtor de ritmo gera.
    """
    text = str(value or "").strip().lower().replace("segundos", "s").replace("minutos", "min")
    if not text:
        return ""

    compacto = _COMPACT_MOVES.match(text)
    if compacto:
        lances, minutos = compacto.group(1), compacto.group(2)
        resto = text[compacto.end() :].strip()
        # `40/90+30` -> 40 lances em 90 min, e o que sobra e o 2o periodo/incremento.
        # Depois de `40/90`, um `+30` SEM marca e o 2o periodo em MINUTOS
        # ("40 lances em 90 min, depois 30 min"), que e a leitura corrente da
        # notacao da FIDE. So `+30"` e incremento. A distincao importa: como
        # incremento o mesmo texto daria 210 minutos em vez de 120.
        segundo = ""
        incremento = ""
        sobra = resto.lstrip("+ ").strip()
        if sobra:
            marca_seg = _SECONDS_MARK.fullmatch(sobra)
            if marca_seg:
                incremento = f" + {marca_seg.group(1)} s"
            else:
                numeros = re.findall(r"\d+", sobra)
                if numeros:
                    segundo = f" + {numeros[0]} min"
        if not segundo:
            # Sem 2o periodo declarado, o resto do jogo corre no mesmo tempo.
            segundo = f" + {minutos} min"
        return f"{minutos} min / {lances} lances{segundo}{incremento}"

    simples = _BARE_PAIR.match(text)
    if simples:
        return f"{simples.group(1)} min + {simples.group(2)} s"

    text = _SECONDS_MARK.sub(r"\1 s", text)
    text = _MINUTES_MARK.sub(r"\1 min", text)
    return text


def parse_time_control(value: object) -> list[TimePeriod]:
    """Períodos do ritmo, ou lista vazia quando o texto não é reconhecido.

    Vazio é resposta legítima: o campo é livre e o árbitro pode ter escrito
    qualquer coisa. Quem chama decide o que fazer com a dúvida — o TRF omite o
    registro e o relatório pede que o ritmo seja declarado.
    """
    text = normalized_text(value)
    if not text:
        return []

    increment = 0
    found = _INCREMENT.search(text)
    if found:
        increment = int(found.group(1))
        text = (text[: found.start()] + text[found.end() :]).strip(" +")

    multi = _MULTI.fullmatch(text)
    if multi:
        return [
            TimePeriod(int(multi.group(2)), int(multi.group(1)) * 60, increment),
            TimePeriod(0, int(multi.group(3)) * 60, increment),
        ]

    single = _SINGLE.fullmatch(text)
    if single:
        return [TimePeriod(0, int(single.group(1)) * 60, increment)]

    return []


def total_seconds(periods: list[TimePeriod], moves: int = REFERENCE_MOVES) -> int:
    """Tempo de uma partida de `moves` lances: soma dos períodos + incremento."""
    if not periods:
        return 0
    base = sum(period.seconds for period in periods)
    increment = max((period.increment for period in periods), default=0)
    return base + increment * int(moves)


def classify_speed(value: object) -> str:
    """Ritmo declarado -> `standard`/`rapid`/`blitz`; `""` quando não dá para dizer."""
    periods = parse_time_control(value)
    if not periods:
        return ""
    return speed_for_seconds(total_seconds(periods))


def speed_for_seconds(seconds: int) -> str:
    if seconds >= STANDARD_FLOOR_SECONDS:
        return STANDARD
    if seconds > RAPID_FLOOR_SECONDS:
        return RAPID
    return BLITZ


def below_blitz_minimum(value: object) -> bool:
    """Ritmo mais rápido do que a FIDE rata (3 minutos, incremento incluso)."""
    periods = parse_time_control(value)
    return bool(periods) and total_seconds(periods) <= BLITZ_FLOOR_SECONDS


def standard_minimum_seconds(highest_rating: int) -> int:
    """B.02 — tempo mínimo para rating standard, pelo maior rating da mesa."""
    for floor, required in STANDARD_MINIMUM_SECONDS:
        if int(highest_rating or 0) >= floor:
            return required
    return STANDARD_MINIMUM_SECONDS[-1][1]


def trf25_descriptor(value: object) -> str | None:
    """Ritmo na gramática do registro 222 do TRF25.

    Um *Time Period Descriptor* é `M/S` (lances/segundos), `S` (só segundos) ou
    `S+I` (com incremento por lance); períodos múltiplos juntam-se com `:`.
    Devolve `None` quando o texto não foi reconhecido — assim o exporter omite o
    222 em vez de emitir um ritmo enganoso ao árbitro.
    """
    periods = parse_time_control(value)
    if not periods:
        return None
    partes = []
    for period in periods:
        sufixo = f"+{period.increment}" if period.increment else ""
        prefixo = f"{period.moves}/" if period.moves else ""
        partes.append(f"{prefixo}{period.seconds}{sufixo}")
    return ":".join(partes)
