/**
 * Shared news and sentiment formatting utilities
 * Used across Market News, Watchlist News Intelligence, and Watchlist Sentiment sections
 */

import { formatDistanceToNow } from "date-fns";

/**
 * Standard vendor labels for news sources
 */
export const VENDOR_LABELS: Record<string, string> = {
  polygon: "Polygon",
  finnhub: "Finnhub",
  fmp: "FMP",
  googleNews: "Google News",
  yfinance: "Yahoo Finance",
};

/**
 * Format sentiment score with consistent null handling
 * @param score Sentiment score (-1.0 to +1.0) or null/undefined
 * @returns Formatted score string (e.g., "+0.85", "-0.23", "—")
 */
export function formatSentimentScore(
  score: number | null | undefined
): string {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "—";
  }
  const rounded = score.toFixed(2);
  return score > 0 ? `+${rounded}` : rounded;
}

/**
 * Format vendor name with standard labels
 * @param vendor Raw vendor identifier (e.g., "polygon", "finnhub")
 * @returns Human-readable vendor label (e.g., "Polygon", "Finnhub")
 */
export function formatVendorLabel(vendor?: string | null): string {
  if (!vendor) {
    return "Unknown Source";
  }
  const normalized = vendor.toLowerCase();
  return VENDOR_LABELS[normalized] || vendor.trim();
}

/**
 * Get badge variant for sentiment display
 * Supports both label-based ("positive", "negative", "neutral") and score-based (0.5, -0.3) input
 * @param labelOrScore Sentiment label string or numeric score
 * @returns Badge variant for consistent color coding
 */
export function getSentimentBadgeVariant(
  labelOrScore: string | number | null | undefined
): "gain" | "loss" | "neutral" {
  // Handle string labels
  if (typeof labelOrScore === "string") {
    const normalized = labelOrScore.toLowerCase();
    if (normalized === "positive") return "gain";
    if (normalized === "negative") return "loss";
    return "neutral";
  }

  // Handle numeric scores
  if (typeof labelOrScore === "number") {
    if (labelOrScore > 0.1) return "gain";
    if (labelOrScore < -0.1) return "loss";
    return "neutral";
  }

  // Handle null/undefined
  return "neutral";
}

/**
 * Format confidence score as percentage
 * @param confidence Confidence value (0.0 to 1.0) or null/undefined
 * @returns Formatted percentage string (e.g., "92%", "—")
 */
export function formatConfidence(
  confidence: number | null | undefined
): string {
  if (
    confidence === null ||
    confidence === undefined ||
    Number.isNaN(confidence)
  ) {
    return "—";
  }
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Format relative date for news articles
 * @param dateString ISO date string
 * @returns Relative date string (e.g., "5 hours ago", "2 days ago")
 */
export function formatNewsDate(dateString: string | null | undefined): string {
  if (!dateString) return "";

  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return "";
  }
}

/**
 * Article-like structure with optional sentiment fields
 */
interface ArticleWithSentiment {
  sentimentScore?: number;
  sentiment?: {
    score: number;
  };
}

/**
 * Extract sentiment score from article with varying data structures.
 * Normalizes the different shapes: sentimentScore directly, or nested sentiment.score
 * @param article Article object with optional sentimentScore or sentiment.score
 * @param defaultValue Value to return if no score found (default: 0)
 * @returns Numeric sentiment score
 */
export function getSentimentScore(
  article: ArticleWithSentiment,
  defaultValue: number = 0
): number {
  return article.sentimentScore ?? article.sentiment?.score ?? defaultValue;
}

/**
 * Extract sentiment score from article, returning undefined if not found.
 * Use this when you need to distinguish "no score" from "score is 0".
 * @param article Article object with optional sentimentScore or sentiment.score
 * @returns Numeric sentiment score or undefined
 */
export function getSentimentScoreOrUndefined(
  article: ArticleWithSentiment
): number | undefined {
  return article.sentimentScore ?? article.sentiment?.score;
}
