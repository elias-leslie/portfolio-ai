/**
 * User preferences API client functions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Types matching backend Pydantic models
export interface PreferencesResponse {
  risk_tolerance: number;
  allow_long: boolean;
  allow_short: boolean;
  allow_options: boolean;
  allow_crypto: boolean;
  allow_futures: boolean;
  max_position_size_pct: number;
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
  const response = await fetch(`${API_BASE_URL}/api/preferences/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch preferences: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update user preferences
 */
export async function updatePreferences(
  data: PreferencesUpdate,
): Promise<PreferencesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/preferences/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Failed to update preferences: ${response.statusText}`);
  }

  return response.json();
}
