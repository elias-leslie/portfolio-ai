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
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdFinanceDashboard,
  HouseholdProfileUpdate,
  RetirementPreviewRequest,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  useRetirementPreview,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'

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
const allocationClasses = [
  { key: 'us_equity', label: 'US stocks' },
  { key: 'intl_equity', label: 'Intl stocks' },
  { key: 'bonds', label: 'Bonds' },
  { key: 'cash', label: 'Cash / SPAXX' },
  { key: 'real_estate', label: 'Real estate' },
  { key: 'alts', label: 'Alts' },
] as const
type AllocationMode = 'current' | 'classes' | 'tickers'
const ssa2026TaxableWageBase = 184_500
const ssa2026FirstBendPoint = 1_286
const ssa2026SecondBendPoint = 7_749
const socialSecurityFullRetirementAge = 67
const defaultSocialSecurityPayableRatio = 0.77
const defaultSpaxxYieldPercent = 3.28

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

function householdRetirementAge(
  inputs:
    | {
        primaryAge: number
        spouseAge: number | null
        retirementAge: number
        spouseRetirementAge?: number | null
      }
    | undefined,
) {
  if (!inputs) return 0
  if (inputs.spouseAge == null || inputs.spouseRetirementAge == null) {
    return inputs.retirementAge
  }
  const spousePrimaryAge =
    inputs.primaryAge +
    Math.max(0, inputs.spouseRetirementAge - inputs.spouseAge)
  return Math.max(inputs.retirementAge, spousePrimaryAge)
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

function parsePercentValue(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

function parseOptionalPercentValue(value: string | undefined) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

function allocationDraftFromPreview(
  allocation: Record<string, number> | undefined,
) {
  return Object.fromEntries(
    allocationClasses.map(({ key }) => [
      key,
      assetAllocationValue(allocation, key) === 0
        ? '0'
        : String(Math.round(assetAllocationValue(allocation, key) * 1000) / 10),
    ]),
  ) as Record<(typeof allocationClasses)[number]['key'], string>
}

function allocationFromDraft(
  draft: Record<(typeof allocationClasses)[number]['key'], string>,
) {
  const entries = allocationClasses
    .map(({ key }) => [key, parsePercentValue(draft[key])] as const)
    .filter(([, value]) => value > 0)
  const total = entries.reduce((sum, [, value]) => sum + value, 0)
  if (total <= 0) return null
  return Object.fromEntries(entries.map(([key, value]) => [key, value / total]))
}

function parseTickerMix(value: string) {
  const rows = value
    .split(/\n|,/)
    .map((row) => row.trim())
    .filter(Boolean)
    .map((row) => {
      const [symbol, rawWeight, rawYield] = row.split(/[:=\s]+/)
      const dividendYield = parseOptionalPercentValue(rawYield)
      return {
        symbol: (symbol ?? '').toUpperCase(),
        weight: parsePercentValue(rawWeight ?? ''),
        ...(dividendYield == null ? {} : { dividendYield }),
      }
    })
    .filter((row) => row.symbol && row.weight > 0)
  return rows.length > 0 ? rows : null
}

function camelAssetClassKey(key: string) {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase())
}

function assetAllocationValue(
  allocation: Record<string, number> | undefined,
  key: string,
) {
  return allocation?.[key] ?? allocation?.[camelAssetClassKey(key)] ?? 0
}

function returnAssumptionNumber(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key] ?? assumptions?.[camelAssetClassKey(key)]
  return typeof value === 'number' ? value : null
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
  const profile = dashboard.profile
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
    primaryMonthly: numberInput(
      profile.primarySocialSecurityMonthly ?? primary?.monthlyAmount,
      '0',
    ),
    primaryStartAge: numberInput(
      profile.primarySocialSecurityStartAge ?? primary?.startAge,
      '67',
    ),
    primaryAnnualEarnings: numberInput(
      profile.primarySocialSecurityAnnualEarnings,
      '0',
    ),
    spouseMonthly: numberInput(
      profile.spouseSocialSecurityMonthly ?? spouse?.monthlyAmount,
      '0',
    ),
    spouseStartAge: numberInput(
      profile.spouseSocialSecurityStartAge ?? spouse?.startAge,
      '67',
    ),
    spouseAnnualEarnings: numberInput(
      profile.spouseSocialSecurityAnnualEarnings,
      '0',
    ),
    payableRatio: percentInput(
      profile.socialSecurityPayableRatio,
      String(defaultSocialSecurityPayableRatio * 100),
    ),
  }
}

