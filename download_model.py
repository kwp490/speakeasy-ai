#!/usr/bin/env python3
"""
Model downloader for SpeakEasy AI.

Standalone script that can also be invoked via ``speakeasy download-model``.

Usage:
    python download_model.py --token hf_... --target-dir "C:\\Program Files\\SpeakEasy AI\\models"
"""

from __future__ import annotations

import argparse
import os
import sys



def main() -> int:
    parser = argparse.ArgumentParser(description="Download the Cohere Transcribe model for SpeakEasy AI.")
    parser.add_argument(
        "--token",
        default=None,
        help="HuggingFace access token (required for gated model)",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Directory to store models (default: C:\\Program Files\\SpeakEasy AI\\models)",
    )
    args = parser.parse_args()

    if "SPEAKEASY_HOME" in os.environ:
        default_dir = os.path.join(os.environ["SPEAKEASY_HOME"], "models")
    else:
        default_dir = os.path.join(
            os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
            "SpeakEasy AI",
            "models",
        )
    target_dir = args.target_dir or default_dir
    os.makedirs(target_dir, exist_ok=True)

    from speakeasy.model_downloader import download_model
    return download_model("cohere", target_dir, token=args.token)


if __name__ == "__main__":
    sys.exit(main())