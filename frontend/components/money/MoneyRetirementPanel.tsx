'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

function preparednessVariant(status: string) {
  if (status.includes('ready') || status.includes('visible')) {
    return 'success' as const
  }
  if (status.includes('gap') || status.includes('blocked')) {
    return 'warning' as const
  }
  return 'outline' as const
}

export function MoneyRetirementPanel({
  dashboard,
  onEditTargets,
}: {
  dashboard: HouseholdFinanceDashboard
  onEditTargets?: () => void
}) {
  const preparedness = dashboard.retirementPreparedness
  const tracker = dashboard.retirementContributionTracker
  const scenarios = dashboard.retirementScenarios

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Retirement preparedness"
        description="A compact pass on readiness, contribution gap, and how long current assets could fund target spending."
        actions={
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onEditTargets}
          >
            Edit targets
          </Button>
        }
      >
        <div className="grid gap-3 lg:grid-cols-4">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                Status
              </p>
              <Badge variant={preparednessVariant(preparedness.status)}>
                {formatEnumLabel(preparedness.status)}
              </Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-text">
              {preparedness.summary}
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Retirement account share
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatPercent(preparedness.retirementAccountShare, {
                decimals: 0,
              })}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              Of total tracked assets currently tagged as retirement-oriented.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Monthly contribution gap
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {tracker.monthlyGap > 0
                ? formatCurrencyWhole(tracker.monthlyGap)
                : 'Covered'}
            </p>
            <p className="mt-2 text-sm text-text-muted">{tracker.detail}</p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Target retirement spend
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(dashboard.profile.targetRetirementSpend)}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              Goal age {dashboard.profile.targetRetirementAge ?? '—'}.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="What looks good"
        description="Keep the good, fix the blockers, and make the next move obvious."
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-gain/25 bg-gain/8 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gain">
              Strengths
            </p>
            <ul className="mt-3 space-y-2 text-sm text-text">
              {(preparedness.strengths.length > 0
                ? preparedness.strengths
                : ['No clear strengths captured yet.']
              )
                .slice(0, 5)
                .map((item) => (
                  <li key={item}>• {item}</li>
                ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-warning/25 bg-warning/8 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-warning">
              Blockers
            </p>
            <ul className="mt-3 space-y-2 text-sm text-text">
              {(preparedness.blockers.length > 0
                ? preparedness.blockers
                : ['No blockers captured yet.']
              )
                .slice(0, 5)
                .map((item) => (
                  <li key={item}>• {item}</li>
                ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Next steps
            </p>
            <ul className="mt-3 space-y-2 text-sm text-text">
              {(preparedness.nextSteps.length > 0
                ? preparedness.nextSteps
                : ['No next steps captured yet.']
              )
                .slice(0, 5)
                .map((item) => (
                  <li key={item}>• {item}</li>
                ))}
            </ul>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Scenario table"
        description="How long current retirement assets could fund different spending assumptions."
      >
        <div className="overflow-hidden rounded-2xl border border-border/35 bg-surface-muted/10">
          <div className="overflow-auto">
            <table className="w-full min-w-[760px] border-separate border-spacing-0 text-sm">
              <thead className="bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Scenario
                  </th>
                  <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Monthly spend
                  </th>
                  <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Annual spend
                  </th>
                  <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Funded years
                  </th>
                  <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Readiness
                  </th>
                  <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Detail
                  </th>
                </tr>
              </thead>
              <tbody>
                {scenarios.length > 0 ? (
                  scenarios.map((scenario) => (
                    <tr
                      key={scenario.name}
                      className="align-top hover:bg-surface-muted/10"
                    >
                      <td className="border-b border-border/20 px-4 py-3 font-medium text-text">
                        {scenario.name}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(scenario.monthlySpend, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(scenario.annualSpend, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {scenario.fundedYears.toFixed(1)}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3">
                        <Badge
                          variant={preparednessVariant(scenario.readiness)}
                        >
                          {formatEnumLabel(scenario.readiness)}
                        </Badge>
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-text-muted">
                        {scenario.detail}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-10 text-center text-sm text-text-muted"
                    >
                      Retirement scenarios will appear once Jenny has enough
                      information to model them.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
