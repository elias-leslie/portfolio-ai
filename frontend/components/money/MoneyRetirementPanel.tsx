'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { HouseholdHoldingsDialog } from '@/components/money/HouseholdHoldingsDialog'
import { freshnessToneClass } from '@/components/money/moneyAccountsUtils'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdFinanceDashboard,
  HouseholdProfileUpdate,
  RetirementAccountRule,
  RetirementAllocationScenario,
  RetirementAllocationScenarioInput,
  RetirementCollegeYear,
  RetirementPreviewRequest,
  RetirementWithdrawalConfig,
} from '@/lib/api/household'
import { fetchRetirementPreview } from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useDebounce } from '@/lib/hooks/useDebounce'
import {
  useAllocationScenarios,
  useReplaceAllocationScenarios,
  useRetirementPreview,
  useUpdateHouseholdPlanning,
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
  bridge: 'var(--color-chart-cyan)',
  other: 'var(--color-chart-6)',
}

const bucketOrder = [
  'cash',
  'taxable',
  'governmental_457b',
  'pre_tax',
  'roth',
  'hsa',
  'bridge',
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
const ssaAssumedCareerStartAge = 22
const defaultSocialSecurityPayableRatio = 0.77
const defaultSpaxxYieldPercent = 3.28
const defaultSpaxxYieldSource = 'Fidelity SPAXX 7-day yield as of 2026-05-07'

function previewStatusVariant(
  successProbability: number,
  trustedTotals: boolean,
) {
  if (!trustedTotals) return 'warning' as const
  if (successProbability >= 0.8) return 'success' as const
  if (successProbability >= 0.6) return 'warning' as const
  return 'destructive' as const
}

function holdingsCoverageVariant(status: string | undefined) {
  if (status === 'exact') return 'success' as const
  if (status === 'partial') return 'warning' as const
  if (status === 'account_value_only') return 'warning' as const
  return 'outline' as const
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
    case 'bridge':
      return 'Bridge sleeve'
    default:
      return formatEnumLabel(value)
  }
}

