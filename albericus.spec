# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path.cwd()


a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=["openpyxl", "xlrd", "pandas", "lxml", "reportlab"],
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
