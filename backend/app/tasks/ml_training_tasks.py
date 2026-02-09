"""Celery tasks for ML model training and retraining."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ml.article_quality_classifier import ArticleQualityClassifier
from app.storage import get_storage
from app.storage.types import DatabaseConnection


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

    # Build parameter list - add kwargs values
    for key, value in kwargs.items():
        update_fields.append(f"{key} = %s")
        # Cast value to acceptable types
        if isinstance(value, (str, int, float, bool, dt.datetime)):
            update_values.append(value)
        else:
            update_values.append(str(value) if value is not None else None)

    update_values.append(session_id)

    conn.execute(
        f"UPDATE ml_training_progress SET {', '.join(update_fields)} WHERE session_id = %s",
        update_values,  # type: ignore[arg-type]
    )
    conn.commit()


def retrain_article_quality_model_manual(session_id: str) -> dict[str, str | float | int]:
    """Manually triggered model retraining with progress tracking."""
    return _retrain_article_quality_model_impl(session_id=session_id)


def retrain_article_quality_model() -> dict[str, str | float | int]:
    """Scheduled daily model retraining (no progress tracking)."""
    return _retrain_article_quality_model_impl(session_id=None)


def _load_training_data(training_data_path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    """Load existing training data and build hash set of labeled articles (Step 1)."""
    if training_data_path.exists():
        with training_data_path.open() as f:
            existing_data = json.load(f)
        print(f"\n📖 Loaded {len(existing_data)} existing training samples")

        labeled_hashes = set()
        for article in existing_data:
            hash_key = f"{article['symbol']}_{article['headline'][:50]}"
            labeled_hashes.add(hash_key)
    else:
        existing_data = []
        labeled_hashes = set()
        print("\n📖 No existing training data found, starting fresh")

    return existing_data, labeled_hashes


def _query_new_articles(
    conn: DatabaseConnection, labeled_hashes: set[str], limit: int = 100
) -> list[dict[str, Any]]:
    """Query and filter new articles from database (Step 2)."""
    print("\n🔍 Querying new articles from database...")

    conn.execute(
        """
        SELECT symbol, headline, summary
        FROM news_cache
        ORDER BY fetched_at DESC
        LIMIT 500
    """
    )

    all_articles = conn.fetchall()
    print(f"   Found {len(all_articles)} recent articles")

    new_articles = []
    for row in all_articles:
        # Cast database row values to proper types
        symbol = str(row[0]) if row[0] is not None else ""
        headline = str(row[1]) if row[1] is not None else ""
        summary = str(row[2]) if row[2] is not None else ""

        hash_key = f"{symbol}_{headline[:50]}"
        if hash_key not in labeled_hashes:
            new_articles.append({"symbol": symbol, "headline": headline, "summary": summary})

    print(f"   {len(new_articles)} are NEW (not yet labeled)")

    if len(new_articles) > limit:
        new_articles = new_articles[:limit]
        print(f"   Limiting to {limit} new articles for this training run")

    return new_articles


def _label_articles_with_gemini(new_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Send articles to Gemini for quality labeling (Step 3)."""
    print(f"\n🤖 Labeling {len(new_articles)} articles with Gemini...")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        for article in new_articles:
            line = f"{article['symbol']}|{article['headline']}|{article['summary']}\n"
            tmp.write(line)
        tmp_path = tmp.name

    gemini_prompt = """You are a financial news quality analyst. Review these news articles (pipe-delimited: symbol|headline|summary) and for EACH article, determine if it's USEFUL for stock investors.

USEFUL: Specific numbers, regulatory filings, material events, analyst actions with targets, objective data.
NOT USEFUL: Clickbait, listicles, vague speculation, opinion without data, generic commentary, marketing.

Return ONLY a JSON array: [{"symbol": "...", "headline": "first 60 chars", "is_useful": true/false, "reasons": ["reason1"], "confidence": "high/medium/low", "explanation": "brief"}]

Reason codes: specific_data, regulatory_filing, material_event, analyst_action, clickbait, listicle, too_vague, opinion_fluff, generic_commentary, marketing, duplicate"""

    with Path(tmp_path).open() as tmp_file:
        env = {"HOME": "/home/kasadis", "PATH": "/usr/local/bin:/usr/bin:/bin"}
        result = subprocess.run(
            ["gemini", "--prompt", gemini_prompt],
            stdin=tmp_file,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=env,
        )

    if result.returncode != 0:
        raise RuntimeError(f"Gemini labeling failed: {result.stderr}")

    gemini_output = result.stdout
    start = gemini_output.find("[")
    end = gemini_output.rfind("]") + 1

    if start < 0 or end <= start:
        print("\n❌ Could not parse Gemini output")
        print(f"   Gemini stdout (first 500 chars): {gemini_output[:500]}")
        print(f"   Gemini stderr: {result.stderr[:500] if result.stderr else 'None'}")
        raise ValueError("Could not parse Gemini JSON output")

    gemini_labels: list[dict[str, Any]] = json.loads(gemini_output[start:end])
    print(f"   ✅ Gemini labeled {len(gemini_labels)} articles")

    return gemini_labels


