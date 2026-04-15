"""Tests for PyInstaller frozen-build compatibility.

These tests catch issues that only manifest in --noconsole PyInstaller builds:
- Relative imports in __main__.py (no parent package context)
- APIs that assume real file descriptors (faulthandler, fileno)
- Modules that must be importable via absolute paths
- Dynamic imports must be listed in dictator.spec hiddenimports
"""

import ast
import io
import os
import re
import sys
import unittest
from pathlib import Path

# Root of the dictator package
_DICTATOR_PKG = Path(__file__).resolve().parent.parent / "dictator"
_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNoRelativeImportsInMain(unittest.TestCase):
    """__main__.py must use absolute imports for PyInstaller compatibility."""

    def test_no_relative_imports(self):
        source = (_DICTATOR_PKG / "__main__.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="__main__.py")

        relative_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
                relative_imports.append(
                    f"line {node.lineno}: from {'.' * node.level}{node.module or ''} import ..."
                )

        self.assertEqual(
            relative_imports,
            [],
            f"__main__.py must not use relative imports (breaks PyInstaller):\n"
            + "\n".join(relative_imports),
        )


class TestFaulthandlerWithStringIO(unittest.TestCase):
    """faulthandler.enable() must be guarded for --noconsole builds."""

    def test_faulthandler_tolerates_stringio_stderr(self):
        import faulthandler

        original_stderr = sys.stderr
        try:
            sys.stderr = io.StringIO()
            try:
                faulthandler.enable()
            except io.UnsupportedOperation:
                pass
        finally:
            sys.stderr = original_stderr

    def test_main_guards_faulthandler(self):
        source = (_DICTATOR_PKG / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("io.UnsupportedOperation", source,
                       "faulthandler.enable() must be guarded with "
                       "except io.UnsupportedOperation")


class TestStdioSafetyPatches(unittest.TestCase):
    """__main__.py must patch None stdout/stderr for --noconsole builds."""

    def test_stdout_none_guard_exists(self):
        source = (_DICTATOR_PKG / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("sys.stdout is None", source)

    def test_stderr_none_guard_exists(self):
        source = (_DICTATOR_PKG / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("sys.stderr is None", source)

    def test_freeze_support_enabled(self):
        source = (_DICTATOR_PKG / "__main__.py").read_text(encoding="utf-8")
        self.assertIn(
            "multiprocessing.freeze_support()",
            source,
            "__main__.py must call multiprocessing.freeze_support() for Windows spawn/frozen workers",
        )

    def test_granite_worker_adds_dll_directory(self):
        """Granite child process must add torch/lib to DLL search path for frozen builds."""
        source = (_DICTATOR_PKG / "engine" / "granite_speech.py").read_text(encoding="utf-8")
        self.assertIn(
            "os.add_dll_directory",
            source,
            "granite_speech.py worker must call os.add_dll_directory() for torch/lib "
            "in frozen builds so shm.dll can find its native dependencies",
        )
        self.assertIn(
            "_MEIPASS",
            source,
            "granite_speech.py worker must check sys._MEIPASS to detect frozen builds",
        )

    def test_runtime_hook_exists(self):
        """A runtime hook must add _MEIPASS to DLL search paths before torch loads."""
        hook = _DICTATOR_PKG / "_runtime_hook_dll.py"
        self.assertTrue(hook.exists(), "dictator/_runtime_hook_dll.py is missing")
        source = hook.read_text(encoding="utf-8")
        self.assertIn("os.add_dll_directory", source)
        self.assertIn("_MEIPASS", source)
        self.assertIn('os.environ["PATH"]', source,
                       "Runtime hook must also prepend to PATH for legacy LoadLibraryW")

    def test_spec_uses_runtime_hook(self):
        """dictator.spec must reference the DLL runtime hook."""
        spec = (_REPO_ROOT / "dictator.spec").read_text(encoding="utf-8")
        self.assertIn("_runtime_hook_dll", spec,
                       "dictator.spec runtime_hooks must include _runtime_hook_dll")


class TestAllModulesImportable(unittest.TestCase):
    """Every .py file in dictator/ must be importable via absolute paths."""

    _SKIP_MODULES = frozenset({
        "dictator.engine.cohere_transcribe",
        "dictator.engine.granite_speech",
    })

    def test_import_all_modules(self):
        failures = []
        for py_file in sorted(_DICTATOR_PKG.rglob("*.py")):
            rel = py_file.relative_to(_DICTATOR_PKG.parent)
            module_name = str(rel.with_suffix("")).replace("\\", ".").replace("/", ".")

            if module_name in self._SKIP_MODULES:
                continue
            if "__pycache__" in module_name:
                continue

            try:
                __import__(module_name)
            except Exception as exc:
                failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

        self.assertEqual(
            failures,
            [],
            f"Failed to import the following modules:\n" + "\n".join(failures),
        )


class TestRelativeImportsInSubpackages(unittest.TestCase):

    def test_engine_subpackage_imports(self):
        from dictator.engine import ENGINES
        self.assertIsInstance(ENGINES, dict)

    def test_engine_base_imports(self):
        from dictator.engine.base import SpeechEngine
        self.assertTrue(callable(SpeechEngine))


class TestHiddenImportsInSpec(unittest.TestCase):
    """Dynamic imports in __main__.py must be listed in dictator.spec hiddenimports."""

    _INTERNAL_PREFIXES = ("dictator.",)

    _STDLIB = frozenset({
        "argparse", "ctypes", "faulthandler", "io", "json", "logging",
        "logging.handlers", "os", "sys", "re", "pathlib", "tempfile",
        "time", "subprocess", "unittest", "importlib", "threading",
        "collections", "functools", "typing", "traceback", "copy",
        "shutil", "signal", "struct", "abc", "dataclasses", "enum",
    })

    def _parse_hidden_imports(self) -> set[str]:
        spec_path = _REPO_ROOT / "dictator.spec"
        spec_text = spec_path.read_text(encoding="utf-8")
        match = re.search(
            r"hiddenimports\s*=\s*\[(.*?)\]", spec_text, re.DOTALL
        )
        self.assertIsNotNone(match, "Could not find hiddenimports in dictator.spec")
        entries = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
        return set(entries)

    def _collect_deferred_imports(self, filepath: Path) -> list[tuple[int, str]]:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filepath.name)

        deferred: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        deferred.append((child.lineno, alias.name.split(".")[0]))
                elif isinstance(child, ast.ImportFrom):
                    if child.level == 0 and child.module:
                        deferred.append((child.lineno, child.module.split(".")[0]))
        return deferred

    def test_dynamic_imports_in_hiddenimports(self):
        hidden = self._parse_hidden_imports()
        deferred = self._collect_deferred_imports(_DICTATOR_PKG / "__main__.py")

        missing = []
        for lineno, top_module in deferred:
            if top_module in self._STDLIB:
                continue
            if any(top_module.startswith(p.rstrip(".")) for p in self._INTERNAL_PREFIXES):
                continue
            if not any(h == top_module or h.startswith(top_module + ".") for h in hidden):
                missing.append(f"line {lineno}: {top_module}")

        self.assertEqual(
            missing,
            [],
            "Dynamic imports in __main__.py not listed in dictator.spec hiddenimports:\n"
            + "\n".join(missing)
            + "\nAdd them to hiddenimports in dictator.spec.",
        )

    def test_dynamic_imports_in_main_window(self):
        hidden = self._parse_hidden_imports()
        deferred = self._collect_deferred_imports(_DICTATOR_PKG / "main_window.py")

        missing = []
        for lineno, top_module in deferred:
            if top_module in self._STDLIB:
                continue
            if any(top_module.startswith(p.rstrip(".")) for p in self._INTERNAL_PREFIXES):
                continue
            if not any(h == top_module or h.startswith(top_module + ".") for h in hidden):
                missing.append(f"line {lineno}: {top_module}")

        self.assertEqual(
            missing,
            [],
            "Dynamic imports in main_window.py not listed in dictator.spec hiddenimports:\n"
            + "\n".join(missing)
            + "\nAdd them to hiddenimports in dictator.spec.",
        )


class TestTransitiveDependenciesInSpec(unittest.TestCase):
    """Transitive dependencies used at runtime must be bundled in the spec."""

    def _read_spec(self) -> str:
        return (_REPO_ROOT / "dictator.spec").read_text(encoding="utf-8")

    def _parse_hidden_imports(self) -> set[str]:
        spec_text = self._read_spec()
        match = re.search(
            r"hiddenimports\s*=\s*\[(.*?)\]", spec_text, re.DOTALL
        )
        assert match, "Could not find hiddenimports in dictator.spec"
        return set(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))

    def _parse_excludes(self) -> set[str]:
        spec_text = self._read_spec()
        match = re.search(
            r"excludes\s*=\s*\[(.*?)\]", spec_text, re.DOTALL
        )
        assert match, "Could not find excludes in dictator.spec"
        return set(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))

    def test_transformers_in_hiddenimports(self):
        hidden = self._parse_hidden_imports()
        self.assertIn("transformers", hidden)

    def test_torch_in_hiddenimports(self):
        hidden = self._parse_hidden_imports()
        self.assertIn("torch", hidden)

    def test_transformers_data_files_collected(self):
        spec_text = self._read_spec()
        self.assertIn(
            "collect_data_files(",
            spec_text,
            "dictator.spec must call collect_data_files() for transformers data",
        )
        self.assertIn(
            "transformers",
            spec_text,
            "dictator.spec must reference transformers in data file collection",
        )


class TestSpecStripPatterns(unittest.TestCase):
    """Verify stripped binaries are not needed and required ones are kept."""

    def _read_spec(self) -> str:
        return (_REPO_ROOT / "dictator.spec").read_text(encoding="utf-8")

    def _parse_strip_patterns(self) -> list[str]:
        spec_text = self._read_spec()
        return re.findall(r"_re\.compile\(r'([^']+)'", spec_text)

    # ── Critical CUDA libs must NOT be stripped ──────────────────────────

    _MUST_KEEP = [
        "cublas64", "cublasLt64", "cudart64", "cudnn64_9",
        "cudnn_graph64", "cudnn_ops64", "cudnn_cnn64",
        "cudnn_heuristic64", "cudnn_engines_precompiled64",
        "cudnn_engines_runtime_compiled64", "cudnn_adv64",
        "cufft64", "cufftw64", "cusolver64", "cusolverMg64",
        "cusparse64", "nvrtc64", "nvrtc-builtins64",
        "nvJitLink", "cupti64", "nvToolsExt64", "caffe2_nvrtc",
        "torch_cuda", "torch_cpu", "c10_cuda", "c10.dll", "shm.dll",
    ]

    def test_critical_cuda_libs_not_stripped(self):
        """Strip patterns must not match any critical CUDA/cuDNN library."""
        patterns = [re.compile(p, re.I) for p in self._parse_strip_patterns()]
        for lib in self._MUST_KEEP:
            for pat in patterns:
                self.assertIsNone(
                    pat.search(lib),
                    f"Strip r'{pat.pattern}' would remove critical '{lib}'.",
                )

    # ── Excluded modules must not break engine imports ───────────────────

    def _parse_excludes(self) -> set[str]:
        spec_text = self._read_spec()
        m = re.search(r"excludes\s*=\s*\[(.*?)\]", spec_text, re.DOTALL)
        assert m, "Could not find excludes in dictator.spec"
        return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))

    _ENGINE_DEPS = [
        "transformers", "torch", "torchaudio", "numpy",
        "huggingface_hub", "sentencepiece", "tokenizers",
    ]

    def test_engine_deps_not_excluded(self):
        """Top-level engine dependencies must not appear in excludes."""
        excludes = self._parse_excludes()
        for dep in self._ENGINE_DEPS:
            self.assertNotIn(
                dep, excludes,
                f"'{dep}' is excluded but is a direct engine dependency.",
            )

    _REQUIRED_TORCH = [
        "torch.nn", "torch.cuda", "torch.autograd",
        "torch.backends", "torch.utils",
    ]

    def test_required_torch_submodules_not_excluded(self):
        """Torch submodules used during inference must not be excluded."""
        excludes = self._parse_excludes()
        for mod in self._REQUIRED_TORCH:
            self.assertNotIn(
                mod, excludes,
                f"'{mod}' is required for model inference.",
            )

    def test_excluded_torch_modules_not_imported_at_startup(self):
        """Excluded torch submodules must not be loaded when torch starts.

        If torch begins importing an excluded module unconditionally (as
        happened with torch._strobelight in torch 2.11), PyInstaller
        will produce a build that crashes immediately with
        ``ModuleNotFoundError``.  Move such modules from ``excludes``
        to ``hiddenimports``.
        """
        import torch  # noqa: F401 — ensures torch startup imports are loaded
        excludes = {e for e in self._parse_excludes() if e.startswith("torch.")}

        loaded_and_excluded = []
        for mod_name in sorted(sys.modules):
            for excl in excludes:
                if mod_name == excl or mod_name.startswith(excl + "."):
                    loaded_and_excluded.append((mod_name, excl))
                    break

        self.assertEqual(
            loaded_and_excluded,
            [],
            "These modules are in dictator.spec excludes but were imported "
            "during torch startup — they must be moved to hiddenimports:\n"
            + "\n".join(f"  {mod} (matched exclude '{excl}')"
                        for mod, excl in loaded_and_excluded),
        )

    _REQUIRED_TF = [
        "transformers.models", "transformers.modeling_utils",
        "transformers.configuration_utils", "transformers.generation",
        "transformers.tokenization_utils_base", "transformers.processing_utils",
        "transformers.integrations",
    ]

    def test_required_transformers_submodules_not_excluded(self):
        """Transformers submodules used by engines must not be excluded."""
        excludes = self._parse_excludes()
        for mod in self._REQUIRED_TF:
            self.assertNotIn(
                mod, excludes,
                f"'{mod}' is needed for model loading.",
            )

    def test_no_blanket_cudnn_strip(self):
        """Strip patterns must not use a blanket pattern matching core cuDNN."""
        for raw in self._parse_strip_patterns():
            pat = re.compile(raw, re.I)
            self.assertIsNone(
                pat.search("cudnn64_9.dll"),
                f"r'{raw}' matches core cudnn64_9.dll",
            )
            self.assertIsNone(
                pat.search("cudnn_graph64_9.dll"),
                f"r'{raw}' matches cudnn_graph64_9.dll",
            )


