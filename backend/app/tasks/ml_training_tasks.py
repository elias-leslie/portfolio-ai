"""Celery tasks for ML model training and retraining."""

from __future__ import annotations

import json
import subprocess
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from app.celery_app import celery_app as celery
from app.ml.article_quality_classifier import ArticleQualityClassifier
from app.storage import get_storage


def _update_progress(
    conn: Any,
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
        update_values.append(value)

    update_values.append(session_id)

    conn.execute(
        f"UPDATE ml_training_progress SET {', '.join(update_fields)} WHERE session_id = %s",
        update_values,
    )
    conn.commit()


@celery.task(name="retrain_article_quality_model_manual")  # type: ignore[misc]
def retrain_article_quality_model_manual(session_id: str) -> dict[str, str | float | int]:
    """Manually triggered model retraining with progress tracking."""
    return _retrain_article_quality_model_impl(session_id=session_id)


@celery.task(name="retrain_article_quality_model")  # type: ignore[misc]
def retrain_article_quality_model() -> dict[str, str | float | int]:
    """Scheduled daily model retraining (no progress tracking)."""
    return _retrain_article_quality_model_impl(session_id=None)


def _retrain_article_quality_model_impl(
    session_id: str | None = None,
) -> dict[str, str | float | int]:
    """Retrain article quality model with new Gemini-labeled data."""
    print("=" * 60)
    print("ARTICLE QUALITY MODEL RETRAINING")
    print("=" * 60)

    storage = get_storage()

    with storage.connection() as conn:
        try:
            _update_progress(conn, session_id, "querying", "Loading existing training data...", 5)

            # Step 1: Load existing training data
            training_data_path = Path("/home/kasadis/portfolio-ai/data/training_data_merged.json")

            if training_data_path.exists():
                with training_data_path.open() as f:
                    existing_data = json.load(f)
                print(f"\n📖 Loaded {len(existing_data)} existing training samples")

                labeled_hashes = set()
                for article in existing_data:
                    hash_key = f"{article['ticker']}_{article['headline'][:50]}"
                    labeled_hashes.add(hash_key)
            else:
                existing_data = []
                labeled_hashes = set()
                print("\n📖 No existing training data found, starting fresh")

            # Step 2: Query new articles
            print("\n🔍 Querying new articles from database...")
            _update_progress(
                conn, session_id, "querying", "Querying database for new articles...", 10
            )

            conn.execute(
                """
                SELECT ticker, headline, summary
                FROM news_cache
                ORDER BY fetched_at DESC
                LIMIT 500
            """
            )

            all_articles = conn.fetchall()
            print(f"   Found {len(all_articles)} recent articles")

            # Filter out already-labeled
            new_articles = []
            for row in all_articles:
                ticker, headline, summary = row
                hash_key = f"{ticker}_{headline[:50]}"
                if hash_key not in labeled_hashes:
                    new_articles.append(
                        {"ticker": ticker, "headline": headline, "summary": summary or ""}
                    )

            print(f"   {len(new_articles)} are NEW (not yet labeled)")

            if len(new_articles) > 100:
                new_articles = new_articles[:100]
                print("   Limiting to 100 new articles for this training run")

            if len(new_articles) < 10:
                print(f"\n⚠️  Only {len(new_articles)} new articles, skipping (need at least 10)")
                _update_progress(
                    conn,
                    session_id,
                    "complete",
                    "Skipped - insufficient new articles",
                    100,
                    articles_found=len(new_articles),
                )
                return {
                    "status": "skipped",
                    "reason": "insufficient_new_data",
                    "new_articles": len(new_articles),
                }

            # Step 3: Label with Gemini
            print(f"\n🤖 Labeling {len(new_articles)} articles with Gemini...")
            _update_progress(
                conn,
                session_id,
                "labeling",
                f"Labeling {len(new_articles)} articles with Gemini...",
                20,
                articles_found=len(all_articles),
                articles_total=len(new_articles),
            )

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
                for article in new_articles:
                    line = f"{article['ticker']}|{article['headline']}|{article['summary']}\n"
                    tmp.write(line)
                tmp_path = tmp.name

            gemini_prompt = """You are a financial news quality analyst. Review these news articles (pipe-delimited: ticker|headline|summary) and for EACH article, determine if it's USEFUL for stock investors.

USEFUL: Specific numbers, regulatory filings, material events, analyst actions with targets, objective data.
NOT USEFUL: Clickbait, listicles, vague speculation, opinion without data, generic commentary, marketing.

Return ONLY a JSON array: [{"ticker": "...", "headline": "first 60 chars", "is_useful": true/false, "reasons": ["reason1"], "confidence": "high/medium/low", "explanation": "brief"}]

Reason codes: specific_data, regulatory_filing, material_event, analyst_action, clickbait, listicle, too_vague, opinion_fluff, generic_commentary, marketing, duplicate"""

            with Path(tmp_path).open() as tmp_file:
                # Set HOME to kasadis user for gemini config access
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
                print(f"\n❌ Gemini labeling failed: {result.stderr}")
                _update_progress(
                    conn,
                    session_id,
                    "failed",
                    "Gemini labeling failed",
                    0,
                    error_message=result.stderr,
                )
                return {"status": "failed", "error": "gemini_labeling_failed"}

            # Parse Gemini output
            gemini_output = result.stdout
            start = gemini_output.find("[")
            end = gemini_output.rfind("]") + 1

            if start < 0 or end <= start:
                print("\n❌ Could not parse Gemini output")
                print(f"   Gemini stdout (first 500 chars): {gemini_output[:500]}")
                print(f"   Gemini stderr: {result.stderr[:500] if result.stderr else 'None'}")
                _update_progress(
                    conn,
                    session_id,
                    "failed",
                    "Could not parse Gemini output",
                    0,
                    error_message=f"Invalid JSON from Gemini. Output: {gemini_output[:200]}",
                )
                return {"status": "failed", "error": "gemini_parse_failed"}

            gemini_labels = json.loads(gemini_output[start:end])
            print(f"   ✅ Gemini labeled {len(gemini_labels)} articles")

            _update_progress(
                conn,
                session_id,
                "labeling",
                "Merging Gemini labels...",
                50,
                articles_labeled=len(gemini_labels),
            )

            # Merge labels with article data
            newly_labeled = []
            for gemini in gemini_labels:
                for article in new_articles:
                    if (
                        gemini["ticker"] == article["ticker"]
                        and gemini["headline"][:40].lower() == article["headline"][:40].lower()
                    ):
                        newly_labeled.append(
                            {
                                "ticker": article["ticker"],
                                "headline": article["headline"],
                                "summary": article["summary"],
                                "is_useful": gemini["is_useful"],
                                "gemini_reasons": gemini["reasons"],
                                "gemini_confidence": gemini["confidence"],
                            }
                        )
                        break

            print(f"   ✅ Merged {len(newly_labeled)} labeled articles")

            # Step 4: Combine and save
            combined_data = existing_data + newly_labeled
            with training_data_path.open("w") as f:
                json.dump(combined_data, f, indent=2)

            print(f"\n💾 Updated training data: {len(combined_data)} total samples")

            # Step 5: Retrain model
            print("\n🎓 Retraining model...")
            _update_progress(
                conn, session_id, "training", f"Training on {len(combined_data)} samples...", 70
            )

            headlines = [a["headline"] for a in combined_data]
            summaries = [a["summary"] for a in combined_data]
            labels = [a["is_useful"] for a in combined_data]

            classifier = ArticleQualityClassifier()
            start_time = datetime.now()
            metrics = classifier.train(headlines, summaries, labels, test_size=0.2)
            training_duration = (datetime.now() - start_time).total_seconds()

            # Step 6: Save model
            model_version = datetime.now().strftime("v%Y%m%d")
            model_path = Path(
                f"/home/kasadis/portfolio-ai/backend/models/article_quality_{model_version}.joblib"
            )
            classifier.save(model_path)

            prod_model_path = Path(
                "/home/kasadis/portfolio-ai/backend/models/article_quality_v1.joblib"
            )
            prod_model_path.unlink(missing_ok=True)
            prod_model_path.symlink_to(model_path.name)

            print(f"\n✅ Production model updated: {prod_model_path} -> {model_path.name}")

            # Step 7: Save metrics
            useful_count = sum(labels)
            not_useful_count = len(labels) - useful_count

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
                    datetime.now(),
                    metrics["train_size"],
                    metrics["test_size"],
                    metrics["accuracy"],
                    metrics["precision"],
                    metrics["recall"],
                    metrics["f1_score"],
                    useful_count,
                    not_useful_count,
                    str(model_path),
                    training_duration,
                ],
            )
            conn.commit()

            print("\n✅ Metrics saved to database")

            # Step 8: Mark complete
            _update_progress(
                conn,
                session_id,
                "complete",
                f"Training complete! Accuracy: {metrics['accuracy']:.1%}",
                100,
                model_version=model_version,
                accuracy=metrics["accuracy"],
                completed_at="NOW()",
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
