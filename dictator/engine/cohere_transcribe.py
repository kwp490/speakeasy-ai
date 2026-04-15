"""
Cohere Transcribe 03-2026 engine.

Uses the ``CohereAsrForConditionalGeneration`` model from HuggingFace
transformers for high-accuracy speech recognition (2B parameters).

Supported languages: en, fr, de, it, es, pt, el, nl, pl, zh, ja, ko, vi, ar.
"""

from __future__ import annotations

import logging
import os

import numpy as np

from .base import SpeechEngine

log = logging.getLogger(__name__)

COHERE_REPO_ID = "CohereLabs/cohere-transcribe-03-2026"


class CohereTranscribeEngine(SpeechEngine):
    """Cohere Transcribe 03-2026 — 2B parameter ASR model."""

    def __init__(self) -> None:
        super().__init__()
        self._processor = None

    # ── Abstract interface ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "cohere"

    @property
    def vram_estimate_gb(self) -> float:
        return 5.0

    def load(self, model_path: str, device: str = "cuda") -> None:
        import torch
        from transformers import AutoProcessor, CohereAsrForConditionalGeneration

        self._device = device
        cohere_dir = os.path.join(model_path, "cohere")

        # Download if not present locally
        if not os.path.isdir(cohere_dir) or not os.path.isfile(
            os.path.join(cohere_dir, "config.json")
        ):
            log.info("Cohere model not found at %s — downloading…", cohere_dir)
            from dictator.model_downloader import download_model, EXIT_SUCCESS, EXIT_AUTH_REQUIRED
            rc = download_model("cohere", model_path)
            if rc == EXIT_AUTH_REQUIRED:
                raise RuntimeError(
                    f"The Cohere Transcribe model requires authentication. "
                    f"Please provide a HuggingFace token with access to {COHERE_REPO_ID}."
                )
            if rc != EXIT_SUCCESS:
                raise RuntimeError(f"Failed to download Cohere model from {COHERE_REPO_ID}.")

        log.info("Loading Cohere Transcribe from %s", cohere_dir)

        self._processor = AutoProcessor.from_pretrained(cohere_dir)
        self._model = CohereAsrForConditionalGeneration.from_pretrained(
            cohere_dir,
            device_map=device if device == "cuda" else "cpu",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        )
        log.info("Cohere Transcribe loaded on %s", device)

    def _transcribe_impl(self, audio_16k: np.ndarray, language: str,
                          keywords: str = "") -> str:
        import torch

        inputs = self._processor(
            audio_16k,
            sampling_rate=16000,
            return_tensors="pt",
            language=language or "en",
        )
        # Move input tensors to model device
        inputs = {k: v.to(self._model.device) if hasattr(v, "to") else v
                  for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = self._model.generate(**inputs, max_new_tokens=512)

        text = self._processor.decode(output_ids, skip_special_tokens=True)
        return text.strip() if isinstance(text, str) else str(text).strip()

    def unload(self) -> None:
        self._processor = None
        self._release_model()
