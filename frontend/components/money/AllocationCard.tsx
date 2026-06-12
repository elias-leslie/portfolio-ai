import Link from 'next/link'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  allocationColors,
  currencyTooltipFormatter,
  trustBadgeVariant,
  trustStatusLabel,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function AllocationCard({
  dashboard,
  allocationData,
  selectedAssetGroup,
  setSelectedAssetGroup,
  selectedAccounts,
  netWorthTrustStatus,
}: {
  dashboard: HouseholdFinanceDashboard
} & Pick<
  DecisionBoardData,
  | 'allocationData'
  | 'selectedAssetGroup'
  | 'setSelectedAssetGroup'
  | 'selectedAccounts'
  | 'netWorthTrustStatus'
>) {
  return (
    <SectionCard
      variant="surface"
      title="Account Allocation"
      actions={
        netWorthTrustStatus !== 'current' ? (
          <InfoBadge
            label={trustStatusLabel(netWorthTrustStatus)}
            detail={dashboard.overview.netWorthDetail}
            variant={trustBadgeVariant(netWorthTrustStatus)}
          />
        ) : undefined
      }
    >
      {allocationData.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No asset allocation visible yet.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={allocationData}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={58}
                  outerRadius={92}
                  paddingAngle={2}
                  onClick={(_, index) => {
                    const entry = allocationData[index]
                    if (entry?.assetGroup) {
                      setSelectedAssetGroup(entry.assetGroup)
                    }
                  }}
                >
                  {allocationData.map((entry, index) => (
                    <Cell
                      key={entry.assetGroup}
                      fill={allocationColors[index % allocationColors.length]}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={currencyTooltipFormatter} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-3">
            {allocationData.map((entry, index) => {
              const isActive = entry.assetGroup === selectedAssetGroup
              return (
                <button
                  key={entry.assetGroup}
                  type="button"
                  onClick={() => setSelectedAssetGroup(entry.assetGroup)}
                  className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors ${
                    isActive
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-border/40 bg-surface-muted/15 hover:border-border/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{
                        backgroundColor:
                          allocationColors[index % allocationColors.length],
                      }}
                    />
                    <div>
                      <p className="text-sm font-semibold text-text">
                        {entry.label}
                      </p>
                      <p className="text-xs text-text-muted">
                        {
                          dashboard.accounts.filter(
                            (account) =>
                              account.assetGroup === entry.assetGroup,
                          ).length
                        }{' '}
                        account
                        {dashboard.accounts.filter(
                          (account) => account.assetGroup === entry.assetGroup,
                        ).length === 1
                          ? ''
                          : 's'}
                      </p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold tabular-nums text-text">
                    {formatCurrencyWhole(entry.value)}
                  </span>
                </button>
              )
            })}
            {selectedAccounts.length > 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Drill-down
                </p>
                <div className="mt-3 space-y-2">
                  {selectedAccounts.slice(0, 4).map((account) => (
                    <div
                      key={account.id}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <div>
                        <p className="font-medium text-text">{account.label}</p>
                        <p className="text-xs text-text-muted">
                          {account.freshnessLabel} · {account.matchStatus}
                        </p>
                      </div>
                      <span className="tabular-nums text-text">
                        {formatCurrencyWhole(account.currentValue)}
                      </span>
                    </div>
                  ))}
                </div>
                {selectedAccounts.length > 4 ? (
                  <p className="mt-2 text-xs text-text-muted">
                    Showing 4 of {selectedAccounts.length} accounts
                  </p>
                ) : null}
                <div className="mt-4">
                  <Button asChild size="sm" variant="outline">
                    <Link href="/money?tab=accounts">Open accounts</Link>
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
