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
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric, index) => {
        const Icon = overviewIcons[index]
        return (
          <SectionCard
            key={metric.label}
            variant="surface"
            className="overflow-hidden"
            contentClassName="space-y-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-text-muted">{metric.label}</p>
                <p className="mt-3 text-3xl font-semibold tracking-tight text-text">
                  {metric.value}
                </p>
              </div>
              <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                <Icon className="h-5 w-5" />
              </div>
            </div>
            <p className="text-sm leading-6 text-text-muted">{metric.detail}</p>
          </SectionCard>
        )
      })}
    </div>
  )
}
