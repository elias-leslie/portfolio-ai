import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  currencyTooltipFormatter,
  formatThousandsAxis,
  trendIncludesCurrentPartialMonth,
  trustBadgeVariant,
  trustStatusLabel,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function WhereMoneyWentCard({
  dashboard,
  categoryData,
  selectedCategory,
  setSelectedCategory,
  selectedTransactions,
  spendTrustStatus,
  spendTrustDetail,
  spendTrustDegraded,
}: {
  dashboard: HouseholdFinanceDashboard
} & Pick<
  DecisionBoardData,
  | 'categoryData'
  | 'selectedCategory'
  | 'setSelectedCategory'
  | 'selectedTransactions'
  | 'spendTrustStatus'
  | 'spendTrustDetail'
  | 'spendTrustDegraded'
>) {
  const hasPartialMonth = trendIncludesCurrentPartialMonth(
    dashboard.reports.monthlySpendTrend,
  )
  return (
    <SectionCard
      variant="surface"
      title="Where Money Went"
      description={`Top categories over the past ${dashboard.reports.executive.coverageMonths} month${
        dashboard.reports.executive.coverageMonths === 1 ? '' : 's'
      }${hasPartialMonth ? ' (current month partial)' : ''} — bars are window totals.`}
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
      {categoryData.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No category split visible yet.
        </div>
      ) : (
        <div className="space-y-5">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={categoryData}
                layout="vertical"
                margin={{ top: 10, right: 12, left: 12, bottom: 8 }}
              >
                <XAxis
                  type="number"
                  tickFormatter={formatThousandsAxis}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="category"
                  width={90}
                  tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip formatter={currencyTooltipFormatter} />
                <Bar
                  dataKey="totalSpend"
                  radius={[0, 10, 10, 0]}
                  onClick={(_, index) => {
                    const entry = categoryData[index]
                    if (entry?.category) {
                      setSelectedCategory(entry.category)
                    }
                  }}
                >
                  {categoryData.map((entry) => (
                    <Cell
                      key={entry.category}
                      fill={
                        entry.category === selectedCategory
                          ? 'var(--color-chart-orange)'
                          : 'var(--color-chart-cyan)'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text">
                  {selectedCategory ?? 'Recent category'}
                </p>
                <p className="text-xs text-text-muted">
                  {selectedTransactions.length > 0
                    ? 'Recent transactions behind this category.'
                    : 'No recent transactions are visible for this category yet.'}
                </p>
              </div>
              {selectedCategory ? (
                <button
                  type="button"
                  onClick={() => setSelectedCategory(null)}
                  className="text-xs font-medium text-text-muted transition-colors hover:text-text"
                >
                  Clear
                </button>
              ) : null}
            </div>
            <div className="mt-4 space-y-2">
              {(selectedCategory
                ? selectedTransactions
                : dashboard.reports.recentTransactions
              )
                .slice(0, 6)
                .map((transaction) => (
                  <div
                    key={`${transaction.date}-${transaction.description}-${transaction.amount}`}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border/30 bg-surface/60 px-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium text-text">
                        {transaction.merchant}
                      </p>
                      <p className="text-xs text-text-muted">
                        {transaction.date} · {transaction.category}
                      </p>
                    </div>
                    <span className="text-sm font-semibold tabular-nums text-text">
                      {formatCurrencyWhole(transaction.amount)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
