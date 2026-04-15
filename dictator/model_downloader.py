"""
Model downloader using huggingface_hub.

Downloads Cohere Transcribe and IBM Granite Speech models
from HuggingFace Hub to local storage.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# ── Exit codes (also used by installer/dictator-setup.iss) ───────────────────
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_AUTH_REQUIRED = 2  # gated repo — anonymous access denied

# ── Model constants (single source of truth) ─────────────────────────────────

COHERE_REPO_ID = "CohereLabs/cohere-transcribe-03-2026"
GRANITE_REPO_ID = "ibm-granite/granite-4.0-1b-speech"

_ENGINE_REPO_MAP = {
    "cohere": COHERE_REPO_ID,
    "granite": GRANITE_REPO_ID,
}


def _is_gated_repo_error(exc: Exception) -> bool:
    """Return True if *exc* indicates a gated/restricted HuggingFace repo."""
    msg = str(exc)
    return ("gated repo" in msg.lower()
            or "access to model" in msg.lower()
            or ("401" in msg and "restricted" in msg.lower()))


def download_model(engine_name: str, model_path: str, token: str | None = None) -> int:
    """Download model files for *engine_name* to *model_path*/<engine_name>.

    Returns
    -------
    EXIT_SUCCESS (0)
        Download succeeded or model already present.
    EXIT_FAILURE (1)
        Unexpected error (network, disk, etc.).
    EXIT_AUTH_REQUIRED (2)
        Repository is gated — anonymous download not possible.
    """
    repo_id = _ENGINE_REPO_MAP.get(engine_name)
    if repo_id is None:
        print(f"ERROR: Unknown engine '{engine_name}'. Choose from: {list(_ENGINE_REPO_MAP)}")
        return EXIT_FAILURE

    target_dir = os.path.join(model_path, engine_name)
    os.makedirs(target_dir, exist_ok=True)

    # Check if already downloaded
    if model_ready(engine_name, model_path):
        print(f"{engine_name.capitalize()} model already present in {target_dir} — skipping download.")
        return EXIT_SUCCESS

    try:
        import huggingface_hub
    except ImportError:
        print("ERROR: huggingface-hub is required for model downloads.")
        print("Install it: pip install huggingface-hub")
        return EXIT_FAILURE

    print(f"Downloading {engine_name} model from {repo_id} to {target_dir}...")
    try:
        huggingface_hub.snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir,
            local_files_only=False,
            token=token,
        )
        # Verify the download actually produced usable model files
        if not model_ready(engine_name, model_path):
            print(f"ERROR: Download appeared to succeed but model files are incomplete in {target_dir}.")
            return EXIT_FAILURE
        print(f"{engine_name.capitalize()} model download complete.")
        return EXIT_SUCCESS
    except Exception as exc:
        if _is_gated_repo_error(exc):
            print(
                f"AUTH REQUIRED: {repo_id} is a gated model that requires "
                f"authentication for download.\n"
                f"The model will need to be made available before it can be "
                f"installed. You can download it later from the application."
            )
            return EXIT_AUTH_REQUIRED
        msg = str(exc)
        if "401" in msg or "Repository Not Found" in msg:
            print(f"ERROR: Repo not found or access denied: {exc}")
        else:
            print(f"ERROR: Download failed: {exc}")
        return EXIT_FAILURE


def model_ready(engine_name: str, model_path: str) -> bool:
    """Return True if the model files for *engine_name* exist."""
    engine_dir = os.path.join(model_path, engine_name)
    return os.path.isdir(engine_dir) and os.path.isfile(
        os.path.join(engine_dir, "config.json")
    )
