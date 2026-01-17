'use client'

import {
  BarChart3,
  Bitcoin,
  DollarSign,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { ToggleCard } from '../ToggleCard'

interface TradingRiskSettingsProps {
  riskTolerance: number
  maxPositionSizePct: string
  allowLong: boolean
  allowShort: boolean
  allowOptions: boolean
  allowCrypto: boolean
  allowFutures: boolean
  onRiskToleranceChange: (value: number) => void
  onMaxPositionSizePctChange: (value: string) => void
  onAllowLongChange: (value: boolean) => void
  onAllowShortChange: (value: boolean) => void
  onAllowOptionsChange: (value: boolean) => void
  onAllowCryptoChange: (value: boolean) => void
  onAllowFuturesChange: (value: boolean) => void
}

export function TradingRiskSettings({
  riskTolerance,
  maxPositionSizePct,
  allowLong,
  allowShort,
  allowOptions,
  allowCrypto,
  allowFutures,
  onRiskToleranceChange,
  onMaxPositionSizePctChange,
  onAllowLongChange,
  onAllowShortChange,
  onAllowOptionsChange,
  onAllowCryptoChange,
  onAllowFuturesChange,
}: TradingRiskSettingsProps) {
  return (
    <div className="space-y-6">
      {/* Risk Tolerance */}
      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Risk Level</Label>
              <span className="text-2xl font-bold text-primary">
                {riskTolerance}
              </span>
            </div>
            <Slider
              value={[riskTolerance]}
              onValueChange={(value) => onRiskToleranceChange(value[0])}
              min={1}
              max={10}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-text-muted">
              <span>1 - Very Conservative</span>
              <span>5 - Moderate</span>
              <span>10 - Very Aggressive</span>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-surface-muted/70 p-4">
            <p className="text-sm text-text-muted">
              {riskTolerance <= 3 && (
                <>
                  <strong>Conservative:</strong> You prefer stable, low-risk
                  investments with predictable returns. AI agents will focus on
                  blue-chip stocks and conservative strategies.
                </>
              )}
              {riskTolerance >= 4 && riskTolerance <= 7 && (
                <>
                  <strong>Moderate:</strong> You&rsquo;re willing to accept some
                  risk for potential growth. AI agents will suggest a balanced
                  mix of growth and value opportunities.
                </>
              )}
              {riskTolerance >= 8 && (
                <>
                  <strong>Aggressive:</strong> You&rsquo;re comfortable with
                  high-risk, high-reward investments. AI agents will explore
                  growth stocks, emerging sectors, and speculative plays.
                </>
              )}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Position Size Limit */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="max-position">Max Position Size (%)</Label>
            <Input
              id="max-position"
              type="number"
              value={maxPositionSizePct}
              onChange={(e) => onMaxPositionSizePctChange(e.target.value)}
              min="1"
              max="100"
              step="1"
            />
            <p className="text-xs text-text-muted">
              Recommended: 10-25% to maintain diversification
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Trading Preferences */}
      <Card>
        <CardContent className="pt-6">
          <h3 className="mb-4 text-base font-semibold text-text">
            Trading Preferences
          </h3>
          <p className="mb-4 text-sm text-text-muted">
            Select which types of trades you&rsquo;re willing to consider
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <ToggleCard
              icon={<TrendingUp className="h-5 w-5" />}
              title="Long Positions"
              description="Buy stocks expecting price to rise"
              checked={allowLong}
              onChange={onAllowLongChange}
              badge="Essential"
            />
            <ToggleCard
              icon={<TrendingDown className="h-5 w-5" />}
              title="Short Positions"
              description="Sell stocks expecting price to fall"
              checked={allowShort}
              onChange={onAllowShortChange}
            />
            <ToggleCard
              icon={<BarChart3 className="h-5 w-5" />}
              title="Options Trading"
              description="Calls, puts, and spreads"
              checked={allowOptions}
              onChange={onAllowOptionsChange}
            />
            <ToggleCard
              icon={<Bitcoin className="h-5 w-5" />}
              title="Cryptocurrency"
              description="Bitcoin, Ethereum, etc."
              checked={allowCrypto}
              onChange={onAllowCryptoChange}
            />
            <ToggleCard
              icon={<DollarSign className="h-5 w-5" />}
              title="Futures & Commodities"
              description="Derivatives and commodities"
              checked={allowFutures}
              onChange={onAllowFuturesChange}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
