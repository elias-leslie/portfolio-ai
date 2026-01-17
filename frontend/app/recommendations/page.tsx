'use client'

import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  Briefcase,
  DollarSign,
  FileText,
  LineChart,
  Sparkles,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/shared/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { useAccounts } from '@/lib/hooks/usePortfolio'
import {
  usePaperTrade,
  useRecommendations,
  useTrackInPortfolio,
} from '@/lib/hooks/useRecommendations'

function SignalBadge({ type, strength }: { type: string; strength: number }) {
  if (type === 'BUY') {
    return (
      <Badge className="bg-gain text-text-inverted">
        <TrendingUp className="mr-1 h-3 w-3" />
        BUY {strength}/10
      </Badge>
    )
  }
  if (type === 'SELL') {
    return (
      <Badge className="bg-loss text-text-inverted">
        <TrendingDown className="mr-1 h-3 w-3" />
        SELL {strength}/10
      </Badge>
    )
  }
  return <Badge variant="outline">HOLD {strength}/10</Badge>
}

function SignalStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'better_entry':
      return (
        <Badge className="bg-gain text-text-inverted">
          <Sparkles className="mr-1 h-3 w-3" />
          Better Entry
        </Badge>
      )
    case 'caution':
      return (
        <Badge className="bg-warning text-text-inverted">
          <AlertTriangle className="mr-1 h-3 w-3" />
          Caution
        </Badge>
      )
    default:
      return null // Don't show badge for "valid" status
  }
}

function ValidationBadge({
  validationType,
}: {
  validationType: 'thesis' | 'backtest' | 'both'
}) {
  switch (validationType) {
    case 'thesis':
      return (
        <Badge
          className="bg-primary text-primary-foreground"
          title="Event-Driven: Validated by investment thesis"
        >
          <FileText className="mr-1 h-3 w-3" />
          Thesis
        </Badge>
      )
    case 'backtest':
      return (
        <Badge
          className="bg-accent text-accent-foreground"
          title="Technical: Validated by backtest (Sharpe >= 1.0)"
        >
          <BarChart3 className="mr-1 h-3 w-3" />
          Technical
        </Badge>
      )
    case 'both':
      return (
        <Badge
          className="bg-warning text-text-inverted"
          title="Highest confidence: Both thesis AND backtest validated"
        >
          <Star className="mr-1 h-3 w-3" />
          Both
        </Badge>
      )
  }
}

function RecommendationCard({
  rec,
  onPaperTrade,
  onTrackInPortfolio,
  isPaperTrading,
}: {
  rec: TradeRecommendation
  onPaperTrade: () => void
  onTrackInPortfolio: () => void
  isPaperTrading: boolean
}) {
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

interface TrackModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  recommendation: TradeRecommendation | null
  onConfirm: (accountId: string, shares: number) => void
  isLoading: boolean
}

function TrackInPortfolioModal({
  open,
  onOpenChange,
  recommendation,
  onConfirm,
  isLoading,
}: TrackModalProps) {
  const { data: accounts } = useAccounts()
  const [selectedAccount, setSelectedAccount] = useState<string>('')
  const [shares, setShares] = useState<number>(0)

  // Filter out paper accounts
  const realAccounts = accounts?.filter((a) => a.accountType !== 'paper') || []

  // Reset form when modal opens with new recommendation
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && recommendation) {
      setShares(recommendation.positionSizeShares)
      setSelectedAccount('')
    }
    onOpenChange(newOpen)
  }

  const handleConfirm = () => {
    if (selectedAccount && shares > 0) {
      onConfirm(selectedAccount, shares)
    }
  }

  if (!recommendation) return null

  const totalCost = shares * recommendation.currentPrice

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5" />
            Track {recommendation.symbol} in Portfolio
          </DialogTitle>
          <DialogDescription>
            Add this position to your real portfolio. This is for tracking
            purposes only - you must execute the actual trade with your broker.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Account Selection */}
          <div className="grid gap-2">
            <Label htmlFor="account">Select Account</Label>
            {realAccounts.length === 0 ? (
              <p className="text-sm text-text-muted">
                No real accounts found. Create an account on the Portfolio page
                first.
              </p>
            ) : (
              <Select
                value={selectedAccount}
                onValueChange={setSelectedAccount}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choose an account..." />
                </SelectTrigger>
                <SelectContent>
                  {realAccounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name} ({account.accountType})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Shares Input */}
          <div className="grid gap-2">
            <Label htmlFor="shares">Number of Shares</Label>
            <Input
              id="shares"
              type="number"
              min={1}
              value={shares}
              onChange={(e) => setShares(parseInt(e.target.value, 10) || 0)}
            />
            <p className="text-xs text-text-muted">
              Suggested: {recommendation.positionSizeShares} shares ($
              {recommendation.positionSizeDollars.toLocaleString()})
            </p>
          </div>

          {/* Summary */}
          <div className="rounded-lg border border-border bg-surface-muted/50 p-3">
            <div className="flex justify-between text-sm">
              <span>Current Price:</span>
              <span className="font-medium">
                ${recommendation.currentPrice.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Shares:</span>
              <span className="font-medium">{shares}</span>
            </div>
            <div className="mt-2 flex justify-between border-t border-border pt-2 text-sm font-medium">
              <span>Total Cost:</span>
              <span>
                $
                {totalCost.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={
              !selectedAccount ||
              shares <= 0 ||
              isLoading ||
              realAccounts.length === 0
            }
          >
            {isLoading ? 'Adding...' : 'Add to Portfolio'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

import { PageContainer } from '@/components/shared/PageContainer'

export default function RecommendationsPage() {
  const [minStrength, setMinStrength] = useState(5)
  const [portfolioSize, setPortfolioSize] = useState(100000)
  const [trackModalOpen, setTrackModalOpen] = useState(false)
  const [selectedRec, setSelectedRec] = useState<TradeRecommendation | null>(
    null,
  )

  const { data, isLoading, error } = useRecommendations({
    minStrength: minStrength,
    limit: 20,
    signalType: 'BUY',
    portfolioSize: portfolioSize,
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
      {/* Page Header */}
      <PageHeader
        title="Trade Picks"
        description="Top picks from active strategies with position sizing"
        size="md"
      />

      {/* Summary Cards */}
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

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Min Signal Strength: {minStrength}</Label>
              <Slider
                value={[minStrength]}
                onValueChange={(v) => setMinStrength(v[0])}
                min={1}
                max={10}
                step={1}
              />
            </div>
            <div className="space-y-2">
              <Label>Portfolio Size: ${portfolioSize.toLocaleString()}</Label>
              <Slider
                value={[portfolioSize]}
                onValueChange={(v) => setPortfolioSize(v[0])}
                min={10000}
                max={1000000}
                step={10000}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recommendations Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-80" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card className="border-loss/30 bg-loss/10">
          <CardContent className="flex items-center gap-3 py-6">
            <AlertCircle className="h-5 w-5 text-loss" />
            <p className="text-loss">
              Failed to load recommendations:{' '}
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </CardContent>
        </Card>
      ) : recommendations.length === 0 ? (
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
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {recommendations.map((rec, i) => (
            <RecommendationCard
              key={`${rec.strategyId}-${rec.symbol}-${i}`}
              rec={rec}
              onPaperTrade={() =>
                paperTradeMutation.mutate({
                  symbol: rec.symbol,
                  strategyId: rec.strategyId,
                })
              }
              onTrackInPortfolio={() => handleTrackClick(rec)}
              isPaperTrading={paperTradeMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Track in Portfolio Modal */}
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
