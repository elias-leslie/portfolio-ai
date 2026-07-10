import type { TrendPoint } from '@/components/home/today/NetWorthTrendLine'
import type {
  HouseholdFinanceDashboard,
  RetirementAcaConfig,
  RetirementBucketStrategy,
  RetirementBucketStrategyBucket,
  RetirementCollegeYear,
  RetirementIncomeActualsStream,
  RetirementIncomeSourceInput,
  RetirementLiquidityEvent,
  RetirementPreviewRequest,
  RetirementSpendingActuals,
  RetirementSpendingReduction,
  RetirementWithdrawalConfig,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import type { categoryBudgetMetaMap } from './household-fact-metadata'

export const bucketColors: Record<string, string> = {
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

export const bucketOrder = [
  'cash',
  'taxable',
  'governmental_457b',
  'pre_tax',
  'roth',
  'hsa',
  'bridge',
  'other',
]
export const allocationClasses = [
  { key: 'us_equity', label: 'US stocks' },
  { key: 'intl_equity', label: 'Intl stocks' },
  { key: 'bonds', label: 'Bonds' },
  { key: 'cash', label: 'Cash / SPAXX' },
  { key: 'real_estate', label: 'Real estate' },
  { key: 'alts', label: 'Alts' },
] as const

export const allocationLabelByKey = {
  ...Object.fromEntries(
    allocationClasses.map(({ key, label }) => [key, label]),
  ),
  usEquity: 'US stocks',
  usequity: 'US stocks',
  intlEquity: 'Intl stocks',
  intlequity: 'Intl stocks',
  realEstate: 'Real estate',
  realestate: 'Real estate',
} as Record<string, string>
export type AllocationMode = 'current' | 'classes' | 'tickers'
// SSA 2026 constants — mirror backend retirement_planning_service.py
// SSA_2026_* (deliberate duplicate for live draft estimates)
export const ssa2026TaxableWageBase = 184_500
export const ssa2026FirstBendPoint = 1_286
export const ssa2026SecondBendPoint = 7_749
export const socialSecurityFullRetirementAge = 67
export const ssaAssumedCareerStartAge = 22
export const defaultSocialSecurityPayableRatio = 0.77
export const defaultSpaxxYieldPercent = 3.28
export const defaultSpaxxYieldSource =
  'Fidelity SPAXX 7-day yield as of 2026-05-07'
// Mirrors backend MEDICARE_DEFAULT_MONTHLY_PER_PERSON (_aca_estimator.py):
// 2026 Part B $202.90 + Part D $38.99 (CMS) + Medigap Plan G $164 (KFF).
export const medicareDefaultMonthlyPerPerson = 405.89

export const incomeCadenceLabels: Record<
  RetirementIncomeActualsStream['cadence'],
  string
> = {
  weekly: 'Weekly',
  biweekly: 'Every 2 weeks',
  monthly: 'Monthly',
  irregular: 'Irregular',
  'one-off': 'One-off',
}

export const incomeOwnerAutoValue = '__auto_owner__'
export const incomeStatusAutoValue = '__auto_status__'
export const incomeMergeTargetNoneValue = '__no_merge_target__'

export const incomeStatusOptions: Array<{
  value: NonNullable<RetirementIncomeActualsStream['statusOverride']>
  label: string
}> = [
  { value: 'active', label: 'Active' },
  { value: 'stopped', label: 'Stopped' },
  { value: 'one_off', label: 'One-off' },
  { value: 'portfolio_yield', label: 'Portfolio yield' },
  { value: 'ignored', label: 'Ignore' },
  { value: 'merged', label: 'Merged into…' },
]

export const incomeStatusLabels: Record<
  RetirementIncomeActualsStream['status'],
  string
> = {
  active: 'Active',
  stopped: 'Stopped',
  one_off: 'One-off',
  portfolio_yield: 'Portfolio yield',
  ignored: 'Ignored',
  merged: 'Merged',
}

export function incomeStreamStatus(stream: RetirementIncomeActualsStream): {
  label: string
  variant: 'success' | 'warning' | 'secondary' | 'outline'
} {
  if (stream.status === 'active') {
    return { label: incomeStatusLabels.active, variant: 'success' }
  }
  if (stream.status === 'stopped') {
    return {
      label: stream.statusOverride ? 'Stopped' : 'Stopped?',
      variant: 'warning',
    }
  }
  if (stream.status === 'portfolio_yield') {
    return { label: incomeStatusLabels.portfolio_yield, variant: 'outline' }
  }
  return { label: incomeStatusLabels[stream.status], variant: 'secondary' }
}

export function previewStatusVariant(
  successProbability: number,
  trustedTotals: boolean,
) {
  if (!trustedTotals) return 'warning' as const
  if (successProbability >= 0.8) return 'success' as const
  if (successProbability >= 0.6) return 'warning' as const
  return 'destructive' as const
}

export function holdingsCoverageVariant(status: string | undefined) {
  if (status === 'exact') return 'success' as const
  if (status === 'partial') return 'warning' as const
  if (status === 'account_value_only') return 'warning' as const
  return 'outline' as const
}

export function bucketStrategyVariant(status: string | undefined) {
  if (status === 'aligned') return 'success' as const
  if (status === 'underfilled' || status === 'empty') return 'warning' as const
  if (status === 'overfilled') return 'secondary' as const
  return 'outline' as const
}

export function strategyBucketFillLabel(
  bucket: RetirementBucketStrategyBucket,
) {
  if (bucket.targetValue <= 0)
    return bucket.currentValue > 0 ? 'No target' : 'N/A'
  return `${Math.round(bucket.fillRatio * 100)}% full`
}

export function strategyBucketGapLabel(bucket: RetirementBucketStrategyBucket) {
  if (Math.abs(bucket.gapValue) < 1) return 'On target'
  if (bucket.gapValue < 0) {
    return `${formatCurrencyWhole(Math.abs(bucket.gapValue))} short`
  }
  return `${formatCurrencyWhole(bucket.gapValue)} above`
}

export type BucketTimingContext = {
  yearsToRetirement: number
  retirementYear: number | null
}

export function formatRunwayYears(years: number) {
  if (years <= 0.1) return 'now'
  if (years < 1) return '<1y'
  const rounded = Math.round(years * 10) / 10
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}y`
}

export function bucketTargetYearsLabel(bucket: RetirementBucketStrategyBucket) {
  if (bucket.targetYears <= 0) return 'No staged target yet'
  return `${bucket.targetYears.toFixed(1)}y target now`
}

export function strategyBucketTimingLabel(
  bucket: RetirementBucketStrategyBucket,
  timing: BucketTimingContext,
) {
  if (timing.yearsToRetirement <= 0.1) return 'In the withdrawal window'
  const runway = formatRunwayYears(timing.yearsToRetirement)
  const targetDate = timing.retirementYear
    ? String(timing.retirementYear)
    : 'retirement start'
  if (bucket.bucketId === 'now') {
    return `${bucketTargetYearsLabel(bucket)} · full 1y cash by ${targetDate}`
  }
  if (bucket.bucketId === 'soon') {
    return `${bucketTargetYearsLabel(bucket)} · full 5y stability by ${targetDate}`
  }
  return `Growth source for staged funding over ${runway}`
}

export function strategyBucketPaceLabel(
  bucket: RetirementBucketStrategyBucket,
  timing: BucketTimingContext,
) {
  if (bucket.status === 'aligned') return 'On pace for this stage.'
  if (Math.abs(bucket.gapValue) < 1) return 'On pace for this stage.'
  if (timing.yearsToRetirement > 0.25) {
    const annualPace = Math.abs(bucket.gapValue) / timing.yearsToRetirement
    const monthlyPace = annualPace / 12
    const targetDate = timing.retirementYear
      ? String(timing.retirementYear)
      : 'retirement'
    const pace = `${formatCurrencyWhole(annualPace)}/yr (${formatCurrencyWhole(
      monthlyPace,
    )}/mo)`
    if (bucket.gapValue < 0) {
      return `Fund about ${pace} by ${targetDate}; not an all-at-once move.`
    }
    if (bucket.bucketId === 'later') {
      return `Source about ${pace} from growth by ${targetDate}.`
    }
    return `Trim about ${pace} by ${targetDate}.`
  }
  return bucket.action
}

export function timingPaceShortLabel(
  bucket: RetirementBucketStrategyBucket,
  timing: BucketTimingContext,
) {
  if (bucket.status === 'aligned') return 'On pace'
  if (Math.abs(bucket.gapValue) < 1) return 'On pace'
  if (timing.yearsToRetirement > 0.25) {
    const annualPace = Math.abs(bucket.gapValue) / timing.yearsToRetirement
    const verb =
      bucket.gapValue < 0
        ? 'Fund'
        : bucket.bucketId === 'later'
          ? 'Source'
          : 'Trim'
    return `${verb} ${formatCurrencyWhole(annualPace)}/yr`
  }
  return bucket.gapValue < 0 ? 'Fund now' : 'Review'
}

export function bucketStrategyRetirementYear(
  strategy: RetirementBucketStrategy | null,
  drawdownSchedule:
    | Array<{ primaryAge: number; calendarYear: number }>
    | undefined,
) {
  if (!strategy) return null
  return (
    drawdownSchedule?.find((row) => row.primaryAge >= strategy.retirementAge)
      ?.calendarYear ?? null
  )
}

export function allocationBreakdownText(allocation: Record<string, number>) {
  const rows = Object.entries(allocation)
    .filter(([, value]) => value >= 0.005)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
  if (rows.length === 0) return 'No allocation detail'
  return rows
    .map(
      ([key, value]) =>
        `${allocationLabelByKey[key] ?? formatEnumLabel(key)} ${formatPercent(
          value * 100,
          { decimals: 0 },
        )}`,
    )
    .join(' · ')
}

export function bucketLabel(value: string) {
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

export function bucketMapValue(values: Record<string, number>, bucket: string) {
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

export function householdRetirementAge(
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

export function numberInput(value: number | null | undefined, fallback = '') {
  return value == null ? fallback : String(Math.round(value))
}

export function percentInput(
  value: number | null | undefined,
  fallback = '2.5',
) {
  if (value == null) return fallback
  return String(Math.round(value * 1000) / 10)
}

export function parseNumber(value: string, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function parseOptionalNumber(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

export function parsePercentValue(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

export function parseOptionalPercentValue(value: string | undefined) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

export function allocationDraftFromPreview(
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

export function allocationFromDraft(
  draft: Record<(typeof allocationClasses)[number]['key'], string>,
) {
  const entries = allocationClasses
    .map(({ key }) => [key, parsePercentValue(draft[key])] as const)
    .filter(([, value]) => value > 0)
  const total = entries.reduce((sum, [, value]) => sum + value, 0)
  if (total <= 0) return null
  return Object.fromEntries(entries.map(([key, value]) => [key, value / total]))
}

export function parseTickerMix(value: string) {
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

export function camelAssetClassKey(key: string) {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase())
}

export function assetAllocationValue(
  allocation: Record<string, number> | undefined,
  key: string,
) {
  return allocation?.[key] ?? allocation?.[camelAssetClassKey(key)] ?? 0
}

export function returnAssumptionNumber(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key] ?? assumptions?.[camelAssetClassKey(key)]
  return typeof value === 'number' ? value : null
}

export function returnAssumptionText(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key] ?? assumptions?.[camelAssetClassKey(key)]
  return typeof value === 'string' ? value : null
}

export function estimateSocialSecurityMonthly(
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

export function memberAge(
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

export function householdAges(dashboard: HouseholdFinanceDashboard) {
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

export function socialSecurityDefaults(dashboard: HouseholdFinanceDashboard) {
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

export function defaultDraft(dashboard: HouseholdFinanceDashboard) {
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
  const plannedContributionMonthly =
    retirementContributionEstimateFromPlanning(dashboard)?.monthlyAmount ?? 0
  const monthlyContribution = Math.max(
    dashboard.profile.monthlySavingsTarget ?? 0,
    dashboard.retirementContributionTracker.estimatedMonthlyContributions ?? 0,
    plannedContributionMonthly,
  )
  return {
    primaryAge: numberInput(ages.primaryAge, ''),
    spouseAge: numberInput(ages.spouseAge, ''),
    retirementAge: numberInput(primaryRetirementAge, '65'),
    spouseRetirementAge: numberInput(spouseRetirementAge, '65'),
    monthlySpend: numberInput(monthlySpend, '6000'),
    monthlyContribution: numberInput(monthlyContribution, '0'),
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

export type WithdrawalDraft = {
  strategy: 'guardrails'
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

export function defaultWithdrawalDraft(
  dashboard: HouseholdFinanceDashboard,
): WithdrawalDraft {
  const profile = dashboard.profile
  const schedule = dashboard.planning?.retirementHealthcareSchedule ?? []
  return {
    strategy: 'guardrails',
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
    bridgeGrowth: 'fixed',
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

export type AcaDraft = {
  tier: 'silver' | 'bronze' | 'none'
  coveredLives: 'until22' | 'until26' | 'adultsOnly'
  premiumOverride: string
  oopMonthly: string
  medicareMonthly: string
}

// Cent-preserving input seed ($99.58 must not round to $100 and drift on
// the next save); blank for unset.
export function amountInput(value: number | null | undefined) {
  return value == null ? '' : String(Math.round(value * 100) / 100)
}

// '' = unset (null); '0' is a real choice (Medicare line off), unlike
// parseOptionalNumber. Negative typing clamps so the API's ge=0
// validation can never 422.
export function parseOptionalAmount(value: string) {
  if (value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.max(0, parsed) : null
}

export function defaultAcaDraft(
  dashboard: HouseholdFinanceDashboard,
): AcaDraft {
  const profile = dashboard.profile
  return {
    tier:
      profile.acaTier === 'bronze' || profile.acaTier === 'none'
        ? profile.acaTier
        : 'silver',
    coveredLives: 'until22',
    premiumOverride: amountInput(profile.acaPremiumAge21Override),
    oopMonthly: amountInput(profile.acaOopMonthly),
    medicareMonthly: amountInput(profile.medicareMonthlyPerPerson),
  }
}

export function acaConfigFromDraft(aca: AcaDraft): RetirementAcaConfig {
  return {
    tier: aca.tier,
    premiumAge21MonthlyOverride: parseOptionalAmount(aca.premiumOverride),
    oopMonthly: parseOptionalAmount(aca.oopMonthly) ?? 0,
    medicareMonthlyPerPerson: parseOptionalAmount(aca.medicareMonthly),
    dependentsCoveredUntilAge:
      aca.coveredLives === 'until26'
        ? 26
        : aca.coveredLives === 'adultsOnly'
          ? 0
          : null,
  }
}

// Partial-retirement window (you retired, spouse still working). Spouse net
// gates the feature: blank = off = legacy behavior.
export type PartialDraft = {
  spouseNetMonthly: string
  windowSpendMonthly: string
  spouseGrossAnnual: string
}

export type ChildReductionDraft = {
  id?: string | null
  label: string
  startYear: string
  monthlyAmount: string
  amountSource?: 'manual' | 'money_actuals'
  notes: string
}

export type ChildReductionDraftField =
  | 'label'
  | 'startYear'
  | 'monthlyAmount'
  | 'notes'

export type ChildCostDropEstimate = {
  householdMonthly: number
  perChildMonthly: number
  categories: string[]
}

export type RetirementContributionEstimate = {
  monthlyAmount: number
  sources: Array<{ label: string; monthlyAmount: number }>
}

export type RealEstateDraft = {
  id?: string | null
  label: string
  housingType: string
  occupancyRole: string
  propertyAddress: string
  propertyValue: string
  valueAsOf: string
  valuationSource: string
  valuationConfidence: string
  valuationRangeLow: string
  valuationRangeHigh: string
  ownershipPercent: string
  mortgageBalance: string
  retirementTreatment: 'track_only' | 'income' | 'planned_sale'
  annualRetirementIncome: string
  liquidityYear: string
  liquidityAmount: string
  notes: string
}

export const childReductionExpenseKind = 'child_spending_reduction'

export function dependentMembers(dashboard: HouseholdFinanceDashboard) {
  return (
    dashboard.planning?.members.filter((member) => {
      const role = member.role.toLowerCase()
      const relationship = member.relationship?.toLowerCase() ?? ''
      return (
        member.isDependent ||
        ['child', 'dependent'].includes(role) ||
        ['child', 'daughter', 'son', 'dependent'].includes(relationship)
      )
    }) ?? []
  )
}

export function dependentNameKeys(dashboard: HouseholdFinanceDashboard) {
  return dependentMembers(dashboard)
    .flatMap((member) => {
      const name = member.displayName.trim().toLowerCase()
      const firstName = name.split(/\s+/)[0]
      return [name, firstName]
    })
    .filter(Boolean)
}

export function ownerMatchesDependent(
  ownerName: string | null | undefined,
  names: string[],
) {
  const owner = ownerName?.trim().toLowerCase()
  if (!owner) return false
  return names.some((name) => owner.includes(name))
}

export function childCostDropEstimateFromActuals(
  spendingActuals: RetirementSpendingActuals | undefined,
  categoryMeta: ReturnType<typeof categoryBudgetMetaMap>,
  dashboard: HouseholdFinanceDashboard,
): ChildCostDropEstimate | null {
  const dependents = dependentMembers(dashboard)
  if (!spendingActuals || dependents.length === 0) return null
  const names = dependentNameKeys(dashboard)
  const childRows = (spendingActuals.categories ?? []).filter((row) => {
    const meta = categoryMeta.get(row.category)
    if (!meta || meta.disabled) return false
    return ownerMatchesDependent(meta.ownerName, names)
  })
  const householdMonthly = childRows.reduce(
    (sum, row) => sum + row.monthlyAverage,
    0,
  )
  if (householdMonthly <= 0) return null
  return {
    householdMonthly,
    perChildMonthly: householdMonthly / dependents.length,
    categories: Array.from(new Set(childRows.map((row) => row.category))),
  }
}

export function monthlyAmountFromPlanningSource(source: {
  monthlyAmount?: number | null
  annualAmount?: number | null
}) {
  if (typeof source.monthlyAmount === 'number' && source.monthlyAmount > 0) {
    return source.monthlyAmount
  }
  if (typeof source.annualAmount === 'number' && source.annualAmount > 0) {
    return source.annualAmount / 12
  }
  return 0
}

export function retirementContributionEstimateFromPlanning(
  dashboard: HouseholdFinanceDashboard,
): RetirementContributionEstimate | null {
  const sources =
    dashboard.planning?.incomeSources
      .filter((source) =>
        source.sourceType.toLowerCase().includes('contribution'),
      )
      .map((source) => ({
        label: source.label,
        monthlyAmount: monthlyAmountFromPlanningSource(source),
      }))
      .filter((source) => source.monthlyAmount > 0) ?? []
  const monthlyAmount = sources.reduce(
    (sum, source) => sum + source.monthlyAmount,
    0,
  )
  if (monthlyAmount <= 0) return null
  return { monthlyAmount, sources }
}

export function defaultChildReductionDraft(
  dashboard: HouseholdFinanceDashboard,
): ChildReductionDraft[] {
  const existing =
    dashboard.planning?.plannedExpenses.filter(
      (expense) => expense.expenseKind === childReductionExpenseKind,
    ) ?? []
  if (existing.length > 0) {
    return existing.map((expense) => ({
      id: expense.id,
      label: expense.label,
      startYear: expense.targetDate?.slice(0, 4) ?? '',
      monthlyAmount: amountInput(expense.targetAmount),
      amountSource: 'manual',
      notes: expense.notes ?? '',
    }))
  }
  const currentYear = new Date(dashboard.generatedAt).getFullYear()
  return dependentMembers(dashboard).map((member, index) => ({
    label: member.displayName || `Child ${index + 1}`,
    startYear: member.birthYear
      ? String(member.birthYear + 22)
      : String(currentYear + 5),
    monthlyAmount: '',
    amountSource: 'manual',
    notes: 'Expected child costs drop after job / move-out.',
  }))
}

export function spendingReductionsFromDraft(
  dashboard: HouseholdFinanceDashboard,
  draft: ReturnType<typeof defaultDraft>,
  reductions: ChildReductionDraft[],
): RetirementSpendingReduction[] {
  const primaryAge = parseOptionalNumber(draft.primaryAge)
  if (primaryAge == null) return []
  const currentYear = new Date(dashboard.generatedAt).getFullYear()
  return reductions
    .map((row) => {
      const startYear = Math.round(parseNumber(row.startYear, 0))
      const monthlyAmount = parseOptionalAmount(row.monthlyAmount) ?? 0
      return {
        label: row.label.trim() || 'Child cost reduction',
        startAge: primaryAge + (startYear - currentYear),
        annualAmount: monthlyAmount * 12,
      }
    })
    .filter(
      (row) =>
        row.startAge >= 18 && row.startAge <= 120 && row.annualAmount > 0,
    )
}

export function childReductionPlanningRows(
  dashboard: HouseholdFinanceDashboard,
  reductions: ChildReductionDraft[],
) {
  const otherRows =
    dashboard.planning?.plannedExpenses.filter(
      (expense) => expense.expenseKind !== childReductionExpenseKind,
    ) ?? []
  return [
    ...otherRows.map((expense) => ({
      id: expense.id,
      label: expense.label,
      expenseKind: expense.expenseKind,
      category: expense.category,
      targetAmount: expense.targetAmount,
      targetDate: expense.targetDate,
      monthlySavingTarget: expense.monthlySavingTarget,
      priority: expense.priority,
      notes: expense.notes,
      confirmationStatus: expense.confirmationStatus,
      provenance: expense.provenance,
      evidenceNote: expense.evidenceNote,
      sourceDocumentId: expense.sourceDocumentId,
    })),
    ...reductions
      .filter((row) => row.label.trim())
      .map((row) => ({
        id: row.id ?? null,
        label: row.label.trim(),
        expenseKind: childReductionExpenseKind,
        category: 'retirement_spending',
        targetAmount:
          row.amountSource === 'money_actuals'
            ? null
            : parseOptionalAmount(row.monthlyAmount),
        targetDate: row.startYear.trim()
          ? `${row.startYear.trim()}-01-01`
          : null,
        monthlySavingTarget: null,
        priority: 'medium',
        notes: row.notes || null,
        confirmationStatus: 'confirmed',
        provenance:
          row.amountSource === 'money_actuals' ? 'money_actuals' : 'manual',
        evidenceNote:
          row.amountSource === 'money_actuals'
            ? 'Amount auto-fed from child-owned Money spending categories.'
            : null,
        sourceDocumentId: null,
      })),
  ]
}

export function defaultRealEstateDraft(
  dashboard: HouseholdFinanceDashboard,
): RealEstateDraft[] {
  return (dashboard.planning?.housingCosts ?? []).map((row) => ({
    id: row.id,
    label: row.label,
    housingType: row.housingType || 'property',
    occupancyRole: row.occupancyRole || 'family_asset',
    propertyAddress: row.propertyAddress ?? '',
    propertyValue: amountInput(row.propertyValue),
    valueAsOf: row.valueAsOf ?? '',
    valuationSource: row.valuationSource ?? '',
    valuationConfidence: amountInput(row.valuationConfidence),
    valuationRangeLow: amountInput(row.valuationRangeLow),
    valuationRangeHigh: amountInput(row.valuationRangeHigh),
    ownershipPercent: amountInput(row.ownershipPercent ?? 100),
    mortgageBalance: amountInput(row.mortgageBalance),
    retirementTreatment:
      row.retirementTreatment === 'income' ||
      row.retirementTreatment === 'planned_sale'
        ? row.retirementTreatment
        : 'track_only',
    annualRetirementIncome: amountInput(row.annualRetirementIncome),
    liquidityYear: row.liquidityYear == null ? '' : String(row.liquidityYear),
    liquidityAmount: amountInput(row.liquidityAmount),
    notes: row.notes ?? '',
  }))
}

export function realEstatePlanningRows(
  dashboard: HouseholdFinanceDashboard,
  rows: RealEstateDraft[],
) {
  const existing = new Map(
    (dashboard.planning?.housingCosts ?? []).map((row) => [row.id, row]),
  )
  return rows
    .filter((row) => row.label.trim())
    .map((row) => {
      const base = row.id ? existing.get(row.id) : null
      return {
        id: row.id ?? null,
        label: row.label.trim(),
        housingType: row.housingType || 'property',
        occupancyRole: row.occupancyRole || 'family_asset',
        propertyAddress: row.propertyAddress.trim() || null,
        monthlyPayment: base?.monthlyPayment ?? null,
        propertyTaxMonthly: base?.propertyTaxMonthly ?? null,
        hoaMonthly: base?.hoaMonthly ?? null,
        insuranceMonthly: base?.insuranceMonthly ?? null,
        utilitiesMonthly: base?.utilitiesMonthly ?? null,
        maintenanceMonthly: base?.maintenanceMonthly ?? null,
        mortgageBalance: parseOptionalAmount(row.mortgageBalance),
        interestRate: base?.interestRate ?? null,
        propertyValue: parseOptionalAmount(row.propertyValue),
        ownershipPercent: parseOptionalAmount(row.ownershipPercent),
        valueAsOf: row.valueAsOf || base?.valueAsOf || null,
        valuationSource: row.valuationSource || base?.valuationSource || null,
        valuationConfidence: parseOptionalAmount(row.valuationConfidence),
        valuationRangeLow: parseOptionalAmount(row.valuationRangeLow),
        valuationRangeHigh: parseOptionalAmount(row.valuationRangeHigh),
        retirementTreatment: row.retirementTreatment,
        annualRetirementIncome: parseOptionalAmount(row.annualRetirementIncome),
        liquidityYear: parseOptionalAmount(row.liquidityYear),
        liquidityAmount: parseOptionalAmount(row.liquidityAmount),
        notes: row.notes || null,
        confirmationStatus: base?.confirmationStatus ?? 'confirmed',
        provenance: base?.provenance ?? 'manual',
        evidenceNote: base?.evidenceNote ?? null,
        sourceDocumentId: base?.sourceDocumentId ?? null,
      }
    })
}

export function liquidityEventsFromRealEstate(
  rows: RealEstateDraft[],
): RetirementLiquidityEvent[] {
  return rows
    .filter((row) => row.retirementTreatment === 'planned_sale')
    .map((row) => ({
      label: `${row.label.trim() || 'Property'} liquidity`,
      calendarYear: Math.round(parseNumber(row.liquidityYear, 0)),
      realAmount: parseOptionalAmount(row.liquidityAmount) ?? 0,
    }))
    .filter(
      (row) =>
        row.calendarYear >= 1900 &&
        row.calendarYear <= 2200 &&
        row.realAmount > 0,
    )
}

export function extraIncomeSourcesFromRealEstate(
  rows: RealEstateDraft[],
  draft: ReturnType<typeof defaultDraft>,
): RetirementIncomeSourceInput[] {
  const startAge = Math.max(
    parseNumber(draft.retirementAge, 65),
    parseOptionalNumber(draft.spouseRetirementAge) ??
      parseNumber(draft.retirementAge, 65),
  )
  return rows
    .filter((row) => row.retirementTreatment === 'income')
    .map((row) => ({
      label: `${row.label.trim() || 'Property'} income`,
      sourceType: 'real_estate_income',
      ownerName: null,
      startAge,
      monthlyAmount:
        (parseOptionalAmount(row.annualRetirementIncome) ?? 0) / 12,
      inflationAdjusted: true,
      survivorBenefit: null,
    }))
    .filter((row) => row.monthlyAmount > 0)
}

export function formatShortDate(value: string | null | undefined) {
  if (!value) return 'No date'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function valuationSourceLabel(source: string | null | undefined) {
  if (!source) return 'Manual value'
  if (source === 'pinellas_county_comps') return 'Pinellas comps'
  if (source === 'pinellas_county_just_market') return 'Pinellas county value'
  if (source === 'hillsborough_county_just_market') {
    return 'Hillsborough county value'
  }
  return formatEnumLabel(source)
}

export function valuationStale(valueAsOf: string | null | undefined) {
  if (!valueAsOf) return true
  const parsed = new Date(`${valueAsOf.slice(0, 10)}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return true
  return Date.now() - parsed.getTime() > 1000 * 60 * 60 * 24 * 90
}

export function propertyTrendPoints(
  points:
    | Array<{ fetchedAt: string; asOf: string; estimateValue: number }>
    | undefined,
): TrendPoint[] {
  return (
    points
      ?.map((point) => ({
        date: (point.fetchedAt || point.asOf).slice(0, 10),
        value: point.estimateValue,
      }))
      .filter((point) => Number.isFinite(point.value)) ?? []
  )
}

export function defaultPartialDraft(
  dashboard: HouseholdFinanceDashboard,
): PartialDraft {
  const profile = dashboard.profile
  return {
    spouseNetMonthly: amountInput(profile.spouseNetMonthlyIncome),
    windowSpendMonthly: amountInput(profile.partialRetirementMonthlySpend),
    spouseGrossAnnual: amountInput(profile.spouseGrossAnnualIncome),
  }
}

export function partialRequestFields(partial: PartialDraft) {
  return {
    spouseNetMonthlyIncome: parseOptionalAmount(partial.spouseNetMonthly),
    partialRetirementMonthlySpend: parseOptionalAmount(
      partial.windowSpendMonthly,
    ),
    spouseGrossAnnualIncome: parseOptionalAmount(partial.spouseGrossAnnual),
  }
}

export function collegeScheduleFromDraft(
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

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

// The backend API validates Social Security claim ages as int 62..70 (422
// otherwise); clamp draft values so the preview request and the live caption
// never leave that window.
export function clampClaimAge(value: number) {
  return clamp(Math.round(value), 62, 70)
}

export function clampOptionalClaimAge(value: number | null) {
  return value == null ? null : clampClaimAge(value)
}

export function withdrawalConfigFromDraft(
  withdrawal: WithdrawalDraft,
): RetirementWithdrawalConfig {
  return {
    strategy: 'guardrails',
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
      growth: 'fixed',
    },
    healthcareSchedule: withdrawal.healthcare
      .map((row) => ({
        age: Math.round(parseNumber(row.age, 0)),
        realAmount: parseNumber(row.realAmount, 0),
      }))
      .filter((row) => row.age >= 18 && row.age <= 120 && row.realAmount >= 0),
    // null = let the server resolve the floor/discretionary split from the
    // saved budget ratio (R7 carve-out,
    // retirement_planning_service._withdrawal_config_from_inputs); sending
    // numbers here would override that derivation. Note: profile *_override
    // columns only apply when no withdrawal config is sent.
    essentialFloor: null,
    baseDiscretionary: null,
  }
}

export function buildRequest(
  householdId: string,
  dashboard: HouseholdFinanceDashboard,
  draft: ReturnType<typeof defaultDraft>,
  allocationMode: AllocationMode = 'current',
  allocationDraft?: Record<(typeof allocationClasses)[number]['key'], string>,
  tickerMix = '',
  withdrawal?: WithdrawalDraft,
  aca?: AcaDraft,
  partial?: PartialDraft,
  childReductions?: ChildReductionDraft[],
  realEstate?: RealEstateDraft[],
): RetirementPreviewRequest {
  const assetAllocation =
    allocationMode === 'classes' && allocationDraft
      ? allocationFromDraft(allocationDraft)
      : null
  const allocationHoldings =
    allocationMode === 'tickers' ? parseTickerMix(tickerMix) : null
  // Empty stays null (server resolves the saved start age); typed values are
  // clamped to the API's 62..70 window so out-of-range typing cannot 422.
  const rawPrimaryStartAge = parseOptionalNumber(
    draft.primarySocialSecurityStartAge,
  )
  const primaryStartAge =
    rawPrimaryStartAge == null ? null : clampClaimAge(rawPrimaryStartAge)
  const rawSpouseStartAge = parseOptionalNumber(
    draft.spouseSocialSecurityStartAge,
  )
  const spouseStartAge =
    rawSpouseStartAge == null ? null : clampClaimAge(rawSpouseStartAge)
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
    primarySocialSecurityStartAge: primaryStartAge,
    spouseSocialSecurityMonthly: parseOptionalNumber(
      draft.spouseSocialSecurityMonthly,
    ),
    spouseSocialSecurityAnnualEarnings: parseOptionalNumber(
      draft.spouseSocialSecurityAnnualEarnings,
    ),
    spouseSocialSecurityStartAge: spouseStartAge,
    socialSecurityPayableRatio:
      parseNumber(
        draft.socialSecurityPayableRatio,
        defaultSocialSecurityPayableRatio * 100,
      ) / 100,
    withdrawal: withdrawal ? withdrawalConfigFromDraft(withdrawal) : null,
    collegeSchedule: withdrawal ? collegeScheduleFromDraft(withdrawal) : null,
    spendingReductions: childReductions
      ? spendingReductionsFromDraft(dashboard, draft, childReductions)
      : null,
    liquidityEvents: realEstate
      ? liquidityEventsFromRealEstate(realEstate)
      : null,
    extraIncomeSources: realEstate
      ? extraIncomeSourcesFromRealEstate(realEstate, draft)
      : null,
    aca: aca ? acaConfigFromDraft(aca) : null,
    ...(partial ? partialRequestFields(partial) : {}),
    trials: 2500,
    seed: 7,
  }
}

export function currencyTooltip(value: unknown) {
  return formatCurrency(typeof value === 'number' ? value : Number(value), {
    decimals: 0,
  })
}

export function percentPoints(value: number) {
  return formatPercent(value * 100, { decimals: 0 })
}

export function taxAssumptionText(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key]
  return typeof value === 'string' ? value : null
}

export function taxAssumptionNumber(
  assumptions: Record<string, unknown> | undefined,
  key: string,
) {
  const value = assumptions?.[key]
  return typeof value === 'number' ? value : null
}

export function taxAssumptionWarnings(
  assumptions: Record<string, unknown> | undefined,
) {
  const warnings = assumptions?.warnings
  return Array.isArray(warnings)
    ? warnings.filter(
        (warning): warning is string => typeof warning === 'string',
      )
    : []
}

export function taxAssumptionTooltip(
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

export function socialSecuritySourceLabel(
  scheduled: number | null,
  manualMonthly: number | null,
) {
  if (manualMonthly != null) return 'manual monthly estimate'
  if (scheduled != null)
    return 'rough salary estimate, earnings stop at retirement'
  return 'not included'
}
