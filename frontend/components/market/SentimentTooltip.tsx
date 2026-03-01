'use client'

// Convert news sentiment (-1 to +1) to 0-100 scale for chart alignment
export function normalizeNewsSentiment(score: number): number {
  return ((score + 1) / 2) * 100
}

// Custom tooltip component - extracted to avoid recreation during render
export interface TooltipPayload {
  value: number
  dataKey: string
  payload: {
    newsRaw?: number
    label?: string
    pcRatioRaw?: number | null
  }
}

export function SentimentTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  const dateStr =
    typeof label === 'string'
      ? new Date(`${label}T12:00:00`).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })
      : ''
  const fgValue = payload.find((p) => p.dataKey === 'score')
  const newsValue = payload.find((p) => p.dataKey === 'newsSentiment')
  const pcValue = payload.find((p) => p.dataKey === 'pcRatioScaled')

  return (
    <div className="bg-surface border border-border rounded-lg p-2 text-xs shadow-lg">
      <div className="font-medium mb-1">{dateStr}</div>
      {fgValue && (
        <div className="flex justify-between gap-4">
          <span className="text-chart-purple">Fear &amp; Greed:</span>
          <span className="font-semibold">
            {fgValue.value} ({fgValue.payload.label})
          </span>
        </div>
      )}
      {newsValue &&
        newsValue.payload.newsRaw !== null &&
        newsValue.payload.newsRaw !== undefined && (
          <div className="flex justify-between gap-4">
            <span className="text-chart-cyan">News Sentiment:</span>
            <span className="font-semibold">
              {newsValue.payload.newsRaw > 0 ? '+' : ''}
              {(newsValue.payload.newsRaw * 100).toFixed(0)}%
            </span>
          </div>
        )}
      {pcValue &&
        pcValue.payload.pcRatioRaw !== null &&
        pcValue.payload.pcRatioRaw !== undefined && (
          <div className="flex justify-between gap-4">
            <span className="text-chart-orange">Put/Call Ratio:</span>
            <span className="font-semibold">
              {pcValue.payload.pcRatioRaw.toFixed(2)}
            </span>
          </div>
        )}
    </div>
  )
}
