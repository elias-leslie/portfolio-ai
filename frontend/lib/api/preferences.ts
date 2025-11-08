/**
 * User preferences API client functions
 */

import { apiRequest } from "./client";

// Weight configuration types (migration 019)
export interface ScoreWeights {
    price: number;
    technical: number;
    fundamental: number;
}

export interface PriceSubWeights {
    change_pct: number;
}

export interface TechnicalSubWeights {
    rsi_14: number;
    trend: number;
    macd: number;
}

export interface FundamentalSubWeights {
    valuation: number;
    growth: number;
    health: number;
    sentiment: number;
}

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
    news_lookback_hours: number;
    news_max_articles: number;
    frontend_poll_interval: number;
    // Legacy watchlist fields (kept for backward compatibility)
    watchlist_refresh_minutes: number;
    watchlist_auto_expand: boolean;
    watchlist_price_weight: number;
    watchlist_technical_weight: number;
    display_timezone: string;
    watchlist_show_news: boolean;
    // New weight configuration fields (migration 019)
    watchlist_score_weights?: ScoreWeights;
    price_sub_weights?: PriceSubWeights;
    technical_sub_weights?: TechnicalSubWeights;
    fundamental_sub_weights?: FundamentalSubWeights;
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
    news_lookback_hours?: number | null;
    news_max_articles?: number | null;
    frontend_poll_interval?: number;
    // Legacy watchlist fields (kept for backward compatibility)
    watchlist_refresh_minutes?: number;
    watchlist_auto_expand?: boolean;
    watchlist_price_weight?: number;
    watchlist_technical_weight?: number;
    display_timezone?: string;
    watchlist_show_news?: boolean;
    // New weight configuration fields (migration 019)
    watchlist_score_weights?: ScoreWeights;
    price_sub_weights?: PriceSubWeights;
    technical_sub_weights?: TechnicalSubWeights;
    fundamental_sub_weights?: FundamentalSubWeights;
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
    data: PreferencesUpdate,
): Promise<PreferencesResponse> {
    return apiRequest<PreferencesResponse>("/api/preferences/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}
