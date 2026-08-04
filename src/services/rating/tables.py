"""Tabelas do sistema Elo da FIDE — só matemática, sem regulamento.

Expectativa (p a partir da diferença de rating), a tabela inversa p -> dp e a
performance. São as mesmas em qualquer ritmo e em qualquer federação que copie
o Elo; o que muda de um regulamento para outro é K, piso e regra de estreia, e
isso mora em `regulation`.
"""

from __future__ import annotations

MAX_RATING_DIFF = 400

# Tabela FIDE de expectativa (jogador de MAIOR rating), por faixa de diferença
# de rating. Pares (limite_superior_inclusivo, p_do_maior). Diferenças são
# limitadas a 400 (regra dos 400), então a tabela termina em 0.92.
_EXPECTANCY: list[tuple[int, float]] = [
    (3, 0.50), (10, 0.51), (17, 0.52), (25, 0.53), (32, 0.54), (39, 0.55),
    (46, 0.56), (53, 0.57), (61, 0.58), (68, 0.59), (76, 0.60), (83, 0.61),
    (91, 0.62), (98, 0.63), (106, 0.64), (113, 0.65), (121, 0.66), (129, 0.67),
    (137, 0.68), (145, 0.69), (153, 0.70), (162, 0.71), (170, 0.72), (179, 0.73),
    (188, 0.74), (197, 0.75), (206, 0.76), (215, 0.77), (225, 0.78), (235, 0.79),
    (245, 0.80), (256, 0.81), (267, 0.82), (278, 0.83), (290, 0.84), (302, 0.85),
    (315, 0.86), (328, 0.87), (344, 0.88), (357, 0.89), (374, 0.90), (391, 0.91),
    (400, 0.92),
]

# Tabela FIDE p -> dp (percentual de pontos -> diferença de rating) para a
# performance. Definida para p em [0.50, 1.00]; abaixo de 0.50 usa simetria.
_DP: dict[int, int] = {
    100: 800, 99: 677, 98: 589, 97: 538, 96: 501, 95: 470, 94: 444, 93: 422,
    92: 401, 91: 383, 90: 366, 89: 351, 88: 336, 87: 322, 86: 309, 85: 296,
    84: 284, 83: 273, 82: 262, 81: 251, 80: 240, 79: 230, 78: 220, 77: 211,
    76: 202, 75: 193, 74: 184, 73: 175, 72: 166, 71: 158, 70: 149, 69: 141,
    68: 133, 67: 125, 66: 117, 65: 110, 64: 102, 63: 95, 62: 87, 61: 80,
    60: 72, 59: 65, 58: 57, 57: 50, 56: 43, 55: 36, 54: 29, 53: 21, 52: 14,
    51: 7, 50: 0,
}


def fide_expected_score(rating: int, opponent_rating: int) -> float:
    """Pontuação esperada de `rating` contra `opponent_rating` (regra dos 400)."""
    diff = int(rating) - int(opponent_rating)
    capped = max(-MAX_RATING_DIFF, min(MAX_RATING_DIFF, diff))
    magnitude = abs(capped)
    probability = 0.92
    for upper, p_high in _EXPECTANCY:
        if magnitude <= upper:
            probability = p_high
            break
    return probability if capped >= 0 else round(1.0 - probability, 2)


def fide_dp(score_percent: float) -> int:
    """Diferença de rating correspondente a um percentual de pontos (p -> dp)."""
    pct = max(0.0, min(1.0, float(score_percent)))
    key = int(round(pct * 100))
    if key >= 50:
        return _DP[key]
    return -_DP[100 - key]


def fide_performance(average_opponent_rating: float, score: float, games: int) -> int:
    """Rating performance (Rp) = média dos adversários + dp(percentual)."""
    if games <= 0:
        return 0
    return int(round(float(average_opponent_rating) + fide_dp(float(score) / games)))
