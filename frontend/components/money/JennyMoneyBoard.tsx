'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'

export function JennyMoneyBoard({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const promptCount = dashboard.jennyBrief.prompts.length
  const opportunityCount = dashboard.opportunities.length
  const resolvedValueCount = dashboard.resolvedValues.length
  const coverageMonths = dashboard.reports.executive.coverageMonths
  const progression = dashboard.jennyBrief.progression

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
        {promptCount} prompt{promptCount === 1 ? '' : 's'}
        {' · '}
        {opportunityCount} opportunit{opportunityCount === 1 ? 'y' : 'ies'}
        {' · '}
        {resolvedValueCount} resolved value{resolvedValueCount === 1 ? '' : 's'}
        {' · '}
        {coverageMonths} month{coverageMonths === 1 ? '' : 's'} of evidence
      </div>

      {dashboard.portfolioContext?.insights && dashboard.portfolioContext.insights.length > 0 && (
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
                  Jenny does not need a follow-up prompt right now. Upload fresher documents or
                  answer household questions to generate the next briefing prompts.
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
          title="Jenny's Next Move"
          description="Here's what Jenny found, what she's working on, and what she needs from you."
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

            {progression && progression.needsFromYou.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-warning">
                  Need from you
                </p>
                <ul className="space-y-1.5">
                  {progression.needsFromYou.map((item, idx) => (
                    <li
                      key={`need-${idx}`}
                      className="rounded-2xl border border-warning/30 bg-warning/10 px-4 py-2.5 text-sm text-text"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(!progression || (progression.found.length === 0 && !progression.workingOn && progression.needsFromYou.length === 0)) && (
              <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                Jenny is getting started. Upload statements or answer household questions to see her first findings here.
              </div>
            )}

            {opportunityCount > 0 && (
              <div className="space-y-2 border-t border-border/30 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Opportunities spotted
                </p>
                {dashboard.opportunities.map((opportunity, idx) => (
                  <div
                    key={`${opportunity.title}-${idx}`}
                    className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-text">{opportunity.title}</p>
                          <Badge variant="outline">{opportunity.category}</Badge>
                        </div>
                        <p className="mt-1 text-sm text-text-muted">{opportunity.detail}</p>
                      </div>
                      <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
                        {opportunity.impact}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
