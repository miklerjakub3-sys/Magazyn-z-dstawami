# -*- mode: python ; coding: utf-8 -*-
from datetime import datetime
from pathlib import Path


def _safe_exe_name(default_name: str) -> str:
    """
    Gdy poprzedni plik EXE jest zablokowany przez działający proces,
    PyInstaller zgłasza PermissionError przy próbie nadpisania.
    Wtedy budujemy pod nazwą z timestampem.
    """
    spec_root = globals().get("SPECPATH")
    root = Path(spec_root).resolve() if spec_root else Path.cwd()
    target = root / "dist" / f"{default_name}.exe"
    if not target.exists():
        return default_name
    try:
        target.unlink()
        return default_name
    except OSError:
        return f"{default_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


a = Analysis(
    ['run_pyside6.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('magazyn/ui/assets/axedserwis.png', 'assets'),
        ('magazyn/ui/assets/axedserwis.png', 'magazyn/ui/assets'),
        ('magazyn/ui/styles/app.qss', 'magazyn/ui/styles'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name=_safe_exe_name('Magazyn'),
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
)
