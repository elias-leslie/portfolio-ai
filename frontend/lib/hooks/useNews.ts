import { useQuery } from "@tanstack/react-query";
import {
  fetchMarketNews,
  fetchSymbolNews,
  fetchWatchlistNews,
  searchNews,
  type MarketNewsResponse,
  type NewsBundle,
  type WatchlistNewsResponse,
} from "@/lib/api/news";

export const newsKeys = {
  all: ["news"] as const,
  market: () => [...newsKeys.all, "market"] as const,
  symbol: (symbol: string) => [...newsKeys.all, "symbol", symbol] as const,
  watchlist: (accountId: string) => [...newsKeys.all, "watchlist", accountId] as const,
  search: (query: string) => [...newsKeys.all, "search", query] as const,
};

export function useMarketNews(options?: { maxResults?: number; forceRefresh?: boolean }) {
  return useQuery<MarketNewsResponse, Error>({
    queryKey: newsKeys.market(),
    queryFn: () => fetchMarketNews(options),
    staleTime: 1000 * 60 * 5,
  });
}

export function useSymbolNews(symbol: string, options?: { maxResults?: number; forceRefresh?: boolean }) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.symbol(symbol),
    queryFn: () => fetchSymbolNews(symbol, options),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 5,
  });
}

export function useWatchlistNews(
  accountId: string,
  options?: { maxResults?: number; forceRefresh?: boolean }
) {
  return useQuery<WatchlistNewsResponse, Error>({
    queryKey: newsKeys.watchlist(accountId),
    queryFn: () => fetchWatchlistNews(accountId, options),
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: true,
  });
}

export function useSearchNews(query: string, options?: { maxResults?: number }) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.search(query),
    queryFn: () => searchNews(query, options),
    enabled: !!query,
  });
}