function defaultDraft(dashboard: HouseholdFinanceDashboard) {
  const monthlySpend =
    dashboard.profile.targetRetirementSpend ||
    dashboard.reports.executive.averageMonthlySpend ||
    6000
  const ages = householdAges(dashboard)
  const socialSecurity = socialSecurityDefaults(dashboard)
  const primaryRetirementAge = dashboard.profile.targetRetirementAge ?? 65
  const spouseRetirementAge =
    dashboard.profile.targetSpouseRetirementAge ??
    (ages.primaryAge != null && ages.spouseAge != null
      ? ages.spouseAge + Math.max(0, primaryRetirementAge - ages.primaryAge)
      : primaryRetirementAge)
  return {
    primaryAge: numberInput(ages.primaryAge, ''),
    spouseAge: numberInput(ages.spouseAge, ''),
    retirementAge: numberInput(primaryRetirementAge, '65'),
    spouseRetirementAge: numberInput(spouseRetirementAge, '65'),
    monthlySpend: numberInput(monthlySpend, '6000'),
    monthlyContribution: numberInput(
      dashboard.profile.monthlySavingsTarget ??
        dashboard.retirementContributionTracker.estimatedMonthlyContributions,
      '0',
    ),
    inflationRate: percentInput(dashboard.profile.retirementInflationRate),
    horizonYears: numberInput(dashboard.profile.retirementHorizonYears, '35'),
    primarySocialSecurityMonthly: socialSecurity.primaryMonthly,
    primarySocialSecurityAnnualEarnings: socialSecurity.primaryAnnualEarnings,
    primarySocialSecurityStartAge: socialSecurity.primaryStartAge,
    spouseSocialSecurityMonthly: socialSecurity.spouseMonthly,
    spouseSocialSecurityAnnualEarnings: socialSecurity.spouseAnnualEarnings,
    spouseSocialSecurityStartAge: socialSecurity.spouseStartAge,
    socialSecurityPayableRatio: socialSecurity.payableRatio,
    cashYield: percentInput(undefined, String(defaultSpaxxYieldPercent)),
  }
}

function buildRequest(
  householdId: string,
  draft: ReturnType<typeof defaultDraft>,
  allocationMode: AllocationMode = 'current',
  allocationDraft?: Record<(typeof allocationClasses)[number]['key'], string>,
  tickerMix = '',
): RetirementPreviewRequest {
  const assetAllocation =
    allocationMode === 'classes' && allocationDraft
      ? allocationFromDraft(allocationDraft)
      : null
  const allocationHoldings =
    allocationMode === 'tickers' ? parseTickerMix(tickerMix) : null
  return {
    householdId,
    assetAllocation,
    allocationHoldings,
    cashYield: parseNumber(draft.cashYield, defaultSpaxxYieldPercent) / 100,
    retirementAge: parseNumber(draft.retirementAge, 65),
    spouseRetirementAge: parseOptionalNumber(draft.spouseRetirementAge),
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
    socialSecurityPayableRatio:
      parseNumber(
        draft.socialSecurityPayableRatio,
        defaultSocialSecurityPayableRatio * 100,
      ) / 100,
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

function taxAssumptionText(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key]
  return typeof value === 'string' ? value : null
}

function taxAssumptionNumber(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key]
  return typeof value === 'number' ? value : null
}

function taxAssumptionWarnings(
  assumptions: Record<string, unknown> | undefined,
) {
  const warnings = assumptions?.warnings
  return Array.isArray(warnings)
    ? warnings.filter(
        (warning): warning is string => typeof warning === 'string',
      )
    : []
}

