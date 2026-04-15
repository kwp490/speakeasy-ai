"""
dictat0r.AI — entry point.

Usage:
    python -m dictator                                          # launch GUI
    python -m dictator download-model --engine granite          # download model
    python -m dictator --version                                # print version

Handles single-instance guard, logging setup, and Qt application lifecycle.
"""

from __future__ import annotations

import argparse
import ctypes
import faulthandler
import io
import logging
import logging.handlers
import multiprocessing
import os
import sys


# ── Stdout/stderr safety (needed for PyInstaller --noconsole builds) ─────────
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()


# ── Single-instance mutex (Windows) ──────────────────────────────────────────

_MUTEX_NAME = "Global\\Dictator0rAIMutex"
_mutex_handle = None


def release_single_instance_mutex() -> None:
    """Release the single-instance mutex so a restarted process can acquire it."""
    global _mutex_handle
    if _mutex_handle is not None:
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)  # type: ignore[attr-defined]
        except Exception:
            pass
        _mutex_handle = None


def _ensure_single_instance() -> bool:
    """Return True if this is the only running instance."""
    global _mutex_handle
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        _mutex_handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        return True
    except Exception:
        # Non-Windows or ctypes not available — skip guard
        return True


# ── Logging ──────────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    from dictator.config import DEFAULT_LOG_DIR

    log_dir = str(DEFAULT_LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "dictator.log")

    # Use a UTF-8 stream for the console handler so Unicode characters
    # don't crash on Windows cp1252 consoles.
    # In PyInstaller --noconsole builds sys.stdout has no real fd.
    try:
        _console_stream = open(
            sys.stdout.fileno(), mode="w", encoding="utf-8",
            errors="replace", closefd=False,
        )
    except (io.UnsupportedOperation, OSError):
        _console_stream = None

    handlers = [
        logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
        ),
    ]
    if _console_stream is not None:
        handlers.append(logging.StreamHandler(_console_stream))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    logging.getLogger("dictator").info("=== dictat0r.AI starting (log: %s) ===", log_path)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dictator",
        description="dictat0r.AI — Native Windows Voice-to-Text",
    )
    parser.add_argument(
        "--version", action="store_true", help="Print version and exit"
    )

    sub = parser.add_subparsers(dest="command")

    dl = sub.add_parser("download-model", help="Download model weights")
    dl.add_argument(
        "--engine",
        choices=["granite", "cohere"],
        required=True,
        help="Engine whose model to download",
    )
    dl.add_argument(
        "--target-dir",
        default=None,
        help="Directory to store models (default: C:\\Program Files\\dictat0r.AI\\models)",
    )
    dl.add_argument(
        "--token",
        default=None,
        help="HuggingFace access token for gated model downloads",
    )

    return parser


def _cmd_download_model(args: argparse.Namespace) -> int:
    """Handle the download-model subcommand."""
    from dictator.config import DEFAULT_MODELS_DIR
    from dictator.model_downloader import download_model

    target_dir = args.target_dir or DEFAULT_MODELS_DIR
    os.makedirs(target_dir, exist_ok=True)

    return download_model(args.engine, target_dir, token=args.token)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        from dictator import __version__
        print(f"dictat0r.AI {__version__}")
        return 0

    if args.command == "download-model":
        _setup_logging()
        return _cmd_download_model(args)

    # Default: launch GUI
    try:
        faulthandler.enable()
    except io.UnsupportedOperation:
        pass  # stderr has no fileno() in PyInstaller --noconsole builds

    if not _ensure_single_instance():
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            _app = QApplication(sys.argv)
            QMessageBox.warning(None, "dictat0r.AI", "Another instance is already running.")
        except Exception:
            print("ERROR: Another instance of dictat0r.AI is already running.")
        return 1

    _setup_logging()

    from PySide6.QtWidgets import QApplication
    from dictator.config import Settings
    from dictator.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("dictat0r.AI")
    app.setOrganizationName("dictat0r.AI")

    settings = Settings.load()

    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
