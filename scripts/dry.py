"""Dryer: pares de funções parecidas demais (duplicação), com nota de 0 a 1.

Cada função vira uma sequência de tokens normalizada — nome vira ``N``, texto
vira ``S``, número vira ``0``; palavra-chave e operador ficam —, e o par recebe
a razão de semelhança do ``difflib``. Nota 1,0 é cópia com outros nomes; o
alvo do ub-mode é eliminar o que der 0,8 ou mais.

Uso:
    uv run --extra dev python scripts/dry.py src/services/x.py [...]
        [--contra src] [--limite 0.8] [--min-tokens 40]

Os arquivos dados são comparados entre si e com todas as funções de
``--contra`` (padrão: ``src``, sem o motor Gacrux copiado da FIDE).
"""
from __future__ import annotations

import argparse
import ast
import io
import keyword
import sys
import tokenize
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FORA = ("src/services/pairing/gacrux/",)


@dataclass(frozen=True)
class Funcao:
    origem: str
    nome: str
    tokens: tuple[str, ...]


def normalizar(fonte: str) -> tuple[str, ...]:
    """Tokens da função sem nomes, textos e números — só a forma."""
    saida: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(fonte).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            continue
        if tok.type == tokenize.NAME:
            saida.append(tok.string if keyword.iskeyword(tok.string) else "N")
        elif tok.type == tokenize.STRING:
            saida.append("S")
        elif tok.type == tokenize.NUMBER:
            saida.append("0")
        elif tok.string:
            saida.append(tok.string)
    return tuple(saida)


def semelhanca(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def funcoes(arquivo: Path, min_tokens: int) -> list[Funcao]:
    fonte = arquivo.read_text(encoding="utf-8")
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return []
    nome = arquivo.resolve().relative_to(RAIZ).as_posix() if arquivo.resolve().is_relative_to(RAIZ) else str(arquivo)
    saida: list[Funcao] = []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = no.body[1:] if ast.get_docstring(no) else no.body
        if not corpo:
            continue
        trecho = "\n".join(ast.unparse(c) for c in corpo)
        try:
            tokens = normalizar(trecho)
        except (tokenize.TokenError, IndentationError):
            continue
        if len(tokens) >= min_tokens:
            saida.append(Funcao(f"{nome}:{no.lineno}", no.name, tokens))
    return saida


def pares(alvos: list[Funcao], universo: list[Funcao], limite: float) -> list[tuple[float, Funcao, Funcao]]:
    achados: list[tuple[float, Funcao, Funcao]] = []
    vistos: set[tuple[str, str]] = set()
    for a in alvos:
        for b in universo:
            if a.origem == b.origem or (b.origem, a.origem) in vistos:
                continue
            curto, longo = sorted((len(a.tokens), len(b.tokens)))
            if curto / longo < limite:
                continue
            matcher = SequenceMatcher(None, a.tokens, b.tokens, autojunk=False)
            if matcher.real_quick_ratio() < limite or matcher.quick_ratio() < limite:
                continue
            nota = matcher.ratio()
            if nota >= limite:
                vistos.add((a.origem, b.origem))
                achados.append((nota, a, b))
    return sorted(achados, key=lambda x: -x[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Funções duplicadas (nota de semelhança).")
    parser.add_argument("arquivos", nargs="+")
    parser.add_argument("--contra", default="src")
    parser.add_argument("--limite", type=float, default=0.8)
    parser.add_argument("--min-tokens", type=int, default=40)
    args = parser.parse_args(argv)

    alvos = [f for arq in args.arquivos for f in funcoes(Path(arq), args.min_tokens)]
    universo = [
        f
        for arq in sorted((RAIZ / args.contra).rglob("*.py"))
        if not arq.relative_to(RAIZ).as_posix().startswith(FORA)
        for f in funcoes(arq, args.min_tokens)
    ]
    achados = pares(alvos, universo, args.limite)
    for nota, a, b in achados:
        print(f"{nota:.2f}  {a.origem} {a.nome}  <->  {b.origem} {b.nome}")
    print(f"\n{len(alvos)} função(ões) conferida(s); {len(achados)} par(es) com nota >= {args.limite:g}.")
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main())
