"""Mapeamento PURO entre os desempates do Albericus e o motor FIDE Gacrux.

Traduz os códigos de critério do Albericus para os especificadores aceitos pelo
`tiebreakchecker.py` (flag ``-t``) e faz o parse de ``tiebreakResult`` de volta
para valores por competidor. Não há I/O aqui — o subprocesso vive em
``gacrux_tiebreak_engine.py``; este módulo é 100% testável sem o motor.

Referência da sintaxe e dos códigos: skill ``/gacrux`` e
``src/services/pairing/gacrux/tiebreak.py`` (tabela ``tiebreaklist``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Código de critério do Albericus -> especificador do Gacrux (``-t``).
#
# O adversário virtual (Buchholz/SB) e o teste FIDE do confronto direto são o
# comportamento PADRÃO do Gacrux (regras @24/@26); por isso BH/SB/DE não levam
# modificadores. ``performance`` -> TPR usa a tabela ``dp`` oficial.
ALBERICUS_TO_GACRUX: dict[str, str] = {
    "buchholz": "BH",
    "buchholz_cut1": "BH/C1",
    "buchholz_cut2": "BH/C2",
    "buchholz_median": "BH/M1",
    "sonneborn_berger": "SB",
    "direct_encounter": "DE",
    "wins": "WON",
    "cumulative": "PS",
    "koya": "KS",
    "aro": "ARO",
    "aroc": "ARO/M1",
    "performance": "TPR",
    "black_games": "BPG",
    "black_wins": "BWG",
    "games_played": "NUM",
}

# Critérios do Albericus sem equivalente direto no Gacrux: continuam no motor
# próprio (não entram no plano enviado ao ``tiebreakchecker``).
UNSUPPORTED_BY_GACRUX: frozenset[str] = frozenset({"cumulative_opp"})

# Pontos são sempre a 1ª coluna do ``tiebreakScore`` (critério primário).
POINTS_SPEC = "PTS"
POINTS_CODE = "points"


@dataclass(frozen=True)
class TiebreakPlan:
    """Plano de execução do ``tiebreakchecker``.

    ``specifiers`` é a lista passada a ``-t`` (sempre inicia com ``PTS``).
    ``code_order`` é o código do Albericus de cada coluna do ``tiebreakScore``,
    paralela a ``specifiers`` (a 1ª é :data:`POINTS_CODE`). ``skipped`` lista os
    códigos da sequência sem equivalente Gacrux (apenas informativo).
    """

    specifiers: tuple[str, ...]
    code_order: tuple[str, ...]
    skipped: tuple[str, ...] = ()


def build_tiebreak_plan(codes: list[str]) -> TiebreakPlan:
    """Monta o :class:`TiebreakPlan` a partir da sequência de códigos do Albericus.

    Sempre começa por ``PTS``. Ignora ``points`` (primário, já incluído),
    duplicados e códigos sem equivalente Gacrux (vão para ``skipped``). A ordem
    define tanto a ordem de desempate quanto a correspondência das colunas do
    ``tiebreakScore``.
    """
    specifiers: list[str] = [POINTS_SPEC]
    code_order: list[str] = [POINTS_CODE]
    skipped: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = str(raw or "").strip()
        if not code or code == POINTS_CODE or code in seen:
            continue
        spec = ALBERICUS_TO_GACRUX.get(code)
        if spec is None:
            skipped.append(code)
            continue
        seen.add(code)
        specifiers.append(spec)
        code_order.append(code)
    return TiebreakPlan(tuple(specifiers), tuple(code_order), tuple(skipped))


def parse_competitors(
    competitors: list[dict[str, Any]],
    plan: TiebreakPlan,
) -> dict[int, dict[str, Any]]:
    """``tiebreakResult.competitors[]`` -> ``{cid: {"rank", "scores"}}``.

    ``scores`` mapeia código do Albericus -> valor, na ordem de
    ``plan.code_order``. Colunas faltantes (saída mais curta que o esperado) são
    ignoradas defensivamente; ``cid`` é o SNo do TRF (1-based).
    """
    result: dict[int, dict[str, Any]] = {}
    for competitor in competitors:
        try:
            cid = int(competitor.get("cid"))
        except (TypeError, ValueError):
            continue
        raw_scores = competitor.get("tiebreakScore") or []
        scores: dict[str, float] = {}
        for index, code in enumerate(plan.code_order):
            if index < len(raw_scores):
                scores[code] = _as_float(raw_scores[index])
        result[cid] = {
            "rank": int(competitor.get("rank") or 0),
            "scores": scores,
        }
    return result


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
