'use client'

import { useState } from 'react'
import { FiltersCard } from '@/components/recommendations/FiltersCard'
import { RecommendationsContent } from '@/components/recommendations/RecommendationsContent'
import { SummaryCards } from '@/components/recommendations/SummaryCards'
import { TrackInPortfolioModal } from '@/components/recommendations/TrackInPortfolioModal'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import {
  usePaperTrade,
  useRecommendations,
  useTrackInPortfolio,
} from '@/lib/hooks/useRecommendations'

export function RecommendationsPageClient() {
  const [minStrength, setMinStrength] = useState(5)
  const [portfolioSize, setPortfolioSize] = useState(100000)
  const [trackModalOpen, setTrackModalOpen] = useState(false)
  const [selectedRec, setSelectedRec] = useState<TradeRecommendation | null>(
    null,
  )

  const { data, isLoading, error } = useRecommendations({
    minStrength,
    limit: 20,
    signalType: 'BUY',
    portfolioSize,
    positionPct: 0.05,
  })

  const paperTradeMutation = usePaperTrade()
  const trackMutation = useTrackInPortfolio()

  const recommendations = data?.recommendations || []
  const summary = data?.summary

  const handleTrackClick = (rec: TradeRecommendation) => {
    setSelectedRec(rec)
    setTrackModalOpen(true)
  }

  const handleTrackConfirm = (accountId: string, shares: number) => {
    if (!selectedRec) return
    trackMutation.mutate(
      {
        symbol: selectedRec.symbol,
        strategyId: selectedRec.strategyId,
        accountId,
        shares,
      },
      {
        onSuccess: () => {
          setTrackModalOpen(false)
          setSelectedRec(null)
        },
      },
    )
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Trade Picks"
        description="Top picks from active strategies with position sizing"
        size="md"
      />

      <SummaryCards summary={summary} portfolioSize={portfolioSize} />

      <FiltersCard
        minStrength={minStrength}
        onMinStrengthChange={setMinStrength}
        portfolioSize={portfolioSize}
        onPortfolioSizeChange={setPortfolioSize}
      />

      <RecommendationsContent
        isLoading={isLoading}
        error={error}
        recommendations={recommendations}
        onPaperTrade={(rec) =>
          paperTradeMutation.mutate({
            symbol: rec.symbol,
            strategyId: rec.strategyId,
          })
        }
        onTrackInPortfolio={handleTrackClick}
        isPaperTrading={paperTradeMutation.isPending}
      />

      <TrackInPortfolioModal
        open={trackModalOpen}
        onOpenChange={setTrackModalOpen}
        recommendation={selectedRec}
        onConfirm={handleTrackConfirm}
        isLoading={trackMutation.isPending}
      />
    </PageContainer>
  )
}
