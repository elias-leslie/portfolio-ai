'use client'

import { Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import { useMacroConditions, useMacroCurrent } from '@/lib/hooks/useMacro'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { useTodayRefresh } from '@/lib/hooks/useTodayRefresh'
import {
  DecisionBrief,
  formatTimestamp,
  MacroContributionBreakdown,
  MarketConditionHero,
  MarketEvidenceStrip,
} from './DailyBriefSections'
import { OverallCautionTrendLine } from './OverallCautionTrendLine'
import { LeadingLaggingStrip } from './today/LeadingLaggingStrip'
import { PrimaryTilesGrid } from './today/PrimaryTilesGrid'

export function DailyBriefPanel() {
  const refreshToday = useTodayRefresh()
  const {
    data: macro,
    isLoading: macroLoading,
    error: macroError,
  } = useMacroCurrent()
  const {
    data: conditions,
    isLoading: conditionsLoading,
    error: conditionsError,
  } = useMacroConditions()
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: netWorthTrend, isLoading: trendLoading } =
    useHouseholdNetWorthTrend({ days: 180 })
  const updateTimestamp =
    conditions?.computedAt ??
    macro?.computedAt ??
    household?.generatedAt ??
    null
  const conditionDataUnavailable = !conditions && !macro

  return (
    <section className="overflow-hidden rounded-2xl border border-border/40 bg-surface/50 surface-highlight backdrop-blur-sm">
      <div className="flex flex-col gap-2 border-b border-border/40 px-6 py-4 md:flex-row md:items-center md:justify-between">
        <h2 className="font-display italic text-lg tracking-tight text-text">
          Daily Brief
        </h2>
        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
            {formatTimestamp(updateTimestamp)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refreshToday.mutate()}
            disabled={refreshToday.isPending}
            aria-busy={refreshToday.isPending}
            title="Force-refresh Today with current quotes and recomputed macro conditions"
          >
            {refreshToday.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 p-4 lg:grid-cols-[minmax(16rem,0.82fr)_minmax(30rem,1.7fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <MarketConditionHero
            conditions={conditions}
            macro={macro}
            loading={
              conditionDataUnavailable && (macroLoading || conditionsLoading)
            }
            error={
              conditionDataUnavailable ? (conditionsError ?? macroError) : null
            }
          />
          <OverallCautionTrendLine />
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <DecisionBrief conditions={conditions} />
          <PrimaryTilesGrid
            household={household}
            householdLoading={householdLoading}
            analytics={analytics}
            analyticsLoading={analyticsLoading}
            netWorthTrend={netWorthTrend}
            trendLoading={trendLoading}
          />
          <LeadingLaggingStrip />
          <MarketEvidenceStrip evidence={conditions?.evidence} />
        </div>
      </div>

      <details className="mx-4 mb-4">
        <summary className="cursor-pointer rounded-xl border border-border-subtle bg-bg/20 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-text-muted transition hover:text-text">
          Score details
        </summary>
        <div className="mt-3">
          <MacroContributionBreakdown macro={macro} />
        </div>
      </details>
    </section>
  )
}
