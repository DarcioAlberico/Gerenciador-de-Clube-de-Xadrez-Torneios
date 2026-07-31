"""Registro DECLARATIVO dos critérios de desempate (spec §10, E1/E2).

Só declaração e validação: o que cada critério é, que parâmetros aceita e como
uma sequência salva vira estrutura confiável. Quem CALCULA vive noutro lugar —
`tiebreaks.py` (individual) e `team_tiebreaks.py` (equipes) —, e quem traduz
para a FIDE vive em `gacrux_tiebreak_map.py`. Três leitores, uma definição.

A ORDEM dos critérios é configurável por torneio (`tournament_settings.
tiebreak_sequence` e `team_tiebreak_sequence`). Sem sequência, valem os padrões
daqui, que reproduzem EXATAMENTE a classificação histórica.

`points`, `rating` e `name` são aplicados FORA da sequência do individual
(pontos sempre primeiro; rating/nome sempre por último), por isso não aparecem
no registro.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TiebreakParam:
    """Um parâmetro configurável de um critério (TBK-04).

    Declarado aqui, no registro, e não na tela: é a mesma razão do registro de
    critérios existir. A tela desenha o que o registro declara, o motor próprio
    lê ao calcular e o mapa do Gacrux traduz para modificador.

    ``choices`` vazio significa número inteiro entre ``minimum`` e ``maximum``;
    preenchido, é uma lista de ``(rótulo, valor)``.
    """

    key: str
    label: str
    default: Any
    choices: tuple[tuple[str, Any], ...] = ()
    minimum: int = 0
    maximum: int = 9

    def normalize(self, raw: Any) -> Any:
        """Valor cru (texto da tela, JSON do banco) → valor válido do parâmetro.

        Nunca levanta: parâmetro inválido volta ao padrão. Um desempate que
        recusa a configuração no meio do torneio seria pior que um que ignora
        um número datilografado errado — e a tela valida antes, de qualquer forma.
        """
        if self.choices:
            validos = {valor for _rotulo, valor in self.choices}
            return raw if raw in validos else self.default
        try:
            numero = int(raw)
        except (TypeError, ValueError):
            return self.default
        return min(max(numero, self.minimum), self.maximum)


_UNPLAYED_CHOICES = (
    ("Jogos disputados (FIDE)", "real"),
    ("Contar não disputados como próprios pontos", "self"),
)


@dataclass(frozen=True)
class TiebreakCriterion:
    """Um critério de desempate: rótulo, fórmula curta, parâmetros e sentido.

    ``higher_is_better=False`` existe por causa do board count (TBK-05), o único
    critério em que o número MENOR classifica melhor. Fica no registro, e não
    numa lista de exceções na hora de ordenar, porque é uma propriedade do
    critério — quem ordena pergunta, em vez de saber de cor.
    """

    code: str
    label: str
    formula: str
    params: tuple[TiebreakParam, ...] = ()
    higher_is_better: bool = True


PLAYER_TIEBREAKS: dict[str, TiebreakCriterion] = {
    "buchholz": TiebreakCriterion(
        "buchholz", "Buchholz", "Soma dos pontos finais dos adversários enfrentados."
    ),
    "buchholz_cut1": TiebreakCriterion(
        "buchholz_cut1",
        "Buchholz Cut-1",
        "Buchholz descartando o adversário de menor pontuação.",
        params=(
            TiebreakParam("cut_low", "Descartar piores", 1, maximum=5),
            TiebreakParam("cut_high", "Descartar melhores", 0, maximum=5),
            TiebreakParam("unplayed", "Jogos não disputados", "real", choices=_UNPLAYED_CHOICES),
        ),
    ),
    "buchholz_cut2": TiebreakCriterion(
        "buchholz_cut2",
        "Buchholz Cut-2",
        "Buchholz descartando os dois adversários de menor pontuação.",
        params=(
            TiebreakParam("cut_low", "Descartar piores", 2, maximum=5),
            TiebreakParam("cut_high", "Descartar melhores", 0, maximum=5),
            TiebreakParam("unplayed", "Jogos não disputados", "real", choices=_UNPLAYED_CHOICES),
        ),
    ),
    "buchholz_median": TiebreakCriterion(
        "buchholz_median",
        "Buchholz mediano",
        "Buchholz descartando o maior e o menor adversário (3+ jogos).",
    ),
    "sonneborn_berger": TiebreakCriterion(
        "sonneborn_berger",
        "Sonneborn-Berger",
        "Pontos do adversário multiplicados pelo resultado obtido contra ele.",
    ),
    "direct_encounter": TiebreakCriterion(
        "direct_encounter",
        "Confronto direto",
        "Pontos marcados contra adversários empatados em pontos.",
    ),
    "wins": TiebreakCriterion(
        "wins", "Vitórias", "Número de partidas vencidas no tabuleiro."
    ),
    "cumulative": TiebreakCriterion(
        "cumulative",
        "Progressivo",
        "Soma das pontuações acumuladas após cada rodada.",
    ),
    "cumulative_opp": TiebreakCriterion(
        "cumulative_opp",
        "Progressivo dos adversários",
        "Soma do progressivo de todos os adversários enfrentados.",
    ),
    "koya": TiebreakCriterion(
        "koya",
        "Sistema Koya",
        "Pontos obtidos contra adversários com ao menos 50% dos pontos.",
        params=(
            TiebreakParam("threshold", "Limiar (% dos pontos)", 50, minimum=1, maximum=99),
        ),
    ),
    "aro": TiebreakCriterion(
        "aro",
        "Rating médio dos adversários",
        "Média de rating dos adversários ranqueados.",
    ),
    "aroc": TiebreakCriterion(
        "aroc",
        "Rating médio (cortado)",
        "Média de rating dos adversários descartando os extremos.",
        params=(TiebreakParam("cut", "Descartar de cada ponta", 1, minimum=1, maximum=5),),
    ),
    "performance": TiebreakCriterion(
        "performance", "Performance", "Rating performance estimado no torneio."
    ),
    "black_games": TiebreakCriterion(
        "black_games", "Partidas com pretas", "Número de partidas jogadas com as pretas."
    ),
    "black_wins": TiebreakCriterion(
        "black_wins", "Vitórias com pretas", "Número de vitórias jogando de pretas."
    ),
    "games_played": TiebreakCriterion(
        "games_played", "Partidas jogadas", "Número de partidas disputadas no tabuleiro."
    ),
}

DEFAULT_PLAYER_TIEBREAKS: list[str] = [
    "buchholz",
    "buchholz_median",
    "sonneborn_berger",
    "wins",
]

# Critérios de EQUIPES (TBK-05).
#
# Os quatro primeiros são os históricos; os quatro seguintes são os desempates
# que qualquer regulamento olímpico/CBX por equipes pede e que faltavam — sem
# eles, um campeonato com regulamento FIDE não era representável no sistema.
TEAM_TIEBREAKS: dict[str, TiebreakCriterion] = {
    "match_points": TiebreakCriterion(
        "match_points", "Match points", "Pontos de confronto da equipe (vitória/empate/derrota)."
    ),
    "game_points": TiebreakCriterion(
        "game_points", "Game points", "Soma dos pontos de tabuleiro da equipe."
    ),
    "buchholz": TiebreakCriterion(
        "buchholz", "Buchholz (equipes)", "Soma dos match points dos adversários da equipe."
    ),
    "wins": TiebreakCriterion(
        "wins", "Vitórias (equipes)", "Número de confrontos vencidos pela equipe."
    ),
    "sonneborn_berger": TiebreakCriterion(
        "sonneborn_berger",
        "Sonneborn-Berger olímpico",
        "Match points do adversário multiplicados pelos game points feitos contra ele.",
        params=(TiebreakParam("cut_low", "Descartar piores", 0, maximum=5),),
    ),
    "direct_encounter": TiebreakCriterion(
        "direct_encounter",
        "Confronto direto (equipes)",
        "Match points obtidos contra as equipes empatadas.",
    ),
    "buchholz_game_points": TiebreakCriterion(
        "buchholz_game_points",
        "Buchholz de game points",
        "Soma dos game points dos adversários enfrentados.",
    ),
    "board_count": TiebreakCriterion(
        "board_count",
        "Board count (Berlin)",
        "Soma do número do tabuleiro vezes os pontos nele obtidos; MENOR é melhor.",
        higher_is_better=False,
    ),
}

DEFAULT_TEAM_TIEBREAKS: list[str] = ["match_points", "game_points", "buchholz", "wins"]


# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------


def criterion_params(
    code: str,
    registry: dict[str, TiebreakCriterion] | None = None,
) -> tuple[TiebreakParam, ...]:
    """Parâmetros declarados de um critério. Vazio se não há.

    ``registry`` é explícito porque os dois registros COMPARTILHAM códigos com
    significados diferentes: `sonneborn_berger` de equipes aceita corte e o
    individual não, `buchholz` de equipes soma match points. Adivinhar o
    registro daria os parâmetros do critério errado (TBK-05).
    """
    criterio = (PLAYER_TIEBREAKS if registry is None else registry).get(code)
    return criterio.params if criterio is not None else ()


def normalize_criterion_params(
    code: str,
    raw: Any,
    registry: dict[str, TiebreakCriterion] | None = None,
) -> dict[str, Any]:
    """Parâmetros crus → só os declarados, já validados e completos (TBK-04).

    Sempre devolve **todos** os parâmetros do critério, inclusive os que não
    vieram: quem lê não precisa repetir o padrão em cada ponto de uso, e o JSON
    salvo passa a descrever a configuração inteira. Chave desconhecida é
    descartada — é como uma sequência antiga sobrevive a um critério que perdeu
    um parâmetro.
    """
    entrada = dict(raw) if isinstance(raw, dict) else {}
    return {
        param.key: param.normalize(entrada.get(param.key, param.default))
        for param in criterion_params(code, registry)
    }


def criterion_param(
    code: str,
    params: dict[str, Any],
    key: str,
    registry: dict[str, TiebreakCriterion] | None = None,
) -> Any:
    """Valor validado de um parâmetro, com o padrão do registro como piso."""
    for param in criterion_params(code, registry):
        if param.key == key:
            return param.normalize((params or {}).get(key, param.default))
    return None


def higher_is_better(
    code: str,
    registry: dict[str, TiebreakCriterion] | None = None,
) -> bool:
    """Sentido do critério. Desconhecido = maior é melhor (o caso comum)."""
    criterio = (PLAYER_TIEBREAKS if registry is None else registry).get(code)
    return criterio.higher_is_better if criterio is not None else True


# ---------------------------------------------------------------------------
# Sequências (banco/UI <-> estrutura)
# ---------------------------------------------------------------------------


def dedup_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _parse_tiebreak_sequence(
    raw: Any,
    registry: dict[str, TiebreakCriterion],
    drop: set[str],
) -> list[dict[str, Any]]:
    """Normaliza uma sequência de desempates vinda do banco/UI.

    Aceita string JSON ou lista; cada item pode ser um código (str) ou um dict
    {"code", "params"}. Descarta códigos desconhecidos, duplicados e os de
    `drop`. Sequência inválida/vazia retorna [] (= usar o padrão).
    """
    if not raw:
        return []
    items: Any = raw
    if isinstance(raw, str):
        try:
            items = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in items:
        if isinstance(entry, str):
            code, params = entry.strip(), {}
        elif isinstance(entry, dict):
            code = str(entry.get("code") or "").strip()
            raw_params = entry.get("params")
            params = dict(raw_params) if isinstance(raw_params, dict) else {}
        else:
            continue
        if code in drop or code not in registry or code in seen:
            continue
        seen.add(code)
        # Normaliza na porta de entrada (TBK-04): o que estiver salvo no banco
        # passa a chegar completo e validado a quem calcula, e um parametro que
        # o critério perdeu numa versão nova some aqui, sem quebrar a sequência.
        result.append({"code": code, "params": normalize_criterion_params(code, params, registry)})
    return result


def parse_player_tiebreak_sequence(raw: Any) -> list[dict[str, Any]]:
    return _parse_tiebreak_sequence(raw, PLAYER_TIEBREAKS, drop={"points"})


def parse_team_tiebreak_sequence(raw: Any) -> list[dict[str, Any]]:
    return _parse_tiebreak_sequence(raw, TEAM_TIEBREAKS, drop=set())


def serialize_tiebreak_sequence(sequence: list[dict[str, Any]]) -> str:
    return json.dumps(
        [{"code": item["code"], "params": item.get("params", {})} for item in sequence],
        ensure_ascii=False,
    )
