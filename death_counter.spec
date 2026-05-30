# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    [r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\death_counter.py'],
    pathex=[r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter'],
    binaries=[],
    datas=[
        (r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\controller.html', '.'),
        (r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\obs_overlay.html', '.'),
        (r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\README.md', '.'),
        (r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\pix.png', '.'),
    ],
    hiddenimports=[
        'flask', 'flask_cors', 'werkzeug', 'jinja2', 'click',
        'mss', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'numpy', 'cv2',
        'pytesseract', 'keyboard', 'pystray',
    ],
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
    name='death_counter',
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
    icon=r'C:\Users\RedBlack-PC\Downloads\death_counter\death_counter\death_counter.ico',
)