class TestDistOutputEssentials(unittest.TestCase):
    """If dist/ exists, verify critical torch/CUDA DLLs are present."""

    _DIST = _REPO_ROOT / "dist" / "dictator" / "_internal"

    @unittest.skipUnless(
        (_REPO_ROOT / "dist" / "dictator" / "_internal").is_dir(),
        "No dist/ build present",
    )
    def test_critical_cuda_dlls_present(self):
        """Core CUDA DLLs required for GPU inference must be in the build."""
        for pat in [
            "cublas64_*.dll", "cublasLt64_*.dll", "cudart64_*.dll",
            "cudnn64_*.dll", "cudnn_graph64_*.dll", "cudnn_ops64_*.dll",
            "cudnn_cnn64_*.dll", "cudnn_heuristic64_*.dll",
            "cudnn_engines_precompiled64_*.dll",
        ]:
            self.assertTrue(
                list(self._DIST.rglob(pat)),
                f"Required '{pat}' missing from dist/ — strip too aggressive?",
            )

    @unittest.skipUnless(
        (_REPO_ROOT / "dist" / "dictator" / "_internal").is_dir(),
        "No dist/ build present",
    )
    def test_torch_cuda_support_dlls_present(self):
        """Torch-managed CUDA support DLLs must be preserved in the build."""
        for pat in [
            "cufft64_*.dll", "cufftw64_*.dll", "cusolver64_*.dll",
            "cusolverMg64_*.dll", "cusparse64_*.dll",
            "cudnn_engines_runtime_compiled64_*.dll", "cudnn_adv64_*.dll",
            "cupti64_*.dll", "nvJitLink*.dll", "nvToolsExt64_*.dll",
            "nvrtc64_*.dll", "nvrtc-builtins64_*.dll", "caffe2_nvrtc.dll",
        ]:
            self.assertTrue(
                list(self._DIST.rglob(pat)),
                f"Required '{pat}' missing from dist/ — torch DLL strip too aggressive?",
            )

    @unittest.skipUnless(
        (_REPO_ROOT / "dist" / "dictator" / "_internal").is_dir(),
        "No dist/ build present",
    )
    def test_torch_core_present(self):
        """Core torch DLLs must be present (including shm.dll for multiprocessing)."""
        for name in ["torch_cpu.dll", "torch_cuda.dll", "torch.dll", "shm.dll", "c10.dll"]:
            self.assertTrue(
                list(self._DIST.rglob(name)),
                f"Core '{name}' missing from dist/.",
            )
