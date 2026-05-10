'use client'

import {
  describeIntradayMood,
  intradayMoodScore,
} from '@/components/portfolio/investing-language'
import { RelativeTime } from '@/components/shared/RelativeTime'
import type { HomeTodayBriefMetric } from '@/lib/api/home'
import type {
  EnrichedIndicator,
  MarketIntelligenceResponse,
} from '@/lib/api/market'
import { metricToneClasses } from '@/lib/dataQuality'
import { cn } from '@/lib/utils'

function formatMetricNumber(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'Unavailable'
  }
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function formatMarketAsOf(value?: string | null) {
  if (!value) {
    return 'As of time unavailable'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'As of time unavailable'
  }
  return `As of ${parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`
}

function formatEtMarketAsOf(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return `As of ${parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
  })} ET`
}

function indicatorAsOf(
  indicator: EnrichedIndicator | undefined,
  fallback?: string | null,
) {
  return indicator?.lastUpdated ?? fallback ?? null
}

export function buildLiveMarketMetrics(
  market: MarketIntelligenceResponse | undefined,
): HomeTodayBriefMetric[] | null {
  if (!market?.indicators || !market.sectorRotation) return null

  const sp500 = market.indicators.sp500
  const vix = market.indicators.vix
  const tnx = market.indicators.tnx
  if (!sp500 || !vix || !tnx) return null

  const leading = market.sectorRotation.leading.slice(0, 3)
  const leadership = leading
    .map((sector) => sector.name)
    .filter(Boolean)
    .join(', ')
  const marketAsOf = market.lastUpdated
  const sp500AsOf = indicatorAsOf(sp500, marketAsOf)
  const vixAsOf = indicatorAsOf(vix, marketAsOf)
  const tnxAsOf = indicatorAsOf(tnx, marketAsOf)
  const leadershipAsOf = leading[0]?.lastUpdated ?? marketAsOf
  const moodScore = intradayMoodScore(market)
  const mood = describeIntradayMood(market)

  return [
    {
      key: 'sp500',
      label: 'S&P 500',
      value: formatMetricNumber(sp500.value),
      changePct: sp500.changePct,
      detail: 'Broad market benchmark',
      horizon: 'Current quote · 1D vs prior close',
      asOf: sp500AsOf,
      asOfLabel: formatEtMarketAsOf(sp500AsOf),
      tone: (sp500.changePct ?? 0) > 0 ? 'positive' : 'negative',
    },
    {
      key: 'vix',
      label: 'VIX',
      value: formatMetricNumber(vix.value),
      changePct: vix.changePct,
      detail: 'Risk pricing',
      horizon: 'Current quote · 1D vs prior close',
      asOf: vixAsOf,
      asOfLabel: formatEtMarketAsOf(vixAsOf),
      tone: vix.value < 20 ? 'positive' : 'warning',
    },
    {
      key: 'tnx',
      label: '10Y Yield',
      value: `${formatMetricNumber(tnx.value, 3)}%`,
      changePct: tnx.changePct,
      detail: 'Rate pressure',
      horizon: 'Current quote · 1D vs prior close',
      asOf: tnxAsOf,
      asOfLabel: formatEtMarketAsOf(tnxAsOf),
      tone: tnx.value >= 4.5 ? 'warning' : 'neutral',
    },
    {
      key: 'intraday_mood',
      label: 'Intraday Mood',
      value: moodScore?.toString() ?? '—',
      changePct: null,
      detail: mood.label,
      horizon: 'Live proxy · Quote inputs',
      asOf: marketAsOf,
      asOfLabel: formatEtMarketAsOf(marketAsOf),
      tone:
        mood.tone === 'gain'
          ? 'positive'
          : mood.tone === 'warning' || mood.tone === 'loss'
            ? 'warning'
            : 'neutral',
    },
    {
      key: 'leadership',
      label: 'Leadership',
      value: leadership || 'Mixed',
      changePct: leading[0]?.changePct ?? null,
      detail: 'Sectors leading today',
      horizon: 'Current quotes · 1D sectors',
      asOf: leadershipAsOf,
      asOfLabel: formatEtMarketAsOf(leadershipAsOf),
      tone: leading.length > 0 ? 'positive' : 'neutral',
      span: 'wide',
    },
  ]
}

function MarketStripItem({ metric }: { metric: HomeTodayBriefMetric }) {
  const wide = metric.span === 'wide'
  return (
    <div
      className={cn(
        'rounded-2xl border px-3 py-3',
        metricToneClasses(metric.tone),
        wide && '@[28rem]:col-span-2',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {metric.label}
        </p>
        {metric.changePct != null ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">
            {metric.changePct > 0 ? '+' : ''}
            {metric.changePct.toFixed(2)}%
          </span>
        ) : null}
      </div>
      <p
        className={cn(
          'mt-1.5 font-semibold tracking-tight text-text',
          wide ? 'text-[13px] leading-5' : 'text-[1.05rem] leading-none',
        )}
      >
        {metric.value}
      </p>
      <p className="mt-1 text-[10px] uppercase tracking-[0.18em] text-text-muted">
        {metric.detail}
      </p>
      <p className="mt-1 text-[10px] uppercase tracking-[0.18em] text-text-muted/80">
        {metric.horizon ?? 'Horizon unavailable'} ·{' '}
        {metric.asOfLabel ?? formatMarketAsOf(metric.asOf)}
      </p>
    </div>
  )
}

export interface MarketStripGridProps {
  metrics: HomeTodayBriefMetric[]
  isLive: boolean
  timestamp: string | null | undefined
  loading: boolean
}

export function MarketStripGrid({
  metrics,
  isLive,
  timestamp,
  loading,
}: MarketStripGridProps) {
  return (
    <section className="@container rounded-2xl border border-border/35 bg-surface/35 p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Market Strip
          </p>
          <h3 className="mt-1 font-display text-base tracking-tight text-text">
            Tape that matters to this portfolio
          </h3>
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
          {timestamp ? (
            <>
              {isLive ? 'Market data' : 'Generated'}{' '}
              <RelativeTime value={timestamp} />
            </>
          ) : loading ? (
            'Loading tape'
          ) : (
            'Update time unavailable'
          )}
        </p>
      </div>

      <div className="mt-3 grid gap-2 @[28rem]:grid-cols-2">
        {loading && metrics.length === 0
          ? [...Array(5)].map((_, index) => (
              <div
                key={`overview-market-strip-skeleton-${index}`}
                className={cn(
                  'h-[4.75rem] rounded-2xl skeleton',
                  index === 4 && '@[28rem]:col-span-2',
                )}
              />
            ))
          : metrics.map((metric) => (
              <MarketStripItem key={metric.key} metric={metric} />
            ))}
      </div>
    </section>
  )
}
