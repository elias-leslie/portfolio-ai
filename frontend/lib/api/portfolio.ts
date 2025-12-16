/**
 * Portfolio API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
export interface Account {
  id: string;
  name: string;
  accountType: string;
  createdAt: string;
  updatedAt: string;
}

export interface Position {
  id: string;
  accountId: string;
  symbol: string;
  shares: number;
  costBasis: number;
  positionType: string;
  createdAt: string;
  updatedAt: string;
}

export interface PositionWithValue extends Position {
  currentPrice: number;
  currentValue: number;
  gain: number;
  gainPct: number;
}

export interface PortfolioResponse {
  positions: PositionWithValue[];
  totalValue: number;
  totalCostBasis: number;
  totalGain: number;
  totalGainPct: number;
}

export interface PositionPerformance {
  symbol: string;
  gainPct: number;
  gainAmount: number;
  currentValue: number;
  weightPct: number;
}

export interface RiskProfile {
  level: string;
  score: number;
  factors: Record<string, string>;
}

export interface DiversificationScore {
  score: number;
  level: string;
  numHoldings: number;
  numSectors: number;
}

export interface PortfolioAnalytics {
  portfolioValue: {
    totalValue: number;
    totalCostBasis: number;
    totalGain: number;
    totalGainPct: number;
  };
  portfolioBeta: number;
  portfolioVolatility: number;
  sharpeRatio: number | null;
  concentration: {
    topHoldingPct: number;
    top3Pct: number;
    top10Pct: number;
    herfindahlIndex: number;
  };
  sectorExposure: Record<string, number>;
  riskProfile: RiskProfile | null;
  diversificationScore: DiversificationScore | null;
  topPerformers: PositionPerformance[];
  bottomPerformers: PositionPerformance[];
  numPositions: number;
  numSymbols: number;
}

export interface CreateAccountRequest {
  name: string;
  accountType: string;
}

export interface AddPositionRequest {
  accountId: string;
  symbol: string;
  shares: number;
  costBasis: number;
  positionType: string;
}

/**
 * Fetch all portfolio positions with current values
 */
export async function fetchPortfolio(): Promise<PortfolioResponse> {
  return apiRequest<PortfolioResponse>("/api/portfolio/");
}

/**
 * Fetch all accounts
 */
export async function fetchAccounts(): Promise<Account[]> {
  return apiRequest<Account[]>("/api/portfolio/accounts");
}

/**
 * Create a new account
 */
export async function createAccount(
  data: CreateAccountRequest
): Promise<Account> {
  return apiRequest<Account>("/api/portfolio/account", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete an account by ID
 */
export async function deleteAccount(accountId: string): Promise<void> {
  await apiRequest<void>(`/api/portfolio/account/${accountId}`, {
    method: "DELETE",
  });
}

/**
 * Add or update a position
 */
export async function addPosition(
  data: AddPositionRequest
): Promise<Position> {
  return apiRequest<Position>("/api/portfolio/position", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing position
 */
export async function updatePosition(
  positionId: string,
  data: AddPositionRequest
): Promise<Position> {
  return apiRequest<Position>(`/api/portfolio/position/${positionId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Delete a position by ID
 */
export async function deletePosition(positionId: string): Promise<void> {
  await apiRequest<void>(`/api/portfolio/position/${positionId}`, {
    method: "DELETE",
  });
}

/**
 * Fetch portfolio analytics (beta, volatility, concentration, sector exposure)
 */
export async function fetchAnalytics(): Promise<PortfolioAnalytics> {
  return apiRequest<PortfolioAnalytics>("/api/portfolio/analytics");
}
