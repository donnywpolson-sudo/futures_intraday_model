# -*- mode: python ; coding: utf-8 -*-

import os


os.environ.setdefault('SETUPTOOLS_USE_DISTUTILS', 'stdlib')


a = Analysis(
    ['live_chart_feed.py'],
    pathex=[],
    binaries=[],
    datas=[('configs/alpha_tiered.yaml', 'configs')],
    hiddenimports=['databento', 'lightweight_charts', 'pandas', 'yaml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numba', 'pytest', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LiveChartFeed',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
