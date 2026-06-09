"""Executa o JaVaFo do Swiss-Manager e registra a saida para auditoria.

Esta ferramenta nao tenta inferir a linha de comando correta do JaVaFo. Use
``--javafo-args`` para passar os argumentos aceitos pela instalacao local.
Quando nenhum argumento extra e informado, o caminho TRF e repassado como
argumento unico ao JAR.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_JAVAFO = Path(r"C:\Program Files (x86)\SwissManagerUniCode\javafo.jar")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita uma chamada local ao JaVaFo.")
    parser.add_argument("--trf", type=Path, help="Arquivo TRF de entrada.")
    parser.add_argument("--java", default="java", help="Executavel Java.")
    parser.add_argument("--javafo", type=Path, default=DEFAULT_JAVAFO, help="Caminho do javafo.jar.")
    parser.add_argument("--output", type=Path, help="Arquivo JSON para salvar a auditoria.")
    parser.add_argument(
        "--javafo-args",
        nargs=argparse.REMAINDER,
        help="Argumentos passados literalmente apos 'java -jar javafo.jar'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.javafo.exists():
        print(f"JaVaFo nao encontrado: {args.javafo}")
        return 2
    if args.trf is not None and not args.trf.exists():
        print(f"TRF nao encontrado: {args.trf}")
        return 2

    javafo_args = list(args.javafo_args or [])
    if not javafo_args and args.trf is not None:
        javafo_args.append(str(args.trf))
    command = [args.java, "-jar", str(args.javafo), *javafo_args]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload: dict[str, Any] = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
