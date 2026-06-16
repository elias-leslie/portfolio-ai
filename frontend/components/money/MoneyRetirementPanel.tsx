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
import { formatBudgetDate } from '@/components/money/budget-helpers'
import { HouseholdHoldingsDialog } from '@/components/money/HouseholdHoldingsDialog'
import { freshnessToneClass } from '@/components/money/moneyAccountsUtils'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdFinanceDashboard,
  HouseholdProfileUpdate,
  RetirementAcaConfig,
  RetirementAccountRule,
  RetirementAllocationScenario,
  RetirementAllocationScenarioInput,
  RetirementCollegeYear,
  RetirementIncomeActualsStream,
  RetirementIncomeSourceInput,
  RetirementLiquidityEvent,
  RetirementPreviewRequest,
  RetirementSpendingReduction,
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
  useRetirementIncomeActuals,
  useRetirementPreview,
  useRetirementSpendingActuals,
  useUpdateHouseholdPlanning,
  useUpdateHouseholdProfile,
  useUpdateRetirementIncomeStreamOverride,
} from '@/lib/hooks/useHousehold'
import { buildOwnerOptions } from './owner-options'

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
// SSA 2026 constants — mirror backend retirement_planning_service.py
// SSA_2026_* (deliberate duplicate for live draft estimates)
const ssa2026TaxableWageBase = 184_500
const ssa2026FirstBendPoint = 1_286
const ssa2026SecondBendPoint = 7_749
const socialSecurityFullRetirementAge = 67
const ssaAssumedCareerStartAge = 22
const defaultSocialSecurityPayableRatio = 0.77
const defaultSpaxxYieldPercent = 3.28
const defaultSpaxxYieldSource = 'Fidelity SPAXX 7-day yield as of 2026-05-07'
// Mirrors backend MEDICARE_DEFAULT_MONTHLY_PER_PERSON (_aca_estimator.py):
// 2026 Part B $202.90 + Part D $38.99 (CMS) + Medigap Plan G $164 (KFF).
const medicareDefaultMonthlyPerPerson = 405.89

const incomeCadenceLabels: Record<
  RetirementIncomeActualsStream['cadence'],
  string
> = {
  weekly: 'Weekly',
  biweekly: 'Every 2 weeks',
  monthly: 'Monthly',
  irregular: 'Irregular',
  'one-off': 'One-off',
}

const incomeOwnerAutoValue = '__auto_owner__'
const incomeStatusAutoValue = '__auto_status__'
const incomeMergeTargetNoneValue = '__no_merge_target__'

