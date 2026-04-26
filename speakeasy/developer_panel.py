"""
Developer Panel — a snapped-but-movable side window with tabs for
Settings, Realtime Data, Logs, and Pro Mode.

Opened from the gear button on the main window or via a global hotkey.
Closing the panel hides it; reopening restores the last active tab.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint, QSize, Signal, QTimer
from PySide6.QtGui import QCloseEvent, QColor, QFont, QPainter, QPen, QResizeEvent, QMoveEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import Settings
from .settings_dialog import SettingsWidget

if TYPE_CHECKING:
    from .main_window import MainWindow

log = logging.getLogger(__name__)

# Tab keys — must match Settings.dev_panel_active_tab valid values
TAB_SETTINGS = "settings"
TAB_REALTIME = "realtime"
TAB_LOGS = "logs"
TAB_PRO = "pro"


# ═══════════════════════════════════════════════════════════════════════════════
# Token sparkline chart
# ═══════════════════════════════════════════════════════════════════════════════


class TokenSparkline(QWidget):
    """Tiny custom-painted line chart for token throughput."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._data: list[float] = []
        self.setMinimumHeight(60)
        self.setMinimumWidth(200)

    def set_data(self, data: list[float]) -> None:
        self._data = list(data)
        self.update()

    def paintEvent(self, event) -> None:
        if not self._data:
            return
        from .theme import Color
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(Color.INPUT_BG))
        max_v = max(self._data) or 1.0
        w, h = self.width(), self.height()
        step = w / max(len(self._data) - 1, 1)
        pen = QPen(QColor(Color.PRIMARY))
        pen.setWidth(2)
        p.setPen(pen)
        prev = None
        for i, v in enumerate(self._data):
            x = i * step
            y = h - (v / max_v) * (h - 4) - 2
            if prev is not None:
                p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
            prev = (x, y)
        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# Realtime Data widget
# ═══════════════════════════════════════════════════════════════════════════════


