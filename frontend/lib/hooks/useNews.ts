import { useQuery } from "@tanstack/react-query";
import {
  fetchMarketNews,
  fetchNewsIntelligence,
  fetchSymbolNews,
  fetchWatchlistNews,
  searchNews,
  type MarketNewsResponse,
  type NewsBundle,
  type WatchlistNewsResponse,
} from "@/lib/api/news";
import { usePortfolio } from "./usePortfolio";

export const newsKeys = {
  all: ["news"] as const,
  intelligence: (ticker?: string) => [...newsKeys.all, "intelligence", ticker ?? "market"] as const,
  market: () => [...newsKeys.all, "market"] as const,
  symbol: (symbol: string) => [...newsKeys.all, "symbol", symbol] as const,
  watchlist: (accountId: string) => [...newsKeys.all, "watchlist", accountId] as const,
  portfolio: () => [...newsKeys.all, "portfolio"] as const,
  search: (query: string) => [...newsKeys.all, "search", query] as const,
};

export function useNewsIntelligence(
  ticker?: string,
  options?: { limit?: number; forceRefresh?: boolean; enabled?: boolean },
) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.intelligence(ticker),
    queryFn: () => fetchNewsIntelligence(ticker, options),
    staleTime: 1000 * 60 * 5,
    enabled: options?.enabled !== false,
    refetchOnWindowFocus: false,
  });
}

export function useMarketNews(options?: { maxResults?: number; forceRefresh?: boolean; enabled?: boolean }) {
  return useQuery<MarketNewsResponse, Error>({
    queryKey: newsKeys.market(),
    queryFn: () => fetchMarketNews(options),
    staleTime: 1000 * 60 * 5,
    enabled: options?.enabled !== false, // Default to true
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
  options?: { maxResults?: number; forceRefresh?: boolean; enabled?: boolean }
) {
  return useQuery<WatchlistNewsResponse, Error>({
    queryKey: newsKeys.watchlist(accountId),
    queryFn: () => fetchWatchlistNews(accountId, options),
    enabled: !!accountId && options?.enabled !== false, // Require accountId AND not explicitly disabled
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false, // Disable to prevent continuous polling on focus events
  });
}

export function useSearchNews(query: string, options?: { maxResults?: number }) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.search(query),
    queryFn: () => searchNews(query, options),
    enabled: !!query,
  });
}

export function usePortfolioNews(options?: { maxResults?: number; forceRefresh?: boolean; enabled?: boolean }) {
  // Always fetch portfolio positions (they're lightweight and cached)
  // This avoids chicken-and-egg problem where we need symbols to enable the query
  const { data: portfolio } = usePortfolio();

  // Extract unique symbols from positions
  const symbols = portfolio?.positions
    ? [...new Set(portfolio.positions.map((p) => p.symbol))]
    : [];

  return useQuery<WatchlistNewsResponse, Error>({
    queryKey: newsKeys.portfolio(),
    queryFn: async () => {
      // Fetch news for each symbol and combine into WatchlistNewsResponse format
      const bundles = await Promise.all(
        symbols.map(async (symbol) => {
          try {
            const bundle = await fetchSymbolNews(symbol, options);
            return bundle;
          } catch (error) {
            console.error(`Failed to fetch news for ${symbol}:`, error);
            return null;
          }
        })
      );

      // Filter out null results and format as WatchlistNewsResponse
      return {
        account_id: "portfolio", // Not used, but required by type
        items: bundles.filter((b): b is NewsBundle => b !== null),
      };
    },
    enabled: symbols.length > 0 && options?.enabled !== false, // Require symbols AND not explicitly disabled
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false, // Disable to prevent continuous polling on focus events
  });
}
