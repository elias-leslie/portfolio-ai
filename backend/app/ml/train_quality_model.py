#!/usr/bin/env python3
"""
Train article quality classifier on Gemini-labeled data.

Usage:
    cd ~/portfolio-ai/backend && source .venv/bin/activate
    python -m app.ml.train_quality_model
"""

import json
from pathlib import Path

from app.ml.article_quality_classifier import ArticleQualityClassifier


def main() -> None:
    """Train and save article quality model."""
    print("=" * 60)
    print("ARTICLE QUALITY MODEL TRAINING")
    print("=" * 60)

    # Load merged data (Gemini labels + original article text)
    labels_file = Path("/home/kasadis/portfolio-ai/data/training_data_merged.json")

    print(f"\n📖 Loading labels from: {labels_file}")

    with labels_file.open() as f:
        labeled_data = json.load(f)

    print(f"   Loaded {len(labeled_data)} labeled articles")

    # Extract features and labels
    headlines = []
    summaries = []
    labels = []

    for article in labeled_data:
        headlines.append(article["headline"])
        summaries.append(article.get("summary", ""))  # Use actual article summary
        labels.append(article["is_useful"])

    # Count label distribution
    useful_count = sum(labels)
    not_useful_count = len(labels) - useful_count

    print("\n📊 Label Distribution:")
    print(f"   USEFUL: {useful_count} ({useful_count / len(labels) * 100:.1f}%)")
    print(f"   NOT USEFUL: {not_useful_count} ({not_useful_count / len(labels) * 100:.1f}%)")

    # Train model
    print("\n🎓 Training model...")

    classifier = ArticleQualityClassifier()

    metrics = classifier.train(
        headlines=headlines,
        summaries=summaries,
        labels=labels,
        test_size=0.2,  # 80% train, 20% test
    )

    # Save model
    model_path = Path("/home/kasadis/portfolio-ai/backend/models/article_quality_v1.joblib")
    model_path.parent.mkdir(parents=True, exist_ok=True)

    classifier.save(model_path)

    # Test on a few examples
    print("\n" + "=" * 60)
    print("SAMPLE PREDICTIONS")
    print("=" * 60)

    test_examples = [
        ("Apple Reports Q4 Earnings Beat with EPS $2.50 vs $2.30 Expected", ""),
        ("5 Stocks to Watch This Week", ""),
        ("Bitcoin To $1M, Jesus Christ's Second Coming: Crypto Speculation", ""),
        ("JPMorgan upgrades AAPL to $200 price target", ""),
        ("Should you buy Tesla stock?", ""),
    ]

    for headline, summary in test_examples:
        pred = classifier.predict(headline, summary)
        label = "✅ USEFUL" if pred["is_useful"] else "❌ NOT USEFUL"
        print(f"\n{label} (confidence: {pred['confidence']:.2f})")
        print(f'   "{headline[:70]}"')

    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print(f"\nModel saved to: {model_path}")
    print(f"Accuracy: {metrics['accuracy']:.1%}")
    print(f"Precision: {metrics['precision']:.1%}")
    print(f"Recall: {metrics['recall']:.1%}")
    print(f"F1 Score: {metrics['f1_score']:.1%}")
    print("\nReady to integrate into backend API!")


if __name__ == "__main__":
    main()
