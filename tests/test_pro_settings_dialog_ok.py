"""Tests for the Professional Mode settings dialog OK button behaviour.

Verifies that:
  1. `_save_and_accept` always calls `self.accept()` even when
     `_save_settings()` raises an exception (e.g. PermissionError writing
     settings.json).
  2. A user-visible error message is shown when the save fails.
  3. The same guarantee holds for the regular settings dialog.
  4. The installer scripts grant write access to BUILTIN\\Users on
     settings.json so the permission issue doesn't occur for fresh installs.

AST-level tests run without Qt or GPU; runtime tests are skipped when Qt
is not importable.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRO_DIALOG_PATH = _REPO_ROOT / "speakeasy" / "pro_settings_dialog.py"
_SETTINGS_DIALOG_PATH = _REPO_ROOT / "speakeasy" / "settings_dialog.py"
_ISS_GPU_PATH = _REPO_ROOT / "installer" / "speakeasy-setup.iss"
_ISS_CPU_PATH = _REPO_ROOT / "installer" / "speakeasy-cpu-setup.iss"


def _qt_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
        return True
    except ImportError:
        return False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _method_source(filepath: Path, class_name: str, method_name: str) -> str:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filepath.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == method_name:
                    seg = ast.get_source_segment(source, child)
                    if seg:
                        return seg
    raise AssertionError(
        f"Method {class_name}.{method_name} not found in {filepath.name}"
    )


# ── AST tests (no Qt required) ───────────────────────────────────────────────

class TestProSettingsDialogStructure(unittest.TestCase):
    """Static source checks for ProSettingsDialog._save_and_accept."""

    def setUp(self):
        self.src = _method_source(
            _PRO_DIALOG_PATH, "ProSettingsDialog", "_save_and_accept"
        )

    def test_accept_called_unconditionally(self):
        """accept() must appear outside any if/try block — always called."""
        # The simplest check: 'self.accept()' must be present in the method.
        self.assertIn("self.accept()", self.src)

    def test_save_settings_wrapped_in_try(self):
        """_save_settings() must be inside a try block so exceptions don't
        prevent accept() from being called."""
        self.assertIn("try:", self.src)
        self.assertIn("_save_settings()", self.src)

    def test_except_clause_present(self):
        """An except clause must be present to catch save errors."""
        self.assertIn("except", self.src)

    def test_error_dialog_shown_on_failure(self):
        """A QMessageBox warning must be shown inside the except branch."""
        self.assertIn("QMessageBox.warning", self.src)

    def test_accept_after_try_except(self):
        """self.accept() must appear AFTER the try/except block, not inside it,
        so it always runs."""
        try_pos = self.src.find("try:")
        accept_pos = self.src.rfind("self.accept()")
        self.assertGreater(
            accept_pos, try_pos,
            "self.accept() should appear after the try/except block",
        )
        # Make sure accept() is NOT inside the except branch
        except_pos = self.src.find("except")
        # accept() should come after the except clause ends (i.e. after the except block)
        # A simple heuristic: the last occurrence of self.accept() is after 'except'
        self.assertGreater(accept_pos, except_pos)


class TestSettingsDialogStructure(unittest.TestCase):
    """Static source checks for SettingsDialog._save_and_accept."""

    def setUp(self):
        self.src = _method_source(
            _SETTINGS_DIALOG_PATH, "SettingsDialog", "_save_and_accept"
        )

    def test_accept_called_unconditionally(self):
        self.assertIn("self.accept()", self.src)

    def test_save_wrapped_in_try(self):
        self.assertIn("try:", self.src)
        self.assertIn("s.save()", self.src)

    def test_except_clause_present(self):
        self.assertIn("except", self.src)

    def test_error_dialog_shown_on_failure(self):
        self.assertIn("QMessageBox.warning", self.src)


class TestInstallerSettingsPermissions(unittest.TestCase):
    """Verify both Inno Setup scripts grant Users write access on settings.json."""

    def _check_iss(self, path: Path, label: str):
        src = path.read_text(encoding="utf-8")
        self.assertIn(
            "icacls.exe",
            src,
            f"{label}: installer should call icacls.exe to set file permissions",
        )
        self.assertIn(
            "S-1-5-32-545",
            src,
            f"{label}: installer should grant access to BUILTIN\\Users (SID S-1-5-32-545)",
        )
        # The grant should include at least Modify (M) rights
        self.assertIn(
            ":(M)",
            src,
            f"{label}: installer should grant Modify (M) rights to allow settings writes",
        )

    def test_gpu_installer_grants_users_write(self):
        self._check_iss(_ISS_GPU_PATH, "GPU installer")

    def test_cpu_installer_grants_users_write(self):
        self._check_iss(_ISS_CPU_PATH, "CPU installer")


# ── Runtime tests (Qt required) ──────────────────────────────────────────────

@unittest.skipUnless(_qt_available(), "PySide6 not available")
class TestProSettingsDialogOKButton(unittest.TestCase):
    """Runtime tests that instantiate ProSettingsDialog with mocked deps."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import sys
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def _make_dialog(self):
        from speakeasy.config import Settings
        from speakeasy.pro_preset import load_all_presets
        from speakeasy.pro_settings_dialog import ProSettingsDialog
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        presets_dir = Path(self._tmpdir.name) / "presets"
        presets_dir.mkdir()
        settings = Settings()
        presets = load_all_presets(presets_dir)
        dlg = ProSettingsDialog(
            settings=settings,
            presets=presets,
            presets_dir=presets_dir,
            parent=None,
            api_key="",
        )
        return dlg

    def tearDown(self):
        if hasattr(self, "_tmpdir"):
            self._tmpdir.cleanup()

    def test_ok_closes_dialog_on_success(self):
        """Clicking OK with no errors should accept (close) the dialog."""
        dlg = self._make_dialog()
        accepted = []
        dlg.accepted.connect(lambda: accepted.append(True))

        with patch.object(dlg, "_save_settings"):
            dlg._save_and_accept()

        self.assertEqual(accepted, [True], "Dialog should have been accepted")

    def test_ok_closes_dialog_even_on_save_error(self):
        """Clicking OK must close the dialog even if _save_settings() raises."""
        dlg = self._make_dialog()
        accepted = []
        dlg.accepted.connect(lambda: accepted.append(True))

        with patch.object(dlg, "_save_settings", side_effect=PermissionError("Access denied")):
            with patch("speakeasy.pro_settings_dialog.QMessageBox") as mock_mb:
                dlg._save_and_accept()

        self.assertEqual(accepted, [True], "Dialog must close even when save raises")
        mock_mb.warning.assert_called_once()

    def test_ok_shows_error_message_on_permission_error(self):
        """A PermissionError should trigger a QMessageBox warning."""
        dlg = self._make_dialog()

        with patch.object(dlg, "_save_settings", side_effect=PermissionError("Access denied")):
            with patch("speakeasy.pro_settings_dialog.QMessageBox") as mock_mb:
                dlg._save_and_accept()

        args = mock_mb.warning.call_args
        # First positional arg is parent, second is title, third is message
        title = args[0][1]
        message = args[0][2]
        self.assertIn("Not Saved", title)
        self.assertIn("Access denied", message)

    def test_ok_does_not_show_error_on_success(self):
        """No error dialog should appear when save succeeds."""
        dlg = self._make_dialog()

        with patch.object(dlg, "_save_settings"):
            with patch("speakeasy.pro_settings_dialog.QMessageBox") as mock_mb:
                dlg._save_and_accept()

        mock_mb.warning.assert_not_called()
