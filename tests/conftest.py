"""Shared fixtures for the SpeakEasy AI test suite.

Every fixture that touches hardware (GPU, mic, OS hotkeys, clipboard) is
mocked so the suite runs headlessly in CI without special resources.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Force Qt offscreen rendering for headless CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── QApplication for xdist workers ────────────────────────────────────────────
# pytest-qt's qapp fixture is session-scoped but only activates when a test
# explicitly requests it (or qtbot).  Fixtures that construct widgets directly
# (e.g. LogsWidget()) need a QApplication to already exist.  Creating one
# eagerly in every xdist worker prevents sporadic crashes.

@pytest.fixture(scope="session", autouse=True)
def _ensure_qapp():
    """Guarantee a QApplication exists for the entire worker session."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        yield
        return
    app = QApplication.instance() or QApplication([])
    yield app


# ── Settings isolation ────────────────────────────────────────────────────────

@pytest.fixture
def temp_settings_dir(tmp_path, monkeypatch):
    """Redirect Settings persistence to a temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    presets_dir = config_dir / "presets"
    presets_dir.mkdir()
    monkeypatch.setattr("speakeasy.config.DEFAULT_CONFIG_DIR", config_dir)
    monkeypatch.setattr("speakeasy.config.DEFAULT_CONFIG_FILE", config_dir / "settings.json")
    monkeypatch.setattr("speakeasy.config.DEFAULT_PRESETS_DIR", presets_dir)
    return config_dir


@pytest.fixture
def fresh_settings(temp_settings_dir):
    """A clean Settings instance with default values, isolated to temp dir."""
    from speakeasy.config import Settings
    return Settings()