class RealtimeDataWidget(QWidget):
    """Live engine status, RAM/VRAM/GPU metrics, audio meter, LLM token throughput."""

    reload_model_requested = Signal()
    validate_requested = Signal()

    TOKEN_HISTORY_LEN = 60  # last 60 samples

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tok_history: list[float] = []
        self._build_ui()

    def _build_ui(self) -> None:
        from .theme import Color, Font, Size, Spacing, make_section

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.XL)

        # ── Model Engine section ─────────────────────────────────────────────
        engine_sec, engine_form = make_section("Model Engine", self)

        self._lbl_engine = QLabel("Engine: —  \u00b7  Device: —")
        self._lbl_engine.setFont(QFont(Font.FAMILY, Font.BODY[0]))
        engine_form.addRow("Engine / Device", self._lbl_engine)

        self._lbl_model_status = QLabel("Status: Not loaded")
        self._lbl_model_status.setFont(QFont(Font.FAMILY, Font.BODY[0]))
        self._lbl_model_status.setTextFormat(Qt.TextFormat.RichText)
        engine_form.addRow("Status", self._lbl_model_status)

        self._lbl_ram = QLabel("RAM: —")
        self._lbl_ram.setFont(QFont(Font.FAMILY, Font.LABEL[0]))
        self._pb_ram = QProgressBar()
        self._pb_ram.setMinimum(0)
        self._pb_ram.setMaximum(100)
        self._pb_ram.setValue(0)
        self._pb_ram.setFixedHeight(Size.PROGRESS_BAR_HEIGHT)
        self._pb_ram.setTextVisible(False)
        engine_form.addRow("RAM", self._build_metric_row(self._lbl_ram, self._pb_ram))

        self._lbl_vram = QLabel("VRAM: —")
        self._lbl_vram.setFont(QFont(Font.FAMILY, Font.LABEL[0]))
        self._pb_vram = QProgressBar()
        self._pb_vram.setMinimum(0)
        self._pb_vram.setMaximum(100)
        self._pb_vram.setValue(0)
        self._pb_vram.setFixedHeight(Size.PROGRESS_BAR_HEIGHT)
        self._pb_vram.setTextVisible(False)
        engine_form.addRow("VRAM", self._build_metric_row(self._lbl_vram, self._pb_vram))

        self._lbl_gpu_info = QLabel("GPU: —")
        self._lbl_gpu_info.setFont(QFont(Font.FAMILY, Font.LABEL[0]))
        engine_form.addRow("GPU", self._lbl_gpu_info)

        btn_row_engine = QHBoxLayout()
        self._btn_reload = QPushButton("Reload Model")
        self._btn_reload.clicked.connect(self.reload_model_requested)
        self._btn_validate = QPushButton("Validate")
        self._btn_validate.clicked.connect(self.validate_requested)
        btn_row_engine.addWidget(self._btn_reload)
        btn_row_engine.addWidget(self._btn_validate)
        btn_row_engine.addStretch()
        engine_sec.layout().addLayout(btn_row_engine)

        layout.addWidget(engine_sec)

        # ── Audio section ────────────────────────────────────────────────────
        audio_sec, audio_form = make_section("Audio", self)
        self._pb_audio = QProgressBar()
        self._pb_audio.setMinimum(0)
        self._pb_audio.setMaximum(100)
        self._pb_audio.setValue(0)
        self._pb_audio.setFixedHeight(Spacing.MD)
        self._pb_audio.setTextVisible(False)
        audio_form.addRow("Input level", self._pb_audio)
        layout.addWidget(audio_sec)

        # ── LLM Throughput section ───────────────────────────────────────────
        tok_sec, tok_form = make_section("LLM Throughput", self)

        self._lbl_tok_rate = QLabel("0 tok/s")
        self._lbl_tok_rate.setFont(QFont(Font.FAMILY, Font.BODY[0]))
        tok_form.addRow("Rate", self._lbl_tok_rate)

        self._lbl_tok_in = QLabel("0 in")
        self._lbl_tok_in.setFont(QFont(Font.FAMILY, Font.LABEL[0]))
        tok_form.addRow("Tokens in", self._lbl_tok_in)

        self._lbl_tok_out = QLabel("0 out")
        self._lbl_tok_out.setFont(QFont(Font.FAMILY, Font.LABEL[0]))
        tok_form.addRow("Tokens out", self._lbl_tok_out)

        self._sparkline = TokenSparkline(self)
        self._sparkline_empty_label = QLabel("No LLM activity yet")
        self._sparkline_empty_label.setStyleSheet(f"color: {Color.TEXT_MUTED};")
        tok_sec.layout().addWidget(self._sparkline_empty_label)
        self._sparkline.hide()
        tok_sec.layout().addWidget(self._sparkline)

        layout.addWidget(tok_sec)

        layout.addStretch()

    def _build_metric_row(self, label: QLabel, bar: QProgressBar) -> QWidget:
        from .theme import Spacing
        w = QWidget(self)
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(Spacing.SM)
        h.addWidget(label)
        h.addWidget(bar, stretch=1)
        return w

    # ── Update methods called by MainWindow ───────────────────────────────────

    def update_engine_status(self, engine: str, device: str, status: str, color: str) -> None:
        device_label = "GPU" if device == "cuda" else "CPU"
        self._lbl_engine.setText(f"Engine: {engine}  \u00b7  Device: {device_label}")
        self._lbl_model_status.setText(
            f'Status: <span style="color:{color}"><b>{status}</b></span>'
        )

    @staticmethod
    def _color_for_percent(pct: float) -> str:
        from .theme import Color
        if pct >= 90:
            return Color.DANGER
        if pct >= 75:
            return Color.WARNING
        return Color.PRIMARY

    @staticmethod
    def _bar_style(pct: float) -> str:
        from .theme import Color
        c = RealtimeDataWidget._color_for_percent(pct)
        return (
            f"QProgressBar {{ border: 1px solid {Color.BORDER}; "
            f"border-radius: 3px; background: {Color.INPUT_BG}; }}"
            f"QProgressBar::chunk {{ background-color: {c}; "
            f"border-radius: 3px; }}"
        )

    def update_ram(self, used_gb: float, total_gb: float, percent: float) -> None:
        if total_gb > 0:
            self._lbl_ram.setText(
                f"RAM: {used_gb:.1f} / {total_gb:.1f} GB ({percent:.0f}%)"
            )
            self._pb_ram.setValue(int(percent))
            self._pb_ram.setStyleSheet(self._bar_style(percent))
        else:
            self._lbl_ram.setText("RAM: —")
            self._pb_ram.setValue(0)

    def update_vram(self, used_gb: float, total_gb: float, percent: float, color: str = "") -> None:
        if total_gb > 0:
            self._lbl_vram.setText(
                f"VRAM: {used_gb:.1f} / {total_gb:.1f} GB ({percent:.0f}%)"
            )
            self._pb_vram.setValue(int(percent))
            self._pb_vram.setStyleSheet(self._bar_style(percent))
        else:
            self._lbl_vram.setText("VRAM: —")
            self._pb_vram.setValue(0)

    def update_gpu(self, label: str) -> None:
        self._lbl_gpu_info.setText(f"GPU: {label}")

    def update_audio_level(self, rms: float) -> None:
        self._pb_audio.setValue(int(min(1.0, max(0.0, rms)) * 100))

    def update_tokens(self, tok_per_sec: float, tokens_in: int, tokens_out: int) -> None:
        self._lbl_tok_rate.setText(f"{tok_per_sec:.0f} tok/s")
        self._lbl_tok_in.setText(f"{tokens_in:,} in")
        self._lbl_tok_out.setText(f"{tokens_out:,} out")
        self._tok_history.append(tok_per_sec)
        if len(self._tok_history) > self.TOKEN_HISTORY_LEN:
            self._tok_history.pop(0)
        self._sparkline.set_data(self._tok_history)
        if not self._sparkline.isVisible():
            self._sparkline_empty_label.hide()
            self._sparkline.show()


