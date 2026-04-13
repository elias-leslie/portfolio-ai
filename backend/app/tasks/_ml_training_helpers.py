"""Private helper functions for the ML model training pipeline."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.ml.article_quality_classifier import ArticleQualityClassifier
from app.services.agent_hub_prompt_service import render_agent_hub_prompt, require_agent_hub_prompt
from app.storage.types import DatabaseConnection

logger = get_logger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
_MODEL_VERSION_FORMAT = "v%Y%m%d"
_PRODUCTION_MODEL_FILENAME = "article_quality_v1.joblib"
_MODEL_FILENAME_TEMPLATE = "article_quality_{version}.joblib"
_MODEL_NAME = "article_quality"
_QUERY_LIMIT = 500
_HASH_HEADLINE_LENGTH = 50
_HEADLINE_MATCH_LENGTH = 40
_ARTICLE_LABELING_AGENT_SLUG = "equity-analyst"
_ARTICLE_LABELING_TEMPLATE = "portfolio-article-quality-labeling-template"
_ARTICLE_LABELING_SYSTEM = "portfolio-article-quality-labeling-system"
_QUERY_ARTICLES_SQL = f"""
        SELECT symbol, headline, summary
        FROM news_cache
        ORDER BY fetched_at DESC
        LIMIT {_QUERY_LIMIT}
    """
_METRICS_INSERT_SQL = """
        INSERT INTO ml_model_metrics
        (model_name, model_version, trained_at, training_samples, test_samples,
         accuracy, precision_score, recall_score, f1_score,
         useful_count, not_useful_count, model_path, training_duration_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """


def _load_training_data(training_data_path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    """Load existing training data and build a hash set of labeled articles."""
    if not training_data_path.exists():
        logger.info("no_existing_training_data")
        return [], set()

    with training_data_path.open(encoding="utf-8") as f:
        raw_existing_data = json.load(f)

    existing_data = [_normalize_training_article(article) for article in raw_existing_data]
    labeled_hashes = {_article_hash(article["symbol"], article["headline"]) for article in existing_data}
    logger.info("training_data_loaded", sample_count=len(existing_data))
    return existing_data, labeled_hashes


def _normalize_training_article(article: dict[str, Any]) -> dict[str, Any]:
    return {**article, "symbol": article.get("symbol") or article.get("ticker") or ""}


def _article_hash(symbol: str, headline: str) -> str:
    return f"{symbol}_{headline[:_HASH_HEADLINE_LENGTH]}"


def _query_new_articles(
    conn: DatabaseConnection, labeled_hashes: set[str], limit: int = 100
) -> list[dict[str, Any]]:
    """Query and filter new articles from the database."""
    logger.info("querying_new_articles")
    conn.execute(_QUERY_ARTICLES_SQL)
    all_articles = conn.fetchall()
    logger.info("recent_articles_found", count=len(all_articles))

    new_articles = [
        article
        for article in map(_row_to_article, all_articles)
        if _article_hash(article["symbol"], article["headline"]) not in labeled_hashes
    ]
    logger.info("new_unlabeled_articles", count=len(new_articles))

    if len(new_articles) <= limit:
        return new_articles

    logger.info("limiting_new_articles", limit=limit)
    return new_articles[:limit]


def _row_to_article(row: Any) -> dict[str, str]:
    return {
        "symbol": str(row[0]) if row[0] is not None else "",
        "headline": str(row[1]) if row[1] is not None else "",
        "summary": str(row[2]) if row[2] is not None else "",
    }


def _label_articles_with_gemini(new_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Send articles to Agent Hub for quality labeling."""
    logger.info("labeling_articles_with_agent_hub", count=len(new_articles))
    prompt = render_agent_hub_prompt(
        _ARTICLE_LABELING_TEMPLATE,
        article_rows="\n".join(
            f"{article['symbol']}|{article['headline']}|{article['summary']}"
            for article in new_articles
        ),
    )
    client = AgentHubAPIClient(agent_slug=_ARTICLE_LABELING_AGENT_SLUG)
    try:
        response = client.generate(
            prompt=prompt,
            system=require_agent_hub_prompt(_ARTICLE_LABELING_SYSTEM),
            purpose="article_quality_labeling",
        )
    finally:
        client.close()

    labels = _parse_gemini_output(response.content, "")
    logger.info("agent_hub_labeling_complete", count=len(labels))
    return labels


def _write_articles_to_tempfile(new_articles: list[dict[str, Any]]) -> str:
    """Legacy helper kept for test compatibility."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        for article in new_articles:
            tmp.write(f"{article['symbol']}|{article['headline']}|{article['summary']}\n")
        return tmp.name


def _parse_gemini_output(stdout: str, stderr: str) -> list[dict[str, Any]]:
    start = stdout.find("[")
    end = stdout.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(stdout[start:end])

    logger.error(
        "gemini_output_parse_failed",
        stdout_preview=stdout[:500],
        stderr_preview=stderr[:500] if stderr else "None",
    )
    raise ValueError("Could not parse Gemini JSON output")


def _merge_gemini_labels(
    gemini_labels: list[dict[str, Any]], new_articles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match Gemini labels with original articles."""
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

    logger.info("labeled_articles_merged", count=len(newly_labeled))
    return newly_labeled


def _headlines_match(gemini: dict[str, Any], article: dict[str, Any]) -> bool:
    return (
        gemini["symbol"] == article["symbol"]
        and gemini["headline"][:_HEADLINE_MATCH_LENGTH].lower()
        == article["headline"][:_HEADLINE_MATCH_LENGTH].lower()
    )


def _train_and_save_model(
    combined_data: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, Path, float]:
    """Train model, save it to disk, and repoint the production symlink."""
    logger.info("retraining_model")
    classifier = ArticleQualityClassifier()
    labels = [article["is_useful"] for article in combined_data]
    start_time = datetime.now(UTC)
    metrics = classifier.train(
        [article["headline"] for article in combined_data],
        [article["summary"] for article in combined_data],
        labels,
        test_size=0.2,
    )
    training_duration = (datetime.now(UTC) - start_time).total_seconds()

    # Add label distribution to metrics (not returned by classifier.train)
    metrics["useful_count"] = sum(1 for label in labels if label)
    metrics["not_useful_count"] = sum(1 for label in labels if not label)

    model_version = datetime.now(UTC).strftime(_MODEL_VERSION_FORMAT)
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _MODEL_DIR / _MODEL_FILENAME_TEMPLATE.format(version=model_version)
    classifier.save(model_path)

    prod_model_path = _MODEL_DIR / _PRODUCTION_MODEL_FILENAME
    prod_model_path.unlink(missing_ok=True)
    prod_model_path.symlink_to(model_path.name)
    logger.info("production_model_updated", prod_model_path=str(prod_model_path), new_model=model_path.name)
    return metrics, model_version, model_path, training_duration


def _save_model_metrics(
    conn: DatabaseConnection,
    model_version: str,
    metrics: dict[str, Any],
    training_duration: float,
) -> None:
    """Save training metrics to the database."""
    conn.execute(
        _METRICS_INSERT_SQL,
        [
            _MODEL_NAME,
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
            str(metrics.get("model_path", "")),
            training_duration,
        ],
    )
    conn.commit()
    logger.info("Metrics saved to database")
