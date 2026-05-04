'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  useFearGreedHistory,
  useMarketStatus,
  useNewsSentimentHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { EventTimeline } from './EventTimeline'
import { MarketPanelMessage } from './MarketPanelMessage'
import { SentimentChart } from './SentimentChart'
import { SentimentLegendSummary } from './SentimentLegendSummary'
import { normalizeNewsSentiment } from './SentimentTooltip'
import {
  calculateTickInterval,
  DEFAULT_MARKET_TIMEFRAME,
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'

export function SentimentTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
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
  const { data: marketStatus } = useMarketStatus()

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
  const formatXAxis = (date: string) => formatChartDate(date, days)
  const tickInterval = useMemo(
    () => calculateTickInterval(chartData.length),
    [chartData.length],
  )

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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-lg tracking-tight text-text">
          Daily Market Mood
        </h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-40 relative">
        <SentimentChart
          data={chartData}
          formatXAxis={formatXAxis}
          tickInterval={tickInterval}
        />
        <EventTimeline
          days={days}
          className="left-[30px] right-[10px] top-[10px] bottom-[25px]"
        />
      </div>

      <SentimentLegendSummary
        currentScore={last?.score ?? null}
        latestNewsSentiment={last?.newsRaw ?? null}
        latestPcRatio={last?.pcRatioRaw ?? null}
        latestDate={last?.date ?? null}
        expectedDataDate={marketStatus?.expectedDataDate}
      />
    </div>
  )
}
