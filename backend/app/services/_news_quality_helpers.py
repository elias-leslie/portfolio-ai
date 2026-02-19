"""Text processing helpers for news quality metrics."""

from __future__ import annotations


def _tokenize(text: str) -> list[str]:
    """Tokenize text by splitting on whitespace and removing punctuation.

    Returns:
        List of normalized tokens (length > 2).
    """
    for char in ".,!?;:()[]{}\"'":
        text = text.replace(char, " ")
    return [token.strip() for token in text.split() if len(token.strip()) > 2]


def _token_overlap_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between token sets of two texts.

    Returns:
        Float 0.0-1.0 where 1.0=identical tokens, 0.0=no overlap.
    """
    tokens1 = set(_tokenize(text1))
    tokens2 = set(_tokenize(text2))

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    if union == 0:
        return 0.0
    return intersection / union
