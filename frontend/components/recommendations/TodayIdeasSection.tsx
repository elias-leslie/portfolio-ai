'use client'

import { Loader2 } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { useRecommendations, useTrackInPortfolio } from '@/lib/hooks/useRecommendations'
import { formatRelativeTime } from '@/lib/utils'
import { DecisionMemoCard } from './DecisionMemoCard'
import { TrackInPortfolioModal } from './TrackInPortfolioModal'

export function TodayIdeasSection() {
  const [portfolioSize, setPortfolioSize] = useState(100_000)
  const [selectedRecommendation, setSelectedRecommendation] =
    useState<TradeRecommendation | null>(null)
  const [trackModalOpen, setTrackModalOpen] = useState(false)

  const { data, isLoading, error, refetch, isFetching } = useRecommendations({
    minStrength: 6,
    limit: 6,
    signalType: 'BUY',
    portfolioSize,
    positionPct: 0.05,
  })
  const trackMutation = useTrackInPortfolio()
  const recommendations = data?.recommendations ?? []
  const summary = data?.summary
  const latestGeneratedAt =
    recommendations.find((r) => r.generatedAt)?.generatedAt ?? null

  const handleTrackConfirm = (accountId: string, shares: number) => {
    if (!selectedRecommendation) return
    trackMutation.mutate(
      {
        symbol: selectedRecommendation.symbol,
        strategyId: selectedRecommendation.strategyId,
        accountId,
        shares,
      },
      {
        onSuccess: () => {
          setTrackModalOpen(false)
          setSelectedRecommendation(null)
        },
      },
    )
  }

  return (
    <>
      <SectionCard
        variant="surface"
        title="Today"
        description="A short list of ideas worth a closer look right now."
      >
        {!isLoading && !error && data ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
            <span>
              Showing {recommendations.length} of {data.total} setup
              {data.total === 1 ? '' : 's'} · average strength{' '}
              {data.summary.avgSignalStrength.toFixed(1)}/10
              {' · '}
              {Math.round(data.summary.positionPct * 100)}% sizing rule
            </span>
            <span>
              Suggested capital {data.summary.totalPositionSize.toLocaleString('en-US', {
                style: 'currency',
                currency: 'USD',
                maximumFractionDigits: 0,
              })}
              {latestGeneratedAt ? ` · refreshed ${formatRelativeTime(latestGeneratedAt)}` : ''}
            </span>
          </div>
        ) : null}

        <div className="mb-6 rounded-xl border border-border/60 bg-surface-muted/30 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-text">Sizing baseline</p>
              <p className="text-sm text-text-muted">
                This sets the sample share count shown below using the default per-idea cap.
              </p>
            </div>
            <div className="w-full md:max-w-sm">
              <div className="mb-2 text-sm text-text-muted">
                ${portfolioSize.toLocaleString()}
              </div>
              <Slider
                value={[portfolioSize]}
                onValueChange={(values) => setPortfolioSize(values[0])}
                min={10_000}
                max={500_000}
                step={5_000}
              />
            </div>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Looking for current ideas...
          </div>
        )}

        {error && (
          <LoadErrorState
            title="Unable to load today’s ideas."
            detail={
              error.message ||
              'Retry to refresh the latest recommendation set and sizing guidance.'
            }
            onRetry={() => {
              void refetch()
            }}
            isRetrying={isFetching}
          />
        )}

        {!isLoading && !error && isFetching ? (
          <div className="mb-4 flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Refreshing ideas with the latest prices and strategy scores...
          </div>
        ) : null}

        {!isLoading && !error && recommendations.length === 0 && (
          <div className="rounded-xl border border-border/60 bg-surface-muted/30 p-5">
            <p className="text-sm text-text-muted">
              No clear ideas right now. That usually means the best move is to review the action
              queue, check existing holdings, or tighten the watchlist instead of forcing a trade.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href="/watchlist">Review Watchlist</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/portfolio">Open Portfolio Coach</Link>
              </Button>
            </div>
          </div>
        )}

        {!isLoading && !error && data && summary && recommendations.length > 0 && (
          <>
            <div className="mb-4 flex flex-wrap gap-2 text-xs text-text-muted">
              <span className="rounded-full border border-border/40 bg-surface px-3 py-1">BUY {summary.buySignals}</span>
              <span className="rounded-full border border-border/40 bg-surface px-3 py-1">HOLD {summary.holdSignals}</span>
              <span className="rounded-full border border-border/40 bg-surface px-3 py-1">SELL {summary.sellSignals}</span>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              {recommendations.map((recommendation) => (
                <DecisionMemoCard
                  key={`${recommendation.strategyId}-${recommendation.symbol}`}
                  recommendation={recommendation}
                  onTrackInPortfolio={() => {
                    setSelectedRecommendation(recommendation)
                    setTrackModalOpen(true)
                  }}
                />
              ))}
            </div>
          </>
        )}
      </SectionCard>

      <TrackInPortfolioModal
        open={trackModalOpen}
        onOpenChange={setTrackModalOpen}
        recommendation={selectedRecommendation}
        onConfirm={handleTrackConfirm}
        isLoading={trackMutation.isPending}
      />
    </>
  )
}
