'use client'

import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import type { RotationPlanView } from '@/lib/api/cards'
import { formatCurrencyWhole } from '@/lib/formatters'

function currencyTickFormatter(value: number) {
  return `$${Math.round(value / 1000)}k`
}

export function RotationValueChart({
  plan,
}: {
  plan: RotationPlanView | undefined
}) {
  const data = plan?.cumulativeValue ?? []

  return (
    <SectionCard
      variant="surface"
      title="Rotation vs single-card value"
      description="Cumulative projected reward value of the rotation plan against keeping the best single card."
    >
      {data.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No rotation projection is available yet.
        </div>
      ) : (
        <div className="h-72">
          <ResponsiveContainer
            width="100%"
            height="100%"
            minWidth={240}
            minHeight={288}
            initialDimension={{ width: 720, height: 288 }}
          >
            <LineChart
              data={data}
              margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
            >
              <XAxis
                dataKey="quarterLabel"
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                axisLine={{ stroke: 'var(--color-border)' }}
                tickLine={false}
              />
              <YAxis
                tickFormatter={currencyTickFormatter}
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                formatter={(value) => formatCurrencyWhole(Number(value ?? 0))}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="rotationCumulativeValue"
                name="Rotation plan"
                stroke="var(--color-chart-1)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="baselineCumulativeValue"
                name={`Single card${plan?.baselineProductSlug ? ` (${plan.baselineProductSlug})` : ''}`}
                stroke="var(--color-chart-3)"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  )
}
