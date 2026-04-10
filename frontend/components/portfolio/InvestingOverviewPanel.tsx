'use client'
import { useState } from 'react'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import type { PortfolioAnalytics, PortfolioResponse } from '@/lib/api/portfolio'
import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { useNewsIntelligence } from '@/lib/hooks/useNews'
import { cn } from '@/lib/utils'
import {
  describeMarketMood,
  describeNewsTone,
  describePortfolioHealth,
  describeTenYearRate,
  describeVolatility,
  type OverviewTone,
} from './investing-language'

function readHighlightedMetric() {
  if (typeof window === 'undefined') {
    return null
  }

  return new URLSearchParams(window.location.search).get('highlight')
}

function formatIndicatorValue(value: number | null | undefined, suffix = '') {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }

  return `${value.toFixed(suffix ? 2 : 1)}${suffix}`
}

function toneSurfaceClasses(tone: OverviewTone) {
  if (tone === 'gain') {
    return 'border-gain/25 bg-gain/10'
  }
  if (tone === 'warning') {
    return 'border-amber-500/25 bg-amber-500/10'
  }
  if (tone === 'loss') {
    return 'border-loss/25 bg-loss/10'
  }
  return 'border-border/30 bg-surface-muted/20'
}

function toneValueClasses(tone: OverviewTone) {
  if (tone === 'gain') {
    return 'text-gain'
  }
  if (tone === 'warning') {
    return 'text-amber-200'
  }
  if (tone === 'loss') {
    return 'text-loss'
  }
  return 'text-text'
}

function OverviewStat({
  label,
  value,
  detail,
  tone = 'default',
  featured = false,
  highlighted = false,
}: {
  label: string
  value: string
  detail: string
  tone?: OverviewTone
  featured?: boolean
  highlighted?: boolean
}) {
  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition-colors',
        toneSurfaceClasses(tone),
        highlighted && 'ring-2 ring-primary/35',
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {label}
      </p>
      <p
        className={cn(
          'mt-2 font-semibold tracking-tight',
          featured ? 'text-3xl' : 'text-2xl',
          toneValueClasses(tone),
        )}
      >
        {value}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-text-muted">{detail}</p>
    </div>
  )
}

export function InvestingOverviewPanel({
  portfolio,
  analytics,
  accountsCount,
}: {
  portfolio?: PortfolioResponse | null
  analytics?: PortfolioAnalytics | null
  accountsCount: number
}) {
  const { data: market } = useMarketIntelligence()
  const { data: marketNews } = useNewsIntelligence(undefined, { limit: 24 })
  const [highlightedMetric] = useState(readHighlightedMetric)

  const positionCount = portfolio?.positions.length ?? 0
  const totalGain = portfolio?.totalGain
  const portfolioHealth = describePortfolioHealth(analytics)
  const marketMood = describeMarketMood(market?.fearGreed)
  const volatility = describeVolatility(market?.indicators.vix?.value)
  const tenYearRate = describeTenYearRate(market?.indicators.tnx?.value)
  const newsTone = describeNewsTone(marketNews?.summary)
  const sp500Value =
    market?.indicators.sp500 != null
      ? formatPercent(market.indicators.sp500.changePct ?? 0, {
          decimals: 2,
          sign: true,
        })
      : 'Loading…'

  return (
    <div id="portfolio-overview">
      <SectionCard
        title="At a glance"
        actions={<MarketStatusBadge />}
        variant="surface"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OverviewStat
            label="Portfolio Value"
            value={formatCurrencyWhole(portfolio?.totalValue)}
            detail={`${positionCount} position${positionCount === 1 ? '' : 's'} across ${accountsCount} account${accountsCount === 1 ? '' : 's'}.`}
            featured
          />
          <OverviewStat
            label="Total Gain"
            value={formatCurrencyWhole(totalGain)}
            detail={formatPercent(portfolio?.totalGainPct, {
              decimals: 2,
              sign: true,
            })}
            tone={totalGain == null ? 'default' : totalGain >= 0 ? 'gain' : 'loss'}
            featured
          />
          <OverviewStat
            label="Portfolio Health"
            value={portfolioHealth.label}
            detail={portfolioHealth.detail}
            tone={portfolioHealth.tone}
            highlighted={highlightedMetric === 'concentration'}
          />
          <OverviewStat
            label="Market Mood"
            value={marketMood.label}
            detail={marketMood.detail}
            tone={marketMood.tone}
          />
          <OverviewStat
            label="S&P 500 Today"
            value={sp500Value}
            detail={
              market?.indicators.sp500?.value != null
                ? `Index ${Math.round(market.indicators.sp500.value).toLocaleString()}.`
                : 'Tracking the broad-market benchmark.'
            }
            tone={
              (market?.indicators.sp500?.changePct ?? 0) >= 0 ? 'gain' : 'loss'
            }
          />
          <OverviewStat
            label="Volatility Now"
            value={formatIndicatorValue(market?.indicators.vix?.value)}
            detail={volatility.detail}
            tone={volatility.tone}
          />
          <OverviewStat
            label="10-Year Rate Now"
            value={formatIndicatorValue(market?.indicators.tnx?.value, '%')}
            detail={tenYearRate.detail}
            tone={tenYearRate.tone}
          />
          <OverviewStat
            label="Recent News Tone"
            value={newsTone.label}
            detail={newsTone.detail}
            tone={newsTone.tone}
          />
        </div>
      </SectionCard>
    </div>
  )
}
