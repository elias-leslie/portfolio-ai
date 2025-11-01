/**
 * User preferences API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
export interface PreferencesResponse {
  risk_tolerance: number;
  allow_long: boolean;
  allow_short: boolean;
  allow_options: boolean;
  allow_crypto: boolean;
  allow_futures: boolean;
  max_position_size_pct: number;
  // Refresh control fields
  default_refresh_minutes: number;
  watchlist_refresh_override: number | null;
  portfolio_refresh_override: number | null;
  news_refresh_override: number | null;
  frontend_poll_interval: number;
  // Legacy watchlist fields (kept for backward compatibility)
  watchlist_refresh_minutes: number;
  watchlist_auto_expand: boolean;
  watchlist_price_weight: number;
  watchlist_technical_weight: number;
  display_timezone: string;
}

export interface PreferencesUpdate {
  risk_tolerance?: number;
  allow_long?: boolean;
  allow_short?: boolean;
  allow_options?: boolean;
  allow_crypto?: boolean;
  allow_futures?: boolean;
  max_position_size_pct?: number;
  // Refresh control fields
  default_refresh_minutes?: number;
  watchlist_refresh_override?: number | null;
  portfolio_refresh_override?: number | null;
  news_refresh_override?: number | null;
  frontend_poll_interval?: number;
  // Legacy watchlist fields (kept for backward compatibility)
  watchlist_refresh_minutes?: number;
  watchlist_auto_expand?: boolean;
  watchlist_price_weight?: number;
  watchlist_technical_weight?: number;
  display_timezone?: string;
}

/**
 * Get user's risk tolerance and trade preferences
 */
export async function fetchPreferences(): Promise<PreferencesResponse> {
  return apiRequest<PreferencesResponse>("/api/preferences/");
}

/**
 * Update user preferences
 */
export async function updatePreferences(
  data: PreferencesUpdate
): Promise<PreferencesResponse> {
  return apiRequest<PreferencesResponse>("/api/preferences/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
