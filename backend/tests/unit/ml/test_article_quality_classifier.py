from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from app.ml.article_quality_classifier import (
    CURRENT_SKLEARN_VERSION,
    ArticleQualityClassifier,
    IncompatibleModelArtifactError,
)


def test_save_persists_sklearn_runtime_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_payload: dict[str, object] = {}

    def fake_dump(payload: dict[str, object], _: Path) -> None:
        captured_payload.update(payload)

    classifier = ArticleQualityClassifier()
    classifier.is_trained = True
    monkeypatch.setattr("app.ml.article_quality_classifier.joblib.dump", fake_dump)

    classifier.save(tmp_path / "article_quality.joblib")

    assert captured_payload["sklearn_version"] == CURRENT_SKLEARN_VERSION


def test_load_rejects_metadata_version_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model_path = tmp_path / "article_quality.joblib"
    model_path.write_text("stub")

    monkeypatch.setattr(
        "app.ml.article_quality_classifier.joblib.load",
        lambda _: {
            "vectorizer": object(),
            "model": object(),
            "is_trained": True,
            "sklearn_version": "0.0-test",
        },
    )

    with pytest.raises(IncompatibleModelArtifactError):
        ArticleQualityClassifier.load(model_path)


def test_load_rejects_inconsistent_version_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class InconsistentVersionWarning(UserWarning):
        pass

    model_path = tmp_path / "article_quality.joblib"
    model_path.write_text("stub")

    def fake_load(_: Path) -> dict[str, object]:
        warnings.warn(
            "Trying to unpickle estimator TfidfVectorizer from version 1.7.2 when using version 1.8.0.",
            InconsistentVersionWarning,
            stacklevel=2,
        )
        return {
            "vectorizer": object(),
            "model": object(),
            "is_trained": True,
        }

    monkeypatch.setattr("app.ml.article_quality_classifier.joblib.load", fake_load)

    with pytest.raises(IncompatibleModelArtifactError):
        ArticleQualityClassifier.load(model_path)