def _merge_gemini_labels(
    gemini_labels: list[dict[str, Any]], new_articles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match Gemini labels with original articles (Step 4)."""
    newly_labeled = []
    for gemini in gemini_labels:
        for article in new_articles:
            if (
                gemini["symbol"] == article["symbol"]
                and gemini["headline"][:40].lower() == article["headline"][:40].lower()
            ):
                newly_labeled.append(
                    {
                        "symbol": article["symbol"],
                        "headline": article["headline"],
                        "summary": article["summary"],
                        "is_useful": gemini["is_useful"],
                        "gemini_reasons": gemini["reasons"],
                        "gemini_confidence": gemini["confidence"],
                    }
                )
                break

    print(f"   ✅ Merged {len(newly_labeled)} labeled articles")
    return newly_labeled


def _train_and_save_model(
    combined_data: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, Path, float]:
    """Train model, save to disk, create symlink (Steps 6-7)."""
    print("\n🎓 Retraining model...")

    headlines = [a["headline"] for a in combined_data]
    summaries = [a["summary"] for a in combined_data]
    labels = [a["is_useful"] for a in combined_data]

    classifier = ArticleQualityClassifier()
    start_time = datetime.now(UTC)
    metrics = classifier.train(headlines, summaries, labels, test_size=0.2)
    training_duration = (datetime.now(UTC) - start_time).total_seconds()

    model_version = datetime.now(UTC).strftime("v%Y%m%d")
    model_path = Path(
        f"/home/kasadis/portfolio-ai/backend/models/article_quality_{model_version}.joblib"
    )
    classifier.save(model_path)

    prod_model_path = Path("/home/kasadis/portfolio-ai/backend/models/article_quality_v1.joblib")
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
        """
        INSERT INTO ml_model_metrics
        (model_name, model_version, trained_at, training_samples, test_samples,
         accuracy, precision_score, recall_score, f1_score,
         useful_count, not_useful_count, model_path, training_duration_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
        [
            "article_quality",
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
) -> dict[str, str | float | int]:
    """Retrain article quality model with new Gemini-labeled data."""
    print("=" * 60)
    print("ARTICLE QUALITY MODEL RETRAINING")
    print("=" * 60)

    storage = get_storage()
    training_data_path = Path("/home/kasadis/portfolio-ai/data/training_data_merged.json")

    with storage.connection() as conn:
        try:
            _update_progress(conn, session_id, "querying", "Loading existing training data...", 5)
            existing_data, labeled_hashes = _load_training_data(training_data_path)
            _update_progress(conn, session_id, "querying", "Querying database...", 10)
            new_articles = _query_new_articles(conn, labeled_hashes, limit=100)

            if len(new_articles) < 10:
                print(f"\n⚠️  Only {len(new_articles)} new articles, skipping (need at least 10)")
                _update_progress(
                    conn,
                    session_id,
                    "complete",
                    "Skipped - insufficient articles",
                    100,
                    articles_found=len(new_articles),
                )
                return {
                    "status": "skipped",
                    "reason": "insufficient_new_data",
                    "new_articles": len(new_articles),
                }

            _update_progress(
                conn,
                session_id,
                "labeling",
                f"Labeling {len(new_articles)} articles...",
                20,
                articles_found=len(new_articles),
                articles_total=len(new_articles),
            )
            try:
                gemini_labels = _label_articles_with_gemini(new_articles)
            except (RuntimeError, ValueError) as e:
                _update_progress(conn, session_id, "failed", str(e), 0, error_message=str(e))
                return {"status": "failed", "error": str(e)}

            _update_progress(
                conn,
                session_id,
                "labeling",
                "Merging labels...",
                50,
                articles_labeled=len(gemini_labels),
            )
            newly_labeled = _merge_gemini_labels(gemini_labels, new_articles)

            combined_data = existing_data + newly_labeled
            with training_data_path.open("w") as f:
                json.dump(combined_data, f, indent=2)
            print(f"\n💾 Updated training data: {len(combined_data)} total samples")

            _update_progress(
                conn, session_id, "training", f"Training on {len(combined_data)} samples...", 70
            )
            metrics, model_version, _, training_duration = _train_and_save_model(combined_data)

            _save_model_metrics(conn, model_version, metrics, training_duration)
            _update_progress(
                conn,
                session_id,
                "complete",
                f"Complete! Accuracy: {metrics['accuracy']:.1%}",
                100,
                model_version=model_version,
                accuracy=metrics["accuracy"],
            )

            return {
                "status": "success",
                "model_version": model_version,
                "new_samples_added": len(newly_labeled),
                "total_training_samples": len(combined_data),
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1_score": metrics["f1_score"],
                "training_duration_seconds": training_duration,
            }

        except Exception as e:
            print(f"\n❌ Retraining failed: {e}")
            traceback.print_exc()
            _update_progress(
                conn, session_id, "failed", "Training failed with error", 0, error_message=str(e)
            )
            return {"status": "failed", "error": str(e)}