function bucketMapValue(values: Record<string, number>, bucket: string) {
  if (bucket === 'pre_tax') return values.pre_tax ?? values.preTax ?? 0
  if (bucket === 'governmental_457b') {
    // es-toolkit camelizes the API key to governmental457B (capital B).
    return (
      values.governmental_457b ??
      values.governmental457b ??
      values.governmental457B ??
      0
    )
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

function returnAssumptionText(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key] ?? assumptions?.[camelAssetClassKey(key)]
  return typeof value === 'string' ? value : null
}

function estimateSocialSecurityMonthly(
  annualEarnings: number | null,
  claimAge: number,
  stopWorkAge?: number | null,
) {
  if (annualEarnings == null || annualEarnings <= 0) return null
  let aime = Math.min(annualEarnings, ssa2026TaxableWageBase) / 12
  if (stopWorkAge != null) {
    // AIME averages the best 35 years; an early retiree fills the missing
    // years with zeros (career assumed to start at 22).
    const yearsWorked = Math.max(
      0,
      Math.min(stopWorkAge, claimAge) - ssaAssumedCareerStartAge,
    )
    aime *= Math.min(yearsWorked, 35) / 35
  }
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

type WithdrawalDraft = {
  strategy: 'vpw' | 'guardrails'
  initialRatePct: string
  declineMode: 'smooth' | 'phase'
  declineRate: number
  phaseSlowGoAge: string
  phaseNoGoAge: string
  phaseGoGoPct: string
  phaseSlowGoPct: string
  phaseNoGoPct: string
  bridgeMode: 'auto' | 'manual'
  bridgeManualAmount: string
  bridgeRealReturnPct: string
  bridgeGrowth: 'fixed' | 'portfolio'
  healthcare: Array<{ age: string; realAmount: string }>
  college: Array<{ calendarYear: string; realAmount: string }>
}

function defaultWithdrawalDraft(
  dashboard: HouseholdFinanceDashboard,
): WithdrawalDraft {
  const profile = dashboard.profile
  const schedule = dashboard.planning?.retirementHealthcareSchedule ?? []
  return {
    strategy:
      profile.withdrawalStrategy === 'guardrails' ? 'guardrails' : 'vpw',
    initialRatePct: percentInput(profile.withdrawalInitialRate, '5'),
    declineMode: profile.withdrawalDeclineMode === 'phase' ? 'phase' : 'smooth',
    declineRate: profile.discretionaryDeclineRate ?? 0.01,
    phaseSlowGoAge: numberInput(profile.phaseSlowGoAge, '75'),
    phaseNoGoAge: numberInput(profile.phaseNoGoAge, '85'),
    phaseGoGoPct: percentInput(profile.phaseGoGoPct, '100'),
    phaseSlowGoPct: percentInput(profile.phaseSlowGoPct, '85'),
    phaseNoGoPct: percentInput(profile.phaseNoGoPct, '75'),
    bridgeMode: profile.bridgeMode === 'manual' ? 'manual' : 'auto',
    bridgeManualAmount: numberInput(profile.bridgeManualAmount, '0'),
    bridgeRealReturnPct: percentInput(profile.bridgeRealReturn, '1'),
    bridgeGrowth: profile.bridgeGrowth === 'portfolio' ? 'portfolio' : 'fixed',
    healthcare: schedule.map((row) => ({
      age: String(row.age),
      realAmount: String(Math.round(row.realAmount)),
    })),
    college: (dashboard.planning?.retirementCollegeSchedule ?? []).map(
      (row) => ({
        calendarYear: String(row.calendarYear),
        realAmount: String(Math.round(row.realAmount)),
      }),
    ),
  }
}

function collegeScheduleFromDraft(
  withdrawal: WithdrawalDraft,
): RetirementCollegeYear[] {
  return withdrawal.college
    .map((row) => ({
      calendarYear: Math.round(parseNumber(row.calendarYear, 0)),
      realAmount: parseNumber(row.realAmount, 0),
    }))
    .filter(
      (row) =>
        row.calendarYear >= 1900 &&
        row.calendarYear <= 2200 &&
        row.realAmount >= 0,
    )
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function withdrawalConfigFromDraft(
  withdrawal: WithdrawalDraft,
): RetirementWithdrawalConfig {
  return {
    strategy: withdrawal.strategy,
    initialRate: clamp(parseNumber(withdrawal.initialRatePct, 5) / 100, 0, 0.2),
    declineMode: withdrawal.declineMode,
    discretionaryDeclineRate: clamp(withdrawal.declineRate, 0, 0.025),
    phase: {
      slowGoAge: clamp(parseNumber(withdrawal.phaseSlowGoAge, 75), 40, 110),
      noGoAge: clamp(parseNumber(withdrawal.phaseNoGoAge, 85), 40, 120),
      goGoPct: clamp(parseNumber(withdrawal.phaseGoGoPct, 100) / 100, 0, 1.5),
      slowGoPct: clamp(
        parseNumber(withdrawal.phaseSlowGoPct, 85) / 100,
        0,
        1.5,
      ),
      noGoPct: clamp(parseNumber(withdrawal.phaseNoGoPct, 75) / 100, 0, 1.5),
    },
    bridge: {
      mode: withdrawal.bridgeMode,
      manualAmount:
        withdrawal.bridgeMode === 'manual'
          ? Math.max(parseNumber(withdrawal.bridgeManualAmount, 0), 0)
          : null,
      realReturn: clamp(
        parseNumber(withdrawal.bridgeRealReturnPct, 1) / 100,
        -0.05,
        0.1,
      ),
      growth: withdrawal.bridgeGrowth,
    },
    healthcareSchedule: withdrawal.healthcare
      .map((row) => ({
        age: Math.round(parseNumber(row.age, 0)),
        realAmount: parseNumber(row.realAmount, 0),
      }))
      .filter((row) => row.age >= 18 && row.age <= 120 && row.realAmount >= 0),
    essentialFloor: null,
    baseDiscretionary: null,
  }
}

function buildRequest(
  householdId: string,
  draft: ReturnType<typeof defaultDraft>,
  allocationMode: AllocationMode = 'current',
  allocationDraft?: Record<(typeof allocationClasses)[number]['key'], string>,
  tickerMix = '',
  withdrawal?: WithdrawalDraft,
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
    withdrawal: withdrawal ? withdrawalConfigFromDraft(withdrawal) : null,
    collegeSchedule: withdrawal ? collegeScheduleFromDraft(withdrawal) : null,
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

function taxAssumptionTooltip(
  assumptions: Record<string, unknown> | undefined,
  warnings: string[],
) {
  const filingStatus =
    taxAssumptionText(assumptions, 'filingStatusLabel') ?? 'Federal estimate'
  const warning = warnings[0]
  if (warning) return `${filingStatus}. ${warning}`

  return `${filingStatus}. Standard deduction ${formatCurrencyWhole(
    taxAssumptionNumber(assumptions, 'standardDeduction'),
  )}; LTCG 0% cap ${formatCurrencyWhole(
    taxAssumptionNumber(assumptions, 'capitalGainsZeroRateLimit'),
  )}. Brokerage is modeled before retirement accounts.`
}

function socialSecuritySourceLabel(
  scheduled: number | null,
  manualMonthly: number | null,
) {
  if (manualMonthly != null) return 'manual monthly estimate'
  if (scheduled != null)
    return 'rough salary estimate, earnings stop at retirement'
  return 'not included'
}

export function MoneyRetirementPanel({
  dashboard,
  onEditTargets,
}: {
  dashboard: HouseholdFinanceDashboard
  onEditTargets?: () => void
}) {
  const [draft, setDraft] = useState(() => defaultDraft(dashboard))
  const [withdrawalDraft, setWithdrawalDraft] = useState(() =>
    defaultWithdrawalDraft(dashboard),
  )
  const [plannerOpen, setPlannerOpen] = useState(false)
  const [withdrawalOpen, setWithdrawalOpen] = useState(true)
  const [allocationOpen, setAllocationOpen] = useState(false)
  const [accountDetailsOpen, setAccountDetailsOpen] = useState(false)
  const [drawdownBasis, setDrawdownBasis] = useState<'real' | 'nominal'>('real')
  const [holdingsDialogAccount, setHoldingsDialogAccount] = useState<{
    householdAccountId: string
    label: string
    currentValue: number
  } | null>(null)
  const [allocationMode, setAllocationMode] =
    useState<AllocationMode>('current')
  const [allocationDraft, setAllocationDraft] = useState(() =>
    allocationDraftFromPreview(undefined),
  )
  const [tickerMix, setTickerMix] = useState(
    'VTI 70\nSCHD 10 3.6\nBND 10 4.0\nSPAXX 10',
  )
  const scenariosQuery = useAllocationScenarios()
  const replaceScenarios = useReplaceAllocationScenarios()
  const [scenarioName, setScenarioName] = useState('')
  const [compareSelection, setCompareSelection] = useState<string[]>([])
  const [compareResults, setCompareResults] = useState<Array<{
    name: string
    success: number
    medianEnding: number
    depletionAge: number | null
  }> | null>(null)
  const [compareRunning, setCompareRunning] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [request, setRequest] = useState<RetirementPreviewRequest>(() =>
    buildRequest(
      dashboard.profile.id,
      defaultDraft(dashboard),
      'current',
      undefined,
      '',
      defaultWithdrawalDraft(dashboard),
    ),
  )
  const updateProfile = useUpdateHouseholdProfile()
  const updatePlanning = useUpdateHouseholdPlanning()
  const previewQuery = useRetirementPreview(request)
  const preview = previewQuery.data
  // Withdrawal-plan knobs re-project live (debounced); the other planner
  // inputs still wait for an explicit "Run preview".
  const debouncedWithdrawal = useDebounce(withdrawalDraft, 250)
  useEffect(() => {
    setRequest((current) => ({
      ...current,
      withdrawal: withdrawalConfigFromDraft(debouncedWithdrawal),
    }))
  }, [debouncedWithdrawal])
  const pendingRequest = useMemo(
    () =>
      buildRequest(
        dashboard.profile.id,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
      ),
    [
      dashboard.profile.id,
      draft,
      allocationMode,
      allocationDraft,
      tickerMix,
      withdrawalDraft,
    ],
  )
  // Edits update `draft`/allocation state but only "Run preview" pushes them
  // into `request` (the query key), so results can lag the inputs. Flag that
  // gap so the displayed plan isn't silently mistaken for the current knobs.
  const hasPendingChanges = useMemo(
    () => JSON.stringify(pendingRequest) !== JSON.stringify(request),
    [pendingRequest, request],
  )
  const fullRetirementAge = householdRetirementAge(preview?.inputs)
  const taxWarnings = taxAssumptionWarnings(preview?.taxAssumptions)
  const taxEstimateTooltip = taxAssumptionTooltip(
    preview?.taxAssumptions,
    taxWarnings,
  )

  useEffect(() => {
    const nextDraft = defaultDraft(dashboard)
    const nextWithdrawal = defaultWithdrawalDraft(dashboard)
    setDraft(nextDraft)
    setWithdrawalDraft(nextWithdrawal)
    setAllocationMode('current')
    setAllocationDraft(allocationDraftFromPreview(undefined))
    setAccountDetailsOpen(false)
    setRequest(
      buildRequest(
        dashboard.profile.id,
        nextDraft,
        'current',
        undefined,
        '',
        nextWithdrawal,
      ),
    )
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
        bridge: bucketMapValue(row.balancesByBucket, 'bridge'),
        other: bucketMapValue(row.balancesByBucket, 'other'),
      })),
    [preview?.drawdownSchedule],
  )

  const failureAgeData = useMemo(() => {
    const entries = Object.entries(preview?.failureAgeDistribution ?? {})
    const totalFailures = entries.reduce((sum, [, count]) => sum + count, 0)
    if (totalFailures === 0) return []
    // Counts are per failed trial; rescale so bars read as % of all trials.
    const failedShare = 1 - (preview?.successProbability ?? 1)
    return entries
      .map(([age, count]) => ({
        age: Number(age),
        share: (count / totalFailures) * failedShare * 100,
      }))
      .sort((a, b) => a.age - b.age)
  }, [preview?.failureAgeDistribution, preview?.successProbability])

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
  const holdingsCoverage = preview?.holdingsCoverage ?? null
  const accountAllocationCoverage = preview?.accountAllocationCoverage ?? null

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

  // Drawdown table rows in the chosen dollar basis. Backend rows are nominal
  // except the engine-decision block (real); the deterministic schedule uses a
  // constant inflation rate, so (1+i)^yearIndex converts exactly both ways.
  // Spend is the spending actually funded (income + bridge + net withdrawal,
  // minus portfolio-paid college) — the engine's target can exceed it in
  // capacity-trimmed years, and RMD-forced surplus is reinvested, not spent.
  const drawdownTableRows = useMemo(() => {
    const inflation = preview?.inputs.inflationRate ?? 0
    return drawdownRows.map((row) => {
      const factor = (1 + inflation) ** row.yearIndex
      const scale = drawdownBasis === 'real' ? 1 / factor : 1
      const bridgeNominal = row.bridgeDraw * factor
      const collegeNominal =
        Math.max(0, row.collegeCost - row.college529Draw) * factor
      const targetNominal = row.spendingTarget * factor
      const spendNominal = Math.min(
        targetNominal,
        Math.max(
          0,
          row.income + bridgeNominal + row.netWithdrawal - collegeNominal,
        ),
      )
      return {
        ...row,
        displaySpend: spendNominal * scale,
        displayTarget: targetNominal * scale,
        spendTrimmed: targetNominal - spendNominal > 1,
        displayIncome: row.income * scale,
        displayBridge: bridgeNominal * scale,
        displayCollege: collegeNominal * scale,
        displayGross: row.grossWithdrawal * scale,
        displayTax: row.taxEstimate * scale,
        displayPenalty: row.penaltyEstimate * scale,
        displayEnding: row.endingBalance * scale,
        displayRmd: row.rmdAmount * scale,
        displayBuckets: Object.fromEntries(
          Object.entries(row.withdrawalsByBucket).map(([key, value]) => [
            key,
            value * scale,
          ]),
        ),
      }
    })
  }, [drawdownRows, drawdownBasis, preview?.inputs.inflationRate])
  const drawdownHasBridge = drawdownTableRows.some(
    (row) => row.displayBridge > 0.5,
  )
  const drawdownHasCollege = drawdownTableRows.some(
    (row) => row.displayCollege > 0.5,
  )
  const drawdownColumnCount =
    13 + (drawdownHasBridge ? 1 : 0) + (drawdownHasCollege ? 1 : 0)

  // Spending smile in real dollars: stacked funding sources vs floor/target,
  // mirrors withdrawalData's retirement-rows windowing.
  const spendingPathData = useMemo(() => {
    const medianPath = preview?.medianDiscretionaryPath ?? []
    const baseAge = preview?.inputs.primaryAge ?? 0
    return (preview?.drawdownSchedule ?? [])
      .filter((row) => row.primaryAge >= fullRetirementAge)
      .slice(0, 35)
      .map((row) => ({
        age: row.primaryAge,
        guaranteed: row.guaranteedIncome,
        bridge: row.bridgeDraw,
        portfolio: row.portfolioDraw,
        floor: row.floorAmount,
        target: row.spendingTarget,
        medianDiscretionary: medianPath[row.primaryAge - baseAge] ?? null,
      }))
  }, [preview, fullRetirementAge])

  const withdrawalSummary = {
    bridgeSize: returnAssumptionNumber(
      preview?.returnAssumptions,
      'bridge_size',
    ),
    bridgeYears: returnAssumptionNumber(
      preview?.returnAssumptions,
      'bridge_length_years',
    ),
    firstYearRate: returnAssumptionNumber(
      preview?.returnAssumptions,
      'first_year_withdrawal_rate',
    ),
    postSocialSecurityRate: returnAssumptionNumber(
      preview?.returnAssumptions,
      'post_social_security_withdrawal_rate',
    ),
  }

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
    const stopWorkAge = parseOptionalNumber(draft.retirementAge)
    const spouseStopWorkAge =
      parseOptionalNumber(draft.spouseRetirementAge) ?? stopWorkAge
    const primaryScheduled =
      primaryManual ??
      estimateSocialSecurityMonthly(
        parseOptionalNumber(draft.primarySocialSecurityAnnualEarnings),
        primaryClaimAge,
        stopWorkAge,
      )
    const spouseScheduled =
      spouseManual ??
      estimateSocialSecurityMonthly(
        parseOptionalNumber(draft.spouseSocialSecurityAnnualEarnings),
        spouseClaimAge,
        spouseStopWorkAge,
      )
    return {
      primaryScheduled,
      spouseScheduled,
      primary:
        primaryScheduled == null ? null : primaryScheduled * payableRatio,
      spouse: spouseScheduled == null ? null : spouseScheduled * payableRatio,
      primarySource: socialSecuritySourceLabel(primaryScheduled, primaryManual),
      spouseSource: socialSecuritySourceLabel(spouseScheduled, spouseManual),
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
  const modeledCashYieldSource =
    returnAssumptionText(preview?.returnAssumptions, 'cash_yield_source') ??
    defaultSpaxxYieldSource
  const modeledTaxableIncome = returnAssumptionNumber(
    preview?.returnAssumptions,
    'estimated_taxable_income',
  )
  const modeledTaxDrag = returnAssumptionNumber(
    preview?.returnAssumptions,
    'estimated_income_tax_drag',
  )
  const incomeYieldFreshnessStatus = returnAssumptionText(
    preview?.returnAssumptions,
    'income_yield_freshness_status',
  )
  const incomeYieldFreshnessLabel = returnAssumptionText(
    preview?.returnAssumptions,
    'income_yield_freshness_label',
  )
  const cashYieldFreshnessStatus = returnAssumptionText(
    preview?.returnAssumptions,
    'cash_yield_freshness_status',
  )
  const cashYieldFreshnessLabel = returnAssumptionText(
    preview?.returnAssumptions,
    'cash_yield_freshness_label',
  )
  const gainRatioSource = taxAssumptionText(
    preview?.taxAssumptions,
    'taxableWithdrawalGainRatioSource',
  )
  const gainRatioDetail = taxAssumptionText(
    preview?.taxAssumptions,
    'taxableWithdrawalGainRatioDetail',
  )
  const accountRules: RetirementAccountRule[] = preview?.accountRules ?? []

  const applyDraft = () => {
    setRequest(
      buildRequest(
        dashboard.profile.id,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
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
      withdrawalStrategy: withdrawalDraft.strategy,
      withdrawalInitialRate: clamp(
        parseNumber(withdrawalDraft.initialRatePct, 5) / 100,
        0,
        0.2,
      ),
      withdrawalDeclineMode: withdrawalDraft.declineMode,
      discretionaryDeclineRate: clamp(withdrawalDraft.declineRate, 0, 0.025),
      phaseSlowGoAge: clamp(
        parseNumber(withdrawalDraft.phaseSlowGoAge, 75),
        40,
        110,
      ),
      phaseNoGoAge: clamp(
        parseNumber(withdrawalDraft.phaseNoGoAge, 85),
        40,
        120,
      ),
      phaseGoGoPct: clamp(
        parseNumber(withdrawalDraft.phaseGoGoPct, 100) / 100,
        0,
        1.5,
      ),
      phaseSlowGoPct: clamp(
        parseNumber(withdrawalDraft.phaseSlowGoPct, 85) / 100,
        0,
        1.5,
      ),
      phaseNoGoPct: clamp(
        parseNumber(withdrawalDraft.phaseNoGoPct, 75) / 100,
        0,
        1.5,
      ),
      bridgeMode: withdrawalDraft.bridgeMode,
      bridgeManualAmount:
        withdrawalDraft.bridgeMode === 'manual'
          ? Math.max(parseNumber(withdrawalDraft.bridgeManualAmount, 0), 0)
          : null,
      bridgeRealReturn: clamp(
        parseNumber(withdrawalDraft.bridgeRealReturnPct, 1) / 100,
        -0.05,
        0.1,
      ),
      bridgeGrowth: withdrawalDraft.bridgeGrowth,
    }
    await updateProfile.mutateAsync(profileUpdate)
    await updatePlanning.mutateAsync({
      retirementHealthcareSchedule: withdrawalConfigFromDraft(
        withdrawalDraft,
      ).healthcareSchedule.map((row) => ({
        age: row.age,
        realAmount: row.realAmount,
      })),
      retirementCollegeSchedule: collegeScheduleFromDraft(withdrawalDraft),
    })
    setRequest(
      buildRequest(
        dashboard.profile.id,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
      ),
    )
  }

  const updateDraft = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const updateWithdrawalDraft = <K extends keyof WithdrawalDraft>(
    key: K,
    value: WithdrawalDraft[K],
  ) => {
    setWithdrawalDraft((current) => ({ ...current, [key]: value }))
  }

  const scenarioInputs = (
    rows: RetirementAllocationScenario[],
  ): RetirementAllocationScenarioInput[] =>
    rows.map((row) => ({
      id: row.id,
      name: row.name,
      holdings: row.holdings,
      bridgeGrowth: row.bridgeGrowth ?? null,
      bridgeRealReturn: row.bridgeRealReturn ?? null,
      notes: row.notes ?? null,
    }))

  const saveScenarioFromMix = async () => {
    const name = scenarioName.trim()
    const holdings = (parseTickerMix(tickerMix) ?? []).map(
      ({ symbol, weight }) => ({ symbol, weight }),
    )
    if (!name || holdings.length === 0) return
    const existing = scenarioInputs(scenariosQuery.data ?? []).filter(
      (row) => row.name.trim().toLowerCase() !== name.toLowerCase(),
    )
    await replaceScenarios.mutateAsync([
      ...existing,
      {
        name,
        holdings,
        bridgeGrowth: withdrawalDraft.bridgeGrowth,
        bridgeRealReturn: clamp(
          parseNumber(withdrawalDraft.bridgeRealReturnPct, 1) / 100,
          -0.05,
          0.1,
        ),
      },
    ])
    setScenarioName('')
  }

  const loadScenario = (scenario: RetirementAllocationScenario) => {
    setTickerMix(
      scenario.holdings.map((row) => `${row.symbol} ${row.weight}`).join('\n'),
    )
    setAllocationMode('tickers')
    setWithdrawalDraft((current) => ({
      ...current,
      bridgeGrowth: scenario.bridgeGrowth ?? current.bridgeGrowth,
      bridgeRealReturnPct:
        scenario.bridgeRealReturn != null
          ? String(scenario.bridgeRealReturn * 100)
          : current.bridgeRealReturnPct,
    }))
  }

  const deleteScenario = async (id: string) => {
    await replaceScenarios.mutateAsync(
      scenarioInputs(scenariosQuery.data ?? []).filter((row) => row.id !== id),
    )
    setCompareSelection((current) => current.filter((item) => item !== id))
  }

  const runCompare = async () => {
    const selected = (scenariosQuery.data ?? []).filter((row) =>
      compareSelection.includes(row.id),
    )
    setCompareRunning(true)
    setCompareError(null)
    try {
      const base = buildRequest(
        dashboard.profile.id,
        draft,
        'current',
        undefined,
        '',
        withdrawalDraft,
      )
      const targets = [
        { name: 'Current accounts', request: base },
        ...selected.map((scenario) => ({
          name: scenario.name,
          request: {
            ...base,
            allocationHoldings: scenario.holdings,
            withdrawal: base.withdrawal
              ? {
                  ...base.withdrawal,
                  bridge: {
                    ...base.withdrawal.bridge,
                    growth:
                      scenario.bridgeGrowth ?? base.withdrawal.bridge.growth,
                    realReturn:
                      scenario.bridgeRealReturn ??
                      base.withdrawal.bridge.realReturn,
                  },
                }
              : base.withdrawal,
          },
        })),
      ]
      const results = await Promise.all(
        targets.map(async (target) => {
          const result = await fetchRetirementPreview(target.request)
          return {
            name: target.name,
            success: result.successProbability,
            medianEnding: result.medianEndingBalance,
            depletionAge: result.firstDepletionAge ?? null,
          }
        }),
      )
      setCompareResults(results)
    } catch (error) {
      setCompareError(
        error instanceof Error ? error.message : 'Comparison failed',
      )
    } finally {
      setCompareRunning(false)
    }
  }

  const updateHealthcareRow = (
    index: number,
    key: 'age' | 'realAmount',
    value: string,
  ) => {
    setWithdrawalDraft((current) => ({
      ...current,
      healthcare: current.healthcare.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    }))
  }

  const addHealthcareRow = () => {
    setWithdrawalDraft((current) => ({
      ...current,
      healthcare: [...current.healthcare, { age: '65', realAmount: '6000' }],
    }))
  }

  const removeHealthcareRow = (index: number) => {
    setWithdrawalDraft((current) => ({
      ...current,
      healthcare: current.healthcare.filter(
        (_, rowIndex) => rowIndex !== index,
      ),
    }))
  }

  const updateCollegeRow = (
    index: number,
    key: 'calendarYear' | 'realAmount',
    value: string,
  ) => {
    setWithdrawalDraft((current) => ({
      ...current,
      college: current.college.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    }))
  }

  const addCollegeRow = () => {
    setWithdrawalDraft((current) => ({
      ...current,
      college: [
        ...current.college,
        {
          calendarYear: String(new Date().getFullYear() + 4),
          realAmount: '8000',
        },
      ],
    }))
  }

  const removeCollegeRow = (index: number) => {
    setWithdrawalDraft((current) => ({
      ...current,
      college: current.college.filter((_, rowIndex) => rowIndex !== index),
    }))
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
                  {previewQuery.isFetching
                    ? 'Running…'
                    : hasPendingChanges
                      ? 'Run preview •'
                      : 'Run preview'}
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
                  aria-label="Your retirement age"
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
                  aria-label="Spouse retirement age"
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
                  aria-label="Monthly spend in retirement"
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
                  aria-label="Monthly savings contribution"
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
                  aria-label="Inflation rate percent"
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
                  aria-label="Planning horizon in years"
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
                  aria-label="Your current age"
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
                  aria-label="Spouse current age"
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
                  aria-label="Your annual salary for Social Security estimate"
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
                  aria-label="Your monthly Social Security benefit"
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
                  aria-label="Your Social Security claim age"
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
                  aria-label="Spouse annual salary for Social Security estimate"
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
                  aria-label="Spouse monthly Social Security benefit"
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
                  aria-label="Spouse Social Security claim age"
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
                  aria-label="Social Security payable percent after trust fund depletion"
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
            <p className="mt-2 text-xs text-text-muted">
              Social Security sources:{' '}
              <span className="font-medium text-text">
                primary: {socialSecurityEstimate.primarySource}
              </span>
              ;{' '}
              <span className="font-medium text-text">
                spouse: {socialSecurityEstimate.spouseSource}
              </span>
              . Salary estimates assume earnings start at 22 and stop at your
              retirement age (zeros fill the rest of the 35-year average). For
              planning-grade accuracy, enter the monthly benefit from ssa.gov
              &ldquo;Plan for Retirement&rdquo; with average future annual
              salary set to $0.
            </p>
          </>
        ) : null}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Withdrawal plan"
        description="Floor-and-upside spending: guaranteed income plus a bridge sleeve cover essentials, the portfolio funds discretionary spend that declines with age. Amounts are in today's dollars."
        padding={withdrawalOpen ? 'md' : 'none'}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setWithdrawalOpen((open) => !open)}
            >
              {withdrawalOpen ? 'Collapse plan' : 'Expand plan'}
            </Button>
            {withdrawalOpen ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void saveDraftDefaults()}
                disabled={updateProfile.isPending || updatePlanning.isPending}
              >
                {updateProfile.isPending || updatePlanning.isPending
                  ? 'Saving…'
                  : 'Save plan'}
              </Button>
            ) : null}
          </div>
        }
      >
        {withdrawalOpen ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Upside strategy
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(
                    [
                      ['vpw', 'VPW'],
                      ['guardrails', 'Guardrails'],
                    ] as const
                  ).map(([value, label]) => (
                    <Button
                      key={value}
                      type="button"
                      size="sm"
                      variant={
                        withdrawalDraft.strategy === value
                          ? 'default'
                          : 'outline'
                      }
                      onClick={() => updateWithdrawalDraft('strategy', value)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                {withdrawalDraft.strategy === 'guardrails' ? (
                  <label className="mt-3 block text-xs text-text-muted">
                    Initial withdrawal rate %
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      aria-label="Guardrails initial withdrawal rate percent"
                      value={withdrawalDraft.initialRatePct}
                      onChange={(event) =>
                        updateWithdrawalDraft(
                          'initialRatePct',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                ) : (
                  <p className="mt-3 text-xs text-text-muted">
                    VPW sizes each year&apos;s draw from remaining capital and
                    horizon, so spending can never deplete early.
                  </p>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Discretionary decline
                  </p>
                  <span className="font-mono text-xs text-text">
                    {formatPercent(withdrawalDraft.declineRate * 100, {
                      decimals: 1,
                    })}
                    /yr
                  </span>
                </div>
                <Slider
                  className="mt-3"
                  aria-label="Discretionary decline rate per year"
                  min={0}
                  max={0.025}
                  step={0.001}
                  value={[withdrawalDraft.declineRate]}
                  onValueChange={(values) =>
                    updateWithdrawalDraft('declineRate', values[0] ?? 0.01)
                  }
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {(
                    [
                      ['smooth', 'Smooth'],
                      ['phase', 'Go-go phases'],
                    ] as const
                  ).map(([value, label]) => (
                    <Button
                      key={value}
                      type="button"
                      size="sm"
                      variant={
                        withdrawalDraft.declineMode === value
                          ? 'default'
                          : 'outline'
                      }
                      onClick={() =>
                        updateWithdrawalDraft('declineMode', value)
                      }
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                {withdrawalDraft.declineMode === 'phase' ? (
                  <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {(
                      [
                        ['phaseSlowGoAge', 'Slow-go age'],
                        ['phaseNoGoAge', 'No-go age'],
                        ['phaseGoGoPct', 'Go-go %'],
                        ['phaseSlowGoPct', 'Slow-go %'],
                        ['phaseNoGoPct', 'No-go %'],
                      ] as const
                    ).map(([key, label]) => (
                      <label key={key} className="text-xs text-text-muted">
                        {label}
                        <Input
                          className="mt-1"
                          inputMode="numeric"
                          aria-label={label}
                          value={withdrawalDraft[key]}
                          onChange={(event) =>
                            updateWithdrawalDraft(key, event.target.value)
                          }
                        />
                      </label>
                    ))}
                  </div>
                ) : null}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Social Security bridge
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(
                    [
                      ['auto', 'Auto size'],
                      ['manual', 'Manual'],
                    ] as const
                  ).map(([value, label]) => (
                    <Button
                      key={value}
                      type="button"
                      size="sm"
                      variant={
                        withdrawalDraft.bridgeMode === value
                          ? 'default'
                          : 'outline'
                      }
                      onClick={() => updateWithdrawalDraft('bridgeMode', value)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {withdrawalDraft.bridgeMode === 'manual' ? (
                    <label className="text-xs text-text-muted">
                      Bridge amount $
                      <Input
                        className="mt-1"
                        inputMode="decimal"
                        aria-label="Manual bridge amount"
                        value={withdrawalDraft.bridgeManualAmount}
                        onChange={(event) =>
                          updateWithdrawalDraft(
                            'bridgeManualAmount',
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ) : null}
                  {withdrawalDraft.bridgeGrowth === 'fixed' ? (
                    <label className="text-xs text-text-muted">
                      Bridge real return %
                      <Input
                        className="mt-1"
                        inputMode="decimal"
                        aria-label="Bridge sleeve real return percent"
                        value={withdrawalDraft.bridgeRealReturnPct}
                        onChange={(event) =>
                          updateWithdrawalDraft(
                            'bridgeRealReturnPct',
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ) : null}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(
                    [
                      ['fixed', 'Conservative (fixed return)'],
                      ['portfolio', 'Invested with portfolio'],
                    ] as const
                  ).map(([value, label]) => (
                    <Button
                      key={value}
                      type="button"
                      size="sm"
                      variant={
                        withdrawalDraft.bridgeGrowth === value
                          ? 'default'
                          : 'outline'
                      }
                      onClick={() =>
                        updateWithdrawalDraft('bridgeGrowth', value)
                      }
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  Auto sizes the sleeve to cover essential-floor gaps from
                  retirement until Social Security starts. Conservative grows
                  the sleeve at the fixed real return; invested lets it ride the
                  simulated portfolio returns, sequence risk included.
                </p>
              </div>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Healthcare / LTC schedule (annual, today&apos;s dollars)
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={addHealthcareRow}
                >
                  Add line
                </Button>
              </div>
              {withdrawalDraft.healthcare.length === 0 ? (
                <p className="mt-2 text-xs text-text-muted">
                  No healthcare lines yet — the floor then has no healthcare
                  carve-out. Add lines like pre-Medicare premiums at 62 or LTC
                  reserves at 85.
                </p>
              ) : (
                <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {withdrawalDraft.healthcare.map((row, index) => (
                    <div
                      key={index}
                      className="flex items-end gap-2 rounded-xl border border-border/25 px-3 py-2"
                    >
                      <label className="text-xs text-text-muted">
                        From age
                        <Input
                          className="mt-1"
                          inputMode="numeric"
                          aria-label={`Healthcare line ${index + 1} age`}
                          value={row.age}
                          onChange={(event) =>
                            updateHealthcareRow(
                              index,
                              'age',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label className="text-xs text-text-muted">
                        Annual $
                        <Input
                          className="mt-1"
                          inputMode="decimal"
                          aria-label={`Healthcare line ${index + 1} annual amount`}
                          value={row.realAmount}
                          onChange={(event) =>
                            updateHealthcareRow(
                              index,
                              'realAmount',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => removeHealthcareRow(index)}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  College schedule (annual, today&apos;s dollars)
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={addCollegeRow}
                >
                  Add line
                </Button>
              </div>
              <p className="mt-2 text-xs text-text-muted">
                529 accounts
                {preview?.inputs.college529Value
                  ? ` (${formatCurrencyWhole(preview.inputs.college529Value)})`
                  : ''}{' '}
                are earmarked for college and excluded from the retirement
                portfolio; each year&apos;s college spend drains them first and
                only the overflow hits retirement money.
              </p>
              {withdrawalDraft.college.length === 0 ? (
                <p className="mt-2 text-xs text-text-muted">
                  No college lines yet — add a line per spend year, e.g. 2030
                  while both kids are at SPC, 2032 at USF.
                </p>
              ) : (
                <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {withdrawalDraft.college.map((row, index) => (
                    <div
                      key={index}
                      className="flex items-end gap-2 rounded-xl border border-border/25 px-3 py-2"
                    >
                      <label className="text-xs text-text-muted">
                        Year
                        <Input
                          className="mt-1"
                          inputMode="numeric"
                          aria-label={`College line ${index + 1} calendar year`}
                          value={row.calendarYear}
                          onChange={(event) =>
                            updateCollegeRow(
                              index,
                              'calendarYear',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label className="text-xs text-text-muted">
                        Annual $
                        <Input
                          className="mt-1"
                          inputMode="decimal"
                          aria-label={`College line ${index + 1} annual amount`}
                          value={row.realAmount}
                          onChange={(event) =>
                            updateCollegeRow(
                              index,
                              'realAmount',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => removeCollegeRow(index)}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Success odds
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {preview ? percentPoints(preview.successProbability) : '—'}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Bridge size
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {withdrawalSummary.bridgeSize == null
                    ? '—'
                    : formatCurrencyWhole(withdrawalSummary.bridgeSize)}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Bridge length
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {withdrawalSummary.bridgeYears == null
                    ? '—'
                    : `${withdrawalSummary.bridgeYears} yrs`}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  First-year rate
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {withdrawalSummary.firstYearRate == null
                    ? '—'
                    : formatPercent(withdrawalSummary.firstYearRate * 100, {
                        decimals: 1,
                      })}
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Post-SS rate
                </p>
                <p className="mt-2 font-mono text-2xl text-text">
                  {withdrawalSummary.postSocialSecurityRate == null
                    ? '—'
                    : formatPercent(
                        withdrawalSummary.postSocialSecurityRate * 100,
                        { decimals: 1 },
                      )}
                </p>
              </div>
            </div>

            <div className="mt-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                Spending plan by age (today&apos;s dollars)
              </p>
              <div className="mt-3 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={spendingPathData}
                    margin={{ left: 8, right: 8 }}
                  >
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
                    <Bar
                      dataKey="guaranteed"
                      stackId="funding"
                      name="Guaranteed income"
                      fill="var(--color-chart-2)"
                    />
                    <Bar
                      dataKey="bridge"
                      stackId="funding"
                      name="Bridge sleeve"
                      fill="var(--color-chart-5)"
                    />
                    <Bar
                      dataKey="portfolio"
                      stackId="funding"
                      name="Portfolio draw"
                      fill="var(--color-chart-1)"
                    />
                    <Line
                      type="monotone"
                      dataKey="floor"
                      name="Essential floor"
                      stroke="var(--color-warning)"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="target"
                      name="Spending target"
                      stroke="var(--color-chart-3)"
                      strokeDasharray="4 4"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="medianDiscretionary"
                      name="Median funded discretionary (MC)"
                      stroke="var(--color-chart-4)"
                      strokeDasharray="2 4"
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs text-text-muted">
                Stacked bars show how each year&apos;s spending target is
                funded. The floor line is essentials plus the healthcare
                schedule; discretionary spend above it declines with age — the
                retirement smile.
              </p>
            </div>
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
                {previewQuery.isFetching
                  ? 'Running…'
                  : hasPendingChanges
                    ? 'Run preview •'
                    : 'Run preview'}
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
                {incomeYieldFreshnessLabel ? (
                  <span
                    className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${freshnessToneClass(
                      incomeYieldFreshnessStatus,
                    )}`}
                  >
                    {incomeYieldFreshnessLabel}
                  </span>
                ) : null}
                <p className="mt-2 text-xs text-text-muted">
                  Shown separately for income and tax drag; success odds use
                  total return, so dividends and interest are not added twice.
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
                <span className="mt-2 block">
                  Source: {modeledCashYieldSource}.
                </span>
                {cashYieldFreshnessLabel ? (
                  <span
                    className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${freshnessToneClass(
                      cashYieldFreshnessStatus,
                    )}`}
                  >
                    {cashYieldFreshnessLabel}
                  </span>
                ) : null}
                <span className="mt-2 block">
                  Editable — update it when money-market yields move.
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
                    {accountAllocationCoverage &&
                    accountAllocationCoverage.status !== 'exact' ? (
                      <p className="mt-2">
                        Current allocation confidence:{' '}
                        <span className="font-medium text-text">
                          {accountAllocationCoverage.label}
                        </span>{' '}
                        (
                        {formatPercent(
                          accountAllocationCoverage.exactShare * 100,
                          {
                            decimals: 0,
                          },
                        )}{' '}
                        exact account allocation/cash).
                      </p>
                    ) : null}
                  </div>
                )}
              </div>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Scenario lab
                </p>
                <Button
                  type="button"
                  size="sm"
                  onClick={runCompare}
                  disabled={compareRunning}
                >
                  {compareRunning
                    ? 'Comparing…'
                    : `Compare current + ${compareSelection.length} selected`}
                </Button>
              </div>
              <p className="mt-1 text-xs text-text-muted">
                Save ticker mixes as named scenarios, then compare them
                side-by-side against your real account allocation. Each scenario
                keeps its own bridge style.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="text-xs text-text-muted">
                  Scenario name
                  <Input
                    className="mt-1 w-56"
                    aria-label="Scenario name"
                    value={scenarioName}
                    onChange={(event) => setScenarioName(event.target.value)}
                    placeholder="e.g. Equity bridge"
                  />
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={saveScenarioFromMix}
                  disabled={
                    replaceScenarios.isPending ||
                    !scenarioName.trim() ||
                    (parseTickerMix(tickerMix) ?? []).length === 0
                  }
                >
                  Save ticker mix as scenario
                </Button>
              </div>
              {(scenariosQuery.data ?? []).length === 0 ? (
                <p className="mt-3 text-xs text-text-muted">
                  No saved scenarios yet. Enter a ticker mix above and save it
                  here to start comparing.
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {(scenariosQuery.data ?? []).map((scenario) => (
                    <div
                      key={scenario.id}
                      className="flex flex-wrap items-center gap-3 rounded-xl border border-border/35 bg-surface-muted/15 px-3 py-2"
                    >
                      <label className="flex items-center gap-2 text-sm text-text">
                        <input
                          type="checkbox"
                          aria-label={`Compare ${scenario.name}`}
                          checked={compareSelection.includes(scenario.id)}
                          onChange={(event) =>
                            setCompareSelection((current) =>
                              event.target.checked
                                ? [...current, scenario.id]
                                : current.filter(
                                    (item) => item !== scenario.id,
                                  ),
                            )
                          }
                        />
                        <span className="font-medium">{scenario.name}</span>
                      </label>
                      <span className="text-xs text-text-muted">
                        {scenario.holdings
                          .map((row) => `${row.symbol} ${row.weight}`)
                          .join(' · ')}
                      </span>
                      <span className="text-xs text-text-muted">
                        bridge:{' '}
                        {scenario.bridgeGrowth === 'portfolio'
                          ? 'invested'
                          : `fixed ${formatPercent(
                              (scenario.bridgeRealReturn ?? 0.01) * 100,
                              { decimals: 1 },
                            )}`}
                      </span>
                      <span className="ml-auto flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => loadScenario(scenario)}
                        >
                          Load
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => deleteScenario(scenario.id)}
                          disabled={replaceScenarios.isPending}
                        >
                          Delete
                        </Button>
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {compareError ? (
                <p className="mt-3 text-xs text-danger">{compareError}</p>
              ) : null}
              {compareResults ? (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[28rem] text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-[0.12em] text-text-muted">
                        <th className="py-1.5 pr-3">Scenario</th>
                        <th className="py-1.5 pr-3">Success</th>
                        <th className="py-1.5 pr-3">Median ending</th>
                        <th className="py-1.5">First depletion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compareResults.map((row) => (
                        <tr
                          key={row.name}
                          className="border-t border-border/30"
                        >
                          <td className="py-1.5 pr-3 font-medium text-text">
                            {row.name}
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums">
                            {percentPoints(row.success)}
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums">
                            {formatCurrencyWhole(row.medianEnding)}
                          </td>
                          <td className="py-1.5 font-mono tabular-nums">
                            {row.depletionAge != null
                              ? `age ${row.depletionAge}`
                              : 'never'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs text-text-muted">
                    Same seed and knob set per run — only the allocation and
                    bridge style differ.
                  </p>
                </div>
              ) : null}
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

      {hasPendingChanges && preview ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-text-muted"
        >
          Inputs changed since this plan ran — the results below reflect the
          last preview. Click{' '}
          <span className="font-medium text-text">Run preview</span> to refresh.
        </div>
      ) : null}

      <div className="grid items-start gap-6 xl:grid-cols-2">
        <SectionCard
          variant="surface"
          padding="md"
          contentClassName="space-y-4"
        >
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
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
              <p className="mt-2 text-2xl font-semibold text-text">
                {preview ? percentPoints(preview.successProbability) : '—'}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Monte Carlo probability for this knob set.
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Median ending balance
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {formatCurrencyWhole(preview?.medianEndingBalance)}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                P50 terminal value at horizon.
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                First depletion
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {preview?.firstDepletionAge
                  ? `Age ${preview.firstDepletionAge}`
                  : 'None'}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Deterministic drawdown schedule.
              </p>
            </div>
          </div>

          {(preview?.leverImpacts ?? []).length > 0 ? (
            <div className="border-t border-border/30 pt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Sensitivity checks
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {(preview?.leverImpacts ?? []).map((lever) => (
                  <div
                    key={lever.id}
                    className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
                  >
                    <p className="text-sm font-semibold text-text">
                      {lever.label}
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-text">
                      {formatPercent(lever.deltaSuccessProbability * 100, {
                        decimals: 1,
                        sign: true,
                      })}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-wide text-text-muted">
                      {lever.value}
                    </p>
                    <p className="mt-3 text-sm text-text-muted">
                      {lever.detail}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard variant="surface">
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
            {holdingsCoverage ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Holdings coverage
                  </p>
                  <Badge
                    variant={holdingsCoverageVariant(holdingsCoverage.status)}
                  >
                    {holdingsCoverage.label}
                  </Badge>
                </div>
                <p className="mt-3 font-mono text-2xl text-text">
                  {formatPercent(holdingsCoverage.exactShare * 100, {
                    decimals: 0,
                  })}
                </p>
                <p className="mt-2 text-xs text-text-muted">
                  {holdingsCoverage.detail}
                </p>
                <div className="mt-3 grid gap-2 text-xs text-text-muted">
                  <div className="flex items-center justify-between gap-3">
                    <span>Exact holdings/cash</span>
                    <span className="font-mono text-text">
                      {formatCurrencyWhole(holdingsCoverage.exactValue)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>Account-value-only</span>
                    <span className="font-mono text-text">
                      {formatCurrencyWhole(holdingsCoverage.inferredValue)}
                    </span>
                  </div>
                  {accountAllocationCoverage ? (
                    <div className="flex items-center justify-between gap-3">
                      <span>Account allocation</span>
                      <span className="text-right text-text">
                        {accountAllocationCoverage.label} ·{' '}
                        {formatPercent(
                          accountAllocationCoverage.exactShare * 100,
                          {
                            decimals: 0,
                          },
                        )}{' '}
                        exact
                      </span>
                    </div>
                  ) : null}
                </div>
                <HouseholdHoldingsDialog
                  open={holdingsDialogAccount !== null}
                  onOpenChange={(nextOpen) => {
                    if (!nextOpen) setHoldingsDialogAccount(null)
                  }}
                  householdAccountId={
                    holdingsDialogAccount?.householdAccountId ?? null
                  }
                  accountLabel={holdingsDialogAccount?.label ?? ''}
                  accountValue={holdingsDialogAccount?.currentValue ?? 0}
                />
                {holdingsCoverage.accounts.length > 0 ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-4"
                      aria-expanded={accountDetailsOpen}
                      onClick={() => setAccountDetailsOpen((isOpen) => !isOpen)}
                    >
                      {accountDetailsOpen
                        ? 'Hide account details'
                        : `Show ${holdingsCoverage.accounts.length} account details`}
                    </Button>
                    {accountDetailsOpen ? (
                      <div className="mt-4 space-y-2">
                        {holdingsCoverage.accounts.map((account, index) => (
                          <div
                            key={`${account.label}-${account.bucketType}-${index}`}
                            className="rounded-xl border border-border/25 px-3 py-2"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-text">
                                  {account.label}
                                </p>
                                <p className="text-xs text-text-muted">
                                  {account.coverageLabel} ·{' '}
                                  {bucketLabel(account.bucketType)}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                {account.householdAccountId &&
                                account.manualHoldingsEditable &&
                                account.coverageStatus !== 'cash' ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      setHoldingsDialogAccount({
                                        householdAccountId:
                                          account.householdAccountId as string,
                                        label: account.label,
                                        currentValue: account.currentValue,
                                      })
                                    }
                                  >
                                    {account.coverageStatus ===
                                    'account_value_only'
                                      ? 'Add holdings'
                                      : 'Edit holdings'}
                                  </Button>
                                ) : null}
                                <p className="font-mono text-sm text-text">
                                  {formatCurrencyWhole(account.currentValue)}
                                </p>
                              </div>
                            </div>
                            <p className="mt-1 text-xs text-text-muted">
                              {account.detail}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-6">
        <SectionCard
          variant="surface"
          title="Probability bands"
          description="Portfolio range by age. Wider bands mean return sequence risk matters more."
        >
          <div className="h-72">
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

        {failureAgeData.length > 0 ? (
          <SectionCard
            variant="surface"
            title="When plans fall short"
            description="Share of Monte Carlo trials that first run short at each age. Early bars signal sequence-of-returns risk; late bars signal longevity risk."
          >
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={failureAgeData} margin={{ left: 8, right: 8 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--color-border)"
                  />
                  <XAxis dataKey="age" tickLine={false} />
                  <YAxis
                    tickFormatter={(value) => `${Number(value).toFixed(1)}%`}
                  />
                  <Tooltip
                    formatter={(value) => [
                      `${Number(value ?? 0).toFixed(2)}% of trials`,
                      'First shortfall',
                    ]}
                    labelFormatter={(label) => `Age ${label}`}
                  />
                  <Bar dataKey="share" fill="var(--color-warning)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        ) : null}

        <SectionCard
          variant="surface"
          title="Annual drawdown by source"
          description="Gross withdrawals needed by account type after retirement income sources. Future (inflated) dollars."
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
                {bucketOrder
                  .filter((bucket) => bucket !== 'bridge')
                  .map((bucket) => (
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

        <SectionCard
          variant="surface"
          title="Account balances by age"
          description="Stacked expected-path balances after contributions, withdrawals, tax estimates, and RMD estimates. Future (inflated) dollars."
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
      </div>

      <SectionCard
        variant="surface"
        title="Drawdown schedule"
        description={`Year-by-year funded spending, income, taxes, early-withdrawal penalties, and withdrawal source mix in ${
          drawdownBasis === 'real'
            ? "today's dollars"
            : 'future (inflated) dollars'
        }.`}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          {(
            [
              ['real', "Today's dollars"],
              ['nominal', 'Future dollars'],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={drawdownBasis === value ? 'default' : 'outline'}
              onClick={() => setDrawdownBasis(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <div className="overflow-hidden rounded-2xl border border-border/35 bg-surface-muted/10">
          <div className="overflow-auto">
            <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
              <thead className="bg-bg/95 backdrop-blur">
                <tr>
                  {[
                    { label: 'Age' },
                    {
                      label: 'Spend',
                      title:
                        'Retirement spending actually funded this year (income + bridge + net withdrawal). Shown in amber when the withdrawal strategy trims it below the plan target.',
                    },
                    { label: 'Income' },
                    ...(drawdownHasBridge
                      ? [
                          {
                            label: 'Bridge',
                            title:
                              'Spending covered by the bridge sleeve carved out at retirement. Not part of Withdrawal.',
                          },
                        ]
                      : []),
                    { label: 'Withdrawal' },
                    { label: 'Tax est.', title: taxEstimateTooltip },
                    { label: 'Penalty' },
                    ...(drawdownHasCollege
                      ? [
                          {
                            label: 'College',
                            title:
                              'College costs paid from the portfolio after the 529 sleeve runs out. Included in Withdrawal; 529-funded amounts never touch retirement accounts.',
                          },
                        ]
                      : []),
                    { label: 'Cash' },
                    { label: 'Taxable' },
                    { label: 'Gov 457(b)' },
                    { label: 'Pre-tax' },
                    { label: 'Roth' },
                    { label: 'Ending' },
                    { label: 'RMD' },
                  ].map((heading) => (
                    <th
                      key={heading.label}
                      className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted first:text-left"
                      title={heading.title}
                    >
                      {heading.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {drawdownTableRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={drawdownColumnCount}
                      className="px-4 py-10 text-center text-sm text-text-muted"
                    >
                      Drawdown rows will appear after the preview runs.
                    </td>
                  </tr>
                ) : (
                  drawdownTableRows.map((row) => (
                    <tr key={`${row.calendarYear}-${row.primaryAge}`}>
                      <td className="border-b border-border/20 px-4 py-3 text-left font-medium text-text">
                        {row.primaryAge}
                      </td>
                      <td
                        className={`border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums ${
                          row.spendTrimmed ? 'text-warning' : 'text-text'
                        }`}
                        title={
                          row.spendTrimmed
                            ? `Below the ${formatCurrency(row.displayTarget, {
                                decimals: 0,
                              })} target — the withdrawal strategy trimmed discretionary spending this year.`
                            : undefined
                        }
                      >
                        {formatCurrency(row.displaySpend, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayIncome, { decimals: 0 })}
                      </td>
                      {drawdownHasBridge ? (
                        <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                          {formatCurrency(row.displayBridge, { decimals: 0 })}
                        </td>
                      ) : null}
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayGross, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.displayTax, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-warning">
                        {formatCurrency(row.displayPenalty, { decimals: 0 })}
                      </td>
                      {drawdownHasCollege ? (
                        <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                          {formatCurrency(row.displayCollege, { decimals: 0 })}
                        </td>
                      ) : null}
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.cash ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.taxable ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(
                            row.displayBuckets,
                            'governmental_457b',
                          ),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(
                          bucketMapValue(row.displayBuckets, 'pre_tax'),
                          { decimals: 0 },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayBuckets.roth ?? 0, {
                          decimals: 0,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.displayEnding, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-4 py-3 text-right">
                        {row.rmdApplied ? (
                          <Badge variant="warning">
                            {formatCurrency(row.displayRmd, { decimals: 0 })}
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
        {drawdownTableRows.length > 0 ? (
          <p className="mt-3 text-xs text-text-muted">
            Each year reconciles: Spend = Income{' '}
            {drawdownHasBridge ? '+ Bridge ' : ''}+ Withdrawal − Tax est. −
            Penalty{drawdownHasCollege ? ' − College' : ''}. When a forced RMD
            withdraws more than the plan needs, the surplus is reinvested in
            taxable rather than spent.
          </p>
        ) : null}
        {gainRatioDetail ? (
          <p className="mt-3 text-xs text-text-muted">
            <span
              className={`mr-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                gainRatioSource === 'tax_lots'
                  ? freshnessToneClass('fresh')
                  : freshnessToneClass('needs_evidence')
              }`}
            >
              {gainRatioSource === 'tax_lots'
                ? 'From your cost basis'
                : 'Planning assumption'}
            </span>
            {gainRatioDetail}
          </p>
        ) : null}
      </SectionCard>

      {accountRules.length > 0 ? (
        <SectionCard
          variant="surface"
          title="How each account is treated"
          description="What the planner assumes for early access and required distributions per account type. Planning context, not tax advice."
        >
          <div className="grid gap-3 md:grid-cols-2">
            {accountRules.map((rule) => (
              <div
                key={rule.bucketType}
                className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {rule.label}
                  </p>
                  <Badge variant="outline">{rule.taxTreatment}</Badge>
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  <span className="font-medium text-text">Early access:</span>{' '}
                  {rule.earlyAccess}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  <span className="font-medium text-text">RMDs:</span>{' '}
                  {rule.rmd}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </div>
  )
}