const incomeStatusOptions: Array<{
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

const incomeStatusLabels: Record<
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

function incomeStreamStatus(stream: RetirementIncomeActualsStream): {
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

export function percentInput(
  value: number | null | undefined,
  fallback = '2.5',
) {
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

function defaultWithdrawalDraft(
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

type AcaDraft = {
  tier: 'silver' | 'bronze' | 'none'
  coveredLives: 'until22' | 'until26' | 'adultsOnly'
  premiumOverride: string
  oopMonthly: string
  medicareMonthly: string
}

// Cent-preserving input seed ($99.58 must not round to $100 and drift on
// the next save); blank for unset.
function amountInput(value: number | null | undefined) {
  return value == null ? '' : String(Math.round(value * 100) / 100)
}

// '' = unset (null); '0' is a real choice (Medicare line off), unlike
// parseOptionalNumber. Negative typing clamps so the API's ge=0
// validation can never 422.
function parseOptionalAmount(value: string) {
  if (value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.max(0, parsed) : null
}

function defaultAcaDraft(dashboard: HouseholdFinanceDashboard): AcaDraft {
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

function acaConfigFromDraft(aca: AcaDraft): RetirementAcaConfig {
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
type PartialDraft = {
  spouseNetMonthly: string
  windowSpendMonthly: string
  spouseGrossAnnual: string
}

type ChildReductionDraft = {
  id?: string | null
  label: string
  startYear: string
  monthlyAmount: string
  notes: string
}

type RealEstateDraft = {
  id?: string | null
  label: string
  housingType: string
  occupancyRole: string
  propertyValue: string
  ownershipPercent: string
  mortgageBalance: string
  retirementTreatment: 'track_only' | 'income' | 'planned_sale'
  annualRetirementIncome: string
  liquidityYear: string
  liquidityAmount: string
  notes: string
}

const childReductionExpenseKind = 'child_spending_reduction'

function dependentMembers(dashboard: HouseholdFinanceDashboard) {
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

function defaultChildReductionDraft(
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
    notes: 'Expected child costs drop after job / move-out.',
  }))
}

function spendingReductionsFromDraft(
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

function childReductionPlanningRows(
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
        targetAmount: parseOptionalAmount(row.monthlyAmount),
        targetDate: row.startYear.trim()
          ? `${row.startYear.trim()}-01-01`
          : null,
        monthlySavingTarget: null,
        priority: 'medium',
        notes: row.notes || null,
        confirmationStatus: 'confirmed',
        provenance: 'manual',
        evidenceNote: null,
        sourceDocumentId: null,
      })),
  ]
}

function defaultRealEstateDraft(
  dashboard: HouseholdFinanceDashboard,
): RealEstateDraft[] {
  return (dashboard.planning?.housingCosts ?? []).map((row) => ({
    id: row.id,
    label: row.label,
    housingType: row.housingType || 'property',
    occupancyRole: row.occupancyRole || 'family_asset',
    propertyValue: amountInput(row.propertyValue),
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

function realEstatePlanningRows(
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
        valueAsOf: base?.valueAsOf ?? null,
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

function liquidityEventsFromRealEstate(
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

function extraIncomeSourcesFromRealEstate(
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

function defaultPartialDraft(
  dashboard: HouseholdFinanceDashboard,
): PartialDraft {
  const profile = dashboard.profile
  return {
    spouseNetMonthly: amountInput(profile.spouseNetMonthlyIncome),
    windowSpendMonthly: amountInput(profile.partialRetirementMonthlySpend),
    spouseGrossAnnual: amountInput(profile.spouseGrossAnnualIncome),
  }
}

function partialRequestFields(partial: PartialDraft) {
  return {
    spouseNetMonthlyIncome: parseOptionalAmount(partial.spouseNetMonthly),
    partialRetirementMonthlySpend: parseOptionalAmount(
      partial.windowSpendMonthly,
    ),
    spouseGrossAnnualIncome: parseOptionalAmount(partial.spouseGrossAnnual),
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

// The backend API validates Social Security claim ages as int 62..70 (422
// otherwise); clamp draft values so the preview request and the live caption
// never leave that window.
function clampClaimAge(value: number) {
  return clamp(Math.round(value), 62, 70)
}

function clampOptionalClaimAge(value: number | null) {
  return value == null ? null : clampClaimAge(value)
}

function withdrawalConfigFromDraft(
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

function buildRequest(
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
  const [acaDraft, setAcaDraft] = useState(() => defaultAcaDraft(dashboard))
  const [partialDraft, setPartialDraft] = useState(() =>
    defaultPartialDraft(dashboard),
  )
  const [childReductionDraft, setChildReductionDraft] = useState(() =>
    defaultChildReductionDraft(dashboard),
  )
  const [realEstateDraft, setRealEstateDraft] = useState(() =>
    defaultRealEstateDraft(dashboard),
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
  const incomeActualsQuery = useRetirementIncomeActuals()
  const spendingActualsQuery = useRetirementSpendingActuals()
  const updateIncomeStreamOverride = useUpdateRetirementIncomeStreamOverride()
  const incomeActuals = incomeActualsQuery.data
  const spendingActuals = spendingActualsQuery.data
  const incomeOwnerOptions = useMemo(
    () =>
      buildOwnerOptions(
        (incomeActuals?.streams ?? []).flatMap((stream) =>
          stream.owner ? [stream.owner] : [],
        ),
      ),
    [incomeActuals],
  )
  const activeIncomeMergeTargets = useMemo(
    () =>
      (incomeActuals?.streams ?? []).filter(
        (stream) => stream.status === 'active',
      ),
    [incomeActuals],
  )
  // Recurring take-home streams that stopped before the coverage window's
  // end — either the income ended or newer statements weren't imported.
  const incomeStaleStreams = useMemo(
    () =>
      (incomeActuals?.streams ?? []).filter(
        (stream) => stream.status === 'stopped',
      ),
    [incomeActuals],
  )
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
      dashboard,
      defaultDraft(dashboard),
      'current',
      undefined,
      '',
      defaultWithdrawalDraft(dashboard),
      defaultAcaDraft(dashboard),
      defaultPartialDraft(dashboard),
      defaultChildReductionDraft(dashboard),
      defaultRealEstateDraft(dashboard),
    ),
  )
  const updateProfile = useUpdateHouseholdProfile()
  const updatePlanning = useUpdateHouseholdPlanning()
  const previewQuery = useRetirementPreview(request)
  const preview = previewQuery.data
  const actualSpendMonthly = spendingActuals?.totalMonthlySpend ?? null
  const actualSpendRequest = useMemo(
    () =>
      actualSpendMonthly == null
        ? request
        : {
            ...request,
            monthlySpend: actualSpendMonthly,
            annualExpenses: actualSpendMonthly * 12,
          },
    [actualSpendMonthly, request],
  )
  const actualSpendPreviewQuery = useRetirementPreview(actualSpendRequest)
  const actualSpendPreview = actualSpendPreviewQuery.data
  // Withdrawal-plan and ACA/Medicare knobs re-project live (debounced);
  // the other planner inputs still wait for an explicit "Run preview".
  const debouncedWithdrawal = useDebounce(withdrawalDraft, 250)
  useEffect(() => {
    setRequest((current) => ({
      ...current,
      withdrawal: withdrawalConfigFromDraft(debouncedWithdrawal),
    }))
  }, [debouncedWithdrawal])
  const debouncedAca = useDebounce(acaDraft, 250)
  useEffect(() => {
    setRequest((current) => ({
      ...current,
      aca: acaConfigFromDraft(debouncedAca),
    }))
  }, [debouncedAca])
  const debouncedPartial = useDebounce(partialDraft, 250)
  useEffect(() => {
    setRequest((current) => ({
      ...current,
      ...partialRequestFields(debouncedPartial),
    }))
  }, [debouncedPartial])
  const pendingRequest = useMemo(
    () =>
      buildRequest(
        dashboard.profile.id,
        dashboard,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
        acaDraft,
        partialDraft,
        childReductionDraft,
        realEstateDraft,
      ),
    [
      dashboard,
      dashboard.profile.id,
      draft,
      allocationMode,
      allocationDraft,
      tickerMix,
      withdrawalDraft,
      acaDraft,
      partialDraft,
      childReductionDraft,
      realEstateDraft,
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
  // Partial-retirement window: years where the primary is retired but the
  // household (spouse) is not. Caption-only derivation.
  const partialWindowStartAge =
    preview?.inputs.retirementAge ?? parseNumber(draft.retirementAge, 65)
  const partialWindowYears = Math.max(
    0,
    fullRetirementAge - partialWindowStartAge,
  )
  // Largest recurring take-home stream from Money transactions — a
  // display-only hint for the spouse-net lever, never fed into the sim.
  const detectedTakeHome = useMemo(() => {
    const candidates = (incomeActuals?.streams ?? []).filter(
      (stream) => stream.status === 'active',
    )
    if (candidates.length === 0) return null
    return candidates.reduce((best, stream) =>
      stream.runRateMonthly > best.runRateMonthly ? stream : best,
    )
  }, [incomeActuals])
  function saveIncomeStreamOverride(
    stream: RetirementIncomeActualsStream,
    patch: {
      ownerName?: string | null
      status?: RetirementIncomeActualsStream['statusOverride']
      mergedIntoStreamKey?: string | null
    },
  ) {
    const nextStatus =
      patch.status !== undefined ? patch.status : stream.statusOverride
    const nextMergedInto =
      nextStatus === 'merged'
        ? (patch.mergedIntoStreamKey ?? stream.mergedIntoStreamKey)
        : null
    void updateIncomeStreamOverride.mutateAsync({
      streamKey: stream.streamKey,
      label: stream.label,
      ownerName:
        patch.ownerName !== undefined
          ? patch.ownerName
          : stream.ownerOverride
            ? stream.owner
            : null,
      status: nextStatus,
      mergedIntoStreamKey: nextMergedInto,
    })
  }
  const taxWarnings = taxAssumptionWarnings(preview?.taxAssumptions)
  const taxEstimateTooltip = taxAssumptionTooltip(
    preview?.taxAssumptions,
    taxWarnings,
  )

  useEffect(() => {
    const nextDraft = defaultDraft(dashboard)
    const nextWithdrawal = defaultWithdrawalDraft(dashboard)
    const nextAca = defaultAcaDraft(dashboard)
    const nextPartial = defaultPartialDraft(dashboard)
    const nextChildReductions = defaultChildReductionDraft(dashboard)
    const nextRealEstate = defaultRealEstateDraft(dashboard)
    setDraft(nextDraft)
    setWithdrawalDraft(nextWithdrawal)
    setAcaDraft(nextAca)
    setPartialDraft(nextPartial)
    setChildReductionDraft(nextChildReductions)
    setRealEstateDraft(nextRealEstate)
    setAllocationMode('current')
    setAllocationDraft(allocationDraftFromPreview(undefined))
    setAccountDetailsOpen(false)
    setRequest(
      buildRequest(
        dashboard.profile.id,
        dashboard,
        nextDraft,
        'current',
        undefined,
        '',
        nextWithdrawal,
        nextAca,
        nextPartial,
        nextChildReductions,
        nextRealEstate,
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
        .filter(
          (row) =>
            row.partialRetirementYear || row.primaryAge >= fullRetirementAge,
        )
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
        (row) =>
          row.partialRetirementYear || row.primaryAge >= fullRetirementAge,
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
      // Partial years: the engine never ran, so spendingNeed (already
      // nominal) is the window spend target and spouse take-home joins
      // income in the funding math.
      const targetNominal = row.partialRetirementYear
        ? row.spendingNeed
        : row.spendingTarget * factor
      const incomeNominal = row.income + (row.spouseNetIncome ?? 0)
      const spendNominal = Math.min(
        targetNominal,
        Math.max(
          0,
          incomeNominal + bridgeNominal + row.netWithdrawal - collegeNominal,
        ),
      )
      // ACA/Medicare row fields are real dollars; scale like bridgeDraw.
      const healthcareNominal =
        ((row.acaNet ?? 0) + (row.medicarePremium ?? 0)) * factor
      return {
        ...row,
        displaySpend: spendNominal * scale,
        displayTarget: targetNominal * scale,
        spendTrimmed: targetNominal - spendNominal > 1,
        displayIncome: incomeNominal * scale,
        displaySpouseNet: (row.spouseNetIncome ?? 0) * scale,
        displayBridge: bridgeNominal * scale,
        displayCollege: collegeNominal * scale,
        displayGross: row.grossWithdrawal * scale,
        displayTax: row.taxEstimate * scale,
        displayPenalty: row.penaltyEstimate * scale,
        displayEnding: row.endingBalance * scale,
        displayRmd: row.rmdAmount * scale,
        displayHealthcare: healthcareNominal * scale,
        displayAcaGross: (row.acaPremiumGross ?? 0) * factor * scale,
        // The used credit caps at the chosen plan's premium (net floors
        // at $0 — e.g. Bronze), so gross − subsidy + OOP ties to the cell.
        displayAcaSubsidy:
          Math.min(row.acaSubsidy ?? 0, row.acaPremiumGross ?? 0) *
          factor *
          scale,
        displayAcaOop: (row.acaOop ?? 0) * factor * scale,
        displayMedicare: (row.medicarePremium ?? 0) * factor * scale,
        displayMagi: (row.magi ?? 0) * factor * scale,
        // ACA share of any spend trim: the MAGI true-up repriced the
        // subsidy above what the planning floor budgeted.
        displayAcaReprice:
          Math.max(0, (row.acaNet ?? 0) - (row.acaPlanningNet ?? 0)) *
          factor *
          scale,
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
  const drawdownHasHealthcare = drawdownTableRows.some(
    (row) => row.displayHealthcare > 0.5,
  )
  const drawdownHasAca = drawdownTableRows.some(
    (row) => (row.acaPremiumGross ?? 0) > 0.5,
  )
  const drawdownColumnCount =
    13 +
    (drawdownHasBridge ? 1 : 0) +
    (drawdownHasCollege ? 1 : 0) +
    (drawdownHasHealthcare ? 1 : 0) +
    (drawdownHasAca ? 1 : 0)

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
    // Clamp to the API's 62..70 claim-age window so the caption never shows
    // an estimate the preview endpoint would reject.
    const primaryClaimAge = clampClaimAge(
      parseOptionalNumber(draft.primarySocialSecurityStartAge) ??
        socialSecurityFullRetirementAge,
    )
    const spouseClaimAge = clampClaimAge(
      parseOptionalNumber(draft.spouseSocialSecurityStartAge) ??
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
  const realEstateSummary = useMemo(() => {
    let trackedEquity = 0
    let modeledLiquidity = 0
    let modeledIncome = 0
    for (const row of realEstateDraft) {
      const value = parseOptionalAmount(row.propertyValue) ?? 0
      const ownership = (parseOptionalAmount(row.ownershipPercent) ?? 100) / 100
      const mortgage = parseOptionalAmount(row.mortgageBalance) ?? 0
      trackedEquity += Math.max(0, value * ownership - mortgage)
      if (row.retirementTreatment === 'planned_sale') {
        modeledLiquidity += parseOptionalAmount(row.liquidityAmount) ?? 0
      }
      if (row.retirementTreatment === 'income') {
        modeledIncome += parseOptionalAmount(row.annualRetirementIncome) ?? 0
      }
    }
    return { trackedEquity, modeledLiquidity, modeledIncome }
  }, [realEstateDraft])

  const applyDraft = () => {
    setRequest(
      buildRequest(
        dashboard.profile.id,
        dashboard,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
        acaDraft,
        partialDraft,
        childReductionDraft,
        realEstateDraft,
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
      primarySocialSecurityStartAge: clampOptionalClaimAge(
        parseOptionalNumber(draft.primarySocialSecurityStartAge),
      ),
      spouseSocialSecurityMonthly: parseOptionalNumber(
        draft.spouseSocialSecurityMonthly,
      ),
      spouseSocialSecurityAnnualEarnings: parseOptionalNumber(
        draft.spouseSocialSecurityAnnualEarnings,
      ),
      spouseSocialSecurityStartAge: clampOptionalClaimAge(
        parseOptionalNumber(draft.spouseSocialSecurityStartAge),
      ),
      socialSecurityPayableRatio:
        parseNumber(
          draft.socialSecurityPayableRatio,
          defaultSocialSecurityPayableRatio * 100,
        ) / 100,
      withdrawalStrategy: 'guardrails',
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
      bridgeGrowth: 'fixed',
      acaTier: acaDraft.tier,
      acaPremiumAge21Override: parseOptionalAmount(acaDraft.premiumOverride),
      acaOopMonthly: parseOptionalAmount(acaDraft.oopMonthly),
      // Blank tracks the published CMS/KFF default; an explicit 0 turns
      // the Medicare line off — both are real states, so null persists.
      medicareMonthlyPerPerson: parseOptionalAmount(acaDraft.medicareMonthly),
      // Partial-retirement window: blank = feature off, so nulls persist
      // to clear the columns.
      ...partialRequestFields(partialDraft),
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
      plannedExpenses: childReductionPlanningRows(
        dashboard,
        childReductionDraft,
      ),
      housingCosts: realEstatePlanningRows(dashboard, realEstateDraft),
    })
    setRequest(
      buildRequest(
        dashboard.profile.id,
        dashboard,
        draft,
        allocationMode,
        allocationDraft,
        tickerMix,
        withdrawalDraft,
        acaDraft,
        partialDraft,
        childReductionDraft,
        realEstateDraft,
      ),
    )
  }

  const updateDraft = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const updatePartialDraft = (key: keyof PartialDraft, value: string) => {
    setPartialDraft((current) => ({ ...current, [key]: value }))
  }

  const updateChildReductionDraft = (
    index: number,
    key: keyof ChildReductionDraft,
    value: string,
  ) => {
    setChildReductionDraft((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    )
  }

  const addChildReduction = () => {
    setChildReductionDraft((current) => [
      ...current,
      {
        label: `Child ${current.length + 1}`,
        startYear: String(new Date(dashboard.generatedAt).getFullYear() + 5),
        monthlyAmount: '',
        notes: '',
      },
    ])
  }

  const removeChildReduction = (index: number) => {
    setChildReductionDraft((current) =>
      current.filter((_, rowIndex) => rowIndex !== index),
    )
  }

  const updateRealEstateDraft = (
    index: number,
    key: keyof RealEstateDraft,
    value: string,
  ) => {
    setRealEstateDraft((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    )
  }

  const addRealEstateAsset = () => {
    setRealEstateDraft((current) => [
      ...current,
      {
        label: `Property ${current.length + 1}`,
        housingType: 'property',
        occupancyRole: 'family_asset',
        propertyValue: '',
        ownershipPercent: '100',
        mortgageBalance: '',
        retirementTreatment: 'track_only',
        annualRetirementIncome: '',
        liquidityYear: '',
        liquidityAmount: '',
        notes: '',
      },
    ])
  }

  const removeRealEstateAsset = (index: number) => {
    setRealEstateDraft((current) =>
      current.filter((_, rowIndex) => rowIndex !== index),
    )
  }

  const updateWithdrawalDraft = <K extends keyof WithdrawalDraft>(
    key: K,
    value: WithdrawalDraft[K],
  ) => {
    setWithdrawalDraft((current) => ({ ...current, [key]: value }))
  }

  const updateAcaDraft = <K extends keyof AcaDraft>(
    key: K,
    value: AcaDraft[K],
  ) => {
    setAcaDraft((current) => ({ ...current, [key]: value }))
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
        dashboard,
        draft,
        'current',
        undefined,
        '',
        withdrawalDraft,
        acaDraft,
        partialDraft,
        childReductionDraft,
        realEstateDraft,
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
            <div className="mt-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                Partial retirement (spouse still working)
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <label className="text-xs text-text-muted">
                  Spouse net take-home $/mo
                  <Input
                    className="mt-1"
                    inputMode="decimal"
                    aria-label="Spouse net monthly take-home during partial retirement"
                    placeholder="blank = off"
                    value={partialDraft.spouseNetMonthly}
                    onChange={(event) =>
                      updatePartialDraft('spouseNetMonthly', event.target.value)
                    }
                  />
                </label>
                <label className="text-xs text-text-muted">
                  Window spend $/mo
                  <Input
                    className="mt-1"
                    inputMode="decimal"
                    aria-label="Household spending per month during the partial-retirement window"
                    placeholder={draft.monthlySpend || 'Spend / month'}
                    value={partialDraft.windowSpendMonthly}
                    onChange={(event) =>
                      updatePartialDraft(
                        'windowSpendMonthly',
                        event.target.value,
                      )
                    }
                  />
                </label>
                <label className="text-xs text-text-muted">
                  Spouse gross wages $/yr
                  <Input
                    className="mt-1"
                    inputMode="decimal"
                    aria-label="Spouse gross annual wages during partial retirement"
                    placeholder="stacks tax brackets"
                    value={partialDraft.spouseGrossAnnual}
                    onChange={(event) =>
                      updatePartialDraft(
                        'spouseGrossAnnual',
                        event.target.value,
                      )
                    }
                  />
                </label>
              </div>
              <p className="mt-2 text-xs text-text-muted">
                {partialDraft.spouseNetMonthly.trim() === ''
                  ? 'Off — years before household retirement are modeled as pure accumulation.'
                  : partialWindowYears > 0
                    ? `Window: your age ${partialWindowStartAge}–${fullRetirementAge - 1}. Spending above spouse take-home is drawn from the portfolio (penalty-aware; gross wages set the tax brackets, but their own tax never hits the portfolio). Save/month keeps contributing through the window — net take-home is already after payroll deferrals. Surplus take-home is not auto-invested.`
                    : 'No window — both retirements land in the same year.'}
              </p>
              {detectedTakeHome ? (
                <p className="mt-1 text-xs text-text-muted">
                  Detected from Money transactions: {detectedTakeHome.label}
                  {detectedTakeHome.owner ? ` (${detectedTakeHome.owner})` : ''}{' '}
                  ≈{' '}
                  {formatCurrency(detectedTakeHome.runRateMonthly, {
                    decimals: 0,
                  })}
                  /mo
                  {detectedTakeHome.active
                    ? ''
                    : `, last deposit ${detectedTakeHome.lastDate}`}{' '}
                  — reference only, never fed into the plan.
                </p>
              ) : null}
            </div>
            <p className="mt-3 text-xs text-text-muted">
              Drawdown starts when both are retired: your age{' '}
              {fullRetirementAge}.
              {partialDraft.spouseNetMonthly.trim() !== '' &&
              partialWindowYears > 0
                ? ` Partial-retirement years (${partialWindowStartAge}–${fullRetirementAge - 1}) fund the spend gap from the portfolio first.`
                : ''}
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
        title="Spending used in the plan"
        description="Two retirement baselines: current actual spending from Money data, and the manual planning spend you entered. Both use the same allocation, guardrails, child drop-offs, healthcare, college, and Social Security assumptions."
      >
        {(spendingActuals && spendingActuals.coverageMonths > 0) ||
        (incomeActuals && incomeActuals.coverageMonths > 0) ? (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Current spend scenario
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {spendingActuals
                    ? `${formatCurrency(spendingActuals.totalMonthlySpend, {
                        decimals: 0,
                      })}/mo`
                    : '—'}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Monte Carlo:{' '}
                  <span className="font-mono text-text">
                    {actualSpendPreview
                      ? percentPoints(actualSpendPreview.successProbability)
                      : actualSpendPreviewQuery.isFetching
                        ? 'running…'
                        : '—'}
                  </span>
                  . Uses deduped ledger spending, not income.
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Manual planning scenario
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {formatCurrency(parseNumber(draft.monthlySpend, 0), {
                    decimals: 0,
                  })}
                  /mo
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Monte Carlo:{' '}
                  <span className="font-mono text-text">
                    {preview ? percentPoints(preview.successProbability) : '—'}
                  </span>
                  . This is the saved retirement spend target.
                </p>
              </div>
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Data confidence
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {spendingActuals?.coverageMonths ?? 0} mo
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {spendingActuals
                    ? `${spendingActuals.sourceLabel} ${spendingActuals.firstMonth ?? ''}–${spendingActuals.lastMonth ?? ''}.`
                    : 'No complete spending window yet.'}
                </p>
              </div>
            </div>
            {incomeActuals &&
            incomeActuals.activeMonthlyIncome > 0 &&
            spendingActuals ? (
              <div className="mt-3 grid gap-2 text-sm text-text md:grid-cols-3">
                <p>
                  Income gap to plan:{' '}
                  <span className="font-mono tabular-nums">
                    {dashboard.profile.monthlyNetIncomeTarget != null
                      ? `${formatCurrency(
                          incomeActuals.activeMonthlyIncome -
                            dashboard.profile.monthlyNetIncomeTarget,
                          { decimals: 0 },
                        )}/mo`
                      : '—'}
                  </span>
                </p>
                <p>
                  Actual net while working:{' '}
                  <span className="font-mono tabular-nums">
                    {formatCurrency(
                      incomeActuals.activeMonthlyIncome -
                        spendingActuals.totalMonthlySpend,
                      { decimals: 0 },
                    )}
                    /mo
                  </span>
                </p>
                <p className="text-text-muted">
                  Spend gap vs take-home:{' '}
                  <span className="font-mono tabular-nums text-text">
                    {formatCurrency(
                      spendingActuals.totalMonthlySpend -
                        incomeActuals.activeMonthlyIncome,
                      { decimals: 0 },
                    )}
                    /mo
                  </span>
                </p>
              </div>
            ) : null}
            {incomeStaleStreams.length > 0 ? (
              <div className="mt-3 rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs text-text">
                <span className="font-semibold">
                  Some income streams have stopped:
                </span>{' '}
                {incomeStaleStreams
                  .map(
                    (stream) =>
                      `${stream.label} (last deposit ${formatBudgetDate(
                        stream.lastDate,
                      )})`,
                  )
                  .join('; ')}
                . Either the income ended or newer bank statements have not been
                imported — only active streams count toward the take-home figure
                above.
              </div>
            ) : null}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[58rem] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-[0.12em] text-text-muted">
                    <th className="py-1.5 pr-3">Stream</th>
                    <th className="py-1.5 pr-3">Owner</th>
                    <th className="py-1.5 pr-3">Cadence</th>
                    <th className="py-1.5 pr-3 text-right">Run-rate / mo</th>
                    <th className="py-1.5 pr-3">Months</th>
                    <th className="py-1.5 pr-3">Last deposit</th>
                    <th className="py-1.5">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(incomeActuals?.streams ?? []).map((stream) => {
                    const status = incomeStreamStatus(stream)
                    const mergeTargets = activeIncomeMergeTargets.filter(
                      (target) => target.streamKey !== stream.streamKey,
                    )
                    const selectedMergeTarget = incomeActuals?.streams.find(
                      (candidate) =>
                        candidate.streamKey === stream.mergedIntoStreamKey,
                    )
                    return (
                      <tr
                        key={stream.streamKey}
                        className="border-t border-border/30 align-top"
                      >
                        <td className="max-w-[18rem] truncate py-1.5 pr-3 font-medium text-text">
                          {stream.label}
                        </td>
                        <td className="py-1.5 pr-3">
                          <Select
                            value={
                              stream.ownerOverride && stream.owner
                                ? stream.owner
                                : incomeOwnerAutoValue
                            }
                            disabled={updateIncomeStreamOverride.isPending}
                            onValueChange={(value) =>
                              saveIncomeStreamOverride(stream, {
                                ownerName:
                                  value === incomeOwnerAutoValue ? null : value,
                              })
                            }
                          >
                            <SelectTrigger
                              size="sm"
                              aria-label={`Owner for ${stream.label}`}
                              className="min-w-[8.5rem] text-xs"
                            >
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent align="start">
                              <SelectItem value={incomeOwnerAutoValue}>
                                Auto
                                {stream.owner ? ` · ${stream.owner}` : ''}
                              </SelectItem>
                              {incomeOwnerOptions.map((owner) => (
                                <SelectItem key={owner} value={owner}>
                                  {owner}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <p className="mt-1 text-[10px] leading-none text-text-muted">
                            {stream.ownerOverride
                              ? 'Manual owner'
                              : stream.owner
                                ? 'Auto-detected'
                                : 'Auto · unassigned'}
                          </p>
                        </td>
                        <td className="py-1.5 pr-3 text-text-muted">
                          {incomeCadenceLabels[stream.cadence]}
                        </td>
                        <td className="py-1.5 pr-3 text-right font-mono tabular-nums">
                          {formatCurrency(stream.runRateMonthly, {
                            decimals: 0,
                          })}
                          {Math.round(stream.runRateMonthly) !==
                          Math.round(stream.monthlyAverage) ? (
                            <p className="text-[10px] font-normal text-text-muted">
                              {formatCurrency(stream.monthlyAverage, {
                                decimals: 0,
                              })}{' '}
                              observed
                            </p>
                          ) : null}
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">
                          {stream.monthsSeen}
                        </td>
                        <td className="py-1.5 pr-3 text-text-muted">
                          {formatBudgetDate(stream.lastDate)}
                        </td>
                        <td className="py-1.5">
                          <div className="flex min-w-[11rem] flex-col gap-1.5">
                            <Select
                              value={
                                stream.statusOverride ?? incomeStatusAutoValue
                              }
                              disabled={updateIncomeStreamOverride.isPending}
                              onValueChange={(value) => {
                                if (value === incomeStatusAutoValue) {
                                  saveIncomeStreamOverride(stream, {
                                    status: null,
                                    mergedIntoStreamKey: null,
                                  })
                                  return
                                }
                                const nextStatus =
                                  value as RetirementIncomeActualsStream['statusOverride']
                                saveIncomeStreamOverride(stream, {
                                  status: nextStatus,
                                  mergedIntoStreamKey:
                                    nextStatus === 'merged'
                                      ? (stream.mergedIntoStreamKey ??
                                        mergeTargets[0]?.streamKey ??
                                        null)
                                      : null,
                                })
                              }}
                            >
                              <SelectTrigger
                                size="sm"
                                aria-label={`Status for ${stream.label}`}
                                className="min-w-[11rem] text-xs"
                              >
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent align="start">
                                <SelectItem value={incomeStatusAutoValue}>
                                  Auto
                                </SelectItem>
                                {incomeStatusOptions.map((option) => (
                                  <SelectItem
                                    key={option.value}
                                    value={option.value}
                                    disabled={
                                      option.value === 'merged' &&
                                      mergeTargets.length === 0
                                    }
                                  >
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <div className="flex flex-wrap items-center gap-1">
                              <Badge variant={status.variant}>
                                {status.label}
                              </Badge>
                              {stream.statusOverride ? (
                                <Badge variant="outline">Manual</Badge>
                              ) : null}
                            </div>
                            {stream.status === 'merged' ? (
                              <Select
                                value={
                                  stream.mergedIntoStreamKey ??
                                  incomeMergeTargetNoneValue
                                }
                                disabled={updateIncomeStreamOverride.isPending}
                                onValueChange={(value) => {
                                  if (value === incomeMergeTargetNoneValue) {
                                    return
                                  }
                                  saveIncomeStreamOverride(stream, {
                                    status: 'merged',
                                    mergedIntoStreamKey: value,
                                  })
                                }}
                              >
                                <SelectTrigger
                                  size="sm"
                                  aria-label={`Merged target for ${stream.label}`}
                                  className="min-w-[11rem] text-xs"
                                >
                                  <SelectValue placeholder="Merged into" />
                                </SelectTrigger>
                                <SelectContent align="start">
                                  <SelectItem
                                    value={incomeMergeTargetNoneValue}
                                  >
                                    Choose stream
                                  </SelectItem>
                                  {mergeTargets.map((target) => (
                                    <SelectItem
                                      key={target.streamKey}
                                      value={target.streamKey}
                                    >
                                      {target.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : null}
                            {selectedMergeTarget ? (
                              <p className="max-w-[12rem] truncate text-[10px] text-text-muted">
                                same as {selectedMergeTarget.label}
                              </p>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-text-muted">
              {incomeActuals?.sourceLabel} Stream run-rates normalize weekly and
              biweekly deposits; observed $/mo still averages over each
              stream&apos;s own active months.
              {(incomeActuals?.aliasRowsCollapsed ?? 0) > 0
                ? ` ${incomeActuals?.aliasRowsCollapsed} duplicate statement rows (the same deposit imported under two account labels) were collapsed.`
                : ''}
            </p>
          </>
        ) : (
          <p className="text-sm text-text-muted">
            {incomeActualsQuery.isLoading
              ? 'Scanning Money transactions for income streams…'
              : incomeActualsQuery.error
                ? 'Failed to load income actuals.'
                : 'No complete months of Money transaction coverage yet — import bank statements to compare plan income against actual deposits.'}
          </p>
        )}
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
                  Baseline strategy
                </p>
                <div className="mt-2 rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                  <Badge variant="success">Guardrails</Badge>
                  <p className="mt-2 text-sm text-text">
                    One retirement paycheck, adjusted annually when the
                    portfolio crosses raise/cut guardrails.
                  </p>
                </div>
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
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  Auto sizes the sleeve to cover essential-floor gaps from
                  retirement until Social Security starts. The sleeve uses a
                  conservative fixed real return so the bridge is not exposed to
                  equity sequence risk.
                </p>
              </div>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Child cost drop-offs
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Reduces base living spend when each child is expected to be
                    self-funded. Healthcare and college stay modeled separately.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={addChildReduction}
                >
                  Add child
                </Button>
              </div>
              {childReductionDraft.length === 0 ? (
                <p className="mt-3 text-sm text-text-muted">
                  No child reductions yet. Add one if retirement spending should
                  fall when a child gets a job or moves out.
                </p>
              ) : (
                <div className="mt-3 grid gap-2 lg:grid-cols-2">
                  {childReductionDraft.map((row, index) => (
                    <div
                      key={`${row.id ?? 'new'}-${index}`}
                      className="rounded-2xl border border-border/35 bg-surface-muted/15 p-3"
                    >
                      <div className="grid gap-2 sm:grid-cols-3">
                        <label className="text-xs text-text-muted">
                          Child
                          <Input
                            className="mt-1"
                            value={row.label}
                            onChange={(event) =>
                              updateChildReductionDraft(
                                index,
                                'label',
                                event.target.value,
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-text-muted">
                          Drop starts year
                          <Input
                            className="mt-1"
                            inputMode="numeric"
                            value={row.startYear}
                            onChange={(event) =>
                              updateChildReductionDraft(
                                index,
                                'startYear',
                                event.target.value,
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-text-muted">
                          Spend drop $/mo
                          <Input
                            className="mt-1"
                            inputMode="decimal"
                            value={row.monthlyAmount}
                            onChange={(event) =>
                              updateChildReductionDraft(
                                index,
                                'monthlyAmount',
                                event.target.value,
                              )
                            }
                          />
                        </label>
                      </div>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <Input
                          aria-label={`Notes for ${row.label}`}
                          placeholder="notes"
                          value={row.notes}
                          onChange={(event) =>
                            updateChildReductionDraft(
                              index,
                              'notes',
                              event.target.value,
                            )
                          }
                        />
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => removeChildReduction(index)}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                ACA marketplace &amp; Medicare (modeled automatically)
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(
                  [
                    ['silver', 'Silver benchmark'],
                    ['bronze', 'Bronze (lowest premium)'],
                    ['none', 'Off'],
                  ] as const
                ).map(([value, label]) => (
                  <Button
                    key={value}
                    type="button"
                    size="sm"
                    variant={acaDraft.tier === value ? 'default' : 'outline'}
                    onClick={() => updateAcaDraft('tier', value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              {acaDraft.tier === 'none' ? (
                <p className="mt-2 text-xs text-text-muted">
                  Healthcare stream off — only the manual schedule lines below
                  hit the essential floor.
                </p>
              ) : (
                <>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(
                      [
                        ['until22', 'Kids covered to 22'],
                        ['until26', 'Kids covered to 26'],
                        ['adultsOnly', 'Adults only'],
                      ] as const
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        type="button"
                        size="sm"
                        variant={
                          acaDraft.coveredLives === value
                            ? 'default'
                            : 'outline'
                        }
                        onClick={() => updateAcaDraft('coveredLives', value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-text-muted">
                    {acaDraft.coveredLives === 'adultsOnly'
                      ? 'Assumes the kids get coverage elsewhere (e.g. FL KidCare). They also leave the subsidy household here, which slightly understates the credit.'
                      : 'Dependents count toward the subsidy household while covered; adults stay on the marketplace until Medicare at 65.'}
                  </p>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <label className="text-xs text-text-muted">
                      Premium override $/mo (age 21)
                      <Input
                        className="mt-1"
                        inputMode="decimal"
                        aria-label="ACA age-21 monthly premium override"
                        placeholder={
                          preview?.inputs.aca?.chosenAge21Monthly != null
                            ? String(preview.inputs.aca.chosenAge21Monthly)
                            : 'marketplace anchor'
                        }
                        value={acaDraft.premiumOverride}
                        onChange={(event) =>
                          updateAcaDraft('premiumOverride', event.target.value)
                        }
                      />
                    </label>
                    <label className="text-xs text-text-muted">
                      Out-of-pocket $/mo
                      <Input
                        className="mt-1"
                        inputMode="decimal"
                        aria-label="ACA out-of-pocket monthly"
                        value={acaDraft.oopMonthly}
                        onChange={(event) =>
                          updateAcaDraft('oopMonthly', event.target.value)
                        }
                      />
                    </label>
                    <label className="text-xs text-text-muted">
                      Medicare $/person/mo
                      <Input
                        className="mt-1"
                        inputMode="decimal"
                        aria-label="Medicare monthly premium per person"
                        placeholder={String(medicareDefaultMonthlyPerPerson)}
                        value={acaDraft.medicareMonthly}
                        onChange={(event) =>
                          updateAcaDraft('medicareMonthly', event.target.value)
                        }
                      />
                    </label>
                  </div>
                  <p className="mt-2 text-xs text-text-muted">
                    {preview?.inputs.aca?.planYear
                      ? `PY${preview.inputs.aca.planYear} marketplace anchors: benchmark Silver ${formatCurrency(
                          preview.inputs.aca.benchmarkAge21Monthly ?? 0,
                          { decimals: 0 },
                        )}/mo at age 21; modeling ${formatCurrency(
                          preview.inputs.aca.chosenAge21Monthly ?? 0,
                          { decimals: 0 },
                        )}/mo. Premiums scale by the CMS age curve and grow +2%/yr real. `
                      : 'Marketplace plan data not ingested yet — the ACA stream is inactive. '}
                    Out-of-pocket is on top of premiums, every retired year. The
                    seed comes from your deduped Money run-rate (ex-ortho); the
                    employer plan absorbs most OOP today, so it likely
                    understates retirement costs.
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Medicare: blank tracks published rates — 2026 Part B $202.90
                    + Part D $38.99 (CMS) + Medigap Plan G $164/mo (KFF national
                    average) ≈ ${medicareDefaultMonthlyPerPerson}
                    /person. Florida Medigap is issue-age rated and typically
                    pricier — consider raising. Enter 0 to turn the line off.
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Net premiums + out-of-pocket ride the essential floor until
                    Medicare takes over at 65. The premium tax credit reprices
                    off each year&apos;s modeled MAGI, so the 400% FPL subsidy
                    cliff is live in the simulation — see the MAGI column in the
                    drawdown table.
                  </p>
                </>
              )}
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
                  No manual healthcare lines yet — when ACA modeling is on,
                  marketplace premiums + out-of-pocket costs are added to the
                  floor automatically until Medicare at 65. Add lines only for
                  extras the ACA stream doesn&apos;t cover, like LTC reserves at
                  85.
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
        title="Real estate & family assets"
        description="Track property value and ownership without inflating retirement success. Include cash flow or sale proceeds only when you explicitly choose that treatment."
      >
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Tracked equity
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrencyWhole(realEstateSummary.trackedEquity)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Value × ownership minus mortgage. Track-only equity is not
              spendable in Monte Carlo.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Modeled sale proceeds
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrencyWhole(realEstateSummary.modeledLiquidity)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Added to taxable assets only in the listed sale year.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Modeled property income
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(realEstateSummary.modeledIncome, {
                decimals: 0,
              })}
              /yr
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Added as inflation-adjusted retirement income.
            </p>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={addRealEstateAsset}
          >
            Add property
          </Button>
        </div>
        {realEstateDraft.length === 0 ? (
          <p className="mt-3 text-sm text-text-muted">
            No real estate rows yet. Add the Tampa house, note receivable, or
            other family property here. Leave treatment as Track only until the
            value/date/cash path is reliable.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {realEstateDraft.map((row, index) => (
              <div
                key={`${row.id ?? 'new'}-${index}`}
                className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
              >
                <div className="grid gap-3 md:grid-cols-4">
                  <label className="text-xs text-text-muted">
                    Property / asset
                    <Input
                      className="mt-1"
                      value={row.label}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'label',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="text-xs text-text-muted">
                    Value
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      value={row.propertyValue}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'propertyValue',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="text-xs text-text-muted">
                    Ownership %
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      value={row.ownershipPercent}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'ownershipPercent',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="text-xs text-text-muted">
                    Mortgage / note balance
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      value={row.mortgageBalance}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'mortgageBalance',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-4">
                  <label className="text-xs text-text-muted">
                    Retirement treatment
                    <Select
                      value={row.retirementTreatment}
                      onValueChange={(value) =>
                        updateRealEstateDraft(
                          index,
                          'retirementTreatment',
                          value,
                        )
                      }
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="track_only">Track only</SelectItem>
                        <SelectItem value="income">Income stream</SelectItem>
                        <SelectItem value="planned_sale">
                          Planned sale / liquidity
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </label>
                  <label className="text-xs text-text-muted">
                    Income $/yr
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      disabled={row.retirementTreatment !== 'income'}
                      value={row.annualRetirementIncome}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'annualRetirementIncome',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="text-xs text-text-muted">
                    Sale/liquidity year
                    <Input
                      className="mt-1"
                      inputMode="numeric"
                      disabled={row.retirementTreatment !== 'planned_sale'}
                      value={row.liquidityYear}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'liquidityYear',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="text-xs text-text-muted">
                    Net proceeds
                    <Input
                      className="mt-1"
                      inputMode="decimal"
                      disabled={row.retirementTreatment !== 'planned_sale'}
                      value={row.liquidityAmount}
                      onChange={(event) =>
                        updateRealEstateDraft(
                          index,
                          'liquidityAmount',
                          event.target.value,
                        )
                      }
                    />
                  </label>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Input
                    aria-label={`Real estate notes for ${row.label}`}
                    placeholder="ownership, inheritance, sibling split, valuation source"
                    value={row.notes}
                    onChange={(event) =>
                      updateRealEstateDraft(index, 'notes', event.target.value)
                    }
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => removeRealEstateAsset(index)}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
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

      {previewQuery.isFetching && preview ? (
        <div
          role="status"
          className="rounded-2xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-text-muted"
        >
          Updating projection…
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
                Monte Carlo probability for this knob set — 2,500 simulated
                trials, fixed seed so scenario runs compare like-for-like.
              </p>
              {preview && previewQuery.dataUpdatedAt ? (
                <p className="mt-1 text-xs text-text-muted/80">
                  Last ran{' '}
                  {new Date(previewQuery.dataUpdatedAt).toLocaleTimeString([], {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </p>
              ) : null}
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
            description="Share of Monte Carlo trials that first miss the essential floor at each age. Early bars signal sequence-of-returns risk; late bars signal longevity risk."
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

        {preview?.outcomeFraming ? (
          <SectionCard
            variant="surface"
            title="Beyond the success number"
            description="What failure actually means in this model, how much warning it gives, and what the success odds already assume."
            contentClassName="grid gap-3 md:grid-cols-2"
          >
            {preview.outcomeFraming.medianYearsShort != null ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  How plans fail
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {formatCurrencyWhole(
                    preview.outcomeFraming.medianFloorGapReal,
                  )}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  A trial counts as failed after a single year missing the
                  essential floor — discretionary is already cut to zero by
                  then. The median failing trial misses the floor in{' '}
                  {preview.outcomeFraming.medianYearsShort} year
                  {preview.outcomeFraming.medianYearsShort === 1 ? '' : 's'} for
                  this total (today's dollars); the worst decile of failures
                  misses{' '}
                  {formatCurrencyWhole(preview.outcomeFraming.tailFloorGapReal)}
                  .
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  How plans fail
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  No floor misses
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  No simulated trial misses the essential floor at this knob
                  set.
                </p>
              </div>
            )}
            {preview.outcomeFraming.medianWarningYears != null ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Warning time
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {preview.outcomeFraming.medianWarningYears} year
                  {preview.outcomeFraming.medianWarningYears === 1 ? '' : 's'}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Median gap between discretionary spending first trimming to
                  zero and the first floor miss. The model never adjusts — a
                  real household has this long to cut spending, downsize, or
                  return to work before the floor breaks.
                </p>
              </div>
            ) : null}
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Penalty backstop
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {percentPoints(preview.outcomeFraming.penaltyTrialsShare)} of
                trials
              </p>
              <p className="mt-1 text-xs text-text-muted">
                The success odds already assume tapping pre-tax accounts before
                59½ (10% penalty; HSA 20% before 65) when the bridge runs dry.
                {preview.outcomeFraming.medianPenaltyPaidReal != null
                  ? ` Median lifetime penalty cost among those trials: ${formatCurrencyWhole(preview.outcomeFraming.medianPenaltyPaidReal)} (today's dollars).`
                  : ' No trial pays an early-access penalty at this knob set.'}
              </p>
            </div>
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                The other side
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {percentPoints(preview.outcomeFraming.endAboveStartShare)} of
                trials
              </p>
              <p className="mt-1 text-xs text-text-muted">
                End the horizon with at least today's{' '}
                {formatCurrencyWhole(preview.outcomeFraming.startBalanceReal)}{' '}
                still in the accounts (real dollars). Padding the plan further
                trades certain working years for percentage points — weigh it
                against the Sensitivity checks above.
              </p>
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
                    ...(drawdownHasHealthcare
                      ? [
                          {
                            label: 'Healthcare',
                            title:
                              'ACA premium net of the premium tax credit, plus out-of-pocket, plus Medicare from 65. Already part of Spend — it rides the essential floor, so withdrawals are sized to cover it.',
                          },
                        ]
                      : []),
                    ...(drawdownHasAca
                      ? [
                          {
                            label: 'MAGI',
                            title:
                              "Modeled MAGI that priced the ACA subsidy: ordinary income + full Social Security + pre-tax/457(b)/HSA draws + the taxable draw's gain share. The credit ends above 400% of the federal poverty line — amber marks cliff years.",
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
                        {row.partialRetirementYear ? (
                          <Badge
                            variant="secondary"
                            className="ml-2"
                            title="Partial retirement: you are retired, spouse still working — the spend gap above their take-home is drawn from the portfolio."
                          >
                            Partial
                          </Badge>
                        ) : null}
                      </td>
                      <td
                        className={`border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums ${
                          row.spendTrimmed ? 'text-warning' : 'text-text'
                        }`}
                        title={
                          row.spendTrimmed
                            ? [
                                `Below the ${formatCurrency(row.displayTarget, {
                                  decimals: 0,
                                })} target — the withdrawal strategy trimmed discretionary spending this year.`,
                                row.displayAcaReprice > 1
                                  ? `${formatCurrency(row.displayAcaReprice, { decimals: 0 })} of the gap is ACA repricing: the MAGI true-up cut the subsidy below plan.`
                                  : '',
                              ]
                                .filter(Boolean)
                                .join(' ')
                            : undefined
                        }
                      >
                        {formatCurrency(row.displaySpend, { decimals: 0 })}
                      </td>
                      <td
                        className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text"
                        title={
                          row.partialRetirementYear
                            ? `Includes spouse take-home ${formatCurrency(row.displaySpouseNet, { decimals: 0 })}.`
                            : undefined
                        }
                      >
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
                      {drawdownHasHealthcare ? (
                        <td
                          className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text"
                          title={[
                            `ACA gross ${formatCurrency(row.displayAcaGross, { decimals: 0 })} − subsidy ${formatCurrency(row.displayAcaSubsidy, { decimals: 0 })} + out-of-pocket ${formatCurrency(row.displayAcaOop, { decimals: 0 })} + Medicare ${formatCurrency(row.displayMedicare, { decimals: 0 })}.`,
                            row.displayAcaReprice > 1
                              ? `Includes ${formatCurrency(row.displayAcaReprice, { decimals: 0 })} above plan — the MAGI true-up repriced the subsidy.`
                              : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                        >
                          {formatCurrency(row.displayHealthcare, {
                            decimals: 0,
                          })}
                        </td>
                      ) : null}
                      {drawdownHasAca ? (
                        <td
                          className={`border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums ${
                            row.acaPremiumGross > 0.5 && row.acaSubsidy < 0.5
                              ? 'text-warning'
                              : 'text-text-muted'
                          }`}
                          title={
                            row.acaPremiumGross > 0.5 && row.acaSubsidy < 0.5
                              ? 'Above the 400% FPL cliff — no premium tax credit this year.'
                              : undefined
                          }
                        >
                          {row.acaPremiumGross > 0.5
                            ? formatCurrency(row.displayMagi, { decimals: 0 })
                            : '—'}
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
            {drawdownHasHealthcare
              ? ' Healthcare is not subtracted — it rides the essential floor inside Spend, so withdrawals are sized to cover it. Amber-trimmed years can include ACA repricing: when draws push MAGI across a subsidy band, the true-up adds the lost credit to that year’s need.'
              : ''}
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
