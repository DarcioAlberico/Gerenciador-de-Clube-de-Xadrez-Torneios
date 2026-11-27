"""Como chamar o Gacrux, no desenvolvimento e no `.exe` (RGS-01).

O Gacrux (Otto Milvang) é um conjunto de **scripts**: ``pairingchecker.py`` e
``tiebreakchecker.py`` importam os vizinhos pelo nome curto (``import version``,
``from helpers import *``) e leem o ``sys.argv`` global. Por isso ele roda em
subprocesso — o que também permite matá-lo no tempo máximo, coisa que uma
thread não permite.

* **Desenvolvimento:** ``[python, <gacrux>/pairingchecker.py, *args]``.
* **Executável:** ``sys.executable`` é o próprio ``Albericus.exe``. O comando
  vira ``[Albericus.exe, --gacrux, pairing, *args]``; ``app.py`` reconhece o
  modo **antes de importar a interface** e chama :func:`run_script`. Os ``.py``
  do Gacrux vão no build como ``datas`` (ver ``albericus.spec``).

Uma decisão, um lugar: os dois motores (pareamento e desempate) montam o
comando só por aqui.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Sequence

from src.core.resources import bundled_resource, is_frozen

GACRUX_FLAG = "--gacrux"

SCRIPTS = {
    "pairing": "pairingchecker.py",
    "tiebreak": "tiebreakchecker.py",
}


def gacrux_dir() -> Path:
    """Pasta dos scripts do Gacrux."""
    if is_frozen():
        return bundled_resource("gacrux")
    return Path(__file__).resolve().parent / "gacrux"


def script_path(kind: str) -> Path:
    try:
        return gacrux_dir() / SCRIPTS[kind]
    except KeyError:
        raise ValueError(
            f"Modo do Gacrux desconhecido: {kind!r} (use {', '.join(sorted(SCRIPTS))})"
        ) from None


def gacrux_command(kind: str, args: Sequence[str]) -> list[str]:
    """Linha de comando do subprocesso para ``kind`` (``"pairing"``/``"tiebreak"``)."""
    path = script_path(kind)
    if is_frozen():
        return [sys.executable, GACRUX_FLAG, kind, *args]
    return [sys.executable, str(path), *args]


def run_script(kind: str, args: Sequence[str]) -> int:
    """Roda o script do Gacrux neste processo, como ``python script.py args``.

    Usado só pelo modo ``--gacrux`` de ``app.py``, num processo filho que não
    tem interface: o estado de módulo do Gacrux morre com ele.
    """
    path = script_path(kind)
    if not path.exists():
        print(f"Motor Gacrux não encontrado em: {path}", file=sys.stderr)
        return 3
    folder = str(path.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    sys.argv = [str(path), *args]
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0
