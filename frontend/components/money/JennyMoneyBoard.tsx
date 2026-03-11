'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'

export function JennyMoneyBoard({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <SectionCard
        variant="surface"
        title="Jenny Money Brief"
        description={dashboard.jennyBrief.body}
      >
        <div className="rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-accent/5 to-surface p-6">
          <p className="text-lg font-semibold tracking-tight text-text">
            {dashboard.jennyBrief.headline}
          </p>
          <div className="mt-5 grid gap-3">
            {dashboard.jennyBrief.prompts.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted">
                Jenny does not need a follow-up prompt right now. Upload fresher documents or
                answer household questions to generate the next briefing prompts.
              </div>
            ) : (
              dashboard.jennyBrief.prompts.map((prompt) => (
                <div
                  key={prompt}
                  className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted"
                >
                  {prompt}
                </div>
              ))
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Opportunity Queue"
        description="These are the next areas where Jenny can create real household value."
      >
        <div className="space-y-3">
          {dashboard.opportunities.length === 0 ? (
            <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
              No open opportunity queue right now. Jenny has enough structure to maintain the
              current household plan without pushing a new optimization theme.
            </div>
          ) : (
            dashboard.opportunities.map((opportunity) => (
              <div
                key={opportunity.title}
                className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-text">{opportunity.title}</p>
                      <Badge variant="outline">{opportunity.category}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-text-muted">{opportunity.detail}</p>
                    <p className="mt-3 text-sm text-text">Next step: {opportunity.nextStep}</p>
                  </div>
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
                    {opportunity.impact}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </SectionCard>
    </div>
  )
}
