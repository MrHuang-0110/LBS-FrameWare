# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir 打包配置。资源(products.yaml/products/tools)不在此收集，
# 由 scripts/build.py 于构建后复制到 dist/LBS-Firmware-Studio/ 旁。
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = collect_data_files("qtawesome")   # fontawesome 字体 .ttf/.json

a = Analysis(
    ["src/lbs_firmware_studio/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=["serial.tools.list_ports"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
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
    name="LBS-Firmware-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LBS-Firmware-Studio",
)
