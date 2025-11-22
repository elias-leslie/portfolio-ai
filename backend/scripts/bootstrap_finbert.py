#!/usr/bin/env python
"""Utility script to preload FinBERT weights and verify sentiment setup.

Run this after installing the backend dependencies to make sure the
`ProsusAI/finbert` model can be downloaded (or located locally) so the
NewsService will score headlines with FinBERT instead of falling back to VADER.

Examples
--------
    # Use defaults (ProsusAI/finbert on CPU)
    python -m scripts.bootstrap_finbert

    # Specify custom Hugging Face cache directory and GPU device
    HF_HOME=~/.cache/huggingface python -m scripts.bootstrap_finbert --device cuda
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.logging_config import get_logger
from app.services.news_processing import FinBertUnavailableError
from app.services.news_service import FinBertSentimentAnalyzer

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preload and verify FinBERT sentiment model.")
    parser.add_argument(
        "--model",
        default=FinBertSentimentAnalyzer.DEFAULT_MODEL_NAME,
        help="Hugging Face model identifier or local path (default: ProsusAI/finbert)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Torch device to load the model onto (default: cpu)",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Only return exit code (suppress informational logging).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    analyzer = FinBertSentimentAnalyzer(model_name=args.model, device=args.device)

    if not args.silent:
        logger.info(
            "finbert_bootstrap_start",
            model=args.model,
            device=args.device,
        )

    try:
        analyzer._ensure_model()
    except FinBertUnavailableError as exc:
        if not args.silent:
            logger.error(
                "finbert_bootstrap_failed",
                model=args.model,
                device=args.device,
                error=str(exc),
                hint="Install torch/transformers/tokenizers and ensure network or HF cache is available.",
            )
        return 1

    model_path = getattr(getattr(analyzer, "_model", None), "name_or_path", args.model)
    tokenizer_path = getattr(
        getattr(analyzer, "_tokenizer", None),
        "name_or_path",
        args.model,
    )

    cache_dir = Path(model_path).resolve() if Path(model_path).exists() else None

    if not args.silent:
        logger.info(
            "finbert_bootstrap_success",
            model=model_path,
            tokenizer=tokenizer_path,
            device=args.device,
            cache_dir=str(cache_dir) if cache_dir else None,
        )
        logger.info(
            "finbert_usage_hint",
            command="celery -A app.celery_app.celery_app worker --loglevel=info",
            note="Once workers are running, headlines fetched by NewsService will use FinBERT scores.",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
