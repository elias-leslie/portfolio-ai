'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  useFearGreedHistory,
  useNewsSentimentHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { EventLegend, EventTimeline } from './EventTimeline'
import { MarketPanelMessage } from './MarketPanelMessage'
import { SentimentChart } from './SentimentChart'
import { normalizeNewsSentiment } from './SentimentTooltip'
import {
  DEFAULT_MARKET_TIMEFRAME,
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'
import {
  ImpactCard,
  type ImpactMetric,
  type ImpactTone,
  TrendImpactPanel,
} from './TrendImpactPanel'

function formatSignedPct(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) return '-'
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`
}

function buildMoodImpact({
  score,
  scoreChange,
  newsSentiment,
  putCallRatio,
}: {
  score: number | null
  scoreChange: number | null
  newsSentiment: number | null | undefined
  putCallRatio: number | null | undefined
}): {
  tone: ImpactTone
  title: string
  summary: string
  metrics: ImpactMetric[]
} {
  if (score == null || !Number.isFinite(score)) {
    return {
      tone: 'neutral',
      title: 'Mood unavailable',
      summary:
        'Sentiment inputs are not available, so this panel should not drive risk decisions.',
      metrics: [],
    }
  }

  const tone: ImpactTone =
    score >= 75
      ? 'warning'
      : score >= 55
        ? 'positive'
        : score >= 35
          ? 'neutral'
          : 'negative'
  const title =
    score >= 75
      ? 'Risk appetite elevated'
      : score >= 55
        ? 'Mood supports risk'
        : score >= 35
          ? 'Mood is mixed'
          : 'Fear is pressuring risk'
  const trendText =
    scoreChange == null
      ? 'trend unavailable'
      : `${scoreChange >= 0 ? 'up' : 'down'} ${Math.abs(scoreChange).toFixed(1)} pts over the window`
  const optionsText =
    putCallRatio == null
      ? 'options hedge data missing'
      : putCallRatio < 0.7
        ? 'low put/call shows complacency risk'
        : putCallRatio > 1.1
          ? 'elevated put/call shows hedging/fear'
          : 'put/call is balanced'

  return {
    tone,
    title,
    summary: `Fear/Greed is ${score.toFixed(0)} and ${trendText}; ${optionsText}. Treat this as the market's risk-appetite layer, not a standalone buy/sell signal.`,
    metrics: [
      {
        label: 'Fear/Greed',
        value: score.toFixed(0),
        detail: trendText,
        tone,
      },
      {
        label: 'News',
        value: formatSignedPct(newsSentiment),
        detail: 'article tone',
        tone:
          newsSentiment == null
            ? 'neutral'
            : newsSentiment > 0.05
              ? 'positive'
              : newsSentiment < -0.05
                ? 'negative'
                : 'neutral',
      },
      {
        label: 'Put/Call',
        value: putCallRatio?.toFixed(2) ?? '-',
        detail: optionsText,
        tone:
          putCallRatio == null
            ? 'neutral'
            : putCallRatio < 0.7
              ? 'warning'
              : putCallRatio > 1.1
                ? 'negative'
                : 'neutral',
      },
    ],
  }
}

export function SentimentTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const [impactCollapsed, setImpactCollapsed] = useState(false)
  const days = timeframeToDays(timeframe)

  const {
    data: fearGreedData,
    isLoading: fgLoading,
    error: fgError,
  } = useFearGreedHistory(days)
  const { data: newsData, isLoading: newsLoading } = useNewsSentimentHistory(
    days,
    'daily',
  )
  // Merge Fear & Greed, News Sentiment, and P/C Ratio data by date
  const chartData = useMemo(() => {
    if (!fearGreedData?.dates?.length) return []

    const newsMap = new Map<string, number>()
    if (newsData?.dates?.length) {
      newsData.dates.forEach((date, idx) => {
        newsMap.set(date.split('T')[0], newsData.scores[idx])
      })
    }

    return fearGreedData.dates.map((date, idx) => {
      const dateKey = date.split('T')[0]
      const newsScore = newsMap.get(dateKey)
      const pcRatio = fearGreedData.putCallRatios?.[idx]
      return {
        date,
        score: fearGreedData.scores[idx],
        label: fearGreedData.labels[idx],
        source: fearGreedData.sources?.[idx] ?? 'daily_close',
        newsSentiment:
          newsScore !== undefined ? normalizeNewsSentiment(newsScore) : null,
        newsRaw: newsScore,
        pcRatioScaled:
          pcRatio != null
            ? Math.min(100, Math.max(0, (pcRatio - 0.5) * 100))
            : null,
        pcRatioRaw: pcRatio,
      }
    })
  }, [fearGreedData, newsData])

  const isLoading = fgLoading || newsLoading

  const last = chartData.length > 0 ? chartData[chartData.length - 1] : null
  const first = chartData.length > 0 ? chartData[0] : null
  const moodImpact = buildMoodImpact({
    score: last?.score ?? null,
    scoreChange:
      last?.score != null && first?.score != null
        ? last.score - first.score
        : null,
    newsSentiment: last?.newsRaw ?? null,
    putCallRatio: last?.pcRatioRaw ?? null,
  })
  const formatXAxis = (date: string) => formatChartDate(date, days)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (fgError || !fearGreedData?.dates?.length) {
    return (
      <MarketPanelMessage
        message="Unable to load market sentiment history right now."
        className="min-h-48"
      />
    )
  }

  return (
    <TrendImpactPanel
      title="Market Mood"
      controls={<TimeframeSelector value={timeframe} onChange={setTimeframe} />}
      collapsed={impactCollapsed}
      chart={
        <div className="space-y-2">
          <div className="relative h-44">
            <SentimentChart data={chartData} formatXAxis={formatXAxis} />
            <EventTimeline
              days={days}
              className="left-[30px] right-[10px] top-[10px] bottom-[25px]"
            />
          </div>
          <EventLegend />
        </div>
      }
      impact={
        <ImpactCard
          eyebrow="Impact"
          title={moodImpact.title}
          summary={moodImpact.summary}
          tone={moodImpact.tone}
          metrics={moodImpact.metrics}
          collapsed={impactCollapsed}
          onToggle={() => setImpactCollapsed((value) => !value)}
          footer={
            last?.date
              ? `Latest ${last.source === 'live_proxy' ? 'live mood' : 'daily close'} through ${last.date.split('T')[0]}${
                  fearGreedData.latestAsOf
                    ? ` · as of ${fearGreedData.latestAsOf}`
                    : ''
                }`
              : null
          }
        />
      }
    />
  )
}
