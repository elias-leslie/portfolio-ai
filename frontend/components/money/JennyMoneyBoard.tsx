'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'

export function JennyMoneyBoard({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const promptCount = dashboard.jennyBrief.prompts.length
  const needsCount = dashboard.jennyNeeds.filter(
    (n) => n.status === 'unsatisfied',
  ).length
  const resolvedValueCount = dashboard.resolvedValues.length
  const coverageMonths = dashboard.reports.executive.coverageMonths
  const progression = dashboard.jennyBrief.progression

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
        {promptCount} prompt{promptCount === 1 ? '' : 's'}
        {' · '}
        {needsCount} need{needsCount === 1 ? '' : 's'}
        {' · '}
        {resolvedValueCount} resolved value{resolvedValueCount === 1 ? '' : 's'}
        {' · '}
        {coverageMonths} month{coverageMonths === 1 ? '' : 's'} of evidence
      </div>

      {dashboard.portfolioContext?.insights &&
        dashboard.portfolioContext.insights.length > 0 && (
          <SectionCard
            variant="surface"
            title="Portfolio × Household"
            description="Cross-domain insights bridging your investments and spending."
          >
            <ul className="space-y-2">
              {dashboard.portfolioContext.insights.map((insight, idx) => (
                <li
                  key={`portfolio-insight-${idx}`}
                  className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted"
                >
                  {insight}
                </li>
              ))}
            </ul>
          </SectionCard>
        )}

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
              {promptCount === 0 ? (
                <div className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted">
                  Jenny does not need a follow-up prompt right now. Upload
                  fresher documents or answer household questions to generate the
                  next briefing prompts.
                </div>
              ) : (
                dashboard.jennyBrief.prompts.map((prompt, index) => (
                  <div
                    key={`${prompt}-${index}`}
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
          title="Jenny's Progress"
          description="What Jenny found and what she's working on."
        >
          <div className="space-y-4">
            {progression && progression.found.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  What I found
                </p>
                <ul className="space-y-1.5">
                  {progression.found.map((item, idx) => (
                    <li
                      key={`found-${idx}`}
                      className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-2.5 text-sm text-text-muted"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {progression?.workingOn && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Working on
                </p>
                <div className="rounded-2xl border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm text-text">
                  {progression.workingOn}
                </div>
              </div>
            )}

            {(!progression ||
              (progression.found.length === 0 && !progression.workingOn)) && (
              <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                Jenny is getting started. Upload statements or answer household
                questions to see her first findings here.
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
