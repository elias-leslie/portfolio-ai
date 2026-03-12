"""Tasks for ML model training and retraining."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.storage import get_storage
from app.storage.types import DatabaseConnection

from ._ml_training_helpers import (
    _label_articles_with_gemini,
    _load_training_data,
    _merge_gemini_labels,
    _query_new_articles,
    _save_model_metrics,
    _train_and_save_model,
)

logger = logging.getLogger(__name__)

STATUS_QUERYING = "querying"
STATUS_LABELING = "labeling"
STATUS_TRAINING = "training"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

STEP_LOAD_TRAINING_DATA = "Loading existing training data..."
STEP_QUERY_DATABASE = "Querying database..."
STEP_INSUFFICIENT_ARTICLES = "Skipped - insufficient articles"
STEP_MERGE_LABELS = "Merging labels..."
STEP_TRAINING_PREFIX = "Training on"
STEP_COMPLETE_PREFIX = "Complete! Accuracy:"
TRAINING_DATA_FILENAME = str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "training_data_merged.json")
NEW_ARTICLE_LIMIT = 100
MIN_ARTICLES_TO_TRAIN = 10
PROGRESS_INITIAL = 5
PROGRESS_QUERY_COMPLETE = 10
PROGRESS_LABELING = 20
PROGRESS_MERGE = 50
PROGRESS_TRAINING = 70
PROGRESS_DONE = 100

_ALLOWED_PROGRESS_COLUMNS = frozenset({
    "articles_found", "articles_total", "articles_labeled",
    "model_version", "accuracy", "error_message",
})


@dataclass(frozen=True)
class TrainingArtifacts:
    existing_data: list[dict[str, Any]]
    labeled_hashes: set[str]
    new_articles: list[dict[str, Any]]
    gemini_labels: list[dict[str, Any]]
    newly_labeled: list[dict[str, Any]]
    combined_data: list[dict[str, Any]]


TrainingResult = dict[str, str | float | int]


def _update_progress(
    conn: DatabaseConnection,
    session_id: str | None,
    status: str,
    current_step: str,
    progress_percent: int,
    **kwargs: Any,
) -> None:
    """Update progress tracking if session_id provided."""
    if not session_id:
        return

    update_fields = [
        "status = %s",
        "current_step = %s",
        "progress_percent = %s",
        "updated_at = NOW()",
    ]
    update_values = [status, current_step, progress_percent]

    for key, value in kwargs.items():
        if key not in _ALLOWED_PROGRESS_COLUMNS:
            raise ValueError(f"Disallowed progress column: {key}")
        update_fields.append(f"{key} = %s")
        update_values.append(_coerce_progress_value(value))

    update_values.append(session_id)
    conn.execute(
        f"UPDATE ml_training_progress SET {', '.join(update_fields)} WHERE session_id = %s",
        update_values,
    )
    conn.commit()


def _coerce_progress_value(value: Any) -> str | int | float | bool | dt.datetime | None:
    if isinstance(value, (str, int, float, bool, dt.datetime)):
        return value
    return str(value) if value is not None else None


def retrain_article_quality_model_manual(session_id: str) -> TrainingResult:
    """Manually triggered model retraining with progress tracking."""
    return _retrain_article_quality_model_impl(session_id=session_id)


def retrain_article_quality_model() -> TrainingResult:
    """Scheduled daily model retraining without progress tracking."""
    return _retrain_article_quality_model_impl(session_id=None)


def _retrain_article_quality_model_impl(session_id: str | None = None) -> TrainingResult:
    """Retrain article quality model with new Gemini-labeled data."""
    logger.info("Starting article quality model retraining")

    storage = get_storage()
    training_data_path = Path(TRAINING_DATA_FILENAME)

    with storage.connection() as conn:
        try:
            artifacts = _prepare_training_artifacts(conn, session_id, training_data_path)
            if len(artifacts.new_articles) < MIN_ARTICLES_TO_TRAIN:
                return _handle_insufficient_articles(conn, session_id, len(artifacts.new_articles))
            return _run_training_phase(conn, session_id, training_data_path, artifacts)
        except Exception as error:
            return _handle_training_exception(conn, session_id, error)


def _prepare_training_artifacts(
    conn: DatabaseConnection,
    session_id: str | None,
    training_data_path: Path,
) -> TrainingArtifacts:
    _update_progress(conn, session_id, STATUS_QUERYING, STEP_LOAD_TRAINING_DATA, PROGRESS_INITIAL)
    existing_data, labeled_hashes = _load_training_data(training_data_path)
    _update_progress(conn, session_id, STATUS_QUERYING, STEP_QUERY_DATABASE, PROGRESS_QUERY_COMPLETE)
    new_articles = _query_new_articles(conn, labeled_hashes, limit=NEW_ARTICLE_LIMIT)
    _update_progress(
        conn,
        session_id,
        STATUS_LABELING,
        f"Labeling {len(new_articles)} articles...",
        PROGRESS_LABELING,
        articles_found=len(new_articles),
        articles_total=len(new_articles),
    )
    gemini_labels = _label_articles_with_gemini(new_articles)
    _update_progress(
        conn,
        session_id,
        STATUS_LABELING,
        STEP_MERGE_LABELS,
        PROGRESS_MERGE,
        articles_labeled=len(gemini_labels),
    )
    newly_labeled = _merge_gemini_labels(gemini_labels, new_articles)
    return TrainingArtifacts(
        existing_data=existing_data,
        labeled_hashes=labeled_hashes,
        new_articles=new_articles,
        gemini_labels=gemini_labels,
        newly_labeled=newly_labeled,
        combined_data=existing_data + newly_labeled,
    )


def _handle_insufficient_articles(
    conn: DatabaseConnection,
    session_id: str | None,
    article_count: int,
) -> TrainingResult:
    logger.info(
        "Only %d new articles, skipping (need at least %d)",
        article_count,
        MIN_ARTICLES_TO_TRAIN,
    )
    _update_progress(
        conn,
        session_id,
        STATUS_COMPLETE,
        STEP_INSUFFICIENT_ARTICLES,
        PROGRESS_DONE,
        articles_found=article_count,
    )
    return {
        "status": STATUS_SKIPPED,
        "reason": "insufficient_new_data",
        "new_articles": article_count,
    }


def _run_training_phase(
    conn: DatabaseConnection,
    session_id: str | None,
    training_data_path: Path,
    artifacts: TrainingArtifacts,
) -> TrainingResult:
    _write_training_data(training_data_path, artifacts.combined_data)
    _update_progress(
        conn,
        session_id,
        STATUS_TRAINING,
        f"{STEP_TRAINING_PREFIX} {len(artifacts.combined_data)} samples...",
        PROGRESS_TRAINING,
    )
    metrics, model_version, model_path, training_duration = _train_and_save_model(artifacts.combined_data)
    metrics["model_path"] = str(model_path)
    _save_model_metrics(conn, model_version, metrics, training_duration)
    _update_progress(
        conn,
        session_id,
        STATUS_COMPLETE,
        f"{STEP_COMPLETE_PREFIX} {metrics['accuracy']:.1%}",
        PROGRESS_DONE,
        model_version=model_version,
        accuracy=metrics["accuracy"],
    )
    return {
        "status": "success",
        "model_version": model_version,
        "new_samples_added": len(artifacts.newly_labeled),
        "total_training_samples": len(artifacts.combined_data),
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1_score": metrics["f1_score"],
        "training_duration_seconds": training_duration,
    }


def _write_training_data(training_data_path: Path, combined_data: list[dict[str, Any]]) -> None:
    training_data_path.parent.mkdir(parents=True, exist_ok=True)
    with training_data_path.open("w", encoding="utf-8") as f:
        json.dump(combined_data, f, indent=2)
    logger.info("Updated training data: %d total samples", len(combined_data))


def _handle_training_exception(
    conn: DatabaseConnection,
    session_id: str | None,
    error: Exception,
) -> TrainingResult:
    logger.exception("Retraining failed: %s", error)
    _update_progress(
        conn,
        session_id,
        STATUS_FAILED,
        "Training failed with error",
        0,
        error_message=str(error),
    )
    return {"status": STATUS_FAILED, "error": str(error)}
