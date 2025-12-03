/**
 * API client for disagreement detection endpoints.
 *
 * Provides functions to fetch multi-LLM disagreement data:
 * - List recent disagreements between Gemini and Claude
 * - Get disagreement statistics and trends
 * - Get symbol-specific disagreement history
 */

import { get } from "./client";

// Types

export interface DisagreementItem {
  review_pair_id: string;
  symbol: string;
  created_at: string;
  agreement_score: number;
  disagreement_severity: "none" | "minor" | "major";
  gemini_review: string | null;
  claude_review: string | null;
  consensus_summary: string;
}

export interface DisagreementsResponse {
  items: DisagreementItem[];
  total: number;
}

export interface TrendDataPoint {
  date: string;
  reviews: number;
  disagreements: number;
  avg_score: number;
}

export interface DisagreementStats {
  total_reviews: number;
  total_review_pairs: number;
  agreement_count: number;
  minor_disagreement_count: number;
  major_disagreement_count: number;
  agreement_rate: number;
  minor_disagreement_rate: number;
  major_disagreement_rate: number;
  avg_agreement_score: number;
  trend_7d: TrendDataPoint[];
}

// API Functions

/**
 * Fetch recent disagreements between LLM providers.
 *
 * @param days - Number of days to look back (default 7)
 * @param severity - Filter by severity (minor, major, or undefined for all)
 * @param limit - Maximum results (default 50)
 */
export async function getDisagreements(
  days: number = 7,
  severity?: "minor" | "major",
  limit: number = 50
): Promise<DisagreementsResponse> {
  const params = new URLSearchParams();
  params.set("days", days.toString());
  params.set("limit", limit.toString());
  if (severity) {
    params.set("severity", severity);
  }
  return get<DisagreementsResponse>(`/api/disagreements?${params.toString()}`);
}

/**
 * Fetch disagreement statistics and trends.
 *
 * @param days - Number of days to analyze (default 30)
 */
export async function getDisagreementStats(
  days: number = 30
): Promise<DisagreementStats> {
  return get<DisagreementStats>(`/api/disagreements/stats?days=${days}`);
}

/**
 * Fetch disagreements for a specific symbol.
 *
 * @param symbol - Stock symbol
 * @param days - Number of days to look back (default 30)
 */
export async function getSymbolDisagreements(
  symbol: string,
  days: number = 30
): Promise<DisagreementsResponse> {
  return get<DisagreementsResponse>(
    `/api/disagreements/${symbol.toUpperCase()}?days=${days}`
  );
}
