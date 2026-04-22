"""
PyInstaller runtime hook — add _MEIPASS to the DLL search path on Windows.

In a frozen onedir build, VC++ runtime DLLs (vcruntime140.dll, msvcp140.dll)
live in _internal/ but torch's _load_dll_libraries() only adds torch/lib/ to
the DLL search directories.  LoadLibraryExW with LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
then can't resolve transitive dependencies of torch DLLs like shm.dll.

This hook runs before any application code and ensures _MEIPASS is on both
os.add_dll_directory() and PATH so every subsequent DLL load succeeds.
"""

import os
import sys

_meipass = getattr(sys, "_MEIPASS", None)
if _meipass is not None and sys.platform == "win32":
    # Add _MEIPASS itself so VC++ runtimes in _internal/ are findable
    if os.path.isdir(_meipass):
        os.add_dll_directory(_meipass)

    # Also add torch/lib in case it exists (belt-and-suspenders)
    _torch_lib = os.path.join(_meipass, "torch", "lib")
    if os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)

    # Prepend to PATH as well — legacy LoadLibraryW fallback uses PATH
    _extra = os.pathsep.join(
        p for p in (_meipass, _torch_lib) if os.path.isdir(p)
    )
    if _extra:
        os.environ["PATH"] = _extra + os.pathsep + os.environ.get("PATH", "")
