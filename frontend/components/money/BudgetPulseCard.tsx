import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  comparisonBadgeVariant,
  formatMonthLabel,
  paceBadgeVariant,
  signedCurrency,
  trustBadgeVariant,
  trustCardValue,
  trustStatusLabel,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function BudgetPulseCard({
  dashboard,
  spendTrustStatus,
  spendTrustDetail,
  spendTrustDegraded,
  monthComparison,
  watchItems,
}: {
  dashboard: HouseholdFinanceDashboard
} & Pick<
  DecisionBoardData,
  | 'spendTrustStatus'
  | 'spendTrustDetail'
  | 'spendTrustDegraded'
  | 'monthComparison'
  | 'watchItems'
>) {
  return (
    <SectionCard
      variant="surface"
      title="Budget Pulse"
      description={dashboard.budgetSnapshot.summary}
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
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">Month to date</p>
            <Badge
              variant={paceBadgeVariant(dashboard.budgetSnapshot.paceStatus)}
            >
              {formatEnumLabel(dashboard.budgetSnapshot.paceStatus)}
            </Badge>
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {trustCardValue(
              spendTrustStatus,
              formatCurrencyWhole(dashboard.budgetSnapshot.monthToDateSpend),
            )}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {`Plan: ${formatCurrencyWhole(
              dashboard.budgetSnapshot.monthToDatePlan,
              { nullDisplay: 'Not set' },
            )} · ${dashboard.budgetSnapshot.monthlyPlanSourceLabel}`}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-muted">
            {dashboard.budgetSnapshot.paceDetail}
          </p>
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">
              Discretionary headroom
            </p>
            {dashboard.budgetSnapshot.discretionaryHeadroom != null ? (
              <Badge
                variant={
                  dashboard.budgetSnapshot.discretionaryHeadroom >= 0
                    ? 'success'
                    : 'warning'
                }
              >
                {dashboard.budgetSnapshot.discretionaryHeadroom >= 0
                  ? 'Inside cap'
                  : 'Above cap'}
              </Badge>
            ) : null}
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {trustCardValue(
              spendTrustStatus,
              signedCurrency(dashboard.budgetSnapshot.discretionaryHeadroom),
            )}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {`Monthly plan: ${formatCurrencyWhole(
              dashboard.budgetSnapshot.monthlyPlanTotal,
              { nullDisplay: 'Not set' },
            )} · ${dashboard.budgetSnapshot.monthlyPlanSourceLabel}`}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-muted">
            {`Remaining after plan: ${formatCurrencyWhole(
              dashboard.budgetSnapshot.remainingCashAfterPlan,
              { nullDisplay: 'Not available' },
            )}`}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">
              Latest full-month change
            </p>
            {!spendTrustDegraded && monthComparison ? (
              <Badge variant={comparisonBadgeVariant(monthComparison.change)}>
                {formatPercent(monthComparison.changePct, {
                  decimals: 0,
                  sign: true,
                  nullDisplay: 'New',
                })}
              </Badge>
            ) : null}
          </div>
          {spendTrustDegraded ? (
            <>
              <p className="mt-3 text-2xl font-semibold text-text">
                {monthComparison
                  ? trustCardValue(
                      spendTrustStatus,
                      signedCurrency(monthComparison.change),
                    )
                  : trustCardValue(spendTrustStatus, '—')}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {monthComparison
                  ? `${formatMonthLabel(monthComparison.latestMonth)} versus ${formatMonthLabel(
                      monthComparison.previousMonth,
                    )}.`
                  : 'No full-month comparison visible yet.'}
              </p>
            </>
          ) : monthComparison ? (
            <>
              <p className="mt-3 text-2xl font-semibold text-text">
                {signedCurrency(monthComparison.change)}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {formatMonthLabel(monthComparison.latestMonth)} versus{' '}
                {formatMonthLabel(monthComparison.previousMonth)}
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-text-muted">
              No full-month comparison visible yet.
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-sm font-semibold text-text">Watch right now</p>
          <div className="mt-3 space-y-2">
            {watchItems.length === 0 ? (
              <p className="text-sm text-text-muted">
                No near-term budget risk is visible right now.
              </p>
            ) : (
              watchItems.map((item) => (
                <p key={item} className="text-sm text-text-muted">
                  {item}
                </p>
              ))
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
