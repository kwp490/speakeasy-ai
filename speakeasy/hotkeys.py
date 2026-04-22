"""
Global hotkey management.

Wraps the ``keyboard`` library so hotkeys can be enabled/disabled at runtime
and callbacks are dispatched as Qt signals for thread-safe UI updates.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class HotkeyManager(QObject):
    """Registers/unregisters global hotkeys and emits Qt signals on activation."""

    # Emitted from the keyboard hook thread; Qt auto-queues to the main thread.
    toggle_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._enabled = False
        self._hooks: list = []
        self._hotkey_start: Optional[str] = None
        self._hotkey_quit: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def register(
        self,
        hotkey_start: str = "ctrl+alt+p",
        hotkey_quit: str = "ctrl+alt+q",
    ) -> None:
        """Register the dictation hotkeys.  Safe to call repeatedly."""
        import keyboard

        self._hotkey_start = hotkey_start
        self._hotkey_quit = hotkey_quit
        self.unregister()
        try:
            self._hooks = [
                keyboard.add_hotkey(hotkey_start, self._on_toggle, suppress=False),
                keyboard.add_hotkey(hotkey_quit, self._on_quit, suppress=False),
            ]
            self._enabled = True
            log.info(
                "Hotkeys registered: record=%s  quit=%s",
                hotkey_start,
                hotkey_quit,
            )
        except Exception:
            log.error("Failed to register hotkeys", exc_info=True)
            self._enabled = False

    def unregister(self) -> None:
        """Remove all hotkey hooks and stop the listener thread."""
        if not self._enabled:
            return
        try:
            import keyboard

            for hook in self._hooks:
                keyboard.remove_hotkey(hook)
            # unhook_all() tears down the non-daemon listener thread that
            # keyboard starts internally; without it the process hangs.
            keyboard.unhook_all()
        except Exception:
            log.warning("Error unhooking hotkeys", exc_info=True)
        self._hooks.clear()
        self._enabled = False
        log.info("Hotkeys unregistered")

    def re_register(self) -> None:
        """Re-register hotkeys using previously saved bindings.

        Call after system resume from sleep — Windows silently invalidates
        low-level keyboard hooks (WH_KEYBOARD_LL) during sleep/wake transitions.
        """
        if self._hotkey_start is not None:
            log.info("Re-registering hotkeys after system resume")
            self.register(self._hotkey_start, self._hotkey_quit)

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ── Callbacks (run on keyboard hook thread) ──────────────────────────────

    def _on_toggle(self) -> None:
        self.toggle_requested.emit()

    def _on_quit(self) -> None:
        self.quit_requested.emit()
