'use client'

import { checkDataFreshness, formatDate } from '@/lib/utils'
import { EventLegend } from './EventTimeline'

export interface SentimentSummaryData {
  currentScore: number | null
  latestNewsSentiment: number | null | undefined
  latestPcRatio: number | null | undefined
  latestDate: string | null
  latestSource?: 'daily_close' | 'live_proxy'
  latestAsOf?: string | null
  expectedDataDate?: string
}

function formatLiveAsOf(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
  })
}

export function SentimentLegendSummary({
  currentScore,
  latestNewsSentiment,
  latestPcRatio,
  latestDate,
  latestSource = 'daily_close',
  latestAsOf,
  expectedDataDate,
}: SentimentSummaryData) {
  const dataDate = latestDate?.split('T')[0]
  const isLiveProxy = latestSource === 'live_proxy'
  const liveAsOf = formatLiveAsOf(latestAsOf)
  const freshness =
    dataDate && !isLiveProxy
      ? checkDataFreshness(dataDate, expectedDataDate)
      : null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-chart-purple rounded"></span>
            <span>
              {isLiveProxy ? 'Live Mood' : 'Fear & Greed'}:{' '}
              <span className="font-semibold text-text">{currentScore}</span>
            </span>
          </span>
          {latestNewsSentiment !== null &&
            latestNewsSentiment !== undefined && (
              <span className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-chart-cyan rounded"></span>
                <span>
                  News:{' '}
                  <span className="font-semibold text-text">
                    {latestNewsSentiment > 0 ? '+' : ''}
                    {(latestNewsSentiment * 100).toFixed(0)}%
                  </span>
                </span>
              </span>
            )}
          {latestPcRatio !== null && latestPcRatio !== undefined && (
            <span className="flex items-center gap-1">
              <span className="w-3 border-t-2 border-dashed border-chart-orange"></span>
              <span>
                P/C:{' '}
                <span className="font-semibold text-text">
                  {latestPcRatio.toFixed(2)}
                </span>
              </span>
            </span>
          )}
        </div>
        {isLiveProxy ? (
          <span className="text-[10px]">
            Live mood as of{' '}
            {liveAsOf ??
              (dataDate ? formatDate(dataDate, false) : 'latest quote')}{' '}
            ET
          </span>
        ) : dataDate && freshness ? (
          <span className="text-[10px]" title={freshness.tooltip}>
            Latest daily sentiment through {formatDate(dataDate, false)}{' '}
            {freshness.indicator}
          </span>
        ) : null}
      </div>
      {/* Event legend */}
      <EventLegend />
    </div>
  )
}
