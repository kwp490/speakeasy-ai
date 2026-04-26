"""Tests for the SettingsWidget auto-apply and risky-field Apply pattern.

Validates:
  - Safe field toggles auto-apply immediately (save + signal)
  - Risky fields require explicit Apply click
  - Apply button enable/disable logic
  - reload_model_requested emitted for model_path/device changes
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from speakeasy.config import Settings


def _qt_available() -> bool:
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _qt_available(), reason="PySide6 not available")


@pytest.fixture
def settings_widget(tmp_path, monkeypatch):
    """Construct an isolated SettingsWidget with temp settings."""
    from speakeasy.config import Settings
    from speakeasy.settings_dialog import SettingsWidget

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr("speakeasy.config.DEFAULT_CONFIG_DIR", config_dir)
    monkeypatch.setattr("speakeasy.config.DEFAULT_CONFIG_FILE", config_dir / "settings.json")
    monkeypatch.setattr("speakeasy.config.DEFAULT_PRESETS_DIR", config_dir / "presets")
    (config_dir / "presets").mkdir()

    settings = Settings()
    widget = SettingsWidget(settings)
    return widget, settings, config_dir


class TestSafeFieldAutoApply:
    """Safe fields auto-apply on toggle — save to disk + emit settings_applied."""

    def test_auto_copy_toggle_auto_applies(self, settings_widget):
        widget, settings, config_dir = settings_widget
        initial = settings.auto_copy
        # Toggle it
        widget._auto_copy.setChecked(not initial)
        assert settings.auto_copy is (not initial)
        # Verify it was saved
        config_file = config_dir / "settings.json"
        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["auto_copy"] is (not initial)

    def test_safe_toggle_emits_settings_applied_signal(self, settings_widget, qtbot):
        widget, settings, _ = settings_widget
        with qtbot.waitSignal(widget.settings_applied, timeout=1000):
            widget._auto_paste.setChecked(not settings.auto_paste)

    def test_punctuation_toggle_auto_applies(self, settings_widget):
        widget, settings, _ = settings_widget
        initial = settings.punctuation
        widget._punctuation.setChecked(not initial)
        assert settings.punctuation is (not initial)

    def test_hotkeys_enabled_toggle_auto_applies(self, settings_widget):
        widget, settings, _ = settings_widget
        initial = settings.hotkeys_enabled
        widget._hotkeys_enabled.setChecked(not initial)
        assert settings.hotkeys_enabled is (not initial)

    def test_streaming_partials_toggle_auto_applies(self, settings_widget):
        widget, settings, _ = settings_widget
        initial = settings.streaming_partials_enabled
        widget._streaming_partials.setChecked(not initial)
        assert settings.streaming_partials_enabled is (not initial)

    def test_clear_logs_on_exit_toggle_auto_applies(self, settings_widget):
        widget, settings, _ = settings_widget
        initial = settings.clear_logs_on_exit
        widget._clear_logs_on_exit.setChecked(not initial)
        assert settings.clear_logs_on_exit is (not initial)


class TestRiskyFieldApply:
    """Risky fields (model_path, device, sample_rate) need explicit Apply."""

    def test_risky_field_change_does_not_save_until_apply(self, settings_widget):
        widget, settings, config_dir = settings_widget
        old_path = settings.model_path
        widget._model_path.setText("C:\\some\\new\\path")
        # Not saved yet
        assert settings.model_path == old_path

    def test_apply_button_disabled_when_no_risky_diff(self, settings_widget):
        widget, settings, _ = settings_widget
        assert not widget._btn_apply.isEnabled()

    def test_apply_button_enabled_when_risky_field_changed(self, settings_widget):
        widget, settings, _ = settings_widget
        widget._model_path.setText("C:\\changed\\path")
        assert widget._btn_apply.isEnabled()

    def test_apply_button_disabled_after_successful_apply(self, settings_widget):
        widget, settings, _ = settings_widget
        widget._model_path.setText("C:\\changed\\path")
        assert widget._btn_apply.isEnabled()
        widget._on_apply()
        assert not widget._btn_apply.isEnabled()

    def test_apply_saves_risky_fields(self, settings_widget):
        widget, settings, config_dir = settings_widget
        widget._device_combo.setCurrentText("cpu")
        widget._on_apply()
        assert settings.device == "cpu"
        config_file = config_dir / "settings.json"
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["device"] == "cpu"

    def test_sample_rate_change_enables_apply(self, settings_widget):
        widget, settings, _ = settings_widget
        widget._sample_rate.setValue(44100)
        assert widget._btn_apply.isEnabled()


class TestReloadSignals:
    """Apply emits reload_model_requested when model_path or device changes."""

    def test_apply_emits_reload_for_model_path_change(self, settings_widget, qtbot):
        widget, settings, _ = settings_widget
        widget._model_path.setText("C:\\new\\model\\dir")
        with qtbot.waitSignal(widget.reload_model_requested, timeout=1000):
            widget._on_apply()

    def test_apply_emits_reload_for_device_change(self, settings_widget, qtbot):
        widget, settings, _ = settings_widget
        # Change to cpu if currently cuda, or vice versa
        new_device = "cpu" if settings.device == "cuda" else "cuda"
        widget._device_combo.setCurrentText(new_device)
        with qtbot.waitSignal(widget.reload_model_requested, timeout=1000):
            widget._on_apply()

    def test_apply_does_not_emit_reload_for_sample_rate_only(self, settings_widget, qtbot):
        widget, settings, _ = settings_widget
        widget._sample_rate.setValue(44100)
        # Should NOT emit reload_model_requested for sample_rate-only change
        with qtbot.assertNotEmitted(widget.reload_model_requested):
            widget._on_apply()


class TestDevPanelHotkeyField:
    """The dev panel hotkey field should auto-apply via editingFinished."""

    def test_hotkey_dev_panel_field_exists(self, settings_widget):
        widget, settings, _ = settings_widget
        assert hasattr(widget, "_hotkey_dev_panel")
        assert widget._hotkey_dev_panel.text() == "ctrl+alt+d"

    def test_changing_hotkey_persists(self, settings_widget, qtbot):
        widget, settings, config_dir = settings_widget
        widget._hotkey_dev_panel.setText("ctrl+shift+d")
        widget._hotkey_dev_panel.editingFinished.emit()
        assert settings.hotkey_dev_panel == "ctrl+shift+d"
        config_file = config_dir / "settings.json"
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["hotkey_dev_panel"] == "ctrl+shift+d"
