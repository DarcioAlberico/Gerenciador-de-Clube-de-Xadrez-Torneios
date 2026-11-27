# -*- mode: python ; coding: utf-8 -*-

import ast
from pathlib import Path


ROOT = Path.cwd()

# RGS-01: o Gacrux roda como SCRIPT (`Albericus.exe --gacrux ...`, ver
# src/services/pairing/gacrux_runner.py). O PyInstaller nao segue scripts que
# so sao chamados por subprocesso, entao:
#  * os .py do Gacrux vao como `datas` para a pasta `gacrux/` do bundle;
#  * o que eles importam de FORA da pasta (stdlib, networkx) vira
#    hiddenimport — varrido do proprio codigo, para nao envelhecer na mao.
GACRUX_DIR = ROOT / "src" / "services" / "pairing" / "gacrux"


def gacrux_external_imports() -> list[str]:
    local = {path.stem for path in GACRUX_DIR.glob("*.py")}
    found = set()
    for path in GACRUX_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module)
    # find_spec descarta o que nem existe (ex.: `convert2jch`, de um script de
    # exemplo do Gacrux que o Albericus nao usa).
    from importlib.util import find_spec

    return sorted(
        name for name in found
        if name.split(".")[0] not in local and find_spec(name.split(".")[0]) is not None
    )


a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("i18n", "i18n"),
        (str(GACRUX_DIR / "*.py"), "gacrux"),
    ],
    hiddenimports=["openpyxl", "xlrd", "pandas", "lxml", "reportlab", *gacrux_external_imports()],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Albericus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.ico"),
)
