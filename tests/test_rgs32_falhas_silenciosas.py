"""RGS-32: nenhum ``except`` engole erro em silêncio sem dizer por quê.

Havia ~67 ``except Exception: pass`` em ``src/``. Cada um virou
``logger.debug(..., exc_info=True)`` ou ficou com o ``pass`` e um comentário
que justifica o silêncio (widget já destruído, limpeza no encerramento...).

Este teste impede o próximo: um ``except`` cujo corpo é só ``pass`` precisa de
um comentário ``# ...`` na linha do ``except``, na do ``pass`` ou entre as
duas. ``src/services/pairing/gacrux/`` é código vendorizado e fica de fora.
"""
from __future__ import annotations

import ast
import io
import tokenize
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
VENDORIZADO = SRC / "services" / "pairing" / "gacrux"


def _linhas_com_comentario(fonte: str) -> set[int]:
    linhas: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(fonte).readline):
        if token.type == tokenize.COMMENT and token.string.strip("# \t"):
            linhas.add(token.start[0])
    return linhas


def _so_pass(corpo: list[ast.stmt]) -> bool:
    return len(corpo) == 1 and isinstance(corpo[0], ast.Pass)


def silencios_sem_justificativa(fonte: str, nome: str) -> list[str]:
    """``nome:linha`` de cada ``except: pass`` sem comentário adjacente."""
    comentarios = _linhas_com_comentario(fonte)
    achados: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.ExceptHandler) or not _so_pass(no.body):
            continue
        faixa = range(no.lineno, no.body[0].lineno + 1)
        if not comentarios.intersection(faixa):
            achados.append(f"{nome}:{no.lineno}")
    return achados


def _arquivos() -> list[Path]:
    return [p for p in sorted(SRC.rglob("*.py")) if VENDORIZADO not in p.parents]


class SemFalhaSilenciosaTest(unittest.TestCase):
    def test_src_nao_tem_except_pass_sem_justificativa(self) -> None:
        achados: list[str] = []
        for arquivo in _arquivos():
            nome = arquivo.relative_to(RAIZ).as_posix()
            achados.extend(silencios_sem_justificativa(arquivo.read_text(encoding="utf-8"), nome))
        self.assertEqual([], achados, f"{len(achados)} except: pass sem justificativa:\n" + "\n".join(achados))

    def test_varre_src_e_pula_o_vendorizado(self) -> None:
        arquivos = _arquivos()
        self.assertGreater(len(arquivos), 100)
        self.assertFalse([p for p in arquivos if "gacrux" in p.parent.name])


class RegraTest(unittest.TestCase):
    def _achados(self, fonte: str) -> list[str]:
        return silencios_sem_justificativa(fonte, "x.py")

    def test_pass_sem_comentario_reprova(self) -> None:
        self.assertEqual(["x.py:3"], self._achados("try:\n    f()\nexcept Exception:\n    pass\n"))

    def test_except_nu_numa_linha_reprova(self) -> None:
        self.assertEqual(["x.py:3"], self._achados("try:\n    f()\nexcept: pass\n"))

    def test_comentario_na_linha_do_except_passa(self) -> None:
        self.assertEqual([], self._achados("try:\n    f()\nexcept OSError:  # arquivo some no shutdown\n    pass\n"))

    def test_comentario_na_linha_do_pass_passa(self) -> None:
        self.assertEqual([], self._achados("try:\n    f()\nexcept OSError:\n    pass  # ja destruido\n"))

    def test_comentario_acima_do_pass_passa(self) -> None:
        self.assertEqual([], self._achados("try:\n    f()\nexcept OSError:\n    # ja destruido\n    pass\n"))

    def test_comentario_vazio_nao_justifica(self) -> None:
        self.assertEqual(["x.py:3"], self._achados("try:\n    f()\nexcept OSError:\n    pass  #\n"))

    def test_comentario_longe_nao_justifica(self) -> None:
        fonte = "# comentario solto\ntry:\n    f()\nexcept OSError:\n    pass\n"
        self.assertEqual(["x.py:4"], self._achados(fonte))

    def test_corpo_com_log_passa(self) -> None:
        fonte = "try:\n    f()\nexcept OSError:\n    logger.debug('x', exc_info=True)\n"
        self.assertEqual([], self._achados(fonte))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
