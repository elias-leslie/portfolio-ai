/**
 * Watchlist API client functions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Types matching backend Pydantic models
export interface ScoreComponent {
  score: number;
  weight: number;
  stale: boolean;
  updated_at?: string;
  metadata?: Record<string, unknown>;
}

export interface ScoreBreakdown {
  price: ScoreComponent;
  technical: ScoreComponent;
  overall: number;
}

export interface WatchlistItem {
  id: string;
  account_id: string;
  symbol: string;
  note?: string;
  created_at: string;
  updated_at: string;
  current_score?: ScoreBreakdown;
  score_alert?: boolean;
}

export interface WatchlistListResponse {
  items: WatchlistItem[];
  total_count: number;
}

export interface WatchlistItemCreate {
  account_id: string;
  symbol: string;
  note?: string;
}

export interface WatchlistItemUpdate {
  note?: string;
}

export interface FailedTickerInfo {
  symbol: string;
  reason: string;
}

export interface RefreshResponse {
  status: string;
  message: string;
  refreshed_count: number;
  failed_count?: number;
  failed?: FailedTickerInfo[];
}

export interface ScoreHistory {
  timestamp: string;
  overall: number;
  price_score: number;
  technical_score: number;
}

export interface ScoreHistoryResponse {
  item_id: string;
  symbol: string;
  history: ScoreHistory[];
}

export interface RefreshStatus {
  is_refreshing: boolean;
  started_at?: string;
  elapsed_seconds?: number;
  total_items?: number;
  processed_items?: number;
  current_symbol?: string;
  percent_complete?: number;
}

/**
 * Get all watchlist items for an account
 */
export async function fetchWatchlistItems(
  accountId: string
): Promise<WatchlistListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/watchlist?account_id=${encodeURIComponent(accountId)}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch watchlist: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a single watchlist item with details
 */
export async function fetchWatchlistItem(
  itemId: string
): Promise<WatchlistItem> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/${itemId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch watchlist item: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Add a ticker to the watchlist
 */
export async function createWatchlistItem(
  data: WatchlistItemCreate
): Promise<WatchlistItem> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to add ticker: ${response.statusText}`
    );
  }

  return response.json();
}

/**
 * Update a watchlist item (notes)
 */
export async function updateWatchlistItem(
  itemId: string,
  data: WatchlistItemUpdate
): Promise<WatchlistItem> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/${itemId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Failed to update item: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a watchlist item
 */
export async function deleteWatchlistItem(itemId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/${itemId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Failed to delete item: ${response.statusText}`);
  }
}

/**
 * Get refresh status for an account's watchlist
 */
export async function fetchRefreshStatus(
  accountId: string
): Promise<RefreshStatus> {
  const response = await fetch(
    `${API_BASE_URL}/api/watchlist/refresh-status?account_id=${encodeURIComponent(accountId)}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch refresh status: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Manually refresh watchlist scores for an account
 */
export async function refreshWatchlistScores(
  accountId: string
): Promise<RefreshResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ account_id: accountId }),
  });

  // Handle 207 Multi-Status (partial success) as success
  if (!response.ok && response.status !== 207) {
    throw new Error(`Failed to refresh scores: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get 7-day score history for a watchlist item
 */
export async function fetchScoreHistory(
  itemId: string
): Promise<ScoreHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/watchlist/${itemId}/history`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    // History endpoint may not exist yet, return empty response
    return {
      item_id: itemId,
      symbol: "",
      history: [],
    };
  }

  return response.json();
}
