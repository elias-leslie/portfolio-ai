import { apiRequest } from "./client";
import type {
  NewsSentimentDetail,
  RecentNewsPayload,
  SentimentArticle,
} from "./watchlist";

export interface NewsBundle {
  ticker: string;
  summary: NewsSentimentDetail;
  articles: SentimentArticle[];
}

export interface MarketNewsResponse extends NewsBundle {}

export interface WatchlistNewsResponse {
  account_id: string;
  items: NewsBundle[];
}

type QueryParams = Record<string, string | number | boolean | undefined>;

function buildQuery(params: QueryParams): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

export async function fetchMarketNews(options?: {
  maxResults?: number;
  forceRefresh?: boolean;
}): Promise<MarketNewsResponse> {
  const query = buildQuery({
    max_results: options?.maxResults,
    force_refresh: options?.forceRefresh,
  });
  return apiRequest<MarketNewsResponse>(`/api/news/market${query}`);
}

export async function fetchSymbolNews(
  symbol: string,
  options?: {
    maxResults?: number;
    forceRefresh?: boolean;
  }
): Promise<NewsBundle> {
  const query = buildQuery({
    max_results: options?.maxResults,
    force_refresh: options?.forceRefresh,
  });
  return apiRequest<NewsBundle>(`/api/news/symbol/${encodeURIComponent(symbol)}${query}`);
}

export async function fetchWatchlistNews(
  accountId: string,
  options?: {
    maxResults?: number;
    forceRefresh?: boolean;
  }
): Promise<WatchlistNewsResponse> {
  const query = buildQuery({
    account_id: accountId,
    max_results: options?.maxResults,
    force_refresh: options?.forceRefresh,
  });
  return apiRequest<WatchlistNewsResponse>(`/api/news/watchlist${query}`);
}

export async function searchNews(
  query: string,
  options?: { maxResults?: number }
): Promise<NewsBundle> {
  const qs = buildQuery({
    query,
    max_results: options?.maxResults,
  });
  return apiRequest<NewsBundle>(`/api/news/search${qs}`);
}
