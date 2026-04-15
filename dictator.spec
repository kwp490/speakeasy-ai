# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for dictat0r.AI — Granite + Cohere engines (transformers/torch).

Build: pyinstaller dictator.spec
Output: dist/dictator/dictator.exe (onedir)
"""

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

block_cipher = None

# Collect PortAudio DLL from sounddevice
binaries = collect_dynamic_libs('sounddevice')

# Collect all native libs from torch so shm.dll and its deps are bundled
binaries += collect_dynamic_libs('torch')

# Collect only transformers data files needed by our two engines.
# The blanket collect_data_files('transformers') pulls in data for all 535+
# model architectures; we only use granite_speech, cohere_asr, and auto.
datas = []
for _subpkg in ('transformers', 'transformers.models.auto',
                 'transformers.models.granite_speech',
                 'transformers.models.cohere_asr'):
    try:
        datas += collect_data_files(_subpkg, include_py_files=False)
    except Exception:
        pass

a = Analysis(
    ['dictator/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        ('dictator/assets', 'dictator/assets'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'sounddevice',
        'soundfile',
        '_soundfile_data',
        'numpy',
        'keyboard',
        'pynvml',
        'transformers',
        'accelerate',
        'torch',
        'torch._strobelight',
        'torch._strobelight.compile_time_profiler',
        'torchaudio',
        'huggingface_hub',
        'sentencepiece',
        'protobuf',
        'tokenizers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['dictator/_runtime_hook_dll.py'],
    excludes=[
        # GUI / image libraries not used
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'PIL',
        # Qt submodules not used (only QtWidgets/QtCore/QtGui needed)
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtPdf',
        # ── Transformers submodules not used ───────────────────────────
        'transformers.pipelines',
        'transformers.trainer',
        'transformers.trainer_seq2seq',
        'transformers.trainer_callback',
        'transformers.trainer_pt_utils',
        'transformers.trainer_utils',
        'transformers.training_args',
        'transformers.training_args_seq2seq',
        'transformers.optimization',
        # ── Dev / build tools not needed at runtime ────────────────────
        'setuptools',
        'pkg_resources',
        'pytest',
        '_pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Strip unnecessary binaries ───────────────────────────────────────────────
import re as _re

_STRIP_PATTERNS = [
    # Qt modules not used by the app
    _re.compile(r'Qt6Quick', _re.I),
    _re.compile(r'Qt6Qml', _re.I),
    _re.compile(r'Qt6Pdf', _re.I),
    _re.compile(r'Qt6VirtualKeyboard', _re.I),
    _re.compile(r'Qt6OpenGL', _re.I),
    _re.compile(r'Qt6Svg', _re.I),
    _re.compile(r'opengl32sw', _re.I),
    # Duplicate / dev binaries in torch/bin
    _re.compile(r'torch[\\/]bin[\\/]asmjit', _re.I),
    _re.compile(r'torch[\\/]bin[\\/]fbgemm', _re.I),
    _re.compile(r'protoc\.exe', _re.I),
]

def _should_keep(entry):
    name = entry[0] if isinstance(entry, tuple) else str(entry)
    return not any(p.search(name) for p in _STRIP_PATTERNS)

a.binaries = [b for b in a.binaries if _should_keep(b)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dictator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='dictator',
)
