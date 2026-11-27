"""Mutator: muda o código de propósito e confere se algum teste percebe.

Cada mutante troca UMA coisa no arquivo — ``==`` por ``!=``, ``<`` por ``<=``,
``and`` por ``or``, tira um ``not``, soma 1 a um número, devolve ``None`` no
lugar do valor, inverte a condição de um ``if`` — e roda os testes dados.
Teste que falha mata o mutante; mutante que sobrevive é comportamento que
nenhum teste confere (ou código morto).

Texto (literal de string) não é mutado: é mensagem de tela, e o teste de
comportamento não deve depender da frase exata.

Por que não o mutmut: no Windows, o mutmut 2.5 deu como "sobrevivente" um
mutante que nem compila. Este roda cada mutante com um cache de bytecode
próprio (``PYTHONPYCACHEPREFIX``), então o ``.pyc`` antigo nunca mascara a
mudança, e o arquivo original volta sempre, mesmo com Ctrl+C.

Uso:
    uv run --extra dev python scripts/mutate.py src/services/x.py -- tests/test_x.py [args do pytest]
        [--funcao nome ...] [--timeout 300]
"""
from __future__ import annotations

import argparse
import ast
import copy
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

_TROCA_COMPARACAO: dict[type, type] = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}


@dataclass(frozen=True)
class Mutante:
    indice: int
    linha: int
    descricao: str
    fonte: str


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = no.body
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
                ids.add(id(corpo[0].value))
    return ids


def _dentro(no: ast.AST, funcoes: list[tuple[int, int]]) -> bool:
    linha = getattr(no, "lineno", 0)
    return not funcoes or any(ini <= linha <= fim for ini, fim in funcoes)


def _pontos(arvore: ast.AST, funcoes: list[tuple[int, int]]) -> list[tuple[ast.AST, str, int]]:
    """``(nó, tipo de mutação, sub-índice)`` de cada mutação possível, em ordem estável."""
    docs = _docstrings(arvore)
    pontos: list[tuple[ast.AST, str, int]] = []
    for no in ast.walk(arvore):
        if not _dentro(no, funcoes):
            continue
        if isinstance(no, ast.Compare):
            for i, op in enumerate(no.ops):
                if type(op) in _TROCA_COMPARACAO:
                    pontos.append((no, "comparacao", i))
        elif isinstance(no, ast.BoolOp):
            pontos.append((no, "booleano", 0))
        elif isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
            pontos.append((no, "tira_not", 0))
        elif isinstance(no, ast.Constant) and id(no) not in docs:
            if isinstance(no.value, (int, float)) and not isinstance(no.value, bool):
                pontos.append((no, "numero", 0))
            elif isinstance(no.value, bool):
                pontos.append((no, "logico", 0))
        elif isinstance(no, ast.Return) and no.value is not None:
            if not (isinstance(no.value, ast.Constant) and no.value.value is None):
                pontos.append((no, "retorna_none", 0))
        elif isinstance(no, (ast.If, ast.IfExp, ast.While)):
            pontos.append((no, "inverte_condicao", 0))
    return pontos


def _aplicar(no: ast.AST, tipo: str, sub: int) -> str:
    if tipo == "comparacao":
        assert isinstance(no, ast.Compare)
        antes = type(no.ops[sub])
        no.ops[sub] = _TROCA_COMPARACAO[antes]()
        return f"{antes.__name__} -> {type(no.ops[sub]).__name__}"
    if tipo == "booleano":
        assert isinstance(no, ast.BoolOp)
        antes = type(no.op).__name__
        no.op = ast.Or() if isinstance(no.op, ast.And) else ast.And()
        return f"{antes} -> {type(no.op).__name__}"
    if tipo == "tira_not":
        assert isinstance(no, ast.UnaryOp)
        no.op = ast.UAdd()  # `+x` em bool: o valor sem o `not`
        return "tira o not"
    if tipo == "numero":
        assert isinstance(no, ast.Constant)
        antes = no.value
        no.value = antes + 1
        return f"{antes!r} -> {no.value!r}"
    if tipo == "logico":
        assert isinstance(no, ast.Constant)
        no.value = not no.value
        return f"{not no.value} -> {no.value}"
    if tipo == "retorna_none":
        assert isinstance(no, ast.Return)
        no.value = ast.Constant(None)
        return "return None"
    assert isinstance(no, (ast.If, ast.IfExp, ast.While))
    no.test = ast.UnaryOp(op=ast.Not(), operand=no.test)
    return "inverte a condição"


def mutantes(fonte: str, nomes: list[str] | None = None) -> list[Mutante]:
    """Todos os mutantes do arquivo (ou só das funções ``nomes``)."""
    original = ast.parse(fonte)
    funcoes = [
        (no.lineno, no.end_lineno or no.lineno)
        for no in ast.walk(original)
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and nomes and no.name in nomes
    ]
    if nomes and not funcoes:
        return []
    total = len(_pontos(original, funcoes))
    saida: list[Mutante] = []
    for indice in range(total):
        arvore = copy.deepcopy(original)
        no, tipo, sub = _pontos(arvore, funcoes)[indice]
        descricao = _aplicar(no, tipo, sub)
        ast.fix_missing_locations(arvore)
        saida.append(Mutante(indice, getattr(no, "lineno", 0), descricao, ast.unparse(arvore)))
    return saida


def _roda(testes: list[str], timeout: int) -> str:
    with tempfile.TemporaryDirectory() as cache:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": cache, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            feito = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *testes],
                cwd=RAIZ, env=env, capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return "morto (tempo)"
    return "sobreviveu" if feito.returncode == 0 else "morto"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--" not in argv:
        print("Uso: mutate.py ARQUIVO [--funcao N] -- TESTES...", file=sys.stderr)
        return 2
    corte = argv.index("--")
    parser = argparse.ArgumentParser(description="Teste de mutação.")
    parser.add_argument("arquivo")
    parser.add_argument("--funcao", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv[:corte])
    testes = argv[corte + 1:]

    alvo = Path(args.arquivo)
    original = alvo.read_bytes()
    lista = mutantes(original.decode("utf-8"), args.funcao or None)
    if _roda(testes, args.timeout) != "sobreviveu":
        print("Os testes já falham sem mutação: nada a medir.", file=sys.stderr)
        return 2
    sobreviventes: list[Mutante] = []
    try:
        for m in lista:
            alvo.write_text(m.fonte, encoding="utf-8")
            estado = _roda(testes, args.timeout)
            print(f"[{m.indice + 1}/{len(lista)}] linha {m.linha}: {m.descricao} — {estado}", flush=True)
            if estado == "sobreviveu":
                sobreviventes.append(m)
    finally:
        alvo.write_bytes(original)
    print(f"\n{len(lista)} mutante(s); {len(sobreviventes)} sobrevivente(s).")
    for m in sobreviventes:
        print(f"  linha {m.linha}: {m.descricao}")
    return 1 if sobreviventes else 0


if __name__ == "__main__":
    sys.exit(main())
