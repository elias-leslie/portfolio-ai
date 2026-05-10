'use client'

import { useId } from 'react'
import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SentimentTooltip } from './SentimentTooltip'

export interface SentimentChartDataPoint {
  date: string
  score: number
  label: string
  source: 'daily_close' | 'live_proxy'
  newsSentiment: number | null
  newsRaw: number | null | undefined
  pcRatioScaled: number | null
  pcRatioRaw: number | null | undefined
}

interface SentimentChartProps {
  data: SentimentChartDataPoint[]
  formatXAxis: (date: string) => string
}

export function SentimentChart({ data, formatXAxis }: SentimentChartProps) {
  const id = useId()
  const gradientId = `${id}-sentimentGradient`
  return (
    <ResponsiveContainer width="100%" height={160}>
      <ComposedChart
        data={data}
        margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
      >
        <ReferenceArea
          y1={0}
          y2={25}
          fill="var(--color-sentiment-fear)"
          fillOpacity={0.1}
        />
        <ReferenceArea
          y1={25}
          y2={45}
          fill="var(--color-sentiment-caution)"
          fillOpacity={0.1}
        />
        <ReferenceArea
          y1={45}
          y2={55}
          fill="var(--color-sentiment-neutral)"
          fillOpacity={0.1}
        />
        <ReferenceArea
          y1={55}
          y2={75}
          fill="var(--color-sentiment-optimism)"
          fillOpacity={0.1}
        />
        <ReferenceArea
          y1={75}
          y2={100}
          fill="var(--color-sentiment-greed)"
          fillOpacity={0.1}
        />
        <XAxis
          dataKey="date"
          tickFormatter={formatXAxis}
          tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
          axisLine={{ stroke: 'var(--color-border)' }}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={36}
        />
        <YAxis
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
          axisLine={false}
          tickLine={false}
          width={30}
        />
        <ReferenceLine
          y={50}
          stroke="var(--color-border)"
          strokeDasharray="3 3"
        />
        <Tooltip content={<SentimentTooltip />} />
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="5%"
              stopColor="var(--color-chart-purple)"
              stopOpacity={0.3}
            />
            <stop
              offset="95%"
              stopColor="var(--color-chart-purple)"
              stopOpacity={0}
            />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="score"
          stroke="var(--color-chart-purple)"
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          name="Market Mood"
        />
        <Line
          type="monotone"
          dataKey="newsSentiment"
          stroke="var(--color-chart-cyan)"
          strokeWidth={2}
          dot={false}
          connectNulls
          name="News Sentiment"
        />
        <Line
          type="monotone"
          dataKey="pcRatioScaled"
          stroke="var(--color-chart-orange)"
          strokeWidth={1.5}
          strokeDasharray="4 2"
          dot={false}
          connectNulls
          name="Put/Call Ratio"
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
