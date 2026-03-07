'use client'

import { AlertCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Slider } from '@/components/ui/slider'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { useRecommendations, useTrackInPortfolio } from '@/lib/hooks/useRecommendations'
import { DecisionMemoCard } from './DecisionMemoCard'
import { TrackInPortfolioModal } from './TrackInPortfolioModal'

export function TodayIdeasSection() {
  const [portfolioSize, setPortfolioSize] = useState(100_000)
  const [selectedRecommendation, setSelectedRecommendation] =
    useState<TradeRecommendation | null>(null)
  const [trackModalOpen, setTrackModalOpen] = useState(false)

  const { data, isLoading, error } = useRecommendations({
    minStrength: 6,
    limit: 6,
    signalType: 'BUY',
    portfolioSize,
    positionPct: 0.05,
  })
  const trackMutation = useTrackInPortfolio()
  const recommendations = data?.recommendations ?? []

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
        <div className="mb-6 rounded-xl border border-border/60 bg-surface-muted/30 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-text">Sizing baseline</p>
              <p className="text-sm text-text-muted">
                This sets the sample share count shown below.
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
          <div className="flex items-center gap-2 rounded-xl border border-loss/40 bg-loss/10 p-4 text-sm text-loss">
            <AlertCircle className="h-4 w-4" />
            Unable to load ideas: {error.message}
          </div>
        )}

        {!isLoading && !error && recommendations.length === 0 && (
          <div className="rounded-xl border border-border/60 bg-surface-muted/30 p-5 text-sm text-text-muted">
            No clear ideas right now. The app is holding back because it does not have enough
            evidence to show a clean setup.
          </div>
        )}

        {!isLoading && !error && recommendations.length > 0 && (
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
