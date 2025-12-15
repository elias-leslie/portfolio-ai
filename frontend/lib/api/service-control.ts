/**
 * Service control API client for status dashboard operations
 */

export interface ServiceRestartResponse {
  success: boolean;
  service: string;
  message: string;
  timestamp: string;
}

export interface CacheClearResponse {
  success: boolean;
  rows_deleted: number;
  message: string;
  timestamp: string;
}

export interface WatchlistRefreshResponse {
  success: boolean;
  task_id: string;
  message: string;
  timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Restart a specific service
 */
export async function restartService(
  service: string
): Promise<ServiceRestartResponse> {
  const response = await fetch(
    `${API_BASE}/api/status/services/${service}/restart`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to restart ${service}`);
  }

  return response.json();
}

/**
 * Clear the price cache
 */
export async function clearCache(): Promise<CacheClearResponse> {
  const response = await fetch(`${API_BASE}/api/status/cache/clear`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to clear cache");
  }

  return response.json();
}

/**
 * Trigger manual watchlist refresh
 */
export async function refreshWatchlist(): Promise<WatchlistRefreshResponse> {
  const response = await fetch(`${API_BASE}/api/status/watchlist/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to refresh watchlist");
  }

  return response.json();
}