# ═══════════════════════════════════════════════════════════════════════════════
# Color-coded log view
# ═══════════════════════════════════════════════════════════════════════════════


class ColorCodedLogView(QPlainTextEdit):
    """QPlainTextEdit that detects log level keywords and colors the line."""

    LEVEL_COLORS: dict[str, str] = {}  # populated lazily

    @classmethod
    def _ensure_colors(cls) -> None:
        if not cls.LEVEL_COLORS:
            from .theme import Color
            cls.LEVEL_COLORS = {
                "ERROR":    Color.LOG_ERROR,
                "CRITICAL": Color.LOG_ERROR,
                "WARNING":  Color.LOG_WARN,
                "WARN":     Color.LOG_WARN,
                "INFO":     Color.LOG_INFO,
                "DEBUG":    Color.TEXT_MUTED,
            }

    def append_log_line(self, line: str) -> None:
        color = self._color_for(line)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.document().isEmpty():
            cursor.insertBlock()
        cursor.setCharFormat(fmt)
        cursor.insertText(line)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _color_for(self, line: str) -> QColor:
        self._ensure_colors()
        head = line[:30].upper()
        for keyword, color_hex in self.LEVEL_COLORS.items():
            if keyword in head:
                return QColor(color_hex)
        from .theme import Color
        return QColor(Color.LOG_INFO)


# ═══════════════════════════════════════════════════════════════════════════════
# Logs widget
# ═══════════════════════════════════════════════════════════════════════════════


class LogsWidget(QWidget):
    """Tab page wrapping the ColorCodedLogView + Clear/Copy buttons."""

    clear_requested = Signal()
    copy_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        from .theme import Font, Spacing

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XS, Spacing.XS, Spacing.XS, Spacing.XS)

        log_header = QHBoxLayout()
        log_header.addStretch()
        btn_clear = QPushButton("\U0001f5d1  Clear Logs")
        btn_clear.clicked.connect(self.clear_requested)
        btn_copy = QPushButton("\U0001f4cb  Copy Logs")
        btn_copy.clicked.connect(self.copy_requested)
        log_header.addWidget(btn_clear)
        log_header.addWidget(btn_copy)
        layout.addLayout(log_header)

        self._log_text = ColorCodedLogView()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        self._log_text.setFont(QFont(Font.FAMILY_MONO, Font.LOG[0]))
        self._log_text.setPlaceholderText("No logs yet. Activity will appear here as the app runs.")
        layout.addWidget(self._log_text)

    @property
    def log_text(self) -> ColorCodedLogView:
        return self._log_text


# ═══════════════════════════════════════════════════════════════════════════════
# Developer Panel
# ═══════════════════════════════════════════════════════════════════════════════


