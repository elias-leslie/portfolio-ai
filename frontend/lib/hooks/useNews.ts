import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  fetchArticleFeedback,
  fetchNewsIntelligence,
  type NewsBundle,
  searchNews,
  submitArticleFeedback,
  type SubmitArticleFeedbackInput,
  fetchWatchlistNews,
  type WatchlistNewsResponse,
} from '@/lib/api/news'
import { usePortfolio } from './usePortfolio'

export const newsKeys = {
  all: ['news'] as const,
  intelligence: (symbol?: string, limit?: number) =>
    [
      ...newsKeys.all,
      'intelligence',
      symbol ?? 'market',
      limit ?? 'default',
    ] as const,
  market: () => [...newsKeys.all, 'market'] as const,
  symbol: (symbol: string) => [...newsKeys.all, 'symbol', symbol] as const,
  watchlist: (accountId: string) =>
    [...newsKeys.all, 'watchlist', accountId] as const,
  portfolio: () => [...newsKeys.all, 'portfolio'] as const,
  search: (query: string) => [...newsKeys.all, 'search', query] as const,
  articleFeedback: (articleHash: string) =>
    [...newsKeys.all, 'article-feedback', articleHash] as const,
}

export function useNewsIntelligence(
  symbol?: string,
  options?: { limit?: number; forceRefresh?: boolean; enabled?: boolean },
) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.intelligence(symbol, options?.limit),
    queryFn: () => fetchNewsIntelligence(symbol, options),
    staleTime: 1000 * 60 * 5,
    enabled: options?.enabled !== false,
    refetchOnWindowFocus: false,
  })
}

export function useWatchlistNews(
  accountId: string,
  options?: { maxResults?: number; forceRefresh?: boolean; enabled?: boolean },
) {
  return useQuery<WatchlistNewsResponse, Error>({
    queryKey: newsKeys.watchlist(accountId),
    queryFn: () => fetchWatchlistNews(accountId, options),
    enabled: !!accountId && options?.enabled !== false, // Require accountId AND not explicitly disabled
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false, // Disable to prevent continuous polling on focus events
  })
}

export function useSearchNews(
  query: string,
  options?: { maxResults?: number },
) {
  return useQuery<NewsBundle, Error>({
    queryKey: newsKeys.search(query),
    queryFn: () => searchNews(query, options),
    enabled: !!query,
  })
}

export function usePortfolioNews(options?: {
  maxResults?: number
  forceRefresh?: boolean
  enabled?: boolean
}) {
  // Always fetch portfolio positions (they're lightweight and cached)
  // This avoids chicken-and-egg problem where we need symbols to enable the query
  const { data: portfolio } = usePortfolio()

  // Extract unique symbols from positions
  const symbols = portfolio?.positions
    ? [...new Set(portfolio.positions.map((p) => p.symbol))]
    : []

  return useQuery<WatchlistNewsResponse, Error>({
    queryKey: newsKeys.portfolio(),
    queryFn: async () => {
      const bundles = await Promise.allSettled(
        symbols.map((symbol) => fetchNewsIntelligence(symbol, options)),
      )

      const fulfilledBundles = bundles.flatMap((bundle) =>
        bundle.status === 'fulfilled' ? [bundle.value] : [],
      )

      if (fulfilledBundles.length === 0 && bundles.length > 0) {
        const firstError = bundles.find(
          (bundle): bundle is PromiseRejectedResult => bundle.status === 'rejected',
        )
        throw (
          firstError?.reason instanceof Error
            ? firstError.reason
            : new Error('Failed to load portfolio news')
        )
      }

      return {
        accountId: 'portfolio',
        items: fulfilledBundles,
      }
    },
    enabled: symbols.length > 0 && options?.enabled !== false, // Require symbols AND not explicitly disabled
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false, // Disable to prevent continuous polling on focus events
  })
}

export function useArticleFeedback(
  articleHash?: string,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: newsKeys.articleFeedback(articleHash ?? 'missing'),
    queryFn: () => fetchArticleFeedback(articleHash ?? ''),
    enabled: !!articleHash && options?.enabled !== false,
    staleTime: 1000 * 60 * 30,
    refetchOnWindowFocus: false,
  })
}

export function useSubmitArticleFeedback() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SubmitArticleFeedbackInput) => submitArticleFeedback(payload),

    onSuccess: (_result, variables) => {
      queryClient.setQueryData(newsKeys.articleFeedback(variables.articleHash), {
        exists: true,
        vendor: variables.vendor,
        isUseful: variables.isUseful,
        createdAt: new Date().toISOString(),
      })

      toast.success(
        variables.isUseful
          ? 'Marked article as useful.'
          : 'Marked article as not useful.',
      )
    },

    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to save article feedback.',
      )
    },
  })
}
