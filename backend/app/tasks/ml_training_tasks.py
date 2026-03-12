"""Tasks for ML model training and retraining."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import tempfile
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ml.article_quality_classifier import ArticleQualityClassifier
from app.storage import get_storage
from app.storage.types import DatabaseConnection

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
TRAINING_DATA_FILENAME = "/home/kasadis/portfolio-ai/data/training_data_merged.json"
MODEL_DIR = "/home/kasadis/portfolio-ai/backend/models"
MODEL_VERSION_FORMAT = "v%Y%m%d"
PRODUCTION_MODEL_FILENAME = "article_quality_v1.joblib"
MODEL_FILENAME_TEMPLATE = "article_quality_{version}.joblib"
MODEL_NAME = "article_quality"
QUERY_LIMIT = 500
NEW_ARTICLE_LIMIT = 100
MIN_ARTICLES_TO_TRAIN = 10
HASH_HEADLINE_LENGTH = 50
HEADLINE_MATCH_LENGTH = 40
PROGRESS_INITIAL = 5
PROGRESS_QUERY_COMPLETE = 10
PROGRESS_LABELING = 20
PROGRESS_MERGE = 50
PROGRESS_TRAINING = 70
PROGRESS_DONE = 100
GEMINI_TIMEOUT_SECONDS = 300
GEMINI_ENV = {"HOME": "/home/kasadis", "PATH": "/usr/local/bin:/usr/bin:/bin"}
TRAINING_BANNER = "=" * 60
TRAINING_TITLE = "ARTICLE QUALITY MODEL RETRAINING"
QUERY_ARTICLES_SQL = f"""
        SELECT symbol, headline, summary
        FROM news_cache
        ORDER BY fetched_at DESC
        LIMIT {QUERY_LIMIT}
    """
GEMINI_PROMPT = """You are a financial news quality analyst. Review these news articles (pipe-delimited: symbol|headline|summary) and for EACH article, determine if it's USEFUL for stock investors.

USEFUL: Specific numbers, regulatory filings, material events, analyst actions with targets, objective data.
NOT USEFUL: Clickbait, listicles, vague speculation, opinion without data, generic commentary, marketing.

Return ONLY a JSON array: [{"symbol": "...", "headline": "first 60 chars", "is_useful": true/false, "reasons": ["reason1"], "confidence": "high/medium/low", "explanation": "brief"}]

