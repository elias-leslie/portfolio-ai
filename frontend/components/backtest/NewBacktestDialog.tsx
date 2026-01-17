'use client'

import { Calendar, ChevronDown, Info, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
import { useStartBacktest } from '@/lib/hooks/useBacktest'

interface NewBacktestDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Detailed strategy information for UI display and AI agent consumption
// Each strategy includes: description, when to use, market conditions, typical hold time, and risk level
interface StrategyDetails {
  name: string
  shortDescription: string
  whenToUse: string
  marketConditions: string
  holdingPeriod: string
  riskLevel: 'Low' | 'Medium' | 'High'
  bestFor: string
  avoidWhen: string
}

const STRATEGIES: Record<string, StrategyDetails> = {
  enhanced: {
    name: 'Enhanced Signal',
    shortDescription:
      'Multi-confirmation technical strategy with configurable parameters',
    whenToUse:
      'Default choice for most backtests. Use when you want balanced risk/reward with tunable parameters.',
    marketConditions:
      'Works in trending and range-bound markets. Requires 5+ of 8 technical confirmations (price > EMA, healthy RSI, positive MACD, volume, momentum alignment).',
    holdingPeriod: '5-30 days typical, configurable up to 120 days',
    riskLevel: 'Medium',
    bestFor:
      'Stocks with clear technical patterns, moderate volatility (ATR 2-4%), good liquidity (>1M daily volume)',
    avoidWhen:
      'Choppy sideways markets, low-volume stocks, earnings week, extreme VIX (>30)',
  },
  signalClassifier: {
    name: 'Signal Classifier',
    shortDescription:
      'Original rule-based classifier requiring 10+ confirmations including fundamentals',
    whenToUse:
      'Use when you have fundamental data available and want stricter entry criteria.',
    marketConditions:
      'Requires fundamental/analyst data for full scoring. Technical-only mode generates fewer signals. Best in stable uptrends.',
    holdingPeriod: '30-60 days typical',
    riskLevel: 'Low',
    bestFor:
      'Blue-chip stocks with analyst coverage, stocks with recent earnings beats, sectors showing institutional accumulation',
    avoidWhen:
      'Small-caps without analyst coverage, pre-earnings periods, sectors under regulatory scrutiny',
  },
  momentum: {
    name: 'Momentum',
    shortDescription:
      'Rides intermediate-term momentum with multi-horizon confirmation',
    whenToUse:
      'Use in strong bull markets or when a stock is breaking out of consolidation with volume.',
    marketConditions:
      'Best when: SPY > 200 SMA, sector showing relative strength, stock RSI 50-70 (bullish but not overbought). Uses 20/60/252-day momentum scoring.',
    holdingPeriod: '30-60 days, exits on momentum fade (RSI < 40)',
    riskLevel: 'High',
    bestFor:
      'Growth stocks in uptrends, sector leaders, stocks with institutional buying, post-earnings momentum plays',
    avoidWhen:
      'Bear markets, mean-reverting sectors (utilities), stocks with declining volume, late-cycle rallies',
  },
  meanReversion: {
    name: 'Mean Reversion',
    shortDescription: 'Catches oversold bounces in fundamentally strong stocks',
    whenToUse:
      'Use when quality stocks are temporarily oversold (RSI < 30) but still in long-term uptrend (price > 200 SMA).',
    marketConditions:
      'Best in: range-bound markets, after sector pullbacks, when VIX spikes then reverses. Requires uptrend context to avoid catching falling knives.',
    holdingPeriod: '3-10 days (quick trades), tight stops',
    riskLevel: 'Medium',
    bestFor:
      'Large-caps with temporary weakness, dividend stocks after ex-date drops, quality names hit by sector rotation',
    avoidWhen:
      'Downtrending stocks (price < 200 SMA), fundamental deterioration, high-beta names in bear markets',
  },
  trendFollowing: {
    name: 'Trend Following',
    shortDescription:
      'Follows strong trends with trailing ATR stops, lets winners run',
    whenToUse:
      'Use for long-term trend capture when all moving averages are aligned (price > 20 SMA > 50 SMA > 200 SMA).',
    marketConditions:
      'Best in: strong bull markets, sector rotations with clear leaders, breakouts from long bases. Requires perfect SMA alignment for entry.',
    holdingPeriod: '60-120+ days, no fixed profit target',
    riskLevel: 'Medium',
    bestFor:
      'Trending sectors (tech in bull markets), stocks making new highs, ETFs with clear directional bias',
    avoidWhen:
      'Choppy/sideways markets, stocks in trading ranges, high-volatility periods (earnings, FOMC), mean-reverting assets',
  },
}

export function NewBacktestDialog({
  open,
  onOpenChange,
}: NewBacktestDialogProps) {
  const [symbol, setSymbol] = useState('')
  const [strategy, setStrategy] = useState('enhanced')
  const [isProcessing, setIsProcessing] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const startBacktest = useStartBacktest()

  // Strategy parameters with defaults
  const [stopLossAtr, setStopLossAtr] = useState(2.0)
  const [maxHoldingDays, setMaxHoldingDays] = useState(30)
  const [targetProfitPct, setTargetProfitPct] = useState(15)
  const [minConfirmations, setMinConfirmations] = useState(5)

  // Calculate default dates (1 year lookback)
  const getDefaultDates = () => {
    const endDate = new Date()
    const startDate = new Date(endDate)
    startDate.setFullYear(startDate.getFullYear() - 1)

    return {
      start: startDate.toISOString().split('T')[0],
      end: endDate.toISOString().split('T')[0],
    }
  }

  const defaultDates = getDefaultDates()
  const [startDate, setStartDate] = useState(defaultDates.start)
  const [endDate, setEndDate] = useState(defaultDates.end)

  /**
   * Validate form inputs
   */
  const getValidationError = (): string | null => {
    if (!symbol.trim()) {
      return 'Please enter a symbol'
    }
    if (symbol.length > 10) {
      return 'Symbol must be 10 characters or less'
    }
    if (!/^[A-Z0-9.-]+$/.test(symbol.toUpperCase())) {
      return 'Symbol must contain only letters, numbers, dots, and dashes'
    }
    if (!startDate) {
      return 'Please select a start date'
    }
    if (!endDate) {
      return 'Please select an end date'
    }
    if (new Date(startDate) >= new Date(endDate)) {
      return 'Start date must be before end date'
    }
    return null
  }

  const validationError = getValidationError()
  const canSubmit = !validationError && !isProcessing

  /**
   * Reset form to defaults
   */
  const resetForm = () => {
    setSymbol('')
    setStrategy('enhanced')
    setStartDate(defaultDates.start)
    setEndDate(defaultDates.end)
    setStopLossAtr(2.0)
    setMaxHoldingDays(30)
    setTargetProfitPct(15)
    setMinConfirmations(5)
    setShowAdvanced(false)
  }

  /**
   * Handle form submission
   */
  const handleSubmit = async () => {
    if (!canSubmit) return

    setIsProcessing(true)
    try {
      await startBacktest.mutateAsync({
        symbol: symbol.toUpperCase(),
        strategy,
        startDate: startDate,
        endDate: endDate,
        parameters: {
          stopLossAtrMultiplier: stopLossAtr,
          maxHoldingDays: maxHoldingDays,
          targetProfitPct: targetProfitPct,
          minConfirmations: minConfirmations,
        },
      })

      // Reset form and close dialog on success
      resetForm()
      onOpenChange(false)
    } catch (error) {
      // Error is already handled by the mutation hook
      console.error('Backtest submission error:', error)
    } finally {
      setIsProcessing(false)
    }
  }

  /**
   * Handle dialog close
   */
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isProcessing) {
      resetForm()
    }
    onOpenChange(newOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        data-testid="new-backtest-dialog"
        className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle>Start New Backtest</DialogTitle>
          <DialogDescription>
            Test a trading strategy against historical data
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Symbol Input */}
          <div className="grid gap-2">
            <Label htmlFor="symbol">Symbol</Label>
            <Input
              id="symbol"
              placeholder="e.g., AAPL, TSLA"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              disabled={isProcessing}
              autoFocus
              className="font-mono uppercase"
            />
          </div>

          {/* Strategy Select */}
          <div className="grid gap-2">
            <Label htmlFor="strategy">Strategy</Label>
            <Select
              value={strategy}
              onValueChange={setStrategy}
              disabled={isProcessing}
            >
              <SelectTrigger id="strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="enhanced">Enhanced Signal</SelectItem>
                <SelectItem value="signal_classifier">
                  Signal Classifier
                </SelectItem>
                <SelectItem value="momentum">Momentum</SelectItem>
                <SelectItem value="mean_reversion">Mean Reversion</SelectItem>
                <SelectItem value="trend_following">Trend Following</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Strategy Details Card - visible for users and AI agents */}
          {STRATEGIES[strategy] && (
            <div
              className="rounded-lg border border-border bg-card/50 p-4 space-y-3"
              data-testid="strategy-details"
              data-strategy={strategy}
              data-strategy-name={STRATEGIES[strategy].name}
              data-risk-level={STRATEGIES[strategy].riskLevel}
              data-holding-period={STRATEGIES[strategy].holdingPeriod}
            >
              {/* Header with risk badge */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Info className="h-4 w-4 text-accent shrink-0" />
                  <span className="font-medium text-sm">
                    {STRATEGIES[strategy].shortDescription}
                  </span>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                    STRATEGIES[strategy].riskLevel === 'High'
                      ? 'bg-loss/20 text-loss'
                      : STRATEGIES[strategy].riskLevel === 'Low'
                        ? 'bg-gain/20 text-gain'
                        : 'bg-warning/20 text-warning'
                  }`}
                >
                  {STRATEGIES[strategy].riskLevel} Risk
                </span>
              </div>

              {/* When to use */}
              <div className="space-y-1">
                <p className="text-xs font-medium text-text-muted">
                  When to use:
                </p>
                <p className="text-xs text-text">
                  {STRATEGIES[strategy].whenToUse}
                </p>
              </div>

              {/* Market conditions */}
              <div className="space-y-1">
                <p className="text-xs font-medium text-text-muted">
                  Market conditions:
                </p>
                <p className="text-xs text-text">
                  {STRATEGIES[strategy].marketConditions}
                </p>
              </div>

              {/* Best for / Avoid grid */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gain">✓ Best for:</p>
                  <p className="text-xs text-text-muted">
                    {STRATEGIES[strategy].bestFor}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-medium text-loss">✗ Avoid when:</p>
                  <p className="text-xs text-text-muted">
                    {STRATEGIES[strategy].avoidWhen}
                  </p>
                </div>
              </div>

              {/* Holding period */}
              <p className="text-xs text-text-muted pt-1 border-t border-border/50">
                <span className="font-medium">Typical hold:</span>{' '}
                {STRATEGIES[strategy].holdingPeriod}
              </p>
            </div>
          )}

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="start-date">Start Date</Label>
              <div className="relative">
                <Input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={isProcessing}
                  className="pr-10"
                />
                <Calendar className="absolute right-3 top-2.5 h-4 w-4 text-text-muted pointer-events-none" />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="end-date">End Date</Label>
              <div className="relative">
                <Input
                  id="end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={isProcessing}
                  className="pr-10"
                />
                <Calendar className="absolute right-3 top-2.5 h-4 w-4 text-text-muted pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Advanced Parameters (Collapsible) */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button
                data-testid="advanced-parameters"
                variant="ghost"
                size="sm"
                className="w-full justify-between text-text-muted hover:text-text"
                disabled={isProcessing}
              >
                <span className="flex items-center gap-2">
                  <Settings2 className="h-4 w-4" />
                  Advanced Parameters
                </span>
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${
                    showAdvanced ? 'rotate-180' : ''
                  }`}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4 space-y-4 rounded-lg border border-border bg-card p-4">
              {/* Stop Loss ATR Multiplier */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Stop Loss</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {stopLossAtr.toFixed(1)}x ATR
                  </span>
                </div>
                <Slider
                  value={[stopLossAtr]}
                  onValueChange={([v]) => setStopLossAtr(v)}
                  min={1.0}
                  max={4.0}
                  step={0.5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Exit when price drops this many ATR from entry
                </p>
              </div>

              {/* Max Holding Days */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Max Holding Period</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {maxHoldingDays} days
                  </span>
                </div>
                <Slider
                  value={[maxHoldingDays]}
                  onValueChange={([v]) => setMaxHoldingDays(v)}
                  min={5}
                  max={120}
                  step={5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Force exit after this many days regardless of price
                </p>
              </div>

              {/* Target Profit % */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Target Profit</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {targetProfitPct}%
                  </span>
                </div>
                <Slider
                  value={[targetProfitPct]}
                  onValueChange={([v]) => setTargetProfitPct(v)}
                  min={5}
                  max={50}
                  step={5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Take profit when gain reaches this percentage
                </p>
              </div>

              {/* Min Confirmations */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Min Confirmations</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {minConfirmations} / 8
                  </span>
                </div>
                <Slider
                  value={[minConfirmations]}
                  onValueChange={([v]) => setMinConfirmations(v)}
                  min={3}
                  max={8}
                  step={1}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Minimum technical confirmations required to enter trade
                </p>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Validation Error */}
          {validationError && (
            <div className="rounded-md border border-loss/50 bg-loss/10 p-3">
              <p className="text-sm text-loss">{validationError}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isProcessing}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {isProcessing ? 'Starting...' : 'Start Backtest'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
