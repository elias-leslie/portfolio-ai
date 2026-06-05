'use client'

import type { Dispatch, SetStateAction } from 'react'
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import { formatCurrency } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import {
  currencyTooltipFormatter,
  formatMonthLabel,
  formatThousandsAxis,
  monthTooltipLabelFormatter,
} from './budget-helpers'

type TrendCategory = { category: string; key: string; color: string }

export interface CategoryTrendChartProps {
  timeframeLabel: string | undefined
  trendData: Array<Record<string, string | number>>
  trendCategories: TrendCategory[]
  chartCategories: TrendCategory[]
  isolatedSeries: string | null
  setIsolatedSeries: Dispatch<SetStateAction<string | null>>
  isolatedCap: number | null
  trendTopN: number
}

export function CategoryTrendChart({
  timeframeLabel,
  trendData,
  trendCategories,
  chartCategories,
  isolatedSeries,
  setIsolatedSeries,
  isolatedCap,
  trendTopN,
}: CategoryTrendChartProps) {
  return (
    <SectionCard
      variant="surface"
      title="Category trendlines"
      description={`Monthly spend by category for ${timeframeLabel ?? 'the selected window'}. Every visible budget category is plotted in one chart.`}
    >
      {trendData.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No category trendline is available for this window yet.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="h-80">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={240}
              minHeight={320}
              initialDimension={{ width: 720, height: 320 }}
            >
              <LineChart
                data={trendData}
                margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
              >
                <XAxis
                  dataKey="month"
                  tickFormatter={formatMonthLabel}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={{ stroke: 'var(--color-border)' }}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={formatThousandsAxis}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip
                  formatter={currencyTooltipFormatter}
                  labelFormatter={monthTooltipLabelFormatter}
                />
                {isolatedCap != null ? (
                  <ReferenceLine
                    y={isolatedCap}
                    stroke="var(--color-warning)"
                    strokeDasharray="4 4"
                    label={{
                      value: `Cap ${formatCurrency(isolatedCap, { decimals: 0 })}`,
                      position: 'insideTopRight',
                      fontSize: 10,
                      fill: 'var(--color-warning)',
                    }}
                  />
                ) : null}
                {chartCategories.map((entry) => (
                  <Line
                    key={entry.key}
                    type="monotone"
                    dataKey={entry.key}
                    name={entry.category}
                    stroke={entry.color}
                    strokeWidth={entry.category === 'Unknown' ? 3 : 2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex max-h-28 flex-wrap items-center gap-x-4 gap-y-2 overflow-auto text-xs text-text-muted">
            {!isolatedSeries && trendCategories.length > trendTopN ? (
              <span className="text-text-muted/70">
                Showing top {trendTopN} of {trendCategories.length} — click a
                category to isolate it:
              </span>
            ) : null}
            {isolatedSeries ? (
              <button
                type="button"
                onClick={() => setIsolatedSeries(null)}
                className="rounded-full border border-border/40 px-2 py-0.5 font-medium text-text hover:border-primary/40"
              >
                ← Show top {trendTopN}
              </button>
            ) : null}
            {trendCategories.map((entry) => (
              <button
                type="button"
                key={entry.key}
                onClick={() =>
                  setIsolatedSeries((current) =>
                    current === entry.category ? null : entry.category,
                  )
                }
                className={cn(
                  'inline-flex items-center gap-2 rounded-full px-2 py-0.5 transition-colors hover:text-text',
                  isolatedSeries === entry.category &&
                    'bg-surface-muted/40 text-text',
                )}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                {entry.category}
              </button>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
