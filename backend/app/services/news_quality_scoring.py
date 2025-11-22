"""ML-based quality scoring for news articles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..logging_config import get_logger
from ..ml.article_quality_classifier import ArticleQualityClassifier

logger = get_logger(__name__)


class NewsQualityScorer:
    """Handles ML-based article quality prediction and scoring."""

    def __init__(self) -> None:
        self.quality_model: ArticleQualityClassifier | None = None
        self._load_quality_model()

    def _load_quality_model(self) -> None:
        """Load ML quality model with graceful fallback."""
        # Model is in backend/models/ not backend/app/models/
        model_path = Path(__file__).parent.parent.parent / "models" / "article_quality_v1.joblib"

        try:
            if model_path.exists():
                self.quality_model = ArticleQualityClassifier.load(model_path)
                logger.info("quality_model_loaded", model_path=str(model_path))
            else:
                logger.warning("quality_model_not_found", model_path=str(model_path))
        except Exception as e:
            logger.error("quality_model_load_failed", error=str(e), model_path=str(model_path))

    def score_articles(self, articles: list[Any]) -> list[Any]:
        """Score article quality using ML model.

        Args:
            articles: List of article objects to score

        Returns:
            Same list with quality_prediction and quality_confidence attributes added
        """
        if not self.quality_model:
            logger.warning("quality_model_not_available", article_count=len(articles))
            return articles

        scored_count = 0
        for article in articles:
            try:
                prediction = self.quality_model.predict(article.headline, article.summary or "")
                article.quality_prediction = prediction["is_useful"]
                article.quality_confidence = prediction["confidence"]
                scored_count += 1
            except Exception as e:
                logger.error(
                    "quality_prediction_failed",
                    ticker=article.ticker,
                    headline=article.headline[:50],
                    error=str(e),
                )
                article.quality_prediction = None
                article.quality_confidence = None

        logger.info("quality_scoring_complete", scored=scored_count, total=len(articles))
        return articles

    def is_available(self) -> bool:
        """Check if quality model is loaded and available."""
        return self.quality_model is not None
