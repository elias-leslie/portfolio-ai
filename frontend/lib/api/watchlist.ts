/**
 * Watchlist API client functions
 */

import { apiRequest } from "./client";

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

export interface SentimentProbabilities {
    [label: string]: number;
}

export interface NewsSentimentDetail {
    score: number | null;
    score_change: number | null;
    positive_count: number;
    neutral_count: number;
    negative_count: number;
    article_count: number;
    latest_published_at?: string | null;
    top_positive?: SentimentArticle | null;
    top_negative?: SentimentArticle | null;
    model_breakdown: Record<string, number>;
}

export interface SentimentScoreMeta {
    score: number;
    label: "positive" | "neutral" | "negative";
    confidence: number;
    model: string;
    probabilities?: SentimentProbabilities;
}

export interface SentimentArticle {
    ticker: string;
    headline: string;
    url?: string | null;
    summary?: string | null;
    source?: string | null;
    vendor?: string | null;
    author?: string | null;
    image_url?: string | null;
    published_at?: string | null;
    fetched_at: string;
    sentiment: SentimentScoreMeta;
    content_hash: string;
    raw?: Record<string, unknown>;
}

export interface RecentNewsPayload {
    summary?: NewsSentimentDetail;
    articles: SentimentArticle[];
}

export interface KeyEvent {
    icon: string;
    text: string;
    time_ago: string;
    is_material: boolean;
    event_category?: string | null;
    published_at?: string | null;
}

export interface NewsIntelligence {
    headline: string;
    sentiment_score: number;
    sentiment_label: string;
    article_count_24h: number;
    key_events: KeyEvent[];
    recent_articles: Record<string, unknown>[];
}

export interface PriorityIndicator {
    icon: string;
    label: string;
    tooltip: string;
    priority: number;
    category: "time_sensitive" | "risk" | "opportunity" | "caution";
}

export interface WatchlistItem {
    id: string;
    symbol: string;
    note?: string;
    created_at: string;
    updated_at: string;
    current_score?: ScoreBreakdown;
    score_alert?: boolean;
    // Narrative Intelligence fields
    signal_type?: "BUY" | "HOLD" | "AVOID" | null;
    signal_strength?: number | null;
    narrative_headline?: string | null;
    recommended_style?: "Index" | "Trend" | "Value" | "Swing" | "Event" | null;
    style_confidence?: number | null;
    optimal_holding_period?: string | null;
    risk_level?: "Low" | "Medium-Low" | "Medium" | "High" | null;
    // Trade Calculator fields
    entry_price?: number | null;
    stop_loss?: number | null;
    profit_target?: number | null;
    position_size_shares?: number | null;
    // News sentiment
    news_sentiment_score?: number | null;
    recent_news?: RecentNewsPayload | null;
    // News Intelligence
    news_intelligence?: NewsIntelligence | null;
    // Priority indicators
    priority_indicators?: PriorityIndicator[];
}

export interface WatchlistListResponse {
    items: WatchlistItem[];
    total_count: number;
}

export interface WatchlistItemCreate {
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
 * Get all watchlist items
 *
 * Watchlist is user-level (not account-specific).
 */
export async function fetchWatchlistItems(): Promise<WatchlistListResponse> {
    return apiRequest<WatchlistListResponse>("/api/watchlist");
}

/**
 * Get a single watchlist item with details
 */
export async function fetchWatchlistItem(
    itemId: string,
): Promise<WatchlistItem> {
    return apiRequest<WatchlistItem>(`/api/watchlist/${itemId}`);
}

/**
 * Add a ticker to the watchlist
 */
export async function createWatchlistItem(
    data: WatchlistItemCreate,
): Promise<WatchlistItem> {
    return apiRequest<WatchlistItem>("/api/watchlist", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

/**
 * Update a watchlist item (notes)
 */
export async function updateWatchlistItem(
    itemId: string,
    data: WatchlistItemUpdate,
): Promise<WatchlistItem> {
    return apiRequest<WatchlistItem>(`/api/watchlist/${itemId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

/**
 * Delete a watchlist item
 */
export async function deleteWatchlistItem(itemId: string): Promise<void> {
    await apiRequest<void>(`/api/watchlist/${itemId}`, {
        method: "DELETE",
    });
}

/**
 * Get refresh status for the watchlist
 */
export async function fetchRefreshStatus(): Promise<RefreshStatus> {
    return apiRequest<RefreshStatus>("/api/watchlist/refresh-status");
}

/**
 * Manually refresh watchlist scores
 */
export async function refreshWatchlistScores(): Promise<RefreshResponse> {
    return apiRequest<RefreshResponse>("/api/watchlist/refresh", {
        method: "POST",
        body: JSON.stringify({}),
    });
}

/**
 * Get 7-day score history for a watchlist item
 */
export async function fetchScoreHistory(
    itemId: string,
): Promise<ScoreHistoryResponse> {
    try {
        return await apiRequest<ScoreHistoryResponse>(
            `/api/watchlist/${itemId}/history`,
        );
    } catch {
        // History endpoint may not exist yet, return empty response
        return {
            item_id: itemId,
            symbol: "",
            history: [],
        };
    }
}
