'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { formatCurrency } from './formatters'

export function HouseholdPlanningPanels({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
      <SectionCard
        variant="surface"
        title="Budget Readiness"
        description={dashboard.budgetReadiness.summary}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-text">Missing inputs</p>
            <div className="mt-3 space-y-2">
              {dashboard.budgetReadiness.missingInputs.length === 0 ? (
                <p className="text-sm text-text-muted">Jenny has the core budget inputs she needs.</p>
              ) : (
                dashboard.budgetReadiness.missingInputs.map((item) => (
                  <p key={item} className="text-sm text-text-muted">
                    {item}
                  </p>
                ))
              )}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-text">Starter lanes</p>
            <div className="mt-3 space-y-3">
              {dashboard.budgetReadiness.starterLanes.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No starter lanes yet. Jenny will suggest these once more recurring spend patterns are confirmed.
                </p>
              ) : (
                dashboard.budgetReadiness.starterLanes.map((lane) => (
                  <div key={lane.name} className="rounded-xl border border-border/40 bg-surface-muted/20 p-3">
                    <p className="text-sm font-semibold text-text">{lane.name}</p>
                    <p className="mt-1 text-sm text-text-muted">{lane.objective}</p>
                    <p className="mt-2 text-xs uppercase tracking-wide text-primary">{lane.status}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Retirement Preparedness"
        description={dashboard.retirementPreparedness.summary}
      >
        <div className="space-y-5">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-sm font-semibold text-text">Contribution tracker</p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {dashboard.retirementContributionTracker.monthlyTarget
                ? formatCurrency(dashboard.retirementContributionTracker.monthlyGap)
                : '—'}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {dashboard.retirementContributionTracker.detail}
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold text-text">Strengths</p>
            <div className="mt-3 space-y-2">
              {dashboard.retirementPreparedness.strengths.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Jenny has not identified a strong retirement edge yet.
                </p>
              ) : (
                dashboard.retirementPreparedness.strengths.map((item) => (
                  <p key={item} className="text-sm text-text-muted">
                    {item}
                  </p>
                ))
              )}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-text">Blockers</p>
            <div className="mt-3 space-y-2">
              {dashboard.retirementPreparedness.blockers.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No retirement blockers are flagged right now.
                </p>
              ) : (
                dashboard.retirementPreparedness.blockers.map((item) => (
                  <p key={item} className="text-sm text-text-muted">
                    {item}
                  </p>
                ))
              )}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-text">Next steps</p>
            <div className="mt-3 space-y-2">
              {dashboard.retirementPreparedness.nextSteps.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Jenny does not have a next-step recommendation yet.
                </p>
              ) : (
                dashboard.retirementPreparedness.nextSteps.map((item) => (
                  <p key={item} className="text-sm text-text-muted">
                    {item}
                  </p>
                ))
              )}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-text">Retirement scenarios</p>
            <div className="mt-3 space-y-3">
              {dashboard.retirementScenarios.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Retirement scenarios will appear once Jenny has enough spending and contribution evidence.
                </p>
              ) : (
                dashboard.retirementScenarios.map((scenario) => (
                  <div
                    key={scenario.name}
                    className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">{scenario.name}</p>
                        <p className="mt-1 text-sm text-text-muted">{scenario.detail}</p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="font-semibold text-text">
                          {formatCurrency(scenario.monthlySpend)}
                        </p>
                        <p className="text-text-muted">{scenario.fundedYears} years funded</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-text">Sinking funds</p>
            <div className="mt-3 space-y-3">
              {dashboard.sinkingFunds.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No obvious sinking funds yet. More recurring bills and lumpy expenses will sharpen this.
                </p>
              ) : (
                dashboard.sinkingFunds.map((fund) => (
                  <div
                    key={fund.name}
                    className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">{fund.name}</p>
                        <p className="mt-1 text-sm text-text-muted">{fund.rationale}</p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="font-semibold text-text">
                          {formatCurrency(fund.monthlyTarget)}
                        </p>
                        <p className="text-text-muted">
                          {formatCurrency(fund.annualCost)} / year
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
