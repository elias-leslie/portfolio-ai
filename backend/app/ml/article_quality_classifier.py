"""
Article Quality Classifier - ML model for predicting article usefulness.

Uses scikit-learn to train a binary classifier on AI-labeled training data.
"""

import re
import warnings
from pathlib import Path
from typing import Any, TypedDict

import joblib
import numpy as np
import numpy.typing as npt
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from app.logging_config import get_logger

logger = get_logger(__name__)

CURRENT_SKLEARN_VERSION = sklearn.__version__


class ArticleFeatures(TypedDict):
    """Feature vector for an article."""

    symbol: str
    headline: str
    summary: str
    sentiment_score: float


class QualityPrediction(TypedDict):
    """Quality prediction result."""

    is_useful: bool
    confidence: float  # 0.0-1.0 probability
    predicted_label: str  # "useful" or "not_useful"


class IncompatibleModelArtifactError(RuntimeError):
    """Raised when a persisted model artifact does not match the runtime."""


def _extract_saved_sklearn_version(message: str) -> str | None:
    match = re.search(r"version ([^ ]+) when using version ([^ ]+)", message)
    return match.group(1) if match else None


def extract_text_features(headline: str, summary: str) -> dict[str, float | int]:
    """
    Extract hand-crafted features from article text.

    These features complement TF-IDF vectorization with domain-specific signals.
    """
    text = (headline + " " + summary).lower()

    # Number patterns (EPS, revenue, price targets)
    has_numbers = 1 if re.search(r"\$\d+\.?\d*[MBK]?|\d+\.?\d*%|\d+\.\d+", text) else 0

    # Question headline (often opinion/speculation)
    is_question = 1 if headline.strip().endswith("?") else 0

    # Listicle patterns
    is_listicle = (
        1 if re.search(r"^\d+\s+(stocks|things|ways|reasons)", headline, re.IGNORECASE) else 0
    )

    # Clickbait indicators
    clickbait_words = ["shocking", "you won't believe", "this one trick", "must see"]
    has_clickbait = 1 if any(word in text for word in clickbait_words) else 0

    # Vague speculation words
    speculation_words = ["could", "might", "may", "analysts say", "sources say"]
    has_speculation = sum(1 for word in speculation_words if word in text)

    # Material event keywords
    material_keywords = ["earnings", "acquisition", "merger", "ceo", "dividend", "buyback"]
    has_material = sum(1 for word in material_keywords if word in text)

    # Text length features
    headline_length = len(headline)
    summary_length = len(summary) if summary else 0

    return {
        "has_numbers": has_numbers,
        "is_question": is_question,
        "is_listicle": is_listicle,
        "has_clickbait": has_clickbait,
        "speculation_count": has_speculation,
        "material_count": has_material,
        "headline_length": headline_length,
        "summary_length": summary_length,
    }


