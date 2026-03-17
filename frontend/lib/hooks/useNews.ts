import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  fetchArticleFeedback,
  fetchNewsIntelligence,
  type NewsBundle,
  submitArticleFeedback,
  type SubmitArticleFeedbackInput,
} from '@/lib/api/news'

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
