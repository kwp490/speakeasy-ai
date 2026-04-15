"""Tests for model-presence validation across source and frozen builds.

Ensures that ``model_ready()`` and ``_model_files_exist()`` agree, that
model path resolution respects DICTATOR_HOME, and that the engine
registry correctly reports availability based on on-disk model files.
"""

import builtins
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from dictator.engine import ENGINES, _model_files_exist, get_available_engines
from dictator.model_downloader import _ENGINE_REPO_MAP, model_ready


class TestModelReadyAndModelFilesExistAgree(unittest.TestCase):
    """``model_ready()`` and ``_model_files_exist()`` must return the same
    result for every engine in ``_ENGINE_REPO_MAP``."""

    def test_both_true_when_config_present(self):
        for engine_name in _ENGINE_REPO_MAP:
            with tempfile.TemporaryDirectory() as d:
                engine_dir = os.path.join(d, engine_name)
                os.makedirs(engine_dir)
                with open(os.path.join(engine_dir, "config.json"), "w") as f:
                    f.write("{}")
                self.assertTrue(
                    model_ready(engine_name, d),
                    f"model_ready should be True for {engine_name}",
                )
                self.assertTrue(
                    _model_files_exist(engine_name, d),
                    f"_model_files_exist should be True for {engine_name}",
                )

    def test_both_false_when_empty_dir(self):
        for engine_name in _ENGINE_REPO_MAP:
            with tempfile.TemporaryDirectory() as d:
                os.makedirs(os.path.join(d, engine_name))
                self.assertFalse(model_ready(engine_name, d))
                self.assertFalse(_model_files_exist(engine_name, d))

    def test_both_false_when_no_dir(self):
        for engine_name in _ENGINE_REPO_MAP:
            with tempfile.TemporaryDirectory() as d:
                self.assertFalse(model_ready(engine_name, d))
                self.assertFalse(_model_files_exist(engine_name, d))


class TestAvailableEnginesReflectsModelPresence(unittest.TestCase):
    """``get_available_engines()`` must only list engines whose model
    files are actually on disk."""

    def test_empty_when_no_models(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(get_available_engines(d), [])

    def test_cohere_listed_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            cohere_dir = os.path.join(d, "cohere")
            os.makedirs(cohere_dir)
            with open(os.path.join(cohere_dir, "config.json"), "w") as f:
                f.write("{}")
            available = get_available_engines(d)
            self.assertIn("cohere", available)

    def test_cohere_missing_when_no_config(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "cohere"))
            self.assertNotIn("cohere", get_available_engines(d))


class TestModelPathResolution(unittest.TestCase):
    """Model path must resolve correctly for source and frozen builds."""

    def test_source_mode_dictator_home(self):
        """When DICTATOR_HOME is set, INSTALL_DIR / 'models' should match."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"DICTATOR_HOME": d}):
                # Re-import to pick up the env var
                import importlib
                import dictator.config as cfg
                importlib.reload(cfg)
                try:
                    expected = Path(d) / "models"
                    self.assertEqual(cfg.DEFAULT_MODELS_DIR, str(expected))
                finally:
                    # Restore so other tests are not affected
                    importlib.reload(cfg)

    def test_frozen_mode_default(self):
        """Without DICTATOR_HOME, INSTALL_DIR defaults to Program Files."""
        with mock.patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("DICTATOR_HOME", None)
            with mock.patch.dict(os.environ, env, clear=True):
                import importlib
                import dictator.config as cfg
                importlib.reload(cfg)
                try:
                    expected = str(
                        Path(r"C:\Program Files\dictat0r.AI") / "models"
                    )
                    self.assertEqual(cfg.DEFAULT_MODELS_DIR, expected)
                finally:
                    importlib.reload(cfg)


class TestEngineRuntimeDependencies(unittest.TestCase):
    """Runtime dependencies required by the engine must be importable."""

    def test_librosa_importable(self):
        """librosa is required by CohereAsrFeatureExtractor."""
        import importlib
        mod = importlib.import_module("librosa")
        self.assertTrue(hasattr(mod, "__version__"))

    def test_scipy_importable(self):
        """scipy is a transitive dependency of librosa."""
        import importlib
        mod = importlib.import_module("scipy")
        self.assertTrue(hasattr(mod, "__version__"))

    def test_safetensors_importable(self):
        """safetensors.torch is used by processing_cohere_asr.py."""
        from safetensors.torch import load_file
        self.assertTrue(callable(load_file))

    def test_multiprocessing_spawn_available(self):
        """Windows only supports 'spawn' — model code must not require 'fork'."""
        import multiprocessing as mp
        import sys
        if sys.platform == "win32":
            with self.assertRaises(ValueError):
                mp.get_context("fork")
            # spawn must work
            ctx = mp.get_context("spawn")
            self.assertIsNotNone(ctx)

    def test_cohere_feature_extractor_runs_without_sklearn(self):
        """The active Cohere feature-extractor path must not require sklearn."""
        blocked_names: list[str] = []
        real_import = builtins.__import__
        saved_modules = {
            name: module
            for name, module in list(sys.modules.items())
            if name == "librosa"
            or name.startswith("librosa.")
            or name == "sklearn"
            or name.startswith("sklearn.")
            or name == "transformers.models.cohere_asr.feature_extraction_cohere_asr"
        }

        for name in saved_modules:
            sys.modules.pop(name, None)

        def guarded_import(name, *args, **kwargs):
            if name == "sklearn" or name.startswith("sklearn."):
                blocked_names.append(name)
                raise ImportError("blocked sklearn for test")
            return real_import(name, *args, **kwargs)

        try:
            builtins.__import__ = guarded_import
            module = importlib.import_module(
                "transformers.models.cohere_asr.feature_extraction_cohere_asr"
            )
            extractor = module.CohereAsrFeatureExtractor()
            output = extractor(
                np.zeros(16000, dtype=np.float32),
                sampling_rate=16000,
                return_tensors="pt",
            )
            self.assertIn("input_features", output)
        finally:
            builtins.__import__ = real_import
            sys.modules.update(saved_modules)

        self.assertEqual(
            blocked_names,
            [],
            "Cohere feature extraction should not attempt to import sklearn.",
        )


class TestAllRegisteredEnginesHaveRepoMapping(unittest.TestCase):
    """Every engine in the registry must have a corresponding entry in
    ``_ENGINE_REPO_MAP`` so that ``download_model()`` can fetch it."""

    def test_all_engines_mapped(self):
        for name in ENGINES:
            self.assertIn(
                name,
                _ENGINE_REPO_MAP,
                f"Engine '{name}' registered but has no repo mapping in _ENGINE_REPO_MAP",
            )


if __name__ == "__main__":
    unittest.main()
