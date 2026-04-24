"""
Settings dialog for SpeakEasy AI.

Provides a form to edit engine, model path, microphone, toggles, etc.
Changes are written back to the ``Settings`` dataclass on accept.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioRecorder
from ._build_variant import VARIANT
from .config import Settings

log = logging.getLogger(__name__)

# Cohere Transcribe 03-2026 supported languages
COHERE_LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("es", "Spanish"),
    ("pt", "Portuguese"),
    ("el", "Greek"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("zh", "Chinese (Mandarin)"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("vi", "Vietnamese"),
    ("ar", "Arabic"),
]


class SettingsDialog(QDialog):
    """Modal dialog for editing application settings."""

    def __init__(
        self,
        settings: Settings,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._build_ui()
        self._populate()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Model Engine group ───────────────────────────────────────────────
        engine_group = QGroupBox("Model Engine")
        engine_form = QFormLayout()

        model_row = QHBoxLayout()
        self._model_path = QLineEdit()
        self._model_path.setToolTip(
            "Folder containing the downloaded model weights.\n"
            "Use Browse\u2026 to locate the directory on disk."
        )
        btn_browse = QPushButton("Browse\u2026")
        btn_browse.clicked.connect(self._browse_model_path)
        model_row.addWidget(self._model_path)
        model_row.addWidget(btn_browse)
        engine_form.addRow("Model path:", model_row)

        self._device_combo = QComboBox()
        self._device_combo.addItems(["cuda", "cpu"])
        self._device_combo.setToolTip(
            "cuda (GPU): Uses your NVIDIA graphics card for transcription.\n"
            "Much faster — recommended if you have a GPU with ~5 GB of VRAM.\n\n"
            "cpu: Runs entirely on the processor — works on any machine,\n"
            "but transcription is significantly slower."
        )
        engine_form.addRow("Device:", self._device_combo)

        self._device_warning = QLabel(
            "\u26a0 CUDA is not available in the CPU edition."
            " Download and install the GPU version to use CUDA."
        )
        self._device_warning.setWordWrap(True)
        self._device_warning.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self._device_warning.setVisible(False)
        engine_form.addRow(self._device_warning)

        self._device_combo.currentTextChanged.connect(self._on_device_changed)

        self._language_combo = QComboBox()
        for code, label in COHERE_LANGUAGES:
            self._language_combo.addItem(f"{label} ({code})", code)
        self._language_combo.setToolTip(
            "The spoken language in your recordings.\n"
            "Choose the language you will be dictating in for best accuracy."
        )
        engine_form.addRow("Language:", self._language_combo)

        self._punctuation = QCheckBox("Enable automatic punctuation")
        self._punctuation.setToolTip(
            "Automatically inserts commas, periods, and other punctuation\n"
            "into the transcribed text based on natural speech patterns."
        )
        engine_form.addRow(self._punctuation)

        self._inference_timeout = QSpinBox()
        self._inference_timeout.setRange(5, 300)
        self._inference_timeout.setSuffix(" s")
        self._inference_timeout.setToolTip(
            "Maximum time (in seconds) to wait for a transcription to finish\n"
            "before giving up. Increase this if long recordings are timing out."
        )
        engine_form.addRow("Inference timeout:", self._inference_timeout)

        engine_group.setLayout(engine_form)
        layout.addWidget(engine_group)

        # ── Audio group ──────────────────────────────────────────────────────
        audio_group = QGroupBox("Audio")
        audio_form = QFormLayout()

        self._mic_combo = QComboBox()
        self._mic_combo.addItem("System default", -1)
        try:
            for idx, name in AudioRecorder.list_input_devices():
                self._mic_combo.addItem(f"[{idx}] {name}", idx)
        except Exception:
            log.warning("Could not enumerate audio devices", exc_info=True)
        self._mic_combo.setToolTip(
            "The audio input device used for recording.\n"
            "Select your microphone from the list, or leave as System default."
        )
        audio_form.addRow("Microphone:", self._mic_combo)

        self._silence_threshold = QDoubleSpinBox()
        self._silence_threshold.setRange(0.0001, 0.1)
        self._silence_threshold.setDecimals(4)
        self._silence_threshold.setSingleStep(0.0005)
        self._silence_threshold.setToolTip(
            "How quiet the audio must be to count as silence and stop recording.\n"
            "Lower value = more sensitive (stops sooner on quiet speech).\n"
            "Higher value = requires more obvious silence before stopping."
        )
        audio_form.addRow("Silence threshold (RMS):", self._silence_threshold)

        self._silence_margin = QSpinBox()
        self._silence_margin.setRange(50, 1000)
        self._silence_margin.setSuffix(" ms")
        self._silence_margin.setToolTip(
            "Extra time to continue recording after silence is detected (in milliseconds).\n"
            "Increase this if the end of your sentences is being clipped."
        )
        audio_form.addRow("Silence margin:", self._silence_margin)

        self._sample_rate = QSpinBox()
        self._sample_rate.setRange(8000, 48000)
        self._sample_rate.setSingleStep(8000)
        self._sample_rate.setSuffix(" Hz")
        self._sample_rate.setToolTip(
            "Recording quality in samples per second.\n"
            "16000 Hz is the standard for speech recognition and recommended for most users.\n"
            "Higher values use more memory with no accuracy benefit."
        )
        audio_form.addRow("Sample rate (recording):", self._sample_rate)

        audio_group.setLayout(audio_form)
        layout.addWidget(audio_group)

        # ── Dictation UX group ───────────────────────────────────────────────
        ux_group = QGroupBox("Dictation UX")
        ux_form = QFormLayout()

        self._auto_copy = QCheckBox("Auto-copy transcription to clipboard")
        self._auto_copy.setToolTip(
            "Automatically copies the transcribed text to your clipboard\n"
            "after each recording completes."
        )
        ux_form.addRow(self._auto_copy)

        self._auto_paste = QCheckBox("Auto-paste (Ctrl+V) after copy")
        self._auto_paste.setToolTip(
            "Simulates a Ctrl+V keypress after copying, pasting the transcribed text\n"
            "directly into whatever application is currently focused."
        )
        ux_form.addRow(self._auto_paste)

        self._hotkeys_enabled = QCheckBox("Enable global hotkeys")
        self._hotkeys_enabled.setToolTip(
            "Allows the record hotkey to trigger even when SpeakEasy\n"
            "is not the focused window (runs in the background)."
        )
        ux_form.addRow(self._hotkeys_enabled)

        self._hotkey_start = QLineEdit()
        self._hotkey_start.setToolTip(
            "Keyboard shortcut to start and stop recording.\n"
            "Format: modifier+key, e.g. ctrl+alt+p or ctrl+shift+r.\n"
            "Requires global hotkeys to be enabled."
        )
        ux_form.addRow("Record hotkey:", self._hotkey_start)

        self._hotkey_quit = QLineEdit()
        self._hotkey_quit.setToolTip(
            "Keyboard shortcut to close SpeakEasy from anywhere.\n"
            "Format: modifier+key, e.g. ctrl+alt+q."
        )
        ux_form.addRow("Quit hotkey:", self._hotkey_quit)

        self._clear_logs_on_exit = QCheckBox("Clear logs on application exit")
        self._clear_logs_on_exit.setToolTip(
            "Erases the contents of the diagnostic log panel\n"
            "each time the application closes."
        )
        ux_form.addRow(self._clear_logs_on_exit)

        self._streaming_partials = QCheckBox(
            "Show live transcription as you speak (chunk-by-chunk)"
        )
        _streaming_tip = (
            "Long recordings are transcribed in ~30 s chunks; when enabled,\n"
            "each chunk appears in the history pane as soon as it is ready\n"
            "instead of waiting for the whole recording to finish.\n"
            "Auto-copy and auto-paste still fire once, on the final result."
        )
        if VARIANT == "cpu":
            _streaming_tip += (
                "\n\nNote: on CPU builds each chunk takes longer to render\n"
                "than on GPU; disable this if your machine is slow."
            )
        self._streaming_partials.setToolTip(_streaming_tip)
        ux_form.addRow(self._streaming_partials)

        ux_group.setLayout(ux_form)
        layout.addWidget(ux_group)

        # ── Button box ───────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Populate / Save ──────────────────────────────────────────────────────

    def _populate(self) -> None:
        s = self.settings
        self._model_path.setText(s.model_path)
        idx = self._device_combo.findText(s.device)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)
        idx = self._language_combo.findData(s.language)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        self._punctuation.setChecked(s.punctuation)
        self._inference_timeout.setValue(s.inference_timeout)
        self._silence_threshold.setValue(s.silence_threshold)
        self._silence_margin.setValue(s.silence_margin_ms)
        self._sample_rate.setValue(s.sample_rate)
        self._auto_copy.setChecked(s.auto_copy)
        self._auto_paste.setChecked(s.auto_paste)
        self._hotkeys_enabled.setChecked(s.hotkeys_enabled)
        self._hotkey_start.setText(s.hotkey_start)
        self._hotkey_quit.setText(s.hotkey_quit)
        self._clear_logs_on_exit.setChecked(s.clear_logs_on_exit)
        self._streaming_partials.setChecked(s.streaming_partials_enabled)

        # Select current mic device
        idx = self._mic_combo.findData(s.mic_device_index)
        if idx >= 0:
            self._mic_combo.setCurrentIndex(idx)

        self._on_device_changed(self._device_combo.currentText())

    def _save_and_accept(self) -> None:
        s = self.settings
        s.model_path = self._model_path.text().strip()
        s.device = self._device_combo.currentText()
        s.language = self._language_combo.currentData() or "en"
        s.punctuation = self._punctuation.isChecked()
        s.inference_timeout = self._inference_timeout.value()
        s.silence_threshold = self._silence_threshold.value()
        s.silence_margin_ms = self._silence_margin.value()
        s.sample_rate = self._sample_rate.value()
        s.auto_copy = self._auto_copy.isChecked()
        s.auto_paste = self._auto_paste.isChecked()
        s.hotkeys_enabled = self._hotkeys_enabled.isChecked()
        s.hotkey_start = self._hotkey_start.text().strip() or "ctrl+alt+p"
        s.hotkey_quit = self._hotkey_quit.text().strip() or "ctrl+alt+q"
        s.clear_logs_on_exit = self._clear_logs_on_exit.isChecked()
        s.streaming_partials_enabled = self._streaming_partials.isChecked()
        s.mic_device_index = self._mic_combo.currentData()

        try:
            s.save()
            log.info("Settings saved")
        except Exception as exc:
            log.error("Failed to save settings: %s", exc, exc_info=True)
            QMessageBox.warning(
                self,
                "Settings Not Saved",
                "Your settings could not be saved to disk:\n\n"
                f"{exc}\n\n"
                "Changes will remain active for this session only.\n"
                "To fix permanently, re-run the installer to repair file permissions.",
            )
        self.accept()

    def _on_device_changed(self, device: str) -> None:
        cuda_blocked = VARIANT == "cpu" and device == "cuda"
        self._device_warning.setVisible(cuda_blocked)
        self._ok_button.setEnabled(not cuda_blocked)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _browse_model_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Model Directory",
            self._model_path.text(),
        )
        if path:
            self._model_path.setText(path)
