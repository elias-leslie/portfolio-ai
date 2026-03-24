'use client'

import { PiggyBank, ShieldCheck, Target, Wallet } from 'lucide-react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { formatCurrency, formatPercent } from './formatters'

const overviewIcons = [Wallet, PiggyBank, ShieldCheck, Target]

export function HouseholdOverviewGrid({
  dashboard,
  stage,
}: {
  dashboard: HouseholdFinanceDashboard
  stage?: 1 | 2 | 3 | 4
}) {
  if (stage != null && stage <= 2) {
    return null
  }

  const metrics = [
    {
      label: 'Tracked assets',
      value: formatCurrency(dashboard.overview.totalTrackedAssets),
      detail: dashboard.overview.visibilityLabel,
    },
    {
      label: 'Retirement assets',
      value: formatCurrency(dashboard.overview.retirementAssets),
      detail: `${formatPercent(
        dashboard.retirementPreparedness.retirementAccountShare,
      )} of tracked assets`,
    },
    {
      label: 'Cash reserve',
      value: formatCurrency(dashboard.overview.cashReserve),
      detail: 'Cash already visible to Jenny',
    },
    {
      label: 'Visibility score',
      value: `${dashboard.overview.visibilityScore}/100`,
      detail: dashboard.overview.nextBestAction,
    },
  ]

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1.2fr_repeat(3,minmax(0,1fr))] animate-stagger">
      {metrics.map((metric, index) => {
        const Icon = overviewIcons[index]
        return (
          <SectionCard
            key={metric.label}
            variant="surface"
            className="group overflow-hidden"
            contentClassName="space-y-3"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                  {metric.label}
                </p>
                <p className="mt-2 font-display italic text-2xl tabular-nums tracking-tight text-text xl:text-[1.75rem]">
                  {metric.value}
                </p>
              </div>
              <div className="rounded-xl bg-primary/10 p-2.5 text-primary transition-all duration-200 group-hover:shadow-[0_0_12px_-3px] group-hover:shadow-primary/20">
                <Icon className="h-4 w-4" />
              </div>
            </div>
            <p className="text-sm leading-5 text-text-muted">{metric.detail}</p>
          </SectionCard>
        )
      })}
    </div>
  )
}
