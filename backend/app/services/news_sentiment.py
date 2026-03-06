"""Sentiment analysis for news articles using FinBERT and VADER."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from importlib import import_module
from typing import Any, Literal, cast

# Ensure HOME environment variable is set before importing transformers
# This prevents transformers/huggingface models from trying to create cache files in non-existent directories
if not os.environ.get("HOME"):
    os.environ["HOME"] = "/var/cache/portfolio-ai"

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..logging_config import get_logger
from .news_models import SentimentScore
from .news_processing import FinBertUnavailableError

logger = get_logger(__name__)

_finbert_instance: FinBertSentimentAnalyzer | None = None
_finbert_lock = threading.Lock()


def _load_finbert_dependencies() -> tuple[Any | None, Any | None, Any | None]:
    """Load FinBERT dependencies only when the model is actually needed."""
    try:
        torch = import_module("torch")
        transformers = import_module("transformers")
    except Exception:  # pragma: no cover - handled via availability checks
        return None, None, None

    return (
        torch,
        getattr(transformers, "AutoTokenizer", None),
        getattr(transformers, "AutoModelForSequenceClassification", None),
    )


def get_finbert_analyzer() -> FinBertSentimentAnalyzer:
    """Return a module-level singleton FinBertSentimentAnalyzer.

    The FinBERT model (~420MB) is expensive to load and should only exist
    once in the worker process. This avoids re-loading the model on every
    task execution.
    """
    global _finbert_instance  # noqa: PLW0603
    if _finbert_instance is not None:
        return _finbert_instance
    with _finbert_lock:
        if _finbert_instance is not None:
            return _finbert_instance
        _finbert_instance = FinBertSentimentAnalyzer()
        return _finbert_instance


class FinBertSentimentAnalyzer:
    """Sentiment analyzer powered by the ProsusAI/finbert model."""

    DEFAULT_MODEL_NAME = "ProsusAI/finbert"

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL_NAME
        self.device = device or "cpu"
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return

            torch, auto_tokenizer, auto_model = _load_finbert_dependencies()
            if auto_tokenizer is None or auto_model is None or torch is None:
                raise FinBertUnavailableError("transformers/torch not available")

            logger.info(
                "Loading FinBERT sentiment model", model_name=self.model_name, device=self.device
            )
            try:
                self._tokenizer = auto_tokenizer.from_pretrained(self.model_name)
                self._model = auto_model.from_pretrained(self.model_name)
                self._model.to(self.device)
                self._model.eval()
            except Exception as exc:  # pragma: no cover - heavy dependency handling
                logger.error("Failed to load FinBERT model", error=str(exc))
                raise FinBertUnavailableError(str(exc)) from exc

    def is_available(self) -> bool:
        try:
            self._ensure_model()
            return True
        except FinBertUnavailableError:
            return False

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        if not texts:
            return []

        self._ensure_model()
        torch, _, _ = _load_finbert_dependencies()
        if torch is None:
            raise FinBertUnavailableError("transformers/torch not available")
        assert self._tokenizer is not None  # For mypy
        assert self._model is not None

        encoded = self._tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            outputs = self._model(**encoded)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)

        id2label = cast(
            dict[int, str],
            getattr(self._model.config, "id2label", {0: "positive", 1: "negative", 2: "neutral"}),
        )
        results: list[SentimentScore] = []

        for idx in range(probabilities.shape[0]):
            probs = probabilities[idx].detach().cpu().tolist()
            prob_map: dict[str, float] = {
                id2label.get(i, f"LABEL_{i}").lower(): float(p) for i, p in enumerate(probs)
            }
            positive = prob_map.get("positive", 0.0)
            negative = prob_map.get("negative", 0.0)
            neutral = prob_map.get("neutral", 0.0)

            label_key = max(prob_map, key=lambda lbl: prob_map[lbl])
            if label_key not in {"positive", "neutral", "negative"}:
                label_key = "neutral"
            label = cast(Literal["positive", "neutral", "negative"], label_key)
            confidence = float(max(prob_map.values()))
            score = float(positive - negative)

            results.append(
                SentimentScore(
                    score=max(-1.0, min(1.0, score)),
                    label=label,
                    confidence=confidence,
                    model="finbert",
                    probabilities={"positive": positive, "negative": negative, "neutral": neutral},
                )
            )

        return results


class VaderSentimentAnalyzer:
    """Fallback VADER sentiment analyzer."""

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()

    @staticmethod
    def _label_from_score(score: float) -> Literal["positive", "neutral", "negative"]:
        if score >= 0.2:
            return "positive"
        if score <= -0.2:
            return "negative"
        return "neutral"

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        results: list[SentimentScore] = []
        for text in texts:
            compound = float(self._analyzer.polarity_scores(text)["compound"])
            label = self._label_from_score(compound)
            confidence = float(min(1.0, abs(compound)))
            results.append(
                SentimentScore(
                    score=max(-1.0, min(1.0, compound)),
                    label=label,
                    confidence=confidence,
                    model="vader",
                    probabilities={"compound": compound},
                )
            )
        return results
