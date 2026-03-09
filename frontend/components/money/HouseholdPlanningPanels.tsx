'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'

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
              {dashboard.budgetReadiness.starterLanes.map((lane) => (
                <div key={lane.name} className="rounded-xl border border-border/40 bg-surface-muted/20 p-3">
                  <p className="text-sm font-semibold text-text">{lane.name}</p>
                  <p className="mt-1 text-sm text-text-muted">{lane.objective}</p>
                  <p className="mt-2 text-xs uppercase tracking-wide text-primary">{lane.status}</p>
                </div>
              ))}
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
          <div>
            <p className="text-sm font-semibold text-text">Strengths</p>
            <div className="mt-3 space-y-2">
              {dashboard.retirementPreparedness.strengths.map((item) => (
                <p key={item} className="text-sm text-text-muted">
                  {item}
                </p>
              ))}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-text">Next steps</p>
            <div className="mt-3 space-y-2">
              {dashboard.retirementPreparedness.nextSteps.map((item) => (
                <p key={item} className="text-sm text-text-muted">
                  {item}
                </p>
              ))}
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
