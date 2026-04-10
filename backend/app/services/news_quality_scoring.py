"""Article quality scoring for news articles."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..logging_config import get_logger
from ..ml.article_quality_classifier import (
    ArticleQualityClassifier,
    QualityPrediction,
    extract_text_features,
)

logger = get_logger(__name__)

_QUESTIONABLE_PATTERNS = (
    r"\b(best|top)\s+\d+\b",
    r"\bshould you\b",
    r"\bto buy now\b",
    r"\bwhat analysts think\b",
    r"\bstock(s)? to watch\b",
)
_USEFUL_PATTERNS = (
    r"\b(10-k|10-q|8-k|13f|sec filing|regulatory filing)\b",
    r"\b(price target|upgrades?|downgrades?)\b",
    r"\b(guidance|forecast|outlook|eps|revenue|margin)\b",
    r"\b(dividend|buyback|acquisition|merger|approval)\b",
)


class NewsQualityScorer:
    """Handles article quality prediction and scoring."""

    def __init__(self) -> None:
        self.quality_model: ArticleQualityClassifier | None = None
        self._model_path = Path(__file__).parent.parent.parent / "models" / "article_quality_v1.joblib"
        self.mode = "heuristic"
        self._load_quality_model()

    def _load_quality_model(self) -> None:
        """Load ML quality model with heuristic fallback."""
        try:
            if self._model_path.exists():
                self.quality_model = ArticleQualityClassifier.load(self._model_path)
                self.mode = "ml"
                logger.info("quality_model_loaded", model_path=str(self._model_path))
            else:
                logger.info("quality_model_not_found_using_heuristic", model_path=str(self._model_path))
        except Exception as e:
            logger.warning(
                "quality_model_load_failed",
                error=str(e),
                model_path=str(self._model_path),
            )
            self.quality_model = None
            self.mode = "heuristic"

    def _heuristic_predict(self, headline: str, summary: str = "") -> QualityPrediction:
        text = f"{headline} {summary}".strip().lower()
        features = extract_text_features(headline, summary)

        score = 0.5
        score += 0.18 if features["has_numbers"] else -0.04
        score += min(float(features["material_count"]) * 0.08, 0.24)
        score += 0.08 if features["summary_length"] >= 80 else -0.06
        score += min(sum(1 for pattern in _USEFUL_PATTERNS if re.search(pattern, text, re.IGNORECASE)) * 0.08, 0.24)
        score -= 0.12 if features["is_question"] else 0.0
        score -= 0.28 if features["is_listicle"] else 0.0
        score -= 0.24 if features["has_clickbait"] else 0.0
        score -= min(float(features["speculation_count"]) * 0.06, 0.18)
        score -= min(
            sum(1 for pattern in _QUESTIONABLE_PATTERNS if re.search(pattern, text, re.IGNORECASE)) * 0.1,
            0.2,
        )

        if "?" not in headline and summary and len(summary) >= 120:
            score += 0.04

        normalized_score = min(max(score, 0.05), 0.95)
        is_useful = normalized_score >= 0.55
        confidence = normalized_score if is_useful else 1.0 - normalized_score
        return QualityPrediction(
            is_useful=is_useful,
            confidence=round(float(confidence), 4),
            predicted_label="useful" if is_useful else "not_useful",
        )

    def score_articles(self, articles: list[Any]) -> list[Any]:
        """Score article quality using the best available scorer.

        Args:
            articles: List of article objects to score

        Returns:
            Same list with quality_prediction and quality_confidence attributes added
        """
        scored_count = 0
        for article in articles:
            try:
                prediction = (
                    self.quality_model.predict(article.headline, article.summary or "")
                    if self.quality_model is not None
                    else self._heuristic_predict(article.headline, article.summary or "")
                )
                article.quality_prediction = prediction["is_useful"]
                article.quality_confidence = prediction["confidence"]
                scored_count += 1
            except Exception as e:
                logger.error(
                    "quality_prediction_failed",
                    symbol=article.symbol,
                    headline=article.headline[:50],
                    error=str(e),
                    exc_info=True,
                )
                article.quality_prediction = None
                article.quality_confidence = None

        logger.info("quality_scoring_complete", mode=self.mode, scored=scored_count, total=len(articles))
        return articles

    def is_available(self) -> bool:
        """Check if article quality scoring is available."""
        return True

    def is_model_available(self) -> bool:
        """Check if the ML model artifact is loaded."""
        return self.quality_model is not None
