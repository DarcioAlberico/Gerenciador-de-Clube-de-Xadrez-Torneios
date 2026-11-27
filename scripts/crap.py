"""Crapper: o índice CRAP de cada função (complexidade x falta de teste).

CRAP(f) = cc(f)² · (1 − cob(f))³ + cc(f)

``cc`` é a complexidade ciclomática (radon) e ``cob`` a fração das linhas da
função que os testes executaram (coverage.py). Função simples e testada fica
perto de ``cc``; função complexa sem teste explode. O alvo do ub-mode é ficar
abaixo de 10.

Uso:
    uv run --extra dev coverage run -m pytest tests/test_x.py
    uv run --extra dev coverage json -o coverage.json
    uv run --extra dev python scripts/crap.py coverage.json src/services/x.py [...]
        [--limite 10] [--funcao nome]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from radon.complexity import cc_visit

RAIZ = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Indice:
    arquivo: str
    funcao: str
    linha: int
    complexidade: int
    cobertura: float

    @property
    def crap(self) -> float:
        return self.complexidade**2 * (1 - self.cobertura) ** 3 + self.complexidade


def crap(complexidade: int, cobertura: float) -> float:
    """A fórmula, sozinha (para teste)."""
    return complexidade**2 * (1 - cobertura) ** 3 + complexidade


def _cobertura_do_arquivo(dados: dict, arquivo: Path) -> tuple[set[int], set[int]]:
    alvo = arquivo.resolve()
    for nome, info in dados.get("files", {}).items():
        if (RAIZ / nome).resolve() == alvo or Path(nome).resolve() == alvo:
            return set(info.get("executed_lines", [])), set(info.get("missing_lines", []))
    return set(), set()


def indices(dados: dict, arquivo: Path) -> list[Indice]:
    executadas, faltando = _cobertura_do_arquivo(dados, arquivo)
    medidas = executadas | faltando
    saida: list[Indice] = []
    for bloco in cc_visit(arquivo.read_text(encoding="utf-8")):
        if not hasattr(bloco, "endline"):
            continue
        nome = f"{bloco.classname}.{bloco.name}" if getattr(bloco, "classname", None) else bloco.name
        linhas = {n for n in range(bloco.lineno, bloco.endline + 1) if n in medidas}
        cobertura = len(linhas & executadas) / len(linhas) if linhas else 0.0
        saida.append(Indice(arquivo.as_posix(), nome, bloco.lineno, bloco.complexity, cobertura))
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Índice CRAP por função.")
    parser.add_argument("coverage_json")
    parser.add_argument("arquivos", nargs="+")
    parser.add_argument("--limite", type=float, default=10.0)
    parser.add_argument("--funcao", action="append", default=[], help="só estas funções (nome ou Classe.nome)")
    args = parser.parse_args(argv)

    dados = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
    todos = [i for arq in args.arquivos for i in indices(dados, Path(arq))]
    if args.funcao:
        todos = [i for i in todos if i.funcao in args.funcao or i.funcao.split(".")[-1] in args.funcao]
    todos.sort(key=lambda i: -i.crap)
    acima = [i for i in todos if i.crap >= args.limite]
    for i in todos:
        marca = "!!" if i.crap >= args.limite else "  "
        print(f"{marca} CRAP {i.crap:6.1f}  cc {i.complexidade:2d}  cob {i.cobertura:4.0%}  {i.arquivo}:{i.linha} {i.funcao}")
    print(f"\n{len(todos)} função(ões); {len(acima)} com CRAP >= {args.limite:g}.")
    return 1 if acima else 0


if __name__ == "__main__":
    sys.exit(main())
