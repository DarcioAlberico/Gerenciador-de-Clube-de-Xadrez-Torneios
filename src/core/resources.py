"""Onde moram os recursos EMPACOTADOS com o programa (RGS-02).

Há duas pastas que o build congelado separa e o desenvolvimento confunde:

* **recursos empacotados** (``assets/``, ``i18n/``, os scripts do Gacrux): no
  `.exe` onefile do PyInstaller eles são extraídos em ``sys._MEIPASS``, uma
  pasta temporária; no desenvolvimento ficam na raiz do projeto;
* **dados do usuário** (banco, backups, exportações, logs): ficam ao lado do
  `.exe` ou na pasta de dados do sistema — ver ``database._base_dir`` e
  ``resolve_app_data_dir``. **Nunca** no ``_MEIPASS``, que some ao fechar.

Este módulo responde só à primeira pergunta. É puro (não importa Tk nem o
banco) para que ``i18n`` e o Gacrux possam usá-lo sem puxar a interface.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    """True dentro do executável do PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Raiz dos recursos empacotados: ``_MEIPASS`` no `.exe`, a raiz do projeto fora dele."""
    meipass = getattr(sys, "_MEIPASS", None)
    if is_frozen() and meipass:
        return Path(meipass)
    return PROJECT_ROOT


def bundled_resource(relative_path: str) -> Path:
    """Caminho de um recurso empacotado (``"i18n"``, ``"assets/app_icon.ico"``)."""
    return bundle_dir() / relative_path
