"""
PyInstaller specification for Perler Beads Designer
Run: pyinstaller pyinstaller.spec
"""

import os
import sys
from PyInstaller.utils.hooks import get_module_file_attribute, collect_data_files, collect_submodules

# Icons: .ico is a Windows-only format. On macOS PyInstaller would need .icns,
# and on Linux the EXE icon is unsupported — passing the .ico there makes
# PyInstaller reference the onedir output dir as a resource and COLLECT crashes
# with "Resource ... is not a valid file!". Only pass an icon on Windows.
_icon = None
if sys.platform == 'win32' and os.path.exists('resources/icons/app.ico'):
    _icon = 'resources/icons/app.ico'
elif sys.platform == 'darwin' and os.path.exists('resources/icons/app.icns'):
    _icon = 'resources/icons/app.icns'

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the bead palette so the frozen exe finds colors_221.json
        # (otherwise ColorManager silently falls back to the 18-color default).
        ('src/assets', 'src/assets'),
        # App icon, resolved at runtime from the same bundle root.
        ('resources/icons', 'resources/icons'),
        # Embedded help document, shown by the in-app 帮助 button.
        ('HELP.md', '.'),
        # Web frontend (HTML/CSS/JS) served by FastAPI at the app root.
        ('src/webapp/static', 'src/webapp/static'),
    ],
    hiddenimports=[
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        # FastAPI / uvicorn ASGI server (lazy-loaded submodules PyInstaller misses)
        'fastapi',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # pywebview native window + Windows (winforms) backend
        'webview',
        'webview.platforms.winforms',
        'pythonnet',
        'clr',
        # webapp backend modules
        'src.webapp',
        'src.webapp.app',
        'src.webapp.state',
        'src.webapp.codecs',
        'src.webapp.updater',
        # HTTP client for online update (PyInstaller misses these submodules)
        'requests',
        'urllib3',
        'charset_normalizer',
        'idna',
        'certifi',
    ],
    # The dependency scan walks the whole import graph; some packages it finds
    # in this dev environment are heavy and unused by the app, and a few (Qt
    # bindings, torch) actively break the build — Qt pulls both PyQt5/PyQt6 in
    # ("multiple Qt bindings" abort) and torch hard-crashes (access violation)
    # while PyInstaller loads its DLLs. Exclude them all.
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy',
        'torch', 'torchvision', 'torchaudio', 'tensorflow', 'keras', 'jax',
        'matplotlib', 'IPython', 'ipykernel', 'jupyter', 'notebook',
        'pandas', 'sympy', 'dask', 'distributed', 'sklearn',
        # scikit-image is no longer used (SLIC is self-implemented in
        # numpy+cv2) — exclude it and its heavy optional deps so the fragile
        # Cython extensions are not bundled at all.
        'skimage', 'scikit-image', 'scipy', 'pywt', 'imageio', 'tifffile',
        'numba', 'llvmlite', 'networkx', 'docutils', 'sphinx',
        # Unrelated heavy packages present in this dev environment that the
        # dependency scan would otherwise bundle (none are used by the app).
        'playwright', 'panel', 'bokeh', 'pyarrow', 'astropy', 'statsmodels',
        'holoviews', 'datashader', 'param', 'pyviz_comms', 'lxml', 'selenium',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# On non-Windows the EXE has no extension, so an EXE named "PerlerBeadsDesigner"
# would be written as the file dist/PerlerBeadsDesigner — colliding with the
# COLLECT output directory of the same name ("Resource ... is not a valid
# file!"). Windows is spared because the EXE keeps its .exe suffix. Give the EXE
# a distinct internal name off-Windows; the COLLECT dir stays PerlerBeadsDesigner.
_exe_name = 'PerlerBeadsDesigner' if sys.platform == 'win32' else 'PerlerBeadsDesigner-bin'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=_exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PerlerBeadsDesigner'
)
