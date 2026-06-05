import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  currencyTooltipFormatter,
  formatMonthLabel,
  formatThousandsAxis,
  monthTooltipLabelFormatter,
  trustBadgeVariant,
  trustStatusLabel,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function SpendTrendCard({
  dashboard,
  spendTrustStatus,
  spendTrustDetail,
  spendTrustDegraded,
}: {
  dashboard: HouseholdFinanceDashboard
} & Pick<
  DecisionBoardData,
  'spendTrustStatus' | 'spendTrustDetail' | 'spendTrustDegraded'
>) {
  return (
    <SectionCard
      variant="surface"
      title="Monthly Spend Trend"
      actions={
        spendTrustDegraded ? (
          <InfoBadge
            label={trustStatusLabel(spendTrustStatus)}
            detail={spendTrustDetail}
            variant={trustBadgeVariant(spendTrustStatus)}
          />
        ) : undefined
      }
    >
      {dashboard.reports.monthlySpendTrend.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No monthly spend trend visible yet.
        </div>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={dashboard.reports.monthlySpendTrend}
              margin={{ top: 10, right: 12, left: 0, bottom: 8 }}
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
                width={40}
              />
              <Tooltip
                formatter={currencyTooltipFormatter}
                labelFormatter={monthTooltipLabelFormatter}
              />
              <Line
                type="monotone"
                dataKey="totalSpend"
                stroke="var(--color-chart-blue)"
                strokeWidth={2.5}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  )
}
