"""Ponto de entrada do Albericus.

Três modos, decididos ANTES de importar a interface (o `.exe` é um só):

* ``Albericus.exe`` — abre a janela;
* ``Albericus.exe --gacrux pairing|tiebreak <args>`` — roda o motor Gacrux
  neste processo e sai com o código dele (RGS-01). É assim que o próprio
  `.exe` chama o Gacrux: ``sys.executable`` é ele mesmo;
* ``Albericus.exe --self-test <pasta>`` — roda o autoteste do build sem
  janela e grava ``<pasta>/selftest.json`` (RGS-05).
"""
from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if argv[:1] == ["--gacrux"]:
        from src.services.pairing.gacrux_runner import run_script

        if len(argv) < 2:
            print("uso: --gacrux pairing|tiebreak <args>", file=sys.stderr)
            return 2
        try:
            return run_script(argv[1], argv[2:])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if argv[:1] == ["--self-test"]:
        from src.selftest import main as selftest_main

        return selftest_main(argv[1:])

    from src.ui.app import AlbericusApp

    app = AlbericusApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
