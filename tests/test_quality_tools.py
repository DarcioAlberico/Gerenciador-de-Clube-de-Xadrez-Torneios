"""As ferramentas do ub-mode (scripts/crap.py e scripts/dry.py) medem o que dizem."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import crap  # noqa: E402
import dry  # noqa: E402
import mutate  # noqa: E402


class CrapTest(unittest.TestCase):
    def test_formula(self) -> None:
        self.assertEqual(1, crap.crap(1, 1.0))
        self.assertEqual(30, crap.crap(5, 0.0))
        self.assertAlmostEqual(10 + 100 * 0.125, crap.crap(10, 0.5))

    def test_indice_por_funcao_usa_as_linhas_executadas(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "alvo.py"
            arquivo.write_text(
                "def simples():\n    return 1\n\n"
                "def ramos(x):\n    if x:\n        return 1\n    elif x is None:\n        return 2\n    return 3\n",
                encoding="utf-8",
            )
            dados = {"files": {str(arquivo): {"executed_lines": [1, 2, 4, 5, 6], "missing_lines": [7, 8, 9]}}}
            por_nome = {i.funcao: i for i in crap.indices(dados, arquivo)}
        self.assertEqual(1.0, por_nome["simples"].crap)
        self.assertEqual(3, por_nome["ramos"].complexidade)
        self.assertAlmostEqual(0.5, por_nome["ramos"].cobertura)
        json.dumps([i.crap for i in por_nome.values()])


class DryTest(unittest.TestCase):
    CORPO = "    total = 0\n    for item in itens:\n        if item.ativo:\n            total += item.valor * 2\n    return total\n"

    def test_copia_com_outros_nomes_da_nota_um(self) -> None:
        a = dry.normalizar(self.CORPO)
        b = dry.normalizar(self.CORPO.replace("total", "soma").replace("item", "x"))
        self.assertEqual(1.0, dry.semelhanca(a, b))

    def test_formas_diferentes_ficam_abaixo_do_limite(self) -> None:
        a = dry.normalizar(self.CORPO)
        b = dry.normalizar("    return {k: v for k, v in dados.items() if v}\n")
        self.assertLess(dry.semelhanca(a, b), 0.8)


class MutateTest(unittest.TestCase):
    FONTE = 'def f(x):\n    """Doc 1."""\n    if x > 0 and not x == 5:\n        return 1\n    return "texto"\n'

    def test_cada_mutante_muda_uma_coisa(self) -> None:
        lista = mutate.mutantes(self.FONTE)
        descricoes = {m.descricao for m in lista}
        self.assertTrue({"Gt -> GtE", "And -> Or", "tira o not", "Eq -> NotEq", "0 -> 1", "return None"} <= descricoes)
        self.assertIn("inverte a condição", descricoes)
        self.assertTrue(all("Doc 1." in m.fonte for m in lista))  # docstring não é mutada
        self.assertTrue(all(m.fonte != self.FONTE for m in lista))

    def test_filtro_por_funcao(self) -> None:
        fonte = self.FONTE + "\ndef g():\n    return 2\n"
        self.assertEqual(["return None", "2 -> 3"], sorted(m.descricao for m in mutate.mutantes(fonte, ["g"]))[::-1])


if __name__ == "__main__":
    unittest.main()