export function MoneyRetirementPanel({
  dashboard,
  onEditTargets,
}: {
  dashboard: HouseholdFinanceDashboard
  onEditTargets?: () => void
}) {
  const [draft, setDraft] = useState(() => defaultDraft(dashboard))
  const [plannerOpen, setPlannerOpen] = useState(false)
  const [allocationOpen, setAllocationOpen] = useState(false)
  const [allocationMode, setAllocationMode] =
    useState<AllocationMode>('current')
  const [allocationDraft, setAllocationDraft] = useState(() =>
    allocationDraftFromPreview(undefined),
  )
  const [tickerMix, setTickerMix] = useState(
    'VTI 70\nSCHD 10 3.6\nBND 10 4.0\nSPAXX 10',
  )
  const [request, setRequest] = useState<RetirementPreviewRequest>(() =>
    buildRequest(dashboard.profile.id, defaultDraft(dashboard)),
  )
  const updateProfile = useUpdateHouseholdProfile()
  const previewQuery = useRetirementPreview(request)
  const preview = previewQuery.data
  const fullRetirementAge = householdRetirementAge(preview?.inputs)
  const preparedness = dashboard.retirementPreparedness
  const taxWarnings = taxAssumptionWarnings(preview?.taxAssumptions)

  useEffect(() => {
    const nextDraft = defaultDraft(dashboard)
    setDraft(nextDraft)
    setAllocationMode('current')
    setAllocationDraft(allocationDraftFromPreview(undefined))
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
        .filter((row) => row.primaryAge >= fullRetirementAge)
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
    [preview, fullRetirementAge],
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

  const allocationRows = useMemo(
    () =>
      allocationClasses.map(({ key, label }) => ({
        key,
        label,
        value: preview
          ? assetAllocationValue(preview.inputs.assetAllocation, key)
          : null,
      })),
    [preview?.inputs.assetAllocation],
  )
  const allocationDraftTotal = allocationClasses.reduce(
    (sum, { key }) => sum + parsePercentValue(allocationDraft[key]),
    0,
  )

  const drawdownRows = useMemo(
    () =>
      (preview?.drawdownSchedule ?? []).filter(
        (row) => row.primaryAge >= fullRetirementAge,
      ),
    [preview, fullRetirementAge],
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
    const payableRatio =
      parseNumber(
        draft.socialSecurityPayableRatio,
        defaultSocialSecurityPayableRatio * 100,
      ) / 100
    const primaryScheduled =
      primaryManual ??
      estimateSocialSecurityMonthly(
        parseOptionalNumber(draft.primarySocialSecurityAnnualEarnings),
        primaryClaimAge,
      )
    const spouseScheduled =
      spouseManual ??
      estimateSocialSecurityMonthly(
        parseOptionalNumber(draft.spouseSocialSecurityAnnualEarnings),
        spouseClaimAge,
      )
    return {
      primaryScheduled,
      spouseScheduled,
      primary:
        primaryScheduled == null ? null : primaryScheduled * payableRatio,
      spouse: spouseScheduled == null ? null : spouseScheduled * payableRatio,
      primaryClaimAge,
      spouseClaimAge,
      payableRatio,
    }
  }, [draft])
  const modeledExpectedReturn = returnAssumptionNumber(
    preview?.returnAssumptions,
    'expected_return',
  )
  const modeledIncomeYield = returnAssumptionNumber(
    preview?.returnAssumptions,
    'income_yield',
  )
  const modeledCashYield =
    returnAssumptionNumber(preview?.returnAssumptions, 'cash_yield') ??
    parseNumber(draft.cashYield, defaultSpaxxYieldPercent) / 100
  const modeledTaxableIncome = returnAssumptionNumber(
    preview?.returnAssumptions,
    'estimated_taxable_income',
  )
  const modeledTaxDrag = returnAssumptionNumber(
    preview?.returnAssumptions,
    'estimated_income_tax_drag',
  )

  const applyDraft = () => {
    setRequest(
      buildRequest(
        dashboard.profile.id,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
      ),
    )
  }

  const saveDraftDefaults = async () => {
    const profileUpdate: HouseholdProfileUpdate = {
      targetRetirementAge: parseNumber(draft.retirementAge, 65),
      targetSpouseRetirementAge: parseOptionalNumber(draft.spouseRetirementAge),
      targetRetirementSpend: parseNumber(draft.monthlySpend, 6000),
      monthlySavingsTarget: parseNumber(draft.monthlyContribution, 0),
      retirementInflationRate: parseNumber(draft.inflationRate, 2.5) / 100,
      retirementHorizonYears: parseNumber(draft.horizonYears, 35),
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
      socialSecurityPayableRatio:
        parseNumber(
          draft.socialSecurityPayableRatio,
          defaultSocialSecurityPayableRatio * 100,
        ) / 100,
    }
    await updateProfile.mutateAsync(profileUpdate)
    setRequest(
      buildRequest(
        dashboard.profile.id,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
      ),
    )
  }

  const updateDraft = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const updateAllocationDraft = (
    key: (typeof allocationClasses)[number]['key'],
    value: string,
  ) => {
    setAllocationDraft((current) => ({ ...current, [key]: value }))
  }

  const useCurrentAllocation = () => {
    setAllocationMode('classes')
    setAllocationDraft(
      allocationDraftFromPreview(preview?.inputs.assetAllocation),
    )
  }

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Retirement planner"
        description="Plug in the levers, then read the plan through probability, balances, and drawdowns. Tax output is a planning estimate, not tax advice."
        padding={plannerOpen ? 'md' : 'none'}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setPlannerOpen((open) => !open)}
            >
              {plannerOpen ? 'Collapse planner' : 'Expand planner'}
            </Button>
            {plannerOpen ? (
              <>
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
                  variant="outline"
                  onClick={() => void saveDraftDefaults()}
                  disabled={updateProfile.isPending}
                >
                  {updateProfile.isPending ? 'Saving…' : 'Save assumptions'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={applyDraft}
                  disabled={previewQuery.isFetching}
                >
                  {previewQuery.isFetching ? 'Running…' : 'Run preview'}
                </Button>
              </>
            ) : null}
          </div>
        }
      >
        {plannerOpen ? (
          <>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Your retire age
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
                  Spouse retire age
                </p>
                <Input
                  className="mt-2"
                  inputMode="numeric"
                  value={draft.spouseRetirementAge}
                  onChange={(event) =>
                    updateDraft('spouseRetirementAge', event.target.value)
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
                  onChange={(event) =>
                    updateDraft('spouseAge', event.target.value)
                  }
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
                    updateDraft(
                      'primarySocialSecurityMonthly',
                      event.target.value,
                    )
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
                    updateDraft(
                      'primarySocialSecurityStartAge',
                      event.target.value,
                    )
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
                    updateDraft(
                      'spouseSocialSecurityMonthly',
                      event.target.value,
                    )
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
                    updateDraft(
                      'spouseSocialSecurityStartAge',
                      event.target.value,
                    )
                  }
                />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  SS payable %
                </p>
                <Input
                  className="mt-2"
                  inputMode="decimal"
                  value={draft.socialSecurityPayableRatio}
                  onChange={(event) =>
                    updateDraft(
                      'socialSecurityPayableRatio',
                      event.target.value,
                    )
                  }
                />
              </div>
            </div>
            <p className="mt-3 text-xs text-text-muted">
              Drawdown starts when both are retired: your age{' '}
              {fullRetirementAge}.
            </p>
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
              values are rough estimates. Modeled at{' '}
              {formatPercent(socialSecurityEstimate.payableRatio * 100, {
                decimals: 0,
              })}{' '}
              of scheduled benefits after projected trust fund depletion.
            </p>
          </>
        ) : null}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Allocation sandbox"
        description="Run the retirement model against current holdings, an asset-class mix, or a ticker basket like VTI / BND / SPAXX."
        padding={allocationOpen ? 'md' : 'none'}
        actions={
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setAllocationOpen((open) => !open)}
          >
            {allocationOpen ? 'Collapse allocation' : 'Expand allocation'}
          </Button>
        }
      >
        {allocationOpen ? (
          <>
            <div className="flex flex-wrap gap-2">
              {[
                ['current', 'Current portfolio'],
                ['classes', 'Asset classes'],
                ['tickers', 'Ticker basket'],
              ].map(([mode, label]) => (
                <Button
                  key={mode}
                  type="button"
                  size="sm"
                  variant={allocationMode === mode ? 'default' : 'outline'}
                  onClick={() => setAllocationMode(mode as AllocationMode)}
                >
                  {label}
                </Button>
              ))}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={useCurrentAllocation}
              >
                Copy current to sliders
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
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Modeled return
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {modeledExpectedReturn == null
                    ? '—'
                    : formatPercent(modeledExpectedReturn * 100, {
                        decimals: 1,
                      })}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Income yield
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {modeledIncomeYield == null
                    ? '—'
                    : formatPercent(modeledIncomeYield * 100, { decimals: 1 })}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Taxable income
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {modeledTaxableIncome == null
                    ? '—'
                    : formatCurrency(modeledTaxableIncome, { decimals: 0 })}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Income tax drag
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {modeledTaxDrag == null
                    ? '—'
                    : formatCurrency(modeledTaxDrag, { decimals: 0 })}
                </p>
              </div>
              <label className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4 text-xs text-text-muted">
                SPAXX / cash yield %
                <Input
                  className="mt-2"
                  inputMode="decimal"
                  value={draft.cashYield}
                  onChange={(event) =>
                    updateDraft('cashYield', event.target.value)
                  }
                />
                <span className="mt-2 block">
                  Cash buckets and SPAXX ticker rows use{' '}
                  {formatPercent(modeledCashYield * 100, { decimals: 2 })}.
                </span>
              </label>
            </div>
            <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Modeled allocation
                </p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {allocationRows.map((row) => (
                    <div
                      key={row.key}
                      className="flex items-center justify-between rounded-xl border border-border/25 px-3 py-2 text-sm"
                    >
                      <span className="text-text-muted">{row.label}</span>
                      <span className="font-mono text-text">
                        {row.value == null
                          ? '—'
                          : formatPercent(row.value * 100, { decimals: 0 })}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-text-muted">
                  VTI, VOO, SPY, SCHD, VYM, DGRO, JEPI and common stocks map to
                  US stocks; SPAXX/FDRXX/VMFXX/SWVXX map to cash.
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                {allocationMode === 'classes' ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                        Asset-class weights
                      </p>
                      <p className="font-mono text-xs text-text-muted">
                        Total {Math.round(allocationDraftTotal)}%
                      </p>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {allocationClasses.map((assetClass) => (
                        <label
                          key={assetClass.key}
                          className="text-xs text-text-muted"
                        >
                          {assetClass.label}
                          <Input
                            className="mt-1"
                            inputMode="decimal"
                            value={allocationDraft[assetClass.key]}
                            onChange={(event) =>
                              updateAllocationDraft(
                                assetClass.key,
                                event.target.value,
                              )
                            }
                          />
                        </label>
                      ))}
                    </div>
                    <p className="text-xs text-text-muted">
                      Percentages are normalized automatically when you run the
                      preview.
                    </p>
                  </div>
                ) : allocationMode === 'tickers' ? (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Ticker weights
                    </p>
                    <Textarea
                      value={tickerMix}
                      onChange={(event) => setTickerMix(event.target.value)}
                      rows={6}
                      placeholder={'VTI 70\nSCHD 10 3.6\nBND 10 4.0\nSPAXX 10'}
                    />
                    <p className="text-xs text-text-muted">
                      Enter symbol, weight, and optional income yield % per
                      line. Unknown tickers fall back to US stocks.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border/40 p-4 text-sm text-text-muted">
                    Current portfolio mode uses live holdings and fund
                    classification. Switch modes, then Run preview, to compare a
                    what-if allocation.
                  </div>
                )}
              </div>
            </div>
          </>
        ) : null}
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

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
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
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Tax model
            </p>
            <Badge variant={taxWarnings.length > 0 ? 'warning' : 'success'}>
              {taxWarnings.length > 0 ? 'Review' : 'Derived'}
            </Badge>
          </div>
          <p className="mt-3 text-sm font-semibold text-text">
            {taxAssumptionText(preview?.taxAssumptions, 'filingStatusLabel') ??
              'Federal estimate'}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            {taxWarnings[0] ??
              `Std. deduction ${formatCurrencyWhole(
                taxAssumptionNumber(
                  preview?.taxAssumptions,
                  'standardDeduction',
                ),
              )}; LTCG 0% cap ${formatCurrencyWhole(
                taxAssumptionNumber(
                  preview?.taxAssumptions,
                  'capitalGainsZeroRateLimit',
                ),
              )}.`}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Brokerage is modeled before retirement accounts.
          </p>
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
