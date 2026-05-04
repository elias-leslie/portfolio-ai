'use client'

import { checkDataFreshness, formatDate } from '@/lib/utils'
import { EventLegend } from './EventTimeline'

export interface SentimentSummaryData {
  currentScore: number | null
  latestNewsSentiment: number | null | undefined
  latestPcRatio: number | null | undefined
  latestDate: string | null
  expectedDataDate?: string
}

export function SentimentLegendSummary({
  currentScore,
  latestNewsSentiment,
  latestPcRatio,
  latestDate,
  expectedDataDate,
}: SentimentSummaryData) {
  const dataDate = latestDate?.split('T')[0]
  const freshness = dataDate
    ? checkDataFreshness(dataDate, expectedDataDate)
    : null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-chart-purple rounded"></span>
            <span>
              Fear &amp; Greed:{' '}
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
        {dataDate && freshness && (
          <span className="text-[10px]" title={freshness.tooltip}>
            Latest daily sentiment through {formatDate(dataDate, false)}{' '}
            {freshness.indicator}
          </span>
        )}
      </div>
      {/* Event legend */}
      <EventLegend />
    </div>
  )
}
