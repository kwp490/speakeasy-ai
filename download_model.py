#!/usr/bin/env python3
"""
Model downloader for dictat0r.AI.

Standalone script that can also be invoked via ``dictator download-model``.

Usage:
    python download_model.py --engine granite --target-dir "C:\\Program Files\\dictat0r.AI\\models"
    python download_model.py --engine cohere --target-dir "C:\\Program Files\\dictat0r.AI\\models"
"""

from __future__ import annotations

import argparse
import os
import sys



def main() -> int:
    parser = argparse.ArgumentParser(description="Download local AI models for dictat0r.AI.")
    parser.add_argument(
        "--engine",
        choices=["granite", "cohere"],
        required=True,
        help="Engine whose model to download",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Directory to store models (default: C:\\Program Files\\dictat0r.AI\\models)",
    )
    args = parser.parse_args()

    default_dir = os.path.join(
        os.environ.get("DICTATOR_HOME", r"C:\Program Files\dictat0r.AI"),
        "models",
    )
    target_dir = args.target_dir or default_dir
    os.makedirs(target_dir, exist_ok=True)

    from dictator.model_downloader import download_model
    return download_model(args.engine, target_dir)


if __name__ == "__main__":
    sys.exit(main())