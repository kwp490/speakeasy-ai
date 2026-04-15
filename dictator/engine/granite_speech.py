"""
IBM Granite 4.0 1B Speech engine.

Uses the ``AutoModelForSpeechSeq2Seq`` model from HuggingFace transformers
for efficient on-device speech recognition (1B parameters, bfloat16).

Supported languages: en, fr, de, es, pt, ja.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import queue
import sys
import time
from multiprocessing.connection import Connection
from typing import Any

import numpy as np

from .base import SpeechEngine

log = logging.getLogger(__name__)

GRANITE_REPO_ID = "ibm-granite/granite-4.0-1b-speech"


def _load_granite_runtime(granite_dir: str, device: str):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    processor = AutoProcessor.from_pretrained(granite_dir)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        granite_dir,
        dtype=torch.bfloat16 if device == "cuda" else torch.float32,
    )
    model = model.to(device if device == "cuda" else "cpu")
    model.eval()
    return processor, model


def _transcribe_with_runtime(
    processor,
    model,
    device: str,
    audio_16k: np.ndarray,
    language: str,
    keywords: str = "",
) -> str:
    import torch

    user_prompt = (
        "<|audio|>Transcribe the speech into a written format with "
        "proper punctuation and capitalization."
    )
    if keywords and keywords.strip():
        user_prompt += f" Keywords: {keywords.strip()}"
    chat = [{"role": "user", "content": user_prompt}]
    prompt = processor.tokenizer.apply_chat_template(
        chat, tokenize=False, add_generation_prompt=True,
    )

    audio_tensor = torch.tensor(np.ascontiguousarray(audio_16k, dtype=np.float32))
    model_inputs = processor(
        prompt, audio_tensor, device="cpu", return_tensors="pt",
    )
    del audio_tensor

    model_inputs = {
        key: value.to(model.device) if hasattr(value, "to") else value
        for key, value in model_inputs.items()
    }

    with torch.inference_mode():
        output_ids = model.generate(**model_inputs, max_new_tokens=512)

    input_len = model_inputs["input_ids"].shape[-1]
    text = processor.tokenizer.decode(
        output_ids[0, input_len:].detach().cpu(), skip_special_tokens=True,
    )
    return text.strip()


def _granite_worker_main(conn: Connection, granite_dir: str, device: str) -> None:
    # In a PyInstaller frozen build, the spawned child process needs
    # _MEIPASS (_internal/) and torch/lib/ on the DLL search path so
    # shm.dll can find its transitive dependencies (c10.dll → vcruntime140.dll).
    # The runtime hook handles this for the parent, but a spawned child
    # re-executes the bootloader; belt-and-suspenders ensures coverage.
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass is not None and sys.platform == "win32":
        torch_lib = os.path.join(_meipass, "torch", "lib")
        for d in (_meipass, torch_lib):
            if os.path.isdir(d):
                os.add_dll_directory(d)
        extra = os.pathsep.join(d for d in (_meipass, torch_lib) if os.path.isdir(d))
        if extra:
            os.environ["PATH"] = extra + os.pathsep + os.environ.get("PATH", "")

    processor = None
    model = None
    try:
        processor, model = _load_granite_runtime(granite_dir, device)
        conn.send({"status": "ready"})

        while True:
            request = conn.recv()
            command = request.get("cmd")

            if command == "shutdown":
                conn.send({"status": "bye"})
                return

            if command == "transcribe":
                text = _transcribe_with_runtime(
                    processor,
                    model,
                    device,
                    request["audio"],
                    request.get("language", "en"),
                    keywords=request.get("keywords", ""),
                )
                conn.send({"status": "ok", "text": text})
                continue

            conn.send({"status": "error", "error": f"Unknown command: {command}"})
    except BaseException as exc:
        try:
            conn.send({"status": "error", "error": str(exc)})
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
        if model is not None:
            try:
                del model
            except Exception:
                pass


class GraniteSpeechEngine(SpeechEngine):
    """IBM Granite 4.0 1B Speech — compact 1B parameter ASR model."""

    def __init__(self) -> None:
        super().__init__()
        self._device: str = "cuda"
        self._worker_process: multiprocessing.Process | None = None
        self._worker_conn: Connection | None = None

    def _make_mp_context(self):
        return multiprocessing.get_context("spawn")

    def _recv_worker_message(self, action: str, timeout_s: float = 300.0) -> dict[str, Any]:
        if self._worker_conn is None or self._worker_process is None:
            raise RuntimeError("Granite worker not running")

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._worker_conn.poll(0.1):
                return self._worker_conn.recv()
            if not self._worker_process.is_alive():
                raise RuntimeError(f"Granite worker process crashed during {action}")
        raise TimeoutError(f"Timed out waiting for Granite worker during {action}")

    def _close_worker(self) -> None:
        if self._worker_conn is not None:
            try:
                self._worker_conn.close()
            except Exception:
                pass
            self._worker_conn = None

        if self._worker_process is not None:
            try:
                if self._worker_process.is_alive():
                    self._worker_process.terminate()
                    self._worker_process.join(5)
            except Exception:
                pass
            self._worker_process = None

    # ── Abstract interface ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "granite"

    @property
    def vram_estimate_gb(self) -> float:
        return 3.0

    def load(self, model_path: str, device: str = "cuda") -> None:
        self._device = device
        granite_dir = os.path.join(model_path, "granite")

        # Download if not present locally
        if not os.path.isdir(granite_dir) or not os.path.isfile(
            os.path.join(granite_dir, "config.json")
        ):
            log.info("Granite model not found at %s — downloading…", granite_dir)
            from dictator.model_downloader import download_model, EXIT_SUCCESS, EXIT_AUTH_REQUIRED
            rc = download_model("granite", model_path)
            if rc == EXIT_AUTH_REQUIRED:
                raise RuntimeError(
                    f"The Granite Speech model requires authentication. "
                    f"Please provide a HuggingFace token with access to {GRANITE_REPO_ID}."
                )
            if rc != EXIT_SUCCESS:
                raise RuntimeError(f"Failed to download Granite model from {GRANITE_REPO_ID}.")

        log.info("Loading Granite 4.0 1B Speech from %s", granite_dir)

        self._close_worker()
        ctx = self._make_mp_context()
        parent_conn, child_conn = ctx.Pipe()
        worker = ctx.Process(
            target=_granite_worker_main,
            args=(child_conn, granite_dir, device),
            daemon=True,
        )
        worker.start()
        child_conn.close()

        self._worker_conn = parent_conn
        self._worker_process = worker

        msg = self._recv_worker_message("load")
        if msg.get("status") != "ready":
            self._close_worker()
            raise RuntimeError(msg.get("error", "Granite worker failed to load"))

        self._model = object()
        log.info("Granite 4.0 1B Speech loaded on %s", device)

    def _transcribe_impl(self, audio_16k: np.ndarray, language: str,
                          keywords: str = "") -> str:
        if self._worker_conn is None or self._worker_process is None:
            raise RuntimeError("Granite worker not running")

        try:
            self._worker_conn.send(
                {
                    "cmd": "transcribe",
                    "audio": np.ascontiguousarray(audio_16k, dtype=np.float32),
                    "language": language,
                    "keywords": keywords,
                }
            )
        except (BrokenPipeError, EOFError, OSError) as exc:
            self._close_worker()
            self._model = None
            raise RuntimeError("Granite worker process crashed during transcription") from exc

        msg = self._recv_worker_message("transcription")
        status = msg.get("status")
        if status == "ok":
            return str(msg.get("text", "")).strip()
        if status == "error":
            raise RuntimeError(msg.get("error", "Granite transcription failed"))
        raise RuntimeError(f"Unexpected Granite worker response: {msg}")

    def unload(self) -> None:
        if self._worker_conn is not None and self._worker_process is not None:
            try:
                if self._worker_process.is_alive():
                    self._worker_conn.send({"cmd": "shutdown"})
                    if self._worker_conn.poll(2.0):
                        self._worker_conn.recv()
            except Exception:
                pass
        self._close_worker()
        self._release_model()
