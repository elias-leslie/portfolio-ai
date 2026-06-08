import type {
  EnrichedIndicator,
  FearGreedScore,
  MarketIntelligenceResponse,
} from '@/lib/api/market-types'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import type { NewsSentimentDetail } from '@/lib/api/watchlist'

export type OverviewTone = 'default' | 'gain' | 'warning' | 'loss'

export function describePortfolioHealth(
  analytics?: PortfolioAnalytics | null,
): { label: string; detail: string; tone: OverviewTone } {
  if (!analytics) {
    return {
      label: 'Awaiting data',
      detail: 'Add holdings to evaluate concentration and spread.',
      tone: 'default',
    }
  }

  const topHoldingPct = analytics.concentration?.topHoldingPct ?? 0
  const concentrationMethod = analytics.concentration?.method ?? 'line_item'
  const topHoldingName =
    analytics.concentration?.topHoldingName ?? 'top exposure'
  const vehicleTopHoldingPct =
    analytics.concentration?.vehicleTopHoldingPct ?? topHoldingPct
  const vehicleTopHoldingName =
    analytics.concentration?.vehicleTopHoldingName ?? 'largest vehicle'
  const diversificationScore = analytics.diversificationScore?.score ?? null

  if (topHoldingPct >= 50) {
    return {
      label: 'Too concentrated',
      detail:
        concentrationMethod === 'lookthrough'
          ? `${topHoldingName} ${topHoldingPct.toFixed(1)}% single-name exposure · ${vehicleTopHoldingName} ${vehicleTopHoldingPct.toFixed(1)}% vehicle weight.`
          : `Top holding ${topHoldingPct.toFixed(1)}% of positioned portfolio.`,
      tone: 'loss',
    }
  }

  if (
    topHoldingPct >= 35 ||
    (diversificationScore != null && diversificationScore < 50)
  ) {
    return {
      label: 'Needs review',
      detail:
        concentrationMethod === 'lookthrough'
          ? `${topHoldingName} ${topHoldingPct.toFixed(1)}% single-name exposure · diversification ${
              diversificationScore != null
                ? diversificationScore.toFixed(0)
                : '—'
            }`
          : `Top holding ${topHoldingPct.toFixed(1)}% · diversification ${
              diversificationScore != null
                ? diversificationScore.toFixed(0)
                : '—'
            }`,
      tone: 'warning',
    }
  }

  if (
    diversificationScore != null &&
    diversificationScore >= 75 &&
    topHoldingPct < 20
  ) {
    const symbolCount = analytics.numSymbols
    const sectorCount = analytics.diversificationScore?.numSectors ?? 0
    return {
      label: 'Well spread',
      detail: `${symbolCount} symbol${symbolCount === 1 ? '' : 's'} across ${sectorCount} sector${sectorCount === 1 ? '' : 's'}.`,
      tone: 'gain',
    }
  }

  return {
    label: 'Balanced',
    detail:
      diversificationScore != null
        ? concentrationMethod === 'lookthrough'
          ? `Diversification ${diversificationScore.toFixed(0)} · top single-name exposure ${topHoldingPct.toFixed(1)}%`
          : `Diversification ${diversificationScore.toFixed(0)} · top holding ${topHoldingPct.toFixed(1)}%`
        : concentrationMethod === 'lookthrough'
          ? `${vehicleTopHoldingName} ${vehicleTopHoldingPct.toFixed(1)}% vehicle weight · ${topHoldingName} ${topHoldingPct.toFixed(1)}% single-name exposure`
          : `Top holding ${topHoldingPct.toFixed(1)}% of positioned portfolio.`,
    tone: 'default',
  }
}

