import Link from 'next/link'
import type { ReactNode } from 'react'
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
  decisionBadgeVariant,
  formatCategoryPreview,
  signedCurrency,
  trustBadgeVariant,
  trustCardValue,
  trustStatusLabel,
} from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function DecisionBoard({
  dashboard,
  description,
  spendTrustStatus,
  spendTrustDetail,
  spendTrustDegraded,
  spendTrustUnavailable,
  whyShortStatus,
  whyShortSummary,
  whyShortDrivers,
  planIsPartial,
  monthGap,
  safeSpendStatus,
  safeSpendSummary,
  safeSpendBindingLabel,
  safeSpendRepairItems,
  weekendSpendAllowance,
  operatingCushion,
  dueSoonTotal,
  needsAmount,
  wantsAmount,
  needsShare,
  wantsShare,
  needCategories,
  wantCategories,
  saveNowLines,
  priceInsights,
  merchantHighlights,
}: {
  dashboard: HouseholdFinanceDashboard
  description: ReactNode
} & Pick<
  DecisionBoardData,
  | 'spendTrustStatus'
  | 'spendTrustDetail'
  | 'spendTrustDegraded'
  | 'spendTrustUnavailable'
  | 'whyShortStatus'
  | 'whyShortSummary'
  | 'whyShortDrivers'
  | 'planIsPartial'
  | 'monthGap'
  | 'safeSpendStatus'
  | 'safeSpendSummary'
  | 'safeSpendBindingLabel'
  | 'safeSpendRepairItems'
  | 'weekendSpendAllowance'
  | 'operatingCushion'
  | 'dueSoonTotal'
  | 'needsAmount'
  | 'wantsAmount'
  | 'needsShare'
  | 'wantsShare'
  | 'needCategories'
  | 'wantCategories'
  | 'saveNowLines'
  | 'priceInsights'
  | 'merchantHighlights'
>) {
  return (
    <SectionCard
      variant="surface"
      title="Decision Board"
      description={description}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">Budget Pace</p>
            <div className="flex flex-wrap items-center gap-2">
              {spendTrustDegraded ? (
                <InfoBadge
                  label={trustStatusLabel(spendTrustStatus)}
                  detail={spendTrustDetail}
                  variant={trustBadgeVariant(spendTrustStatus)}
                />
              ) : null}
              <Badge variant={decisionBadgeVariant(whyShortStatus)}>
                {formatEnumLabel(whyShortStatus)}
              </Badge>
            </div>
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {spendTrustUnavailable
              ? trustCardValue(spendTrustStatus, signedCurrency(monthGap))
              : planIsPartial
                ? formatCurrencyWhole(dashboard.budgetSnapshot.monthToDateSpend)
                : spendTrustDegraded
                  ? trustCardValue(spendTrustStatus, signedCurrency(monthGap))
                  : signedCurrency(monthGap)}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {planIsPartial
              ? 'Spent so far this month. Plan only covers part of it, so this is not a pace verdict.'
              : dashboard.budgetSnapshot.monthToDatePlan != null
                ? 'Current month pace versus plan.'
                : 'Waiting on a full monthly plan for a cleaner answer.'}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-muted">
            {whyShortSummary}
          </p>
          <div className="mt-3 space-y-2">
            {!spendTrustDegraded
              ? whyShortDrivers.slice(0, 3).map((driver) => (
                  <p key={driver} className="text-xs text-text-muted">
                    {driver}
                  </p>
                ))
              : null}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border/30 pt-3 text-xs">
            {planIsPartial ? (
              <Link
                href="/money?tab=spending"
                className="font-medium text-primary transition-colors hover:text-primary/80"
              >
                Complete your plan →
              </Link>
            ) : null}
            <Link
              href="/money?tab=spending"
              className="text-text-muted transition-colors hover:text-text"
            >
              Open Budget
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">Safe to Spend</p>
            <div className="flex flex-wrap items-center gap-2">
              {spendTrustDegraded ? (
                <InfoBadge
                  label={trustStatusLabel(spendTrustStatus)}
                  detail={spendTrustDetail}
                  variant={trustBadgeVariant(spendTrustStatus)}
                />
              ) : null}
              <Badge variant={decisionBadgeVariant(safeSpendStatus)}>
                {formatEnumLabel(safeSpendStatus)}
              </Badge>
            </div>
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {trustCardValue(
              spendTrustStatus,
              formatCurrencyWhole(weekendSpendAllowance, {
                nullDisplay: 'Review',
              }),
              'Review',
            )}
          </p>
          <p className="mt-1 text-sm text-text-muted">{safeSpendSummary}</p>
          <div className="mt-3 space-y-2 text-xs text-text-muted">
            <p>
              Operating cushion: {formatCurrencyWhole(operatingCushion)}
              {dashboard.profile.monthlyEssentialTarget != null
                ? ' (essentials target, not actual)'
                : ''}
            </p>
            <p>Due in 14 days: {formatCurrencyWhole(dueSoonTotal)}</p>
            <p>
              Remaining after plan:{' '}
              {formatCurrencyWhole(
                dashboard.budgetSnapshot.remainingCashAfterPlan,
                { nullDisplay: 'Not set' },
              )}
            </p>
            <p>
              Monthly plan source:{' '}
              {dashboard.budgetSnapshot.monthlyPlanSourceLabel}
            </p>
            {safeSpendBindingLabel ? (
              <p className="text-text-muted/80">
                Limited by {safeSpendBindingLabel}.
              </p>
            ) : null}
          </div>
          {spendTrustDegraded && safeSpendRepairItems.length > 0 ? (
            <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                Refresh blockers
              </p>
              {safeSpendRepairItems.map((item) => (
                <Link
                  key={item.id}
                  href={item.actionHref ?? '/money?tab=accounts'}
                  className="block rounded-xl border border-border/40 bg-background/30 px-3 py-2 text-xs text-text-muted transition-colors hover:border-primary/40 hover:text-text"
                >
                  <span className="font-medium text-text">{item.title}</span>
                  <span className="mt-1 block">{item.detail}</span>
                </Link>
              ))}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">Want vs need</p>
            <div className="flex flex-wrap items-center gap-2">
              {spendTrustDegraded ? (
                <InfoBadge
                  label={trustStatusLabel(spendTrustStatus)}
                  detail={spendTrustDetail}
                  variant={trustBadgeVariant(spendTrustStatus)}
                />
              ) : null}
              <Badge
                variant={decisionBadgeVariant(
                  spendTrustDegraded
                    ? 'mixed'
                    : wantsAmount > needsAmount
                      ? 'wants_leading'
                      : 'needs_leading',
                )}
              >
                {!spendTrustDegraded && wantsShare != null
                  ? wantsAmount > needsAmount
                    ? `Wants leading ${formatPercent(wantsShare, { decimals: 0 })}`
                    : `Needs leading ${formatPercent(needsShare ?? 0, { decimals: 0 })}`
                  : 'Split'}
              </Badge>
            </div>
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {trustCardValue(
              spendTrustStatus,
              `${formatCurrencyWhole(needsAmount)} / ${formatCurrencyWhole(wantsAmount)}`,
              'Awaiting split',
            )}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {!spendTrustDegraded &&
            wantsShare != null &&
            wantsAmount > needsAmount
              ? `Wants are outspending needs (${formatPercent(wantsShare, { decimals: 0 })} vs ${formatPercent(needsShare ?? 0, { decimals: 0 })}).`
              : 'Needs versus wants from the recent monthly average.'}
          </p>
          <div className="mt-3 space-y-2 text-xs text-text-muted">
            <p>Needs: {formatCategoryPreview(needCategories)}</p>
            <p>Wants: {formatCategoryPreview(wantCategories)}</p>
            <p>
              Wants share:{' '}
              {formatPercent(wantsShare, {
                decimals: 0,
                nullDisplay: '—',
              })}
            </p>
          </div>
          <div className="mt-3 border-t border-border/30 pt-3 text-xs">
            <Link
              href="/money?tab=spending"
              className="text-text-muted transition-colors hover:text-text"
            >
              Open categories
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text">Savings Levers</p>
            <Badge
              variant={decisionBadgeVariant(
                saveNowLines.length > 0 ? 'mixed' : 'inside_guardrails',
              )}
            >
              {priceInsights.length + merchantHighlights.length} signal
              {priceInsights.length + merchantHighlights.length === 1
                ? ''
                : 's'}
            </Badge>
          </div>
          <p className="mt-3 text-2xl font-semibold text-text">
            {saveNowLines.length}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Levers to pull now, drawn from{' '}
            {priceInsights.length + merchantHighlights.length} price and
            merchant signals.
          </p>
          <div className="mt-3 space-y-2">
            {saveNowLines.length === 0 ? (
              <p className="text-xs text-text-muted">
                No live savings lever is visible yet.
              </p>
            ) : (
              saveNowLines.map((line) => (
                <p key={line} className="text-xs text-text-muted">
                  {line}
                </p>
              ))
            )}
          </div>
          <div className="mt-3 border-t border-border/30 pt-3 text-xs">
            <Link
              href="/money?tab=levers"
              className="text-text-muted transition-colors hover:text-text"
            >
              Open Levers
            </Link>
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border/30 pt-3 text-[11px] text-text-muted">
        <span className="font-semibold uppercase tracking-[0.16em]">
          Badge key
        </span>
        <span>Estimate — data degraded, refresh before relying</span>
        <span>Partial plan — covers only part of the month</span>
        <span>Wants / Needs leading — which side outspends</span>
        <span>Review — needs your input before a verdict</span>
      </div>
    </SectionCard>
  )
}
