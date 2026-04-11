from __future__ import annotations

from app.services.news_processing import _compose_text, _sanitize_summary


def test_sanitize_summary_drops_google_news_wrapper_html() -> None:
    summary = (
        '<a href="https://news.google.com/rss/articles/abc" target="_blank">'
        "Why Monday, April 13 Begins A Critical Week For The Stock Market Rally"
        '</a>&nbsp;&nbsp;<font color="#6f6f6f">Investor\'s Business Daily</font>'
    )

    cleaned = _sanitize_summary(
        summary,
        headline="Why Monday, April 13 Begins A Critical Week For The Stock Market Rally",
        source="Investor's Business Daily",
    )

    assert cleaned is None


def test_compose_text_ignores_wrapped_google_news_summary_boilerplate() -> None:
    entry = {
        "headline": "Why Monday, April 13 Begins A Critical Week For The Stock Market Rally",
        "summary": (
            '<a href="https://news.google.com/rss/articles/abc" target="_blank">'
            "Why Monday, April 13 Begins A Critical Week For The Stock Market Rally"
            '</a>&nbsp;&nbsp;<font color="#6f6f6f">Investor\'s Business Daily</font>'
        ),
        "source": "Investor's Business Daily",
    }

    composed = _compose_text(entry)

    assert composed == "Why Monday, April 13 Begins A Critical Week For The Stock Market Rally"
