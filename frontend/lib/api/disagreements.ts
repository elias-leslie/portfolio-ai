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
  reviewPairId: string;
  symbol: string;
  createdAt: string;
  agreementScore: number;
  disagreementSeverity: "none" | "minor" | "major";
  geminiReview: string | null;
  claudeReview: string | null;
  consensusSummary: string;
}

export interface DisagreementsResponse {
  items: DisagreementItem[];
  total: number;
}

export interface TrendDataPoint {
  date: string;
  reviews: number;
  disagreements: number;
  avgScore: number;
}

export interface DisagreementStats {
  totalReviews: number;
  totalReviewPairs: number;
  agreementCount: number;
  minorDisagreementCount: number;
  majorDisagreementCount: number;
  agreementRate: number;
  minorDisagreementRate: number;
  majorDisagreementRate: number;
  avgAgreementScore: number;
  trend7D: TrendDataPoint[];
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