class DeveloperPanel(QWidget):
    """Snapped-but-movable side window with tabbed dev tools."""

    closed = Signal()

    SNAP_THRESHOLD_PX = 30  # within this distance of the main window's right edge → re-snap

    def __init__(self, settings: Settings, main_window: "MainWindow") -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Developer Panel")
        self.settings = settings
        self._main_window = main_window
        self._snapped = settings.dev_panel_snapped
        self._suppress_move_persist = False  # True during programmatic moves
        self._build_ui()
        self._wire_signals()
        self.resize(settings.dev_panel_width, settings.dev_panel_height)
        self.setMinimumWidth(320)
        self.setMaximumWidth(800)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from .theme import Font, Spacing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.SM)

        self._tabs = QTabWidget()
        self._tabs.setFont(QFont(Font.FAMILY, Font.BODY[0]))
        layout.addWidget(self._tabs)

        # Tab 0: Settings
        self._settings_widget = SettingsWidget(self.settings, self)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(self._settings_widget)
        self._tabs.addTab(settings_scroll, "\u2699\ufe0f  Settings")

        # Tab 1: Realtime Data
        self.realtime_widget = RealtimeDataWidget(self)
        self._tabs.addTab(self.realtime_widget, "\U0001f4ca  Realtime Data")

        # Tab 2: Logs
        self.logs_widget = LogsWidget(self)
        self._tabs.addTab(self.logs_widget, "\U0001f4cb  Logs")

        # Tab 3: Pro Mode
        from .pro_mode_widget import ProModeWidget  # noqa: F811

        self.pro_mode_widget = ProModeWidget(
            settings=self.settings,
            on_disclosure_required=self._show_pro_disclosure,
            parent=self,
        )
        pro_scroll = QScrollArea()
        pro_scroll.setWidgetResizable(True)
        pro_scroll.setWidget(self.pro_mode_widget)
        self._tabs.addTab(pro_scroll, "\U0001f4bc  Pro Mode")

        # Restore last active tab
        self._tabs.setCurrentIndex(self._tab_key_to_index(self.settings.dev_panel_active_tab))
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _wire_signals(self) -> None:
        # Settings tab
        self._settings_widget.reload_model_requested.connect(self._main_window._on_reload_model)
        self._settings_widget.settings_applied.connect(self._main_window._apply_settings)
        # Realtime tab
        self.realtime_widget.reload_model_requested.connect(self._main_window._on_reload_model)
        self.realtime_widget.validate_requested.connect(self._main_window._on_validate)
        # Logs tab
        self.logs_widget.clear_requested.connect(self._main_window._on_clear_logs)
        self.logs_widget.copy_requested.connect(self._main_window._on_copy_logs)
        # Pro Mode tab
        self.pro_mode_widget.settings_applied.connect(self._main_window._on_pro_mode_applied)
        self.pro_mode_widget.presets_changed.connect(self._main_window._populate_pro_preset_combo)

    def _show_pro_disclosure(self) -> bool:
        """Show data-privacy disclosure; return True if the user accepts."""
        from PySide6.QtWidgets import QMessageBox

        disc = QMessageBox(self)
        disc.setIcon(QMessageBox.Icon.Warning)
        disc.setWindowTitle("Data Privacy Notice: Optional Professional Mode")
        disc.setText(
            "All transcription is local to this machine and is not stored, "
            "externally transmitted, or logged."
        )
        disc.setInformativeText(
            "If you choose to enable <b>Professional Mode</b>, dictation results will "
            "be transmitted to <b>api.openai.com</b> under your specified "
            "OpenAI API key.<br><br>"
            "&#x26a0;&#xfe0f;&nbsp; Do not dictate confidential content, "
            "including personal data (PII/PHI), financial records, "
            "proprietary business information, or content that identifies "
            "colleagues or customers.<br><br>"
            "By clicking <b>I Understand</b> you acknowledge this notice. "
            "It will not be shown again."
        )
        disc.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        disc.setDefaultButton(QMessageBox.StandardButton.Cancel)
        disc.button(QMessageBox.StandardButton.Ok).setText("I Understand")
        if disc.exec() == QMessageBox.StandardButton.Ok:
            self.settings.pro_disclosure_accepted = True
            self.settings.save()
            return True
        return False

    # ── Snapping ──────────────────────────────────────────────────────────────

    def show_snapped(self) -> None:
        """Show the panel; if snapped, position it to the right of the main window."""
        if self._snapped:
            self._snap_to_main()
        self.show()
        self.raise_()
        self.activateWindow()

    def _snap_to_main(self) -> None:
        mw = self._main_window
        geom = mw.frameGeometry()
        target = QPoint(geom.right() + 1, geom.top())
        self._suppress_move_persist = True
        self.move(target)
        self.resize(self.settings.dev_panel_width, geom.height())
        self._suppress_move_persist = False

    def on_main_window_moved(self) -> None:
        """Called by MainWindow when its position or size changes."""
        if self._snapped and self.isVisible():
            self._snap_to_main()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _tab_key_to_index(key: str) -> int:
        return {TAB_SETTINGS: 0, TAB_REALTIME: 1, TAB_LOGS: 2, TAB_PRO: 3}.get(key, 0)

    @staticmethod
    def _index_to_tab_key(idx: int) -> str:
        return [TAB_SETTINGS, TAB_REALTIME, TAB_LOGS, TAB_PRO][idx] if 0 <= idx < 4 else TAB_SETTINGS

    def _on_tab_changed(self, idx: int) -> None:
        self.settings.dev_panel_active_tab = self._index_to_tab_key(idx)
        self.settings.save()

    def activate_tab(self, key: str) -> None:
        """Switch to the tab identified by *key* (e.g. TAB_PRO)."""
        self._tabs.setCurrentIndex(self._tab_key_to_index(key))

    # ── Geometry persistence ──────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        # Hide instead of destroying so reopen is fast
        event.ignore()
        self.hide()
        self.closed.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._suppress_move_persist:
            self.settings.dev_panel_width = self.width()
            self.settings.dev_panel_height = self.height()
            self.settings.save()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        if self._suppress_move_persist:
            return
        # User dragged the panel — check if they pulled it away from the main window's edge
        mw_right = self._main_window.frameGeometry().right()
        delta = abs(self.frameGeometry().left() - (mw_right + 1))
        new_snapped = delta <= self.SNAP_THRESHOLD_PX
        if new_snapped != self._snapped:
            self._snapped = new_snapped
            self.settings.dev_panel_snapped = new_snapped
            self.settings.save()
