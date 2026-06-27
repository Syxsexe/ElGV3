# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — El G POS (app de escritorio).
Modo onedir: genera dist/ElGV3/ con el .exe + dependencias, listo para
empaquetar con Inno Setup.

Build (en Windows):
    pyinstaller ElGV3.spec --noconfirm
"""
import os

block_cipher = None

# Icono opcional: coloca uno en assets/icon.ico para personalizarlo.
icon_path = os.path.join("assets", "icon.ico")
icon = icon_path if os.path.exists(icon_path) else None

# Recursos de solo lectura a empaquetar (referencia de config DIAN).
datas = []
if os.path.exists("dian_config.example.json"):
    datas.append(("dian_config.example.json", "."))

# Imports que PyInstaller a veces no detecta por análisis estático.
hiddenimports = [
    "reportlab.graphics.barcode",
    "reportlab.graphics.barcode.code128",
    "reportlab.pdfbase._fontdata",
    "PIL._tkinter_finder",
    "openpyxl",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # No empaquetar el backend cloud ni las pruebas.
    excludes=["backend", "tests", "pytest", "alembic"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ElGV3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # app GUI: sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ElGV3",
)
