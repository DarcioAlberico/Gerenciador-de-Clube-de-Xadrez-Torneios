"""Varredura da fronteira numérica (F1.1: RG2-46, RG2-14, RG2-27, RG2-10).

A leitura de número digitado mora em ``src/domain/numbers.py``. Aqui se reprova
a volta dos dois idiomas que erravam:

- ``float(str(x).replace(",", "."))`` em ``src/services`` — lê "1.500" como 1,5;
- ``.get("…points…") or <número ≠ 0>`` em ``src`` — lê o 0 gravado como ausente.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SERVICOS = RAIZ / "src" / "services"
FONTES = RAIZ / "src"
# Motor FIDE vendorizado: não é nosso, e não lê número digitado pelo usuário.
VENDORIZADO = SERVICOS / "pairing" / "gacrux"

VIRGULA_POR_PONTO = re.compile(r"""float\(\s*str\(.*\)\s*\.replace\(\s*["'],["']\s*,\s*["']\.["']\s*\)""")
PONTOS_OR_NUMERO = re.compile(
    r"""(?:\.get\(\s*|\[\s*)["'][^"']*points[^"']*["'][^)\]]*[)\]]\s*or\s+(?!0(?:\.0+)?\b)\d"""
)


def _achados(raiz: Path, padrao: re.Pattern[str]) -> list[str]:
    achados = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if VENDORIZADO in arquivo.parents:
            continue
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            if padrao.search(linha):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()}")
    return achados


class FronteiraNumericaVarreduraTest(unittest.TestCase):
    def test_servicos_nao_trocam_virgula_por_ponto_na_mao(self) -> None:
        self.assertEqual(
            [], _achados(SERVICOS, VIRGULA_POR_PONTO),
            "use parse_decimal_br / parse_decimal / parse_points (src/domain/numbers.py)",
        )

    def test_pontos_nao_usam_or_numero(self) -> None:
        self.assertEqual(
            [], _achados(FONTES, PONTOS_OR_NUMERO),
            "use setting_number(row, chave, padrão): o 0 gravado é 0",
        )

    def test_a_varredura_pega_os_idiomas_antigos(self) -> None:
        for linha in (
            'float(str(data.get("bye_points") or "0").replace(",", "."))',
            "float(str(value).replace(',', '.'))",
        ):
            with self.subTest(linha=linha):
                self.assertTrue(VIRGULA_POR_PONTO.search(linha))
        for linha in (
            'float(tournament.get("bye_points") or 1.0)',
            'float(settings.get("team_match_draw_points", 1.0) or 1.0)',
            'float(row["team_match_win_points"] or 2)',
        ):
            with self.subTest(linha=linha):
                self.assertTrue(PONTOS_OR_NUMERO.search(linha))
        for linha in (
            'float(data.get("late_entry_points", 0.0) or 0.0)',
            'float(player.get("starting_points") or 0)',
        ):
            with self.subTest(linha=linha):
                self.assertFalse(PONTOS_OR_NUMERO.search(linha))


if __name__ == "__main__":
    unittest.main()