Reason codes: specific_data, regulatory_filing, material_event, analyst_action, clickbait, listicle, too_vague, opinion_fluff, generic_commentary, marketing, duplicate"""
METRICS_INSERT_SQL = """
        INSERT INTO ml_model_metrics
        (model_name, model_version, trained_at, training_samples, test_samples,
         accuracy, precision_score, recall_score, f1_score,
         useful_count, not_useful_count, model_path, training_duration_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """


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
    """Update progress tracking if session_id provided (manual trigger)."""
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
    """Scheduled daily model retraining (no progress tracking)."""
    return _retrain_article_quality_model_impl(session_id=None)


def _load_training_data(training_data_path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    """Load existing training data and build hash set of labeled articles (Step 1)."""
    if not training_data_path.exists():
        print("\n📖 No existing training data found, starting fresh")
        return [], set()

    with training_data_path.open() as f:
        raw_existing_data = json.load(f)

    existing_data = [_normalize_training_article(article) for article in raw_existing_data]
    labeled_hashes = {_article_hash(article["symbol"], article["headline"]) for article in existing_data}
    print(f"\n📖 Loaded {len(existing_data)} existing training samples")
    return existing_data, labeled_hashes


def _normalize_training_article(article: dict[str, Any]) -> dict[str, Any]:
    return {**article, "symbol": article.get("symbol") or article.get("ticker") or ""}


def _article_hash(symbol: str, headline: str) -> str:
    return f"{symbol}_{headline[:HASH_HEADLINE_LENGTH]}"


def _query_new_articles(
    conn: DatabaseConnection, labeled_hashes: set[str], limit: int = NEW_ARTICLE_LIMIT
) -> list[dict[str, Any]]:
    """Query and filter new articles from database (Step 2)."""
    print("\n🔍 Querying new articles from database...")
    conn.execute(QUERY_ARTICLES_SQL)
    all_articles = conn.fetchall()
    print(f"   Found {len(all_articles)} recent articles")

    new_articles = [
        article
        for article in map(_row_to_article, all_articles)
        if _article_hash(article["symbol"], article["headline"]) not in labeled_hashes
    ]
    print(f"   {len(new_articles)} are NEW (not yet labeled)")

    if len(new_articles) <= limit:
        return new_articles

    print(f"   Limiting to {limit} new articles for this training run")
    return new_articles[:limit]


def _row_to_article(row: Any) -> dict[str, str]:
    return {
        "symbol": str(row[0]) if row[0] is not None else "",
        "headline": str(row[1]) if row[1] is not None else "",
        "summary": str(row[2]) if row[2] is not None else "",
    }


def _label_articles_with_gemini(new_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Send articles to Gemini for quality labeling (Step 3)."""
    print(f"\n🤖 Labeling {len(new_articles)} articles with Gemini...")
    tmp_path = _write_articles_to_tempfile(new_articles)

    with Path(tmp_path).open() as tmp_file:
        result = subprocess.run(
            ["gemini", "--prompt", GEMINI_PROMPT],
            stdin=tmp_file,
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT_SECONDS,
            check=False,
            env=GEMINI_ENV,
        )

    if result.returncode != 0:
        raise RuntimeError(f"Gemini labeling failed: {result.stderr}")

    gemini_labels = _parse_gemini_output(result.stdout, result.stderr)
    print(f"   ✅ Gemini labeled {len(gemini_labels)} articles")
    return gemini_labels


def _write_articles_to_tempfile(new_articles: list[dict[str, Any]]) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        for article in new_articles:
            tmp.write(f"{article['symbol']}|{article['headline']}|{article['summary']}\n")
        return tmp.name


def _parse_gemini_output(stdout: str, stderr: str) -> list[dict[str, Any]]:
    start = stdout.find("[")
    end = stdout.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(stdout[start:end])

    print("\n❌ Could not parse Gemini output")
    print(f"   Gemini stdout (first 500 chars): {stdout[:500]}")
    print(f"   Gemini stderr: {stderr[:500] if stderr else 'None'}")
    raise ValueError("Could not parse Gemini JSON output")


def _merge_gemini_labels(
    gemini_labels: list[dict[str, Any]], new_articles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match Gemini labels with original articles (Step 4)."""
    newly_labeled = []
    for gemini in gemini_labels:
        match = next((article for article in new_articles if _headlines_match(gemini, article)), None)
        if match is None:
            continue
        newly_labeled.append(
            {
                "symbol": match["symbol"],
                "headline": match["headline"],
                "summary": match["summary"],
                "is_useful": gemini["is_useful"],
                "gemini_reasons": gemini["reasons"],
                "gemini_confidence": gemini["confidence"],
            }
        )

    print(f"   ✅ Merged {len(newly_labeled)} labeled articles")
    return newly_labeled


def _headlines_match(gemini: dict[str, Any], article: dict[str, Any]) -> bool:
    return (
        gemini["symbol"] == article["symbol"]
        and gemini["headline"][:HEADLINE_MATCH_LENGTH].lower()
        == article["headline"][:HEADLINE_MATCH_LENGTH].lower()
    )


def _train_and_save_model(
    combined_data: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, Path, float]:
    """Train model, save to disk, create symlink (Steps 6-7)."""
    print("\n🎓 Retraining model...")
    classifier = ArticleQualityClassifier()
    start_time = datetime.now(UTC)
    metrics = classifier.train(
        [article["headline"] for article in combined_data],
        [article["summary"] for article in combined_data],
        [article["is_useful"] for article in combined_data],
        test_size=0.2,
    )
    training_duration = (datetime.now(UTC) - start_time).total_seconds()
    model_version = datetime.now(UTC).strftime(MODEL_VERSION_FORMAT)
    model_path = Path(MODEL_DIR) / MODEL_FILENAME_TEMPLATE.format(version=model_version)
    classifier.save(model_path)

    prod_model_path = Path(MODEL_DIR) / PRODUCTION_MODEL_FILENAME
    prod_model_path.unlink(missing_ok=True)
    prod_model_path.symlink_to(model_path.name)
    print(f"\n✅ Production model updated: {prod_model_path} -> {model_path.name}")
    return metrics, model_version, model_path, training_duration


def _save_model_metrics(
    conn: DatabaseConnection,
    model_version: str,
    metrics: dict[str, Any],
    training_duration: float,
) -> None:
    """Save training metrics to database (Step 8)."""
    conn.execute(
        METRICS_INSERT_SQL,
        [
            MODEL_NAME,
            model_version,
            datetime.now(UTC),
            metrics["train_size"],
            metrics["test_size"],
            metrics["accuracy"],
            metrics["precision"],
            metrics["recall"],
            metrics["f1_score"],
            metrics.get("useful_count", 0),
            metrics.get("not_useful_count", 0),
            metrics.get("model_path", ""),
            training_duration,
        ],
    )
    conn.commit()
    print("\n✅ Metrics saved to database")


def _retrain_article_quality_model_impl(
    session_id: str | None = None,
) -> TrainingResult:
    """Retrain article quality model with new Gemini-labeled data."""
    print(TRAINING_BANNER)
    print(TRAINING_TITLE)
    print(TRAINING_BANNER)

    storage = get_storage()
    training_data_path = Path(TRAINING_DATA_FILENAME)

    with storage.connection() as conn:
        try:
            artifacts = _prepare_training_artifacts(conn, session_id, training_data_path)
            if len(artifacts.new_articles) < MIN_ARTICLES_TO_TRAIN:
                return _handle_insufficient_articles(conn, session_id, len(artifacts.new_articles))
            return _complete_training(conn, session_id, training_data_path, artifacts)
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
    new_articles = _query_new_articles(conn, labeled_hashes)
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
    print(
        f"\n⚠️  Only {article_count} new articles, skipping (need at least {MIN_ARTICLES_TO_TRAIN})"
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


def _complete_training(
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
    metrics, model_version, _, training_duration = _train_and_save_model(artifacts.combined_data)
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
    with training_data_path.open("w") as f:
        json.dump(combined_data, f, indent=2)
    print(f"\n💾 Updated training data: {len(combined_data)} total samples")


def _handle_training_exception(
    conn: DatabaseConnection,
    session_id: str | None,
    error: Exception,
) -> TrainingResult:
    print(f"\n❌ Retraining failed: {error}")
    traceback.print_exc()
    _update_progress(
        conn,
        session_id,
        STATUS_FAILED,
        "Training failed with error",
        0,
        error_message=str(error),
    )
    return {"status": STATUS_FAILED, "error": str(error)}
