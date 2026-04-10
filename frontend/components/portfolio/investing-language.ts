import type { NewsSentimentDetail } from '@/lib/api/watchlist'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import type { EnrichedIndicator, FearGreedScore } from '@/lib/api/market-types'

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
  const diversificationScore = analytics.diversificationScore?.score ?? null

  if (topHoldingPct >= 50) {
    return {
      label: 'Too concentrated',
      detail: `Top holding ${topHoldingPct.toFixed(1)}% of invested assets.`,
      tone: 'loss',
    }
  }

  if (topHoldingPct >= 35 || (diversificationScore != null && diversificationScore < 50)) {
    return {
      label: 'Needs review',
      detail: `Top holding ${topHoldingPct.toFixed(1)}% · diversification ${
        diversificationScore != null ? diversificationScore.toFixed(0) : '—'
      }`,
      tone: 'warning',
    }
  }

  if (diversificationScore != null && diversificationScore >= 75 && topHoldingPct < 20) {
    return {
      label: 'Well spread',
      detail: `${analytics.numSymbols} symbols across ${
        analytics.diversificationScore?.numSectors ?? 0
      } sectors.`,
      tone: 'gain',
    }
  }

  return {
    label: 'Balanced',
    detail:
      diversificationScore != null
        ? `Diversification ${diversificationScore.toFixed(0)} · top holding ${topHoldingPct.toFixed(1)}%`
        : `Top holding ${topHoldingPct.toFixed(1)}% of invested assets.`,
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

export function describeMarketMood(
  mood?: FearGreedScore | null,
): { label: string; detail: string; tone: OverviewTone } {
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
      detail: `Score ${score} · still defensive but ${trendDetail}.`,
      tone: 'loss',
    }
  }

  if (score <= 45) {
    return {
      label,
      detail: `Score ${score} · sentiment is cautious.`,
      tone: 'warning',
    }
  }

  if (score >= 70) {
    return {
      label,
      detail: `Score ${score} · risk appetite is elevated.`,
      tone: 'gain',
    }
  }

  return {
    label,
    detail: `Score ${score} · sentiment looks balanced.`,
    tone: 'default',
  }
}

export function describeVolatility(
  value?: number | null,
): { detail: string; tone: OverviewTone } {
  if (value == null) {
    return {
      detail: 'Volatility data is still loading.',
      tone: 'default',
    }
  }

  if (value >= 30) {
    return {
      detail: 'Markets are swinging hard right now.',
      tone: 'loss',
    }
  }

  if (value >= 20) {
    return {
      detail: 'Volatility is elevated.',
      tone: 'warning',
    }
  }

  if (value >= 15) {
    return {
      detail: 'Volatility is in a normal range.',
      tone: 'default',
    }
  }

  return {
    detail: 'Markets look calm.',
    tone: 'gain',
  }
}

export function describeTenYearRate(
  value?: number | null,
): { detail: string; tone: OverviewTone } {
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

export function describeNewsTone(
  summary?: NewsSentimentDetail | null,
): {
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

export function describeMarketPositioning(
  indicator?: EnrichedIndicator | null,
): { label: string; detail: string; tone: OverviewTone } {
  if (!indicator || indicator.value == null) {
    return {
      label: 'Unavailable',
      detail: 'Options positioning will return after refresh.',
      tone: 'default',
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
