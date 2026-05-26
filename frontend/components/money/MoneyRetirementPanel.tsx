'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  HouseholdFinanceDashboard,
  RetirementPreviewRequest,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useRetirementPreview } from '@/lib/hooks/useHousehold'

const bucketColors: Record<string, string> = {
  cash: 'var(--color-chart-5)',
  taxable: 'var(--color-chart-1)',
  governmental_457b: 'var(--color-warning)',
  preTax: 'var(--color-chart-2)',
  pre_tax: 'var(--color-chart-2)',
  roth: 'var(--color-chart-3)',
  hsa: 'var(--color-chart-4)',
  other: 'var(--color-chart-6)',
}

const bucketOrder = [
  'cash',
  'taxable',
  'governmental_457b',
  'pre_tax',
  'hsa',
  'roth',
  'other',
]
const ssa2026TaxableWageBase = 184_500
const ssa2026FirstBendPoint = 1_286
const ssa2026SecondBendPoint = 7_749
const socialSecurityFullRetirementAge = 67

function preparednessVariant(status: string) {
  if (status.includes('ready') || status.includes('visible')) {
    return 'success' as const
  }
  if (status.includes('gap') || status.includes('blocked')) {
    return 'warning' as const
  }
  return 'outline' as const
}

function previewStatusVariant(
  successProbability: number,
  trustedTotals: boolean,
) {
  if (!trustedTotals) return 'warning' as const
  if (successProbability >= 0.8) return 'success' as const
  if (successProbability >= 0.6) return 'warning' as const
  return 'destructive' as const
}

function bucketLabel(value: string) {
  switch (value) {
    case 'cash':
      return 'Cash'
    case 'taxable':
      return 'Taxable'
    case 'governmental_457b':
      return 'Gov 457(b)'
    case 'pre_tax':
    case 'preTax':
      return 'Pre-tax'
    case 'roth':
      return 'Roth'
    case 'hsa':
      return 'HSA'
    default:
      return formatEnumLabel(value)
  }
}

function bucketMapValue(values: Record<string, number>, bucket: string) {
  if (bucket === 'pre_tax') return values.pre_tax ?? values.preTax ?? 0
  if (bucket === 'governmental_457b') {
    return values.governmental_457b ?? values.governmental457b ?? 0
  }
  return values[bucket] ?? 0
}

function numberInput(value: number | null | undefined, fallback = '') {
  return value == null ? fallback : String(Math.round(value))
}

function percentInput(value: number | null | undefined, fallback = '2.5') {
  if (value == null) return fallback
  return String(Math.round(value * 1000) / 10)
}

