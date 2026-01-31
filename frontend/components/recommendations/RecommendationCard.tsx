import { Briefcase, LineChart } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { SignalBadge, SignalStatusBadge, ValidationBadge } from './SignalBadges'

interface RecommendationCardProps {
  rec: TradeRecommendation
  onPaperTrade: () => void
  onTrackInPortfolio: () => void
  isPaperTrading: boolean
}

export function RecommendationCard({
  rec,
  onPaperTrade,
  onTrackInPortfolio,
  isPaperTrading,
}: RecommendationCardProps) {
  const riskReward = rec.riskRewardRatio
  const potentialGain = rec.targetPrice - rec.currentPrice
  const potentialLoss = rec.currentPrice - rec.stopLoss
  const potentialGainPct = (potentialGain / rec.currentPrice) * 100
  const potentialLossPct = (potentialLoss / rec.currentPrice) * 100
  const priceChange = rec.currentPrice - rec.entryPrice
  const priceChangePct = (priceChange / rec.entryPrice) * 100

  return (
    <Card
      className={`transition-shadow hover:shadow-lg ${rec.signalStatus === 'caution' ? 'border-warning' : ''}`}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex flex-wrap items-center gap-2 text-xl">
              {rec.symbol}
              <SignalBadge
                type={rec.signalType}
                strength={rec.signalStrength}
              />
              <ValidationBadge validationType={rec.validationType} />
              <SignalStatusBadge status={rec.signalStatus} />
            </CardTitle>
            <p className="mt-1 text-sm text-text-muted">
              {rec.strategyName} ({rec.strategyType})
            </p>
          </div>
          {rec.expectedSharpe && (
            <Badge variant="outline" className="text-xs">
              Sharpe: {rec.expectedSharpe.toFixed(2)}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current Price Banner */}
        <div className="flex items-center justify-between rounded-lg bg-surface-muted p-3">
          <div>
            <p className="text-xs font-medium text-text-muted">Current Price</p>
            <p className="text-2xl font-bold">${rec.currentPrice.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Since Signal</p>
            <p
              className={`text-lg font-bold ${priceChange >= 0 ? 'text-gain' : 'text-loss'}`}
            >
              {priceChange >= 0 ? '+' : ''}
              {priceChangePct.toFixed(2)}%
            </p>
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="rounded-lg bg-loss/10 p-3">
            <p className="text-xs font-medium text-loss">Stop Loss</p>
            <p className="text-lg font-bold text-loss-strong">
              ${rec.stopLoss.toFixed(2)}
            </p>
            <p className="text-xs text-loss">-{potentialLossPct.toFixed(1)}%</p>
          </div>
          <div className="rounded-lg bg-accent/10 p-3">
            <p className="text-xs font-medium text-accent">Signal Price</p>
            <p className="text-lg font-bold text-accent">
              ${rec.entryPrice.toFixed(2)}
            </p>
            <p className="text-xs text-accent">{rec.signalDate}</p>
          </div>
          <div className="rounded-lg bg-gain/10 p-3">
            <p className="text-xs font-medium text-gain">Target</p>
            <p className="text-lg font-bold text-gain-strong">
              ${rec.targetPrice.toFixed(2)}
            </p>
            <p className="text-xs text-gain">+{potentialGainPct.toFixed(1)}%</p>
          </div>
        </div>

        {/* Position Sizing */}
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-muted/50 p-3">
          <div>
            <p className="text-sm font-medium">Position Size</p>
            <p className="text-xs text-text-muted">
              {rec.positionSizeShares} shares @ ${rec.currentPrice.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-lg font-bold">
              ${rec.positionSizeDollars.toLocaleString()}
            </p>
            <p className="text-xs text-text-muted">
              R/R: {riskReward > 0 ? `1:${riskReward.toFixed(1)}` : 'N/A'}
            </p>
          </div>
        </div>

        {/* Signal Reasons */}
        <div>
          <p className="mb-2 text-xs font-medium text-text-muted">
            Signal Reasons:
          </p>
          <div className="flex flex-wrap gap-1">
            {rec.signalReasons.slice(0, 4).map((reason, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {reason}
              </Badge>
            ))}
            {rec.signalReasons.length > 4 && (
              <Badge variant="outline" className="text-xs">
                +{rec.signalReasons.length - 4} more
              </Badge>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Button
            onClick={onPaperTrade}
            disabled={isPaperTrading}
            className="flex-1"
            variant={rec.signalType === 'BUY' ? 'default' : 'outline'}
          >
            <LineChart className="mr-2 h-4 w-4" />
            {isPaperTrading ? 'Trading...' : 'Paper Trade'}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={onTrackInPortfolio}
          >
            <Briefcase className="mr-2 h-4 w-4" />
            Track in Portfolio
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
