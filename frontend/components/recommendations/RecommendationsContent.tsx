import { AlertCircle, Target } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { RecommendationCard } from './RecommendationCard'

interface RecommendationsContentProps {
  isLoading: boolean
  error: Error | null
  recommendations: TradeRecommendation[]
  onPaperTrade: (rec: TradeRecommendation) => void
  onTrackInPortfolio: (rec: TradeRecommendation) => void
  isPaperTrading: boolean
}

export function RecommendationsContent({
  isLoading,
  error,
  recommendations,
  onPaperTrade,
  onTrackInPortfolio,
  isPaperTrading,
}: RecommendationsContentProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="h-80" />
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <Card className="border-loss/30 bg-loss/10">
        <CardContent className="flex items-center gap-3 py-6">
          <AlertCircle className="h-5 w-5 text-loss" />
          <p className="text-loss">
            Failed to load recommendations:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </CardContent>
      </Card>
    )
  }

  if (recommendations.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Target className="mx-auto h-12 w-12 text-text-muted" />
          <h3 className="mt-4 text-lg font-medium">No Validated Picks</h3>
          <p className="mt-2 text-text-muted">
            No validated picks found. Picks require EITHER:
          </p>
          <ul className="mt-2 text-sm text-text-muted">
            <li>• Active investment thesis (cross-validation score ≥ 0.7)</li>
            <li>• OR strong backtest performance (Sharpe ratio ≥ 1.0)</li>
          </ul>
          <p className="mt-4 text-sm text-text-muted">
            Generate a thesis or run backtests for watchlist symbols to see
            recommendations.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {recommendations.map((rec, i) => (
        <RecommendationCard
          key={`${rec.strategyId}-${rec.symbol}-${i}`}
          rec={rec}
          onPaperTrade={() => onPaperTrade(rec)}
          onTrackInPortfolio={() => onTrackInPortfolio(rec)}
          isPaperTrading={isPaperTrading}
        />
      ))}
    </div>
  )
}