function simplifyMoodLabel(label: FearGreedScore['label'] | undefined) {
  if (!label) {
    return 'Waiting'
  }

  if (label === 'Extreme Fear') {
    return 'Fear'
  }

  if (label === 'Extreme Greed') {
    return 'Greed'
  }

  return label
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function finiteNumber(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function intradayMoodLabel(score: number) {
  if (score < 25) return 'Fearful'
  if (score < 45) return 'Cautious'
  if (score < 58) return 'Mixed'
  if (score < 75) return 'Constructive'
  return 'Risk-on'
}

function intradayMoodTone(score: number): OverviewTone {
  if (score < 25) return 'loss'
  if (score < 45) return 'warning'
  if (score >= 70) return 'gain'
  return 'default'
}

export function intradayMoodScore(
  market?: MarketIntelligenceResponse | null,
): number | null {
  if (!market?.indicators) return null
  const sp500Change = finiteNumber(market.indicators.sp500?.changePct)
  const vixValue = finiteNumber(market.indicators.vix?.value)
  const vixChange = finiteNumber(market.indicators.vix?.changePct)
  const tnxChange = finiteNumber(market.indicators.tnx?.changePct)
  const dxyChange = finiteNumber(market.indicators.dxy?.changePct)
  const sectors = [
    ...(market.sectorRotation?.leading ?? []),
    ...(market.sectorRotation?.neutral ?? []),
    ...(market.sectorRotation?.lagging ?? []),
  ]
  const sectorChanges = sectors
    .map((sector) => finiteNumber(sector.changePct))
    .filter((value): value is number => value != null)

  let score = 50
  if (sp500Change != null) score += clamp(sp500Change * 8, -18, 18)
  if (vixValue != null) {
    score += vixValue < 15 ? 12 : vixValue < 20 ? 4 : vixValue < 25 ? -8 : -18
  }
  if (vixChange != null) score -= clamp(vixChange * 0.8, -12, 12)
  if (tnxChange != null) score -= clamp(tnxChange * 1.5, -8, 8)
  if (dxyChange != null) score -= clamp(dxyChange * 0.8, -6, 6)
  if (sectorChanges.length > 0) {
    const average =
      sectorChanges.reduce((sum, value) => sum + value, 0) /
      sectorChanges.length
    const breadth =
      sectorChanges.reduce(
        (sum, value) => sum + (value > 0 ? 1 : value < 0 ? -1 : 0),
        0,
      ) / sectorChanges.length
    score += clamp(average * 5, -8, 8)
    score += clamp(breadth * 10, -10, 10)
  }

  return Math.round(clamp(score, 0, 100))
}

export function describeIntradayMood(
  market?: MarketIntelligenceResponse | null,
): {
  label: string
  detail: string
  tone: OverviewTone
} {
  const score = intradayMoodScore(market)
  if (score == null) {
    return {
      label: 'Waiting',
      detail: 'Live quote mood data is still loading.',
      tone: 'default',
    }
  }
  const sp500Change = finiteNumber(market?.indicators.sp500?.changePct)
  const vixValue = finiteNumber(market?.indicators.vix?.value)
  const parts = [`Live proxy ${score}/100`]
  if (sp500Change != null) {
    parts.push(`S&P ${sp500Change >= 0 ? '+' : ''}${sp500Change.toFixed(2)}%`)
  }
  if (vixValue != null) {
    parts.push(`VIX ${vixValue.toFixed(1)}`)
  }
  return {
    label: intradayMoodLabel(score),
    detail: `${parts.join(' · ')}.`,
    tone: intradayMoodTone(score),
  }
}

export function describeMarketMood(mood?: FearGreedScore | null): {
  label: string
  detail: string
  tone: OverviewTone
} {
  if (!mood) {
    return {
      label: 'Waiting',
      detail: 'Market mood data is still loading.',
      tone: 'default',
    }
  }

  const label = simplifyMoodLabel(mood.label)
  const score = Math.round(mood.score)
  const trendDetail =
    mood.trend === 'up'
      ? 'improving'
      : mood.trend === 'down'
        ? 'cooling off'
        : 'holding steady'

  if (score <= 25) {
    return {
      label,
      detail: `Daily score ${score} · still defensive but ${trendDetail}.`,
      tone: 'loss',
    }
  }

  if (score <= 45) {
    return {
      label,
      detail: `Daily score ${score} · sentiment is cautious.`,
      tone: 'warning',
    }
  }

  if (score >= 70) {
    return {
      label,
      detail: `Daily score ${score} · risk appetite is elevated.`,
      tone: 'gain',
    }
  }

  return {
    label,
    detail: `Daily score ${score} · sentiment looks balanced.`,
    tone: 'default',
  }
}

export function describeVolatility(value?: number | null): {
  detail: string
  tone: OverviewTone
} {
  if (value == null) {
    return {
      detail: 'Cboe Volatility Index data is still loading.',
      tone: 'default',
    }
  }

  if (value >= 30) {
    return {
      detail: 'Cboe Volatility Index is high; markets are swinging hard.',
      tone: 'loss',
    }
  }

  if (value >= 20) {
    return {
      detail: 'Cboe Volatility Index is elevated.',
      tone: 'warning',
    }
  }

  if (value >= 15) {
    return {
      detail: 'Cboe Volatility Index is in a normal range.',
      tone: 'default',
    }
  }

  return {
    detail: 'Cboe Volatility Index is calm.',
    tone: 'gain',
  }
}

export function describeTenYearRate(value?: number | null): {
  detail: string
  tone: OverviewTone
} {
  if (value == null) {
    return {
      detail: 'Rate data is still loading.',
      tone: 'default',
    }
  }

  if (value >= 4.75) {
    return {
      detail: 'Higher rates are adding pressure to stocks.',
      tone: 'warning',
    }
  }

  if (value <= 3.5) {
    return {
      detail: 'Rates are relatively supportive for stocks.',
      tone: 'gain',
    }
  }

  return {
    detail: 'Rates are in a workable range for stocks.',
    tone: 'default',
  }
}

export function describeNewsTone(summary?: NewsSentimentDetail | null): {
  label: string
  detail: string
  tone: OverviewTone
} {
  if (!summary || summary.articleCount === 0 || summary.score == null) {
    return {
      label: 'Quiet',
      detail: 'No strong headline tone yet.',
      tone: 'default',
    }
  }

  if (summary.score >= 0.2) {
    return {
      label: 'Constructive',
      detail: `${summary.articleCount} recent articles · ${summary.positiveCount} positive`,
      tone: 'gain',
    }
  }

  if (summary.score <= -0.2) {
    return {
      label: 'Cautious',
      detail: `${summary.articleCount} recent articles · ${summary.negativeCount} negative`,
      tone: 'warning',
    }
  }

  return {
    label: 'Mixed',
    detail: `${summary.articleCount} recent articles across both sides.`,
    tone: 'default',
  }
}

// Mirrors backend account_valuation._quote_freshness "stale" tier.
const POSITIONING_STALE_MS_OPEN = 15 * 60 * 1000
const POSITIONING_STALE_MS_CLOSED = 24 * 60 * 60 * 1000

function isPositioningStale(
  lastUpdated: string | null | undefined,
  marketIsOpen: boolean,
): boolean {
  if (!lastUpdated) return false
  const ts = new Date(lastUpdated).getTime()
  if (Number.isNaN(ts)) return false
  const ageMs = Date.now() - ts
  return (
    ageMs >
    (marketIsOpen ? POSITIONING_STALE_MS_OPEN : POSITIONING_STALE_MS_CLOSED)
  )
}

export function describeMarketPositioning(
  indicator?: EnrichedIndicator | null,
  options: { marketIsOpen?: boolean } = {},
): { label: string; detail: string; tone: OverviewTone } {
  if (!indicator || indicator.value == null) {
    return {
      label: 'Unavailable',
      detail: 'Options positioning will return after refresh.',
      tone: 'default',
    }
  }

  if (
    isPositioningStale(indicator.lastUpdated, options.marketIsOpen ?? false)
  ) {
    return {
      label: 'Stale',
      detail:
        'Options positioning data is older than the freshness threshold for the current market session.',
      tone: 'warning',
    }
  }

  if (indicator.value >= 1.1) {
    return {
      label: 'Defensive',
      detail: 'Options traders are leaning cautious.',
      tone: 'warning',
    }
  }

  if (indicator.value < 0.8) {
    return {
      label: 'Optimistic',
      detail: 'Options traders are leaning risk-on.',
      tone: 'gain',
    }
  }

  return {
    label: 'Balanced',
    detail: 'Options positioning looks fairly balanced.',
    tone: 'default',
  }
}
