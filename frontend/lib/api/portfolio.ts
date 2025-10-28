/**
 * Portfolio API client functions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Types matching backend Pydantic models
export interface Account {
  id: string;
  name: string;
  account_type: string;
  created_at: string;
  updated_at: string;
}

export interface Position {
  id: string;
  account_id: string;
  symbol: string;
  shares: number;
  cost_basis: number;
  position_type: string;
  created_at: string;
  updated_at: string;
}

export interface PositionWithValue extends Position {
  current_price: number;
  current_value: number;
  gain: number;
  gain_pct: number;
}

export interface PortfolioResponse {
  positions: PositionWithValue[];
  total_value: number;
  total_cost_basis: number;
  total_gain: number;
  total_gain_pct: number;
}

export interface PortfolioAnalytics {
  total_value: number;
  total_cost_basis: number;
  total_gain: number;
  total_gain_pct: number;
  portfolio_beta: number;
  portfolio_volatility: number;
  concentration: {
    top_holding_pct: number;
    top_3_pct: number;
    top_10_pct: number;
    herfindahl_index: number;
  };
  sector_exposure: Record<string, number>;
}

export interface CreateAccountRequest {
  name: string;
  account_type: string;
}

export interface AddPositionRequest {
  account_id: string;
  symbol: string;
  shares: number;
  cost_basis: number;
  position_type: string;
}

/**
 * Fetch all portfolio positions with current values
 */
export async function fetchPortfolio(): Promise<PortfolioResponse> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch portfolio: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new account
 */
export async function createAccount(
  data: CreateAccountRequest
): Promise<Account> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/account`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Failed to create account: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Add or update a position
 */
export async function addPosition(
  data: AddPositionRequest
): Promise<Position> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/position`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Failed to add position: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a position by ID
 */
export async function deletePosition(positionId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/portfolio/position/${positionId}`,
    {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to delete position: ${response.statusText}`);
  }
}

/**
 * Fetch portfolio analytics (beta, volatility, concentration, sector exposure)
 */
export async function fetchAnalytics(): Promise<PortfolioAnalytics> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/analytics`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch analytics: ${response.statusText}`);
  }

  return response.json();
}