function parseNumber(value: string, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function parseOptionalNumber(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function estimateSocialSecurityMonthly(
  annualEarnings: number | null,
  claimAge: number,
) {
  if (annualEarnings == null || annualEarnings <= 0) return null
  const aime = Math.min(annualEarnings, ssa2026TaxableWageBase) / 12
  const pia =
    Math.min(aime, ssa2026FirstBendPoint) * 0.9 +
    Math.max(
      Math.min(aime, ssa2026SecondBendPoint) - ssa2026FirstBendPoint,
      0,
    ) *
      0.32 +
    Math.max(aime - ssa2026SecondBendPoint, 0) * 0.15
  if (claimAge < socialSecurityFullRetirementAge) {
    const monthsEarly = Math.max(
      0,
      (socialSecurityFullRetirementAge - claimAge) * 12,
    )
    const first36 = Math.min(monthsEarly, 36)
    const extra = Math.max(monthsEarly - 36, 0)
    return Math.max(pia - pia * (first36 * (5 / 900) + extra * (5 / 1200)), 0)
  }
  const monthsLate = Math.min(
    Math.max(0, (claimAge - socialSecurityFullRetirementAge) * 12),
    36,
  )
  return pia * (1 + monthsLate * (2 / 300))
}

function memberAge(
  member: NonNullable<HouseholdFinanceDashboard['planning']>['members'][number],
  asOf: Date,
) {
  if (!member.birthYear) return null
  let age = asOf.getFullYear() - member.birthYear
  const isoMatch = member.notes?.match(
    /\b(?:dob|birth(?:day)?)\s*:\s*\d{4}-(\d{1,2})-(\d{1,2})\b/i,
  )
  if (isoMatch) {
    const month = Number(isoMatch[1])
    const day = Number(isoMatch[2])
    const asOfMonth = asOf.getMonth() + 1
    if (
      Number.isFinite(month) &&
      Number.isFinite(day) &&
      (asOfMonth < month || (asOfMonth === month && asOf.getDate() < day))
    ) {
      age -= 1
    }
  }
  return Math.max(age, 0)
}

function householdAges(dashboard: HouseholdFinanceDashboard) {
  const asOf = new Date(dashboard.generatedAt)
  const adults =
    dashboard.planning?.members.filter((member) => {
      const role = member.role.toLowerCase()
      const relationship = member.relationship?.toLowerCase() ?? ''
      return (
        !member.isDependent &&
        !['child', 'dependent'].includes(role) &&
        !['child', 'daughter', 'son', 'dependent'].includes(relationship)
      )
    }) ?? []
  const primary =
    adults.find((member) =>
      ['primary', 'self', 'owner'].includes(member.role.toLowerCase()),
    ) ??
    adults.find((member) =>
      ['father', 'husband', 'self', 'owner'].includes(
        member.relationship?.toLowerCase() ?? '',
      ),
    )
  const spouse =
    adults.find((member) =>
      ['spouse', 'partner'].includes(member.role.toLowerCase()),
    ) ??
    adults.find((member) =>
      ['mother', 'wife', 'spouse', 'partner'].includes(
        member.relationship?.toLowerCase() ?? '',
      ),
    )
  return {
    primaryAge: primary ? memberAge(primary, asOf) : null,
    spouseAge: spouse ? memberAge(spouse, asOf) : null,
  }
}

function socialSecurityDefaults(dashboard: HouseholdFinanceDashboard) {
  const sources = dashboard.planning?.retirementIncomeSources ?? []
  const socialSecurity = sources.filter(
    (source) => source.sourceType.toLowerCase() === 'social_security',
  )
  const primary = socialSecurity.find((source) =>
    (source.ownerName ?? source.label).toLowerCase().includes('primary'),
  )
  const spouse = socialSecurity.find((source) =>
    (source.ownerName ?? source.label).toLowerCase().includes('spouse'),
  )
  return {
    primaryMonthly: numberInput(primary?.monthlyAmount, '0'),
    primaryStartAge: numberInput(primary?.startAge, '67'),
    primaryAnnualEarnings: '0',
    spouseMonthly: numberInput(spouse?.monthlyAmount, '0'),
    spouseStartAge: numberInput(spouse?.startAge, '67'),
    spouseAnnualEarnings: '0',
  }
}

function defaultDraft(dashboard: HouseholdFinanceDashboard) {
  const monthlySpend =
    dashboard.profile.targetRetirementSpend ||
    dashboard.reports.executive.averageMonthlySpend ||
    6000
  const ages = householdAges(dashboard)
  const socialSecurity = socialSecurityDefaults(dashboard)
  return {
    primaryAge: numberInput(ages.primaryAge, ''),
    spouseAge: numberInput(ages.spouseAge, ''),
    retirementAge: numberInput(dashboard.profile.targetRetirementAge, '65'),
    monthlySpend: numberInput(monthlySpend, '6000'),
    monthlyContribution: numberInput(
      dashboard.profile.monthlySavingsTarget ??
        dashboard.retirementContributionTracker.estimatedMonthlyContributions,
      '0',
    ),
    inflationRate: percentInput(0.025),
    horizonYears: '35',
    primarySocialSecurityMonthly: socialSecurity.primaryMonthly,
    primarySocialSecurityAnnualEarnings: socialSecurity.primaryAnnualEarnings,
    primarySocialSecurityStartAge: socialSecurity.primaryStartAge,
    spouseSocialSecurityMonthly: socialSecurity.spouseMonthly,
    spouseSocialSecurityAnnualEarnings: socialSecurity.spouseAnnualEarnings,
    spouseSocialSecurityStartAge: socialSecurity.spouseStartAge,
  }
}

function buildRequest(
  householdId: string,
  draft: ReturnType<typeof defaultDraft>,
): RetirementPreviewRequest {
  return {
    householdId,
    retirementAge: parseNumber(draft.retirementAge, 65),
    monthlySpend: parseNumber(draft.monthlySpend, 6000),
    annualContribution: parseNumber(draft.monthlyContribution, 0) * 12,
    inflationRate: parseNumber(draft.inflationRate, 2.5) / 100,
    horizonYears: parseNumber(draft.horizonYears, 35),
    primaryAge: parseOptionalNumber(draft.primaryAge),
    spouseAge: parseOptionalNumber(draft.spouseAge),
    primarySocialSecurityMonthly: parseOptionalNumber(
      draft.primarySocialSecurityMonthly,
    ),
    primarySocialSecurityAnnualEarnings: parseOptionalNumber(
      draft.primarySocialSecurityAnnualEarnings,
    ),
    primarySocialSecurityStartAge: parseOptionalNumber(
      draft.primarySocialSecurityStartAge,
    ),
    spouseSocialSecurityMonthly: parseOptionalNumber(
      draft.spouseSocialSecurityMonthly,
    ),
    spouseSocialSecurityAnnualEarnings: parseOptionalNumber(
      draft.spouseSocialSecurityAnnualEarnings,
    ),
    spouseSocialSecurityStartAge: parseOptionalNumber(
      draft.spouseSocialSecurityStartAge,
    ),
    trials: 2500,
    seed: 7,
  }
}

function currencyTooltip(value: unknown) {
  return formatCurrency(typeof value === 'number' ? value : Number(value), {
    decimals: 0,
  })
}

function percentPoints(value: number) {
  return formatPercent(value * 100, { decimals: 0 })
}

export function MoneyRetirementPanel({
  dashboard,
  onEditTargets,
}: {
  dashboard: HouseholdFinanceDashboard
  onEditTargets?: () => void
}) {
  const [draft, setDraft] = useState(() => defaultDraft(dashboard))
  const [request, setRequest] = useState<RetirementPreviewRequest>(() =>
    buildRequest(dashboard.profile.id, defaultDraft(dashboard)),
  )
  const previewQuery = useRetirementPreview(request)
  const preview = previewQuery.data
  const preparedness = dashboard.retirementPreparedness

  useEffect(() => {
    const nextDraft = defaultDraft(dashboard)
    setDraft(nextDraft)
    setRequest(buildRequest(dashboard.profile.id, nextDraft))
  }, [dashboard])

  const projectionData = useMemo(() => {
    if (!preview) return []
    const paths = preview.endingBalancePaths
    const length = Math.max(
      paths.p10?.length ?? 0,
      paths.p50?.length ?? 0,
      paths.p90?.length ?? 0,
    )
    return Array.from({ length }).map((_, index) => ({
      age: preview.inputs.primaryAge + index,
      p10: paths.p10?.[index] ?? null,
      p50: paths.p50?.[index] ?? null,
      p90: paths.p90?.[index] ?? null,
    }))
  }, [preview])

  const balanceData = useMemo(
    () =>
      (preview?.drawdownSchedule ?? []).map((row) => ({
        age: row.primaryAge,
        cash: bucketMapValue(row.balancesByBucket, 'cash'),
        taxable: bucketMapValue(row.balancesByBucket, 'taxable'),
        governmental_457b: bucketMapValue(
          row.balancesByBucket,
          'governmental_457b',
        ),
        pre_tax: bucketMapValue(row.balancesByBucket, 'pre_tax'),
        hsa: bucketMapValue(row.balancesByBucket, 'hsa'),
        roth: bucketMapValue(row.balancesByBucket, 'roth'),
        other: bucketMapValue(row.balancesByBucket, 'other'),
      })),
    [preview?.drawdownSchedule],
  )

  const withdrawalData = useMemo(
    () =>
      (preview?.drawdownSchedule ?? [])
        .filter((row) => row.primaryAge >= (preview?.inputs.retirementAge ?? 0))
        .slice(0, 30)
        .map((row) => ({
          age: row.primaryAge,
          cash: bucketMapValue(row.withdrawalsByBucket, 'cash'),
          taxable: bucketMapValue(row.withdrawalsByBucket, 'taxable'),
          governmental_457b: bucketMapValue(
            row.withdrawalsByBucket,
            'governmental_457b',
          ),
          pre_tax: bucketMapValue(row.withdrawalsByBucket, 'pre_tax'),
          hsa: bucketMapValue(row.withdrawalsByBucket, 'hsa'),
          roth: bucketMapValue(row.withdrawalsByBucket, 'roth'),
          other: bucketMapValue(row.withdrawalsByBucket, 'other'),
        })),
    [preview],
  )

  const bucketTotals = useMemo(() => {
    const totals = new Map<string, number>()
    for (const bucket of preview?.accountBuckets ?? []) {
      totals.set(
        bucket.bucketType,
        (totals.get(bucket.bucketType) ?? 0) + bucket.currentValue,
      )
    }
    return bucketOrder
      .map((bucket) => ({ bucket, value: totals.get(bucket) ?? 0 }))
      .filter((row) => row.value > 0)
  }, [preview?.accountBuckets])

  const drawdownRows = useMemo(
    () =>
      (preview?.drawdownSchedule ?? [])
        .filter((row) => row.primaryAge >= (preview?.inputs.retirementAge ?? 0))
        .slice(0, 24),
    [preview],
  )

  const socialSecurityEstimate = useMemo(() => {
    const primaryManual = parseOptionalNumber(
      draft.primarySocialSecurityMonthly,
    )
    const spouseManual = parseOptionalNumber(draft.spouseSocialSecurityMonthly)
    const primaryClaimAge = parseNumber(
      draft.primarySocialSecurityStartAge,
      socialSecurityFullRetirementAge,
    )
    const spouseClaimAge = parseNumber(
      draft.spouseSocialSecurityStartAge,
      socialSecurityFullRetirementAge,
    )
    return {
      primary:
        primaryManual ??
        estimateSocialSecurityMonthly(
          parseOptionalNumber(draft.primarySocialSecurityAnnualEarnings),
          primaryClaimAge,
        ),
      spouse:
        spouseManual ??
        estimateSocialSecurityMonthly(
          parseOptionalNumber(draft.spouseSocialSecurityAnnualEarnings),
          spouseClaimAge,
        ),
      primaryClaimAge,
      spouseClaimAge,
    }
  }, [draft])

  const applyDraft = () => {
    setRequest(buildRequest(dashboard.profile.id, draft))
  }

  const updateDraft = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Retirement planner"
        description="Plug in the levers, then read the plan through probability, balances, and drawdowns. Tax output is a planning estimate, not tax advice."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onEditTargets}
            >
              Edit saved assumptions
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={applyDraft}
              disabled={previewQuery.isFetching}
            >
              {previewQuery.isFetching ? 'Running…' : 'Run preview'}
            </Button>
          </div>
        }
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Retire age
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.retirementAge}
              onChange={(event) =>
                updateDraft('retirementAge', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Spend / month
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.monthlySpend}
              onChange={(event) =>
                updateDraft('monthlySpend', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Save / month
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.monthlyContribution}
              onChange={(event) =>
                updateDraft('monthlyContribution', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Inflation %
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.inflationRate}
              onChange={(event) =>
                updateDraft('inflationRate', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Horizon years
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.horizonYears}
              onChange={(event) =>
                updateDraft('horizonYears', event.target.value)
              }
            />
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Your age
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.primaryAge}
              onChange={(event) =>
                updateDraft('primaryAge', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Spouse age
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.spouseAge}
              onChange={(event) => updateDraft('spouseAge', event.target.value)}
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Your salary
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.primarySocialSecurityAnnualEarnings}
              onChange={(event) =>
                updateDraft(
                  'primarySocialSecurityAnnualEarnings',
                  event.target.value,
                )
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Your SS / mo
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.primarySocialSecurityMonthly}
              onChange={(event) =>
                updateDraft('primarySocialSecurityMonthly', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Your SS age
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.primarySocialSecurityStartAge}
              onChange={(event) =>
                updateDraft('primarySocialSecurityStartAge', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Spouse salary
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.spouseSocialSecurityAnnualEarnings}
              onChange={(event) =>
                updateDraft(
                  'spouseSocialSecurityAnnualEarnings',
                  event.target.value,
                )
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Spouse SS / mo
            </p>
            <Input
              className="mt-2"
              inputMode="decimal"
              value={draft.spouseSocialSecurityMonthly}
              onChange={(event) =>
                updateDraft('spouseSocialSecurityMonthly', event.target.value)
              }
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Spouse SS age
            </p>
            <Input
              className="mt-2"
              inputMode="numeric"
              value={draft.spouseSocialSecurityStartAge}
              onChange={(event) =>
                updateDraft('spouseSocialSecurityStartAge', event.target.value)
              }
            />
          </div>
        </div>
        <p className="mt-3 text-xs text-text-muted">
          Social Security included:{' '}
          <span className="font-mono text-text">
            {formatCurrency(socialSecurityEstimate.primary ?? 0, {
              decimals: 0,
            })}
            /mo at {socialSecurityEstimate.primaryClaimAge}
          </span>{' '}
          for you and{' '}
          <span className="font-mono text-text">
            {formatCurrency(socialSecurityEstimate.spouse ?? 0, {
              decimals: 0,
            })}
            /mo at {socialSecurityEstimate.spouseClaimAge}
          </span>{' '}
          for spouse. Enter exact SSA estimates when available; salary-based
          values are rough estimates.
        </p>
      </SectionCard>

      {previewQuery.error ? (
        <LoadErrorState
          title="Failed to run retirement preview."
          detail={
            previewQuery.error instanceof Error
              ? previewQuery.error.message
              : 'Retry the planner after checking the saved Money assumptions.'
          }
          onRetry={() => void previewQuery.refetch()}
          isRetrying={previewQuery.isFetching}
        />
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Success odds
            </p>
            {preview ? (
              <Badge
                variant={previewStatusVariant(
                  preview.successProbability,
                  preview.trustedTotals,
                )}
              >
                {preview.trustedTotals ? 'Trusted' : 'Guarded'}
              </Badge>
            ) : null}
          </div>
          <p className="mt-3 text-3xl font-semibold text-text">
            {preview ? percentPoints(preview.successProbability) : '—'}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Monte Carlo probability for this knob set.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Median ending balance
          </p>
          <p className="mt-3 text-3xl font-semibold text-text">
            {formatCurrencyWhole(preview?.medianEndingBalance)}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            P50 terminal value at horizon.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            First depletion
          </p>
          <p className="mt-3 text-3xl font-semibold text-text">
            {preview?.firstDepletionAge
              ? `Age ${preview.firstDepletionAge}`
              : 'None'}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Deterministic drawdown schedule.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Save gap / month
          </p>
          <p className="mt-3 text-3xl font-semibold text-text">
            {preview && preview.estimatedMonthlyContributionGap > 0
              ? formatCurrencyWhole(preview.estimatedMonthlyContributionGap)
              : 'Covered'}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Simple 25x spend checkpoint.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Data guard
          </p>
          <p className="mt-3 text-sm font-semibold text-text">
            {preview?.accountControlSummary || preparedness.summary}
          </p>
          <Badge
            className="mt-3"
            variant={
              preview?.trustedTotals === false
                ? 'warning'
                : preparednessVariant(preparedness.status)
            }
          >
            {formatEnumLabel(
              preview?.accountControlStatus ?? preparedness.status,
            )}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <SectionCard
          variant="surface"
          title="Probability bands"
          description="Portfolio range by age. Wider bands mean return sequence risk matters more."
        >
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={projectionData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="p90"
                  name="P90"
                  stroke="var(--color-chart-3)"
                  fill="var(--color-chart-3)"
                  fillOpacity={0.12}
                />
                <Area
                  type="monotone"
                  dataKey="p50"
                  name="P50"
                  stroke="var(--color-chart-1)"
                  fill="var(--color-chart-1)"
                  fillOpacity={0.16}
                />
                <Line
                  type="monotone"
                  dataKey="p10"
                  name="P10"
                  stroke="var(--color-warning)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Account buckets"
          description="Current planner buckets by tax treatment and drawdown priority."
        >
          <div className="space-y-3">
            {bucketTotals.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-5 text-sm text-text-muted">
                No account buckets are available yet.
              </div>
            ) : (
              bucketTotals.map((bucket) => (
                <div
                  key={bucket.bucket}
                  className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: bucketColors[bucket.bucket] }}
                      />
                      <p className="text-sm font-semibold text-text">
                        {bucketLabel(bucket.bucket)}
                      </p>
                    </div>
                    <p className="font-mono text-sm tabular-nums text-text">
                      {formatCurrencyWhole(bucket.value)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          variant="surface"
          title="Account balances by age"
          description="Stacked expected-path balances after contributions, withdrawals, tax estimates, and RMD estimates."
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={balanceData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                {bucketOrder.map((bucket) => (
                  <Area
                    key={bucket}
                    type="monotone"
                    dataKey={bucket}
                    stackId="1"
                    name={bucketLabel(bucket)}
                    stroke={bucketColors[bucket]}
                    fill={bucketColors[bucket]}
                    fillOpacity={0.55}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          variant="surface"
          title="Annual drawdown by source"
          description="Gross withdrawals needed by account type after retirement income sources."
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={withdrawalData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                />
                <XAxis dataKey="age" tickLine={false} />
                <YAxis
                  tickFormatter={(value) =>
                    `$${Math.round(Number(value) / 1000)}k`
                  }
                />
                <Tooltip formatter={currencyTooltip} />
                <Legend />
                {bucketOrder.map((bucket) => (
                  <Bar
                    key={bucket}
                    dataKey={bucket}
                    stackId="withdrawals"
                    name={bucketLabel(bucket)}
                    fill={bucketColors[bucket]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        variant="surface"
        title="Knobs and levers"
        description="Modeled impact of simple changes against the current preview."
      >
        <div className="grid gap-3 md:grid-cols-3">
          {(preview?.leverImpacts ?? []).map((lever) => (
            <div
              key={lever.id}
              className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
            >
              <p className="text-sm font-semibold text-text">{lever.label}</p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {formatPercent(lever.deltaSuccessProbability * 100, {
                  decimals: 1,
                  sign: true,
                })}
              </p>
              <p className="mt-1 text-xs uppercase tracking-wide text-text-muted">
                {lever.value}
              </p>
              <p className="mt-3 text-sm text-text-muted">{lever.detail}</p>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Drawdown schedule"
        description="Year-by-year spending, income, taxes, early-withdrawal penalties, and withdrawal source mix."
      >
        <div className="overflow-hidden rounded-2xl border border-border/35 bg-surface-muted/10">
          <div className="overflow-auto">
            <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
              <thead className="bg-bg/95 backdrop-blur">
                <tr>
                  {[
                    'Age',
                    'Spend',
                    'Income',
                    'Withdrawal',
                    'Tax est.',
                    'Penalty',
                    'Cash',
                    'Taxable',
                    'Gov 457(b)',
                    'Pre-tax',
                    'Roth',
                    'Ending',
                    'RMD',
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted first:text-left"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {drawdownRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={13}
                      className="px-4 py-10 text-center text-sm text-text-muted"
                    >
                      Drawdown rows will appear after the preview runs.
                    </td>
                  </tr>
                ) : (
                  drawdownRows.map((row) => (
                    <tr key={`${row.calendarYear}-${row.primaryAge}`}>
                      <td className="border-b border-border/20 px-4 py-3 text-left font-medium text-text">
                        {row.primaryAge}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.spendingNeed, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.income, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.grossWithdrawal, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.taxEstimate, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.penaltyEstimate, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.withdrawalsByBucket.cash ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.withdrawalsByBucket.taxable ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(
                            row.withdrawalsByBucket,
                            'governmental_457b',
                          ),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(row.withdrawalsByBucket, 'pre_tax'),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.withdrawalsByBucket.roth ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.endingBalance, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right">
                        {row.rmdApplied ? (
                          <Badge variant="warning">
                            {formatCurrency(row.rmdAmount, { decimals: 0 })}
                          </Badge>
                        ) : (
                          <span className="text-text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
