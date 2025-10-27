/**
 * User preferences API client functions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Types matching backend Pydantic models
export interface PreferencesResponse {
  risk_tolerance: number;
  allow_long: boolean;
  allow_short: boolean;
  allow_options: boolean;
  allow_crypto: boolean;
  allow_futures: boolean;
  max_position_size_pct: number;
}

export interface PreferencesUpdate {
  risk_tolerance?: number;
  allow_long?: boolean;
  allow_short?: boolean;
  allow_options?: boolean;
  allow_crypto?: boolean;
  allow_futures?: boolean;
  max_position_size_pct?: number;
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
  data: PreferencesUpdate
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