class ArticleQualityClassifier:
    """
    Binary classifier for article quality prediction.

    Combines TF-IDF text features with hand-crafted domain features.
    """

    def __init__(self) -> None:
        """Initialize classifier with vectorizer and model."""
        self.vectorizer = TfidfVectorizer(
            max_features=500,  # Top 500 most important words
            ngram_range=(1, 2),  # Unigrams and bigrams
            stop_words="english",
            min_df=2,  # Word must appear in at least 2 documents
        )

        # Random Forest performs better than Logistic Regression for this task
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight="balanced",  # Handle class imbalance
        )

        self.is_trained = False

    def _prepare_features(
        self, headlines: list[str], summaries: list[str], fit_vectorizer: bool = False
    ) -> npt.NDArray[Any]:
        """
        Prepare feature matrix combining TF-IDF and hand-crafted features.

        Args:
            headlines: List of article headlines
            summaries: List of article summaries
            fit_vectorizer: If True, fit the TF-IDF vectorizer (training only)

        Returns:
            Feature matrix (n_samples, n_features)
        """
        # Combine headline and summary for TF-IDF
        texts = [f"{h} {s}" for h, s in zip(headlines, summaries, strict=True)]

        # TF-IDF features
        if fit_vectorizer:
            tfidf_features = self.vectorizer.fit_transform(texts).toarray()
        else:
            tfidf_features = self.vectorizer.transform(texts).toarray()

        # Hand-crafted features
        manual_features = []
        for headline, summary in zip(headlines, summaries, strict=True):
            features = extract_text_features(headline, summary or "")
            manual_features.append(list(features.values()))

        manual_features_array = np.array(manual_features)

        # Concatenate TF-IDF and manual features
        combined_features = np.hstack([tfidf_features, manual_features_array])

        return combined_features

    def train(
        self, headlines: list[str], summaries: list[str], labels: list[bool], test_size: float = 0.2
    ) -> dict[str, float]:
        """
        Train the classifier on labeled data.

        Args:
            headlines: Article headlines
            summaries: Article summaries
            labels: True = useful, False = not useful
            test_size: Fraction of data to hold out for testing

        Returns:
            Dictionary with training metrics
        """
        # Split data
        x_train_h, x_test_h, x_train_s, x_test_s, y_train, y_test = train_test_split(
            headlines, summaries, labels, test_size=test_size, random_state=42, stratify=labels
        )

        # Prepare features
        x_train = self._prepare_features(x_train_h, x_train_s, fit_vectorizer=True)
        x_test = self._prepare_features(x_test_h, x_test_s, fit_vectorizer=False)

        # Train model
        self.model.fit(x_train, y_train)
        self.is_trained = True

        # Evaluate
        y_pred = self.model.predict(x_test)

        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary")

        logger.info(
            "training_results",
            train_samples=len(y_train),
            test_samples=len(y_test),
            accuracy=round(accuracy, 3),
            precision=round(precision, 3),
            recall=round(recall, 3),
            f1_score=round(f1, 3),
        )

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "train_size": len(y_train),
            "test_size": len(y_test),
        }

    def predict(self, headline: str, summary: str = "") -> QualityPrediction:
        """
        Predict quality for a single article.

        Args:
            headline: Article headline
            summary: Article summary (optional)

        Returns:
            Quality prediction with confidence score
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained yet. Call train() first.")

        # Prepare features
        x = self._prepare_features([headline], [summary], fit_vectorizer=False)

        # Predict
        prediction = self.model.predict(x)[0]
        probabilities = self.model.predict_proba(x)[0]

        # Probability of "useful" class (class 1)
        confidence = probabilities[1] if prediction else probabilities[0]

        return QualityPrediction(
            is_useful=bool(prediction),
            confidence=float(confidence),
            predicted_label="useful" if prediction else "not_useful",
        )

    def save(self, model_path: str | Path) -> None:
        """Save trained model to disk."""
        if not self.is_trained:
            raise RuntimeError("Cannot save untrained model")

        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "model": self.model,
                "is_trained": self.is_trained,
                "sklearn_version": CURRENT_SKLEARN_VERSION,
            },
            model_path,
        )

        logger.info("model_saved", path=str(model_path))

    @classmethod
    def load(cls, model_path: str | Path) -> "ArticleQualityClassifier":
        """Load trained model from disk."""
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            data = joblib.load(model_path)

        saved_version = data.get("sklearn_version")
        incompatible_warning = next(
            (
                warning
                for warning in caught_warnings
                if warning.category.__name__ == "InconsistentVersionWarning"
            ),
            None,
        )
        inferred_saved_version = (
            _extract_saved_sklearn_version(str(incompatible_warning.message))
            if incompatible_warning
            else None
        )
        artifact_version = saved_version or inferred_saved_version

        if incompatible_warning or (
            artifact_version is not None and artifact_version != CURRENT_SKLEARN_VERSION
        ):
            raise IncompatibleModelArtifactError(
                "Article quality model artifact is incompatible with the current sklearn "
                f"runtime (artifact={artifact_version or 'unknown'}, "
                f"runtime={CURRENT_SKLEARN_VERSION}). Retrain and republish the model."
            )

        classifier = cls()
        classifier.vectorizer = data["vectorizer"]
        classifier.model = data["model"]
        classifier.is_trained = data["is_trained"]

        logger.info("model_loaded", path=str(model_path))

        return classifier
