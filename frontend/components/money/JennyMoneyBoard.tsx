'use client'

import Link from 'next/link'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { formatCurrency } from './formatters'

export function JennyMoneyBoard({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const executive = dashboard.reports.executive
  const promptCount = dashboard.jennyBrief.prompts.length
  const needsCount = dashboard.jennyNeeds.filter(
    (n) => n.status === 'unsatisfied',
  ).length
  const nextNeed =
    dashboard.jennyNeeds.find((need) => need.status === 'unsatisfied') ?? null
  const resolvedValueCount = dashboard.resolvedValues.length
  const openQuestionCount = dashboard.questions.filter(
    (question) => !question.answeredAt,
  ).length
  const coverageMonths = executive.coverageMonths
  const progression = dashboard.jennyBrief.progression
  const portfolioContext = dashboard.portfolioContext
  const summaryCards = [
    {
      label: 'Prompts ready',
      value: String(promptCount),
      detail:
        promptCount > 0
          ? 'Short prompts Jenny wants answered next.'
          : 'No follow-up prompts right now.',
    },
    {
      label: 'Open needs',
      value: String(needsCount),
      detail:
        needsCount > 0
          ? 'Missing confirmations or evidence still blocking Jenny.'
          : 'No unresolved needs are currently blocking the system.',
    },
    {
      label: 'Open questions',
      value: String(openQuestionCount),
      detail:
        openQuestionCount > 0
          ? 'Questions still awaiting your answer.'
          : 'No unanswered household questions right now.',
    },
    {
      label: 'Evidence coverage',
      value: `${coverageMonths} mo`,
      detail:
        coverageMonths > 0
          ? `${coverageMonths} month${coverageMonths === 1 ? '' : 's'} of normalized spend evidence.`
          : 'Upload statements to give Jenny real household evidence.',
    },
  ]
  const portfolioStats = [
    {
      label: 'Portfolio value',
      value: formatCurrency(portfolioContext?.totalPortfolioValue),
      visible: portfolioContext?.totalPortfolioValue != null,
    },
    {
      label: 'Cash runway',
      value:
        portfolioContext?.cashReservesMonths != null
          ? `${portfolioContext.cashReservesMonths.toFixed(1)} months`
          : null,
      visible: portfolioContext?.cashReservesMonths != null,
    },
    {
      label: 'Portfolio / annual spend',
      value:
        portfolioContext?.portfolioToAnnualSpendRatio != null
          ? `${portfolioContext.portfolioToAnnualSpendRatio.toFixed(1)}x`
          : null,
      visible: portfolioContext?.portfolioToAnnualSpendRatio != null,
    },
  ].filter((item) => item.visible)

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
          >
            <p className="text-sm font-medium text-text-muted">{card.label}</p>
            <p className="mt-3 font-display text-3xl tracking-tight text-text">
              {card.value}
            </p>
            <p className="mt-2 text-sm text-text-muted">{card.detail}</p>
          </div>
        ))}
      </div>

      <SectionCard
        variant="surface"
        title="What Jenny Needs Next"
        description="Keep the next unblocker explicit instead of buried in the broader dashboard."
      >
        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Next best action
            </p>
            <p className="mt-2 text-lg font-semibold text-text">
              {dashboard.overview.nextBestAction}
            </p>
            <p className="mt-2 text-sm text-text-muted">
              {resolvedValueCount} resolved value
              {resolvedValueCount === 1 ? '' : 's'} already anchored in the household model.
            </p>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Highest-priority need
            </p>
            {nextNeed ? (
              <>
                <p className="mt-2 text-base font-semibold text-text">{nextNeed.title}</p>
                <p className="mt-2 text-sm text-text-muted">{nextNeed.detail}</p>
                {nextNeed.actionHref ? (
                  <div className="mt-4">
                    <Button asChild size="sm" variant="outline">
                      <Link href={nextNeed.actionHref}>Open related workflow</Link>
                    </Button>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="mt-2 text-sm text-text-muted">
                Jenny does not have an urgent blocker right now. Upload fresher documents or answer
                open questions to keep the system current.
              </p>
            )}
          </div>
        </div>
      </SectionCard>

      {portfolioStats.length > 0 || dashboard.portfolioContext?.insights?.length ? (
          <SectionCard
            variant="surface"
            title="Portfolio × Household"
            description="Cross-domain insights bridging your investments and spending."
          >
            <div className="space-y-4">
              {portfolioStats.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-3">
                  {portfolioStats.map((stat) => (
                    <div
                      key={stat.label}
                      className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
                    >
                      <p className="text-sm font-medium text-text-muted">{stat.label}</p>
                      <p className="mt-2 font-display text-xl text-text">{stat.value}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {dashboard.portfolioContext?.insights?.length ? (
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
              ) : null}
            </div>
          </SectionCard>
        ) : null}

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
                Jenny is getting started. {openQuestionCount > 0
                  ? `There ${openQuestionCount === 1 ? 'is' : 'are'} ${openQuestionCount} open question${openQuestionCount === 1 ? '' : 's'} waiting in Planning.`
                  : 'Upload statements or answer household questions to see her first findings here.'}
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
