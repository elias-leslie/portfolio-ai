'use client'

import {
  describeIntradayMood,
  intradayMoodScore,
} from '@/components/portfolio/investing-language'
import { RelativeTime } from '@/components/shared/RelativeTime'
import type {
  EnrichedIndicator,
  MarketIntelligenceResponse,
} from '@/lib/api/market'
import { metricToneClasses } from '@/lib/dataQuality'
import { cn } from '@/lib/utils'

export interface MarketStripMetric {
  key: string
  label: string
  value: string
  changePct: number | null
  detail: string
  tone: string
  horizon?: string | null
  asOf?: string | null
  asOfLabel?: string | null
  span?: 'wide' | null
  isStale?: boolean
}

// Mirrors backend account_valuation._quote_freshness "stale" tier:
// open market → > 15 minutes old; closed market → > 24 hours old.
const STALE_THRESHOLD_MS_OPEN = 15 * 60 * 1000
const STALE_THRESHOLD_MS_CLOSED = 24 * 60 * 60 * 1000

function isIndicatorStale(
  asOf: string | null | undefined,
  marketIsOpen: boolean,
): boolean {
  if (!asOf) return false
  const ts = new Date(asOf).getTime()
  if (Number.isNaN(ts)) return false
  const ageMs = Date.now() - ts
  return (
    ageMs > (marketIsOpen ? STALE_THRESHOLD_MS_OPEN : STALE_THRESHOLD_MS_CLOSED)
  )
}

function formatMetricNumber(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'Unavailable'
  }
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function indicatorAsOf(
  indicator: EnrichedIndicator | undefined,
  fallback?: string | null,
) {
  return indicator?.lastUpdated ?? fallback ?? null
}

export function buildLiveMarketMetrics(
  market: MarketIntelligenceResponse | undefined,
  options: { marketIsOpen?: boolean } = {},
): MarketStripMetric[] | null {
  if (!market?.indicators || !market.sectorRotation) return null

  const sp500 = market.indicators.sp500
  const vix = market.indicators.vix
  const tnx = market.indicators.tnx
  if (!sp500 || !vix || !tnx) return null

  const marketAsOf = market.lastUpdated
  const sp500AsOf = indicatorAsOf(sp500, marketAsOf)
  const vixAsOf = indicatorAsOf(vix, marketAsOf)
  const tnxAsOf = indicatorAsOf(tnx, marketAsOf)
  const moodScore = intradayMoodScore(market)
  const mood = describeIntradayMood(market)
  const marketIsOpen = options.marketIsOpen ?? false

  return [
    {
      key: 'sp500',
      label: 'S&P 500',
      value: formatMetricNumber(sp500.value),
      changePct: sp500.changePct,
      detail: 'Broad market benchmark',
      horizon: 'Current quote · 1D vs prior close',
      asOf: sp500AsOf,
      asOfLabel: null,
      tone: (sp500.changePct ?? 0) > 0 ? 'positive' : 'negative',
      isStale: isIndicatorStale(sp500AsOf, marketIsOpen),
    },
    {
      key: 'vix',
      label: 'VIX',
      value: formatMetricNumber(vix.value),
      changePct: vix.changePct,
      detail: 'Risk pricing',
      horizon: 'Current quote · 1D vs prior close',
      asOf: vixAsOf,
      asOfLabel: null,
      tone: vix.value < 20 ? 'positive' : 'warning',
      isStale: isIndicatorStale(vixAsOf, marketIsOpen),
    },
    {
      key: 'tnx',
      label: '10Y Yield',
      value: `${formatMetricNumber(tnx.value, 3)}%`,
      changePct: tnx.changePct,
      detail: 'Rate pressure',
      horizon: 'Current quote · 1D vs prior close',
      asOf: tnxAsOf,
      asOfLabel: null,
      tone: tnx.value >= 4.5 ? 'warning' : 'neutral',
      isStale: isIndicatorStale(tnxAsOf, marketIsOpen),
    },
    {
      key: 'intraday_mood',
      label: 'Intraday Mood',
      value: moodScore?.toString() ?? '—',
      changePct: null,
      detail: mood.label,
      horizon: 'Live proxy · Quote inputs',
      asOf: marketAsOf,
      asOfLabel: null,
      tone:
        mood.tone === 'gain'
          ? 'positive'
          : mood.tone === 'warning' || mood.tone === 'loss'
            ? 'warning'
            : 'neutral',
      isStale: isIndicatorStale(marketAsOf, marketIsOpen),
    },
  ]
}

function MarketStripItem({ metric }: { metric: MarketStripMetric }) {
  const wide = metric.span === 'wide'
  return (
    <div
      className={cn(
        'rounded-2xl border px-3 py-3',
        metricToneClasses(metric.tone),
        wide && '@[36rem]:col-span-2',
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
        {metric.isStale ? (
          <span
            className="ml-1 text-warning"
            title="This indicator's quote is older than the freshness threshold for the current market session."
          >
            · stale
          </span>
        ) : null}
      </p>
    </div>
  )
}

export interface MarketStripGridProps {
  metrics: MarketStripMetric[]
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
        <h3 className="font-display text-base tracking-tight text-text">
          Market Strip
        </h3>
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

      <div className="mt-3 grid gap-2 @[36rem]:grid-cols-4">
        {loading && metrics.length === 0
          ? [...Array(4)].map((_, index) => (
              <div
                key={`overview-market-strip-skeleton-${index}`}
                className="h-[4.75rem] rounded-2xl skeleton"
              />
            ))
          : metrics.map((metric) => (
              <MarketStripItem key={metric.key} metric={metric} />
            ))}
      </div>
    </section>
  )
}
