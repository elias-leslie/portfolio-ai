'use client'

import { ShieldAlert, Target, Wallet } from 'lucide-react'
import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TradeRecommendation } from '@/lib/api/recommendations'

interface DecisionMemoCardProps {
  recommendation: TradeRecommendation
  onTrackInPortfolio: () => void
}

function getConfidenceLabel(recommendation: TradeRecommendation): string {
  if (recommendation.validationType === 'both' && recommendation.signalStrength >= 8) {
    return 'High'
  }
  if (recommendation.signalStrength >= 6) {
    return 'Medium'
  }
  return 'Low'
}

function buildWhyNow(recommendation: TradeRecommendation): string {
  const reasons = recommendation.signalReasons.slice(0, 2).join(', ')
  return reasons || 'The setup still matches the main checklist.'
}

function buildBreakText(recommendation: TradeRecommendation): string {
  return `Step aside if it falls near $${recommendation.stopLoss.toFixed(2)} or the reason for owning it changes.`
}

function buildSizingText(recommendation: TradeRecommendation): string {
  return `${recommendation.positionSizeShares} shares, about $${recommendation.positionSizeDollars.toLocaleString()}, using your current sizing baseline.`
}

function buildConfidenceText(recommendation: TradeRecommendation): string {
  const label = getConfidenceLabel(recommendation)
  const trustReason =
    recommendation.validationType === 'both'
      ? 'backed by both a live thesis and a tested strategy'
      : recommendation.validationType === 'backtest'
        ? 'backed by tested past results'
        : 'backed by a live thesis'
  return `${label} confidence. Scored ${recommendation.signalStrength}/10 and ${trustReason}.`
}

export function DecisionMemoCard({
  recommendation,
  onTrackInPortfolio,
}: DecisionMemoCardProps) {
  return (
    <Card className="border-border/40 bg-surface/70">
      <CardHeader className="gap-3 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="font-display text-2xl">{recommendation.symbol}</CardTitle>
            <p className="mt-1 text-sm text-text-muted">
              {recommendation.strategyName}
            </p>
          </div>
          <Badge variant="outline">
            {getConfidenceLabel(recommendation)} confidence
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <Target className="h-4 w-4 text-primary" />
            Why now
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {buildWhyNow(recommendation)}
          </p>
        </div>

        <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <ShieldAlert className="h-4 w-4 text-warning" />
            What breaks it
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {buildBreakText(recommendation)}
          </p>
        </div>

        <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <Wallet className="h-4 w-4 text-accent" />
            Sizing
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {buildSizingText(recommendation)}
          </p>
        </div>

        <div className="rounded-xl border border-border/40 bg-surface-muted/20 p-4">
          <div className="text-sm font-semibold text-text">Confidence</div>
          <p className="mt-2 text-sm text-text-muted">
            {buildConfidenceText(recommendation)}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={onTrackInPortfolio}>
            Track in Portfolio
          </Button>
          <Button asChild variant="outline">
            <Link href={`/symbols/${recommendation.symbol}`}>Symbol Workspace</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
