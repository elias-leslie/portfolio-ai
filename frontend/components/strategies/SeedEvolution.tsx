'use client'

import { formatDistanceToNow } from 'date-fns'
import {
  ArrowRight,
  CheckCircle,
  FlaskConical,
  Lightbulb,
  Target,
  TrendingUp,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useStrategyEvolution } from '@/lib/hooks/useStrategies'

interface SeedEvolutionProps {
  strategyId: string
}

const statusColors = {
  pending: 'bg-warning/10 text-warning',
  processing: 'bg-accent/10 text-accent',
  converted: 'bg-gain/10 text-gain',
  rejected: 'bg-loss/10 text-loss',
}

export function SeedEvolution({ strategyId }: SeedEvolutionProps) {
  const { data: evolution, isLoading, error } = useStrategyEvolution(strategyId)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Evolution Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error || !evolution) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Evolution Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-muted">
            Unable to load evolution data
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Target className="h-4 w-4" />
          Strategy Evolution
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Evolution Timeline */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {/* Seed Stage */}
          <TimelineStage
            icon={Lightbulb}
            label="Seed"
            active={!!evolution.seed}
            details={
              evolution.seed
                ? {
                    confidence: evolution.seed.confidence,
                    date: evolution.seed.createdAt,
                  }
                : undefined
            }
          />
          <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" />

          {/* Backtest Stage */}
          <TimelineStage
            icon={FlaskConical}
            label="Backtest"
            active={evolution.backtests.length > 0}
            details={
              evolution.backtests.length > 0
                ? {
                    count: evolution.backtests.length,
                    bestSharpe: Math.max(
                      ...evolution.backtests.map((b) => b.sharpeRatio || 0),
                    ),
                  }
                : undefined
            }
          />
          <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" />

          {/* Strategy Stage */}
          <TimelineStage
            icon={Target}
            label="Strategy"
            active={true}
            details={{
              status: evolution.status,
              sharpe: evolution.performance.expectedSharpe,
            }}
          />
          <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" />

          {/* Signals Stage */}
          <TimelineStage
            icon={TrendingUp}
            label="Signals"
            active={evolution.signals.length > 0}
            details={
              evolution.signals.length > 0
                ? { count: evolution.signals.length }
                : undefined
            }
          />
          <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" />

          {/* Trades Stage */}
          <TimelineStage
            icon={CheckCircle}
            label="Trades"
            active={evolution.trades.length > 0}
            details={
              evolution.trades.length > 0
                ? { count: evolution.trades.length }
                : undefined
            }
          />
        </div>

        {/* Seed Details (if exists) */}
        {evolution.seed && (
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-warning" />
              <span className="text-sm font-medium">Seed Origin</span>
              <Badge variant="outline" className={statusColors.converted}>
                Confidence: {evolution.seed.confidence}/10
              </Badge>
            </div>
            <p className="text-sm text-text-muted line-clamp-3">
              {evolution.seed.thesis}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Created{' '}
              {formatDistanceToNow(new Date(evolution.seed.createdAt), {
                addSuffix: true,
              })}
            </p>
          </div>
        )}

        {/* Performance Summary */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MiniMetric
            label="Expected Sharpe"
            value={evolution.performance.expectedSharpe?.toFixed(2) || '-'}
          />
          <MiniMetric
            label="Live Sharpe"
            value={evolution.performance.liveSharpe?.toFixed(2) || '-'}
          />
          <MiniMetric
            label="Win Rate"
            value={
              evolution.performance.liveWinRate
                ? `${(evolution.performance.liveWinRate * 100).toFixed(0)}%`
                : '-'
            }
          />
          <MiniMetric
            label="Total Trades"
            value={evolution.performance.totalTrades.toString()}
          />
        </div>
      </CardContent>
    </Card>
  )
}

interface TimelineStageProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  active: boolean
  details?: {
    confidence?: number
    date?: string
    count?: number
    bestSharpe?: number
    status?: string
    sharpe?: number | null
  }
}

function TimelineStage({
  icon: Icon,
  label,
  active,
  details,
}: TimelineStageProps) {
  return (
    <div
      className={`flex shrink-0 flex-col items-center gap-1 rounded-lg border p-2 ${
        active ? 'border-primary bg-primary/5' : 'border-border bg-muted/30'
      }`}
    >
      <Icon
        className={`h-5 w-5 ${active ? 'text-primary' : 'text-text-muted'}`}
      />
      <span
        className={`text-xs font-medium ${
          active ? 'text-primary' : 'text-text-muted'
        }`}
      >
        {label}
      </span>
      {details && (
        <span className="text-xs text-text-muted">
          {details.confidence && `${details.confidence}/10`}
          {details.count !== undefined && `${details.count}`}
          {details.bestSharpe !== undefined &&
            `Best: ${details.bestSharpe.toFixed(2)}`}
          {details.status && details.status}
          {details.sharpe !== undefined &&
            details.sharpe !== null &&
            `${details.sharpe.toFixed(2)}`}
        </span>
      )}
    </div>
  )
}

interface MiniMetricProps {
  label: string
  value: string
}

function MiniMetric({ label, value }: MiniMetricProps) {
  return (
    <div className="rounded-md border bg-muted/30 p-2 text-center">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}
