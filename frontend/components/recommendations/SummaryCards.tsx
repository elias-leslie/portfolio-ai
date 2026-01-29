import { DollarSign, Target } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { RecommendationsSummary } from '@/lib/api/recommendations'

interface SummaryCardsProps {
  summary: RecommendationsSummary | undefined
  portfolioSize: number
}

export function SummaryCards({ summary, portfolioSize }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">
                Active Picks
              </p>
              <p className="text-3xl font-bold text-gain">
                {summary?.buySignals || 0}
              </p>
            </div>
            <Target className="h-8 w-8 text-primary" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">
                Avg Strength
              </p>
              <p className="text-3xl font-bold">
                {summary?.avgSignalStrength?.toFixed(1) || 0}
              </p>
            </div>
            <Badge variant="outline" className="text-lg">
              /10
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">
                Total Position
              </p>
              <p className="text-3xl font-bold">
                ${(summary?.totalPositionSize || 0).toLocaleString()}
              </p>
            </div>
            <DollarSign className="h-8 w-8 text-gain" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">
                Portfolio Size
              </p>
              <p className="text-3xl font-bold">
                ${portfolioSize.toLocaleString()}
              </p>
            </div>
            <Badge variant="outline">
              {((summary?.positionPct || 0.05) * 100).toFixed(0)}% each
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
