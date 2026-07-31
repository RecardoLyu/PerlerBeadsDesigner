"""
PyInstaller specification for Perler Beads Designer
Run: pyinstaller pyinstaller.spec
"""

import os
from PyInstaller.utils.hooks import get_module_file_attribute

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the bead palette so the frozen exe finds colors_221.json
        # (otherwise ColorManager silently falls back to the 18-color default).
        ('src/assets', 'src/assets'),
        # App icon, resolved at runtime from the same bundle root.
        ('resources/icons', 'resources/icons'),
    ],
    hiddenimports=[
        'cv2',
        'numpy',
        'PIL',
        'PIL.ImageTk',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PerlerBeadsDesigner',
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
    icon='resources/icons/app.ico' if os.path.exists('resources/icons/app.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PerlerBeadsDesigner'
)
