'use client'

import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { NetWorthTrendLine } from '@/components/home/today/NetWorthTrendLine'
import { formatBudgetDate } from '@/components/money/budget-helpers'
import { HouseholdHoldingsDialog } from '@/components/money/HouseholdHoldingsDialog'
import { freshnessToneClass } from '@/components/money/moneyAccountsUtils'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
  RetirementAllocationScenario,
  RetirementAllocationScenarioInput,
  RetirementBucketStrategyBucket,
  RetirementIncomeActualsStream,
  RetirementPreviewRequest,
} from '@/lib/api/household'
import { fetchRetirementPreview } from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatPercent,
} from '@/lib/formatters'
import { useDebounce } from '@/lib/hooks/useDebounce'
import {
  useAllocationScenarios,
  useHouseholdFacts,
  useHouseholdPropertyValuations,
  useRefreshHouseholdPropertyValuation,
  useReplaceAllocationScenarios,
  useRetirementIncomeActuals,
  useRetirementPreview,
  useRetirementSpendingActuals,
  useUpdateHouseholdPlanning,
  useUpdateHouseholdProfile,
  useUpdateRetirementIncomeStreamOverride,
} from '@/lib/hooks/useHousehold'
import { categoryBudgetMetaMap } from './household-fact-metadata'
import { buildOwnerOptions } from './owner-options'
import { RetirementResults } from './RetirementResults'
import {
  type AcaDraft,
  type AllocationMode,
  acaConfigFromDraft,
  allocationBreakdownText,
  allocationClasses,
  allocationDraftFromPreview,
  amountInput,
  assetAllocationValue,
  type BucketTimingContext,
  bucketColors,
  bucketLabel,
  bucketOrder,
  bucketStrategyRetirementYear,
  bucketStrategyVariant,
  buildRequest,
  type ChildReductionDraftField,
  childCostDropEstimateFromActuals,
  childReductionPlanningRows,
  clamp,
  clampClaimAge,
  clampOptionalClaimAge,
  collegeScheduleFromDraft,
  currencyTooltip,
  defaultAcaDraft,
  defaultChildReductionDraft,
  defaultDraft,
  defaultPartialDraft,
  defaultRealEstateDraft,
  defaultSocialSecurityPayableRatio,
  defaultSpaxxYieldPercent,
  defaultSpaxxYieldSource,
  defaultWithdrawalDraft,
  estimateSocialSecurityMonthly,
  formatRunwayYears,
  formatShortDate,
  holdingsCoverageVariant,
  householdRetirementAge,
  incomeCadenceLabels,
  incomeMergeTargetNoneValue,
  incomeOwnerAutoValue,
  incomeStatusAutoValue,
  incomeStatusOptions,
  incomeStreamStatus,
  medicareDefaultMonthlyPerPerson,
  type PartialDraft,
  parseNumber,
  parseOptionalAmount,
  parseOptionalNumber,
  parsePercentValue,
  parseTickerMix,
  partialRequestFields,
  percentPoints,
  previewStatusVariant,
  propertyTrendPoints,
  type RealEstateDraft,
  realEstatePlanningRows,
  retirementContributionEstimateFromPlanning,
  returnAssumptionNumber,
  returnAssumptionText,
  socialSecurityFullRetirementAge,
  socialSecuritySourceLabel,
  spendingReductionsFromDraft,
  strategyBucketFillLabel,
  strategyBucketGapLabel,
  strategyBucketPaceLabel,
  strategyBucketTimingLabel,
  timingPaceShortLabel,
  valuationSourceLabel,
  valuationStale,
  type WithdrawalDraft,
  withdrawalConfigFromDraft,
} from './retirement-planner-model'

export {
  estimateSocialSecurityMonthly,
  householdAges,
  memberAge,
  percentInput,
} from './retirement-planner-model'

const strategyBucketColors: Record<string, string> = {
  now: 'var(--color-chart-5)',
  soon: 'var(--color-chart-2)',
  later: 'var(--color-chart-1)',
}

function PlannerAccordionHeader({
  title,
  detail,
  meta,
}: {
  title: string
  detail: string
  meta?: ReactNode
}) {
  return (
    <div className="flex w-full flex-col gap-2 text-left md:flex-row md:items-center md:justify-between">
      <div>
        <p className="font-display italic text-base tracking-tight text-text">
          {title}
        </p>
        <p className="mt-1 text-xs font-normal text-text-muted">{detail}</p>
      </div>
      {meta ? (
        <div className="flex shrink-0 flex-wrap gap-2">{meta}</div>
      ) : null}
    </div>
  )
}

function PlannerFieldLabel({
  children,
  help,
}: {
  children: ReactNode
  help?: ReactNode
}) {
  return (
    <span className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
      {children}
      {help ? (
        <InfoBadge
          label="?"
          detail={help}
          className="h-5 min-w-5 justify-center rounded-full px-1 text-[10px]"
        />
      ) : null}
    </span>
  )
}

function BucketStrategyTooltip({
  active,
  payload,
  timing,
}: {
  active?: boolean
  payload?: Array<{ payload?: RetirementBucketStrategyBucket }>
  timing: BucketTimingContext
}) {
  if (!active) return null
  const bucket = payload?.[0]?.payload
  if (!bucket) return null
  return (
    <div className="max-w-xs rounded-2xl border border-border/50 bg-surface p-4 shadow-xl">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-text">{bucket.label}</p>
        <Badge variant={bucketStrategyVariant(bucket.status)}>
          {bucket.statusLabel}
        </Badge>
      </div>
      <p className="mt-1 text-xs text-text-muted">{bucket.timeHorizon}</p>
      <p className="mt-1 text-xs text-text-muted">
        {strategyBucketTimingLabel(bucket, timing)}
      </p>
      <div className="mt-3 grid gap-1 text-xs text-text-muted">
        <div className="flex justify-between gap-3">
          <span>Current</span>
          <span className="font-mono text-text">
            {formatCurrencyWhole(bucket.currentValue)}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span>Target</span>
          <span className="font-mono text-text">
            {formatCurrencyWhole(bucket.targetValue)}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span>Status</span>
          <span className="text-right text-text">
            {strategyBucketFillLabel(bucket)} · {strategyBucketGapLabel(bucket)}
          </span>
        </div>
      </div>
      <p className="mt-3 text-xs text-text-muted">
        {allocationBreakdownText(bucket.assetAllocation)}
      </p>
      <p className="mt-2 text-xs text-text-muted">
        {strategyBucketPaceLabel(bucket, timing)}
      </p>
      {bucket.holdings.length > 0 ? (
        <div className="mt-3 space-y-1">
          {bucket.holdings.slice(0, 5).map((holding, index) => (
            <div
              key={`${holding.symbol}-${holding.accountLabel ?? ''}-${index}`}
              className="flex justify-between gap-3 text-xs"
            >
              <span className="min-w-0 truncate text-text-muted">
                {holding.label}
                {holding.source === 'inferred' ? ' (inferred)' : ''}
              </span>
              <span className="font-mono text-text">
                {formatCurrencyWhole(holding.currentValue)}
              </span>
            </div>
          ))}
          {bucket.holdings.length > 5 ? (
            <p className="text-xs text-text-muted">
              +{bucket.holdings.length - 5} more holding
              {bucket.holdings.length - 5 === 1 ? '' : 's'}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
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
  const [
    monthlyContributionManualOverride,
    setMonthlyContributionManualOverride,
  ] = useState(false)
  const [partialNetManualOverride, setPartialNetManualOverride] =
    useState(false)
  const [childReductionDraft, setChildReductionDraft] = useState(() =>
    defaultChildReductionDraft(dashboard),
  )
  const [childReductionAutoSeeded, setChildReductionAutoSeeded] =
    useState(false)
  const [realEstateDraft, setRealEstateDraft] = useState(() =>
    defaultRealEstateDraft(dashboard),
  )
  const [plannerOpen, setPlannerOpen] = useState(false)
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
  const householdFactsQuery = useHouseholdFacts()
  const updateIncomeStreamOverride = useUpdateRetirementIncomeStreamOverride()
  const incomeActuals = incomeActualsQuery.data
  const spendingActuals = spendingActualsQuery.data
  const categoryBudgetMeta = useMemo(
    () => categoryBudgetMetaMap(householdFactsQuery.data ?? []),
    [householdFactsQuery.data],
  )
  const childCostDropEstimate = useMemo(
    () =>
      childCostDropEstimateFromActuals(
        spendingActuals,
        categoryBudgetMeta,
        dashboard,
      ),
    [spendingActuals, categoryBudgetMeta, dashboard],
  )
  const retirementContributionEstimate = useMemo(
    () => retirementContributionEstimateFromPlanning(dashboard),
    [dashboard],
  )
  const detectedContributionMonthly = Math.max(
    dashboard.retirementContributionTracker.estimatedMonthlyContributions ?? 0,
    retirementContributionEstimate?.monthlyAmount ?? 0,
  )
  const contributionAutoActive =
    !monthlyContributionManualOverride &&
    (dashboard.profile.monthlySavingsTarget ?? 0) <= 0 &&
    detectedContributionMonthly > 0
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
  const propertyValuationsQuery = useHouseholdPropertyValuations({ limit: 36 })
  const refreshPropertyValuation = useRefreshHouseholdPropertyValuation()
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
  const successRatesUpdatedAt = Math.max(
    previewQuery.dataUpdatedAt || 0,
    actualSpendPreviewQuery.dataUpdatedAt || 0,
  )
  const successRatesRunLabel =
    successRatesUpdatedAt > 0
      ? new Date(successRatesUpdatedAt).toLocaleString([], {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        })
      : null
  const investedAssets = dashboard.overview.investedAssets
  const college529Value = preview?.inputs.college529Value ?? 0
  // Monthly spend plus withdrawal-plan and ACA/Medicare knobs re-project live
  // (debounced); the other planner inputs still wait for "Run preview".
  const debouncedMonthlySpend = useDebounce(draft.monthlySpend, 500)
  useEffect(() => {
    const monthlySpend = parseNumber(debouncedMonthlySpend, 6000)
    setRequest((current) => ({
      ...current,
      monthlySpend,
      annualExpenses: monthlySpend * 12,
    }))
  }, [debouncedMonthlySpend])
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
  const debouncedChildReductions = useDebounce(childReductionDraft, 250)
  useEffect(() => {
    setRequest((current) => ({
      ...current,
      spendingReductions: spendingReductionsFromDraft(
        dashboard,
        draft,
        debouncedChildReductions,
      ),
    }))
  }, [dashboard, draft, debouncedChildReductions])
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
  const draftRetirementInputs = useMemo(
    () => ({
      primaryAge: parseNumber(draft.primaryAge, 0),
      spouseAge: parseOptionalNumber(draft.spouseAge),
      retirementAge: parseNumber(draft.retirementAge, 65),
      spouseRetirementAge: parseOptionalNumber(draft.spouseRetirementAge),
    }),
    [
      draft.primaryAge,
      draft.retirementAge,
      draft.spouseAge,
      draft.spouseRetirementAge,
    ],
  )
  const fullRetirementAge = householdRetirementAge(
    preview?.inputs ?? draftRetirementInputs,
  )
  // Partial-retirement window: years where the primary is retired but the
  // household (spouse) is not. Caption-only derivation.
  const partialWindowStartAge =
    preview?.inputs.retirementAge ?? parseNumber(draft.retirementAge, 65)
  const partialWindowYears = Math.max(
    0,
    fullRetirementAge - partialWindowStartAge,
  )
  // Largest recurring take-home stream from Money transactions — auto-feeds
  // the spouse-net lever until the user edits it.
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
  const [expandedPropertyKeys, setExpandedPropertyKeys] = useState<string[]>([])

  useEffect(() => {
    const nextDraft = defaultDraft(dashboard)
    const nextWithdrawal = defaultWithdrawalDraft(dashboard)
    const nextAca = defaultAcaDraft(dashboard)
    const nextPartial = defaultPartialDraft(dashboard)
    const nextChildReductions = defaultChildReductionDraft(dashboard)
    const nextRealEstate = defaultRealEstateDraft(dashboard)
    setMonthlyContributionManualOverride(false)
    setPartialNetManualOverride(false)
    setChildReductionAutoSeeded(false)
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

  useEffect(() => {
    if (!detectedTakeHome || partialNetManualOverride) return
    const next = amountInput(detectedTakeHome.runRateMonthly)
    setPartialDraft((current) =>
      current.spouseNetMonthly === next
        ? current
        : { ...current, spouseNetMonthly: next },
    )
  }, [detectedTakeHome, partialNetManualOverride])

  useEffect(() => {
    if (childReductionAutoSeeded || !childCostDropEstimate) return
    const next = amountInput(childCostDropEstimate.perChildMonthly)
    let changed = false
    setChildReductionDraft((current) =>
      current.map((row) => {
        if (row.monthlyAmount.trim()) return row
        changed = true
        return {
          ...row,
          monthlyAmount: next,
          amountSource: 'money_actuals',
        }
      }),
    )
    if (changed) {
      setChildReductionAutoSeeded(true)
    }
  }, [childReductionAutoSeeded, childCostDropEstimate])

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
  const bucketStrategy = preview?.bucketStrategy ?? null
  const bucketStrategyPieData = useMemo(
    () =>
      (bucketStrategy?.buckets ?? []).filter(
        (bucket) => bucket.currentValue > 0 || bucket.targetValue > 0,
      ),
    [bucketStrategy?.buckets],
  )
  const bucketRetirementYear = bucketStrategyRetirementYear(
    bucketStrategy,
    preview?.drawdownSchedule,
  )
  const bucketStrategyTiming = useMemo<BucketTimingContext>(
    () => ({
      yearsToRetirement: bucketStrategy?.yearsToRetirement ?? 0,
      retirementYear: bucketRetirementYear,
    }),
    [bucketStrategy?.yearsToRetirement, bucketRetirementYear],
  )
  const bucketStrategyMoveActions = useMemo(
    () =>
      (bucketStrategy?.buckets ?? [])
        .filter(
          (bucket) =>
            bucket.status !== 'aligned' &&
            Math.abs(bucket.gapValue) >= 1 &&
            bucket.targetValue > 0,
        )
        .map(
          (bucket) =>
            `${bucket.label}: ${strategyBucketPaceLabel(
              bucket,
              bucketStrategyTiming,
            )}`,
        ),
    [bucketStrategy?.buckets, bucketStrategyTiming],
  )
  const terminalProjection =
    projectionData.length > 0 ? projectionData[projectionData.length - 1] : null
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
  const valuationHistoryByProperty = useMemo(
    () =>
      new Map(
        (propertyValuationsQuery.data?.items ?? []).map((history) => [
          history.housingCostId,
          history,
        ]),
      ),
    [propertyValuationsQuery.data?.items],
  )
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

  const togglePropertyExpanded = (key: string) => {
    setExpandedPropertyKeys((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    )
  }

  const saveRealEstateAssets = async () => {
    const snapshot = await updatePlanning.mutateAsync({
      housingCosts: realEstatePlanningRows(dashboard, realEstateDraft),
    })
    if (snapshot?.housingCosts) {
      setRealEstateDraft(
        defaultRealEstateDraft({
          ...dashboard,
          planning: snapshot,
        } as HouseholdFinanceDashboard),
      )
    }
    return snapshot
  }

  const refreshPropertyValue = async (row: RealEstateDraft) => {
    const address = (row.propertyAddress || row.label).trim()
    if (
      !address ||
      refreshPropertyValuation.isPending ||
      updatePlanning.isPending
    ) {
      return
    }
    let housingCostId = row.id ?? null
    if (!housingCostId) {
      const snapshot = await saveRealEstateAssets()
      const label = row.label.trim().toLowerCase()
      const normalizedAddress = row.propertyAddress.trim().toLowerCase()
      const saved = snapshot?.housingCosts?.find((candidate) => {
        if (candidate.id === row.id) return true
        const candidateLabel = candidate.label.trim().toLowerCase()
        const candidateAddress = (candidate.propertyAddress ?? '')
          .trim()
          .toLowerCase()
        return (
          candidateLabel === label &&
          (!normalizedAddress || candidateAddress === normalizedAddress)
        )
      })
      housingCostId = saved?.id ?? null
    }
    if (!housingCostId) return
    await refreshPropertyValuation.mutateAsync({
      housingCostId,
      address,
    })
  }

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
      monthlySavingsTarget: contributionAutoActive
        ? dashboard.profile.monthlySavingsTarget
        : parseNumber(draft.monthlyContribution, 0),
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
    if (key === 'monthlyContribution') {
      setMonthlyContributionManualOverride(true)
    }
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const updatePartialDraft = (key: keyof PartialDraft, value: string) => {
    if (key === 'spouseNetMonthly') {
      setPartialNetManualOverride(true)
    }
    setPartialDraft((current) => ({ ...current, [key]: value }))
  }

  const updateChildReductionDraft = (
    index: number,
    key: ChildReductionDraftField,
    value: string,
  ) => {
    setChildReductionDraft((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index
          ? {
              ...row,
              [key]: value,
              amountSource:
                key === 'monthlyAmount' ? 'manual' : row.amountSource,
            }
          : row,
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
        amountSource: 'manual',
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
        propertyAddress: '',
        propertyValue: '',
        valueAsOf: '',
        valuationSource: '',
        valuationConfidence: '',
        valuationRangeLow: '',
        valuationRangeHigh: '',
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
        title="Overview"
        description="Readiness, bucket alignment, Monte Carlo bands, and data coverage at a glance."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Success rates
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
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-muted">
                  Plan{' '}
                  {formatCurrency(parseNumber(draft.monthlySpend, 0), {
                    decimals: 0,
                  })}
                  /mo
                </span>
                <span className="font-mono text-lg text-text">
                  {preview
                    ? percentPoints(preview.successProbability)
                    : previewQuery.isFetching
                      ? 'running…'
                      : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-muted">
                  Current spend{' '}
                  {spendingActuals
                    ? `${formatCurrency(spendingActuals.totalMonthlySpend, {
                        decimals: 0,
                      })}/mo`
                    : '—'}
                </span>
                <span className="font-mono text-lg text-text">
                  {actualSpendMonthly == null
                    ? '—'
                    : actualSpendPreview
                      ? percentPoints(actualSpendPreview.successProbability)
                      : actualSpendPreviewQuery.isFetching
                        ? 'running…'
                        : '—'}
                </span>
              </div>
            </div>
            {successRatesRunLabel ? (
              <p className="mt-2 text-xs text-text-muted/80">
                Last run {successRatesRunLabel}
              </p>
            ) : null}
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Invested assets
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrencyWhole(investedAssets)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {college529Value > 0
                ? `Includes 529 college sleeve ${formatCurrencyWhole(
                    college529Value,
                  )}.`
                : 'Same source as Today.'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Median ending
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {preview
                ? formatCurrencyWhole(preview.medianEndingBalance)
                : previewQuery.isFetching
                  ? 'running…'
                  : '—'}
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

        <div className="mt-4 grid items-start gap-4 xl:grid-cols-12">
          {bucketStrategy && bucketStrategyPieData.length > 0 ? (
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4 xl:col-span-8">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Bucket strategy
                  </p>
                  <p className="mt-1 text-sm font-semibold text-text">
                    {bucketStrategy.label}
                  </p>
                  <p className="mt-1 max-w-2xl text-xs text-text-muted">
                    {bucketStrategy.detail}
                  </p>
                  <p className="mt-1 max-w-2xl text-xs text-text-muted">
                    Gaps are shown as a glide-path pace over the remaining
                    retirement runway, not as same-day trade instructions.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={bucketStrategyVariant(bucketStrategy.status)}>
                    {bucketStrategy.statusLabel}
                  </Badge>
                  <Badge variant="outline">
                    {formatPercent(bucketStrategy.alignmentScore * 100, {
                      decimals: 0,
                    })}{' '}
                    aligned
                  </Badge>
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(13rem,0.85fr)_minmax(0,1.15fr)]">
                <div>
                  <div className="h-56 rounded-2xl border border-border/25 bg-bg/20 p-2">
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={220}
                      minHeight={200}
                      initialDimension={{ width: 320, height: 224 }}
                    >
                      <PieChart>
                        <Pie
                          data={bucketStrategyPieData}
                          dataKey="currentValue"
                          nameKey="label"
                          innerRadius={48}
                          outerRadius={80}
                          paddingAngle={2}
                        >
                          {bucketStrategyPieData.map((bucket) => (
                            <Cell
                              key={bucket.bucketId}
                              fill={strategyBucketColors[bucket.bucketId]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          content={
                            <BucketStrategyTooltip
                              timing={bucketStrategyTiming}
                            />
                          }
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="rounded-xl border border-border/25 bg-bg/25 p-2">
                      <p className="text-text-muted">Current</p>
                      <p className="mt-1 font-mono text-sm text-text">
                        {formatCurrencyWhole(bucketStrategy.currentTotal)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-border/25 bg-bg/25 p-2">
                      <p className="text-text-muted">Target</p>
                      <p className="mt-1 font-mono text-sm text-text">
                        {formatCurrencyWhole(bucketStrategy.targetTotal)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-border/25 bg-bg/25 p-2">
                      <p className="text-text-muted">Full retirement</p>
                      <p className="mt-1 font-mono text-sm text-text">
                        {bucketRetirementYear
                          ? bucketRetirementYear
                          : formatRunwayYears(bucketStrategy.yearsToRetirement)}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-2">
                  {bucketStrategy.buckets.map((bucket) => (
                    <div
                      key={bucket.bucketId}
                      className="rounded-xl border border-border/30 bg-bg/25 p-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className="h-3 w-3 rounded-full"
                              style={{
                                backgroundColor:
                                  strategyBucketColors[bucket.bucketId],
                              }}
                            />
                            <p className="truncate text-sm font-semibold text-text">
                              {bucket.label}
                            </p>
                          </div>
                          <p className="mt-1 text-xs text-text-muted">
                            {bucket.timeHorizon} ·{' '}
                            {allocationBreakdownText(bucket.assetAllocation)}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            Timing:{' '}
                            {strategyBucketTimingLabel(
                              bucket,
                              bucketStrategyTiming,
                            )}
                          </p>
                        </div>
                        <Badge variant={bucketStrategyVariant(bucket.status)}>
                          {strategyBucketFillLabel(bucket)}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                        <div>
                          <p className="text-text-muted">Current</p>
                          <p className="font-mono text-text">
                            {formatCurrencyWhole(bucket.currentValue)}
                          </p>
                        </div>
                        <div>
                          <p className="text-text-muted">Target</p>
                          <p className="font-mono text-text">
                            {formatCurrencyWhole(bucket.targetValue)}
                          </p>
                        </div>
                        <div>
                          <p className="text-text-muted">Gap</p>
                          <p className="font-mono text-text">
                            {strategyBucketGapLabel(bucket)}
                          </p>
                        </div>
                        <div>
                          <p className="text-text-muted">Pace</p>
                          <p className="font-mono text-text">
                            {timingPaceShortLabel(bucket, bucketStrategyTiming)}
                          </p>
                        </div>
                      </div>
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-border/30">
                        <div
                          className={`h-full rounded-full ${
                            bucket.status === 'underfilled' ||
                            bucket.status === 'empty'
                              ? 'bg-warning'
                              : bucket.status === 'overfilled'
                                ? 'bg-text-muted'
                                : 'bg-success'
                          }`}
                          style={{
                            width: `${
                              Math.min(
                                Math.max(
                                  bucket.fillRatio,
                                  bucket.targetValue > 0 ? 0.03 : 0,
                                ),
                                1,
                              ) * 100
                            }%`,
                          }}
                        />
                      </div>
                      <p className="mt-2 text-xs text-text-muted">
                        {strategyBucketPaceLabel(bucket, bucketStrategyTiming)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div
                  className={`rounded-xl border p-3 ${
                    bucketStrategyMoveActions.length > 0
                      ? 'border-warning/30 bg-warning/10'
                      : 'border-success/25 bg-success/10'
                  }`}
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Glide-path funding plan
                  </p>
                  {bucketStrategyMoveActions.length > 0 ? (
                    <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-text-muted">
                      {bucketStrategyMoveActions.map((action) => (
                        <li key={action}>{action}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-text-muted">
                      Current buckets match the target bands for this retirement
                      date.
                    </p>
                  )}
                </div>
                <div className="rounded-xl border border-border/25 bg-bg/25 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Monte Carlo inclusion
                  </p>
                  <p className="mt-2 text-xs text-text-muted">
                    {bucketStrategy.monteCarloDetail}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          <div className="grid gap-4 xl:col-span-4">
            {projectionData.length > 0 ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Monte Carlo band
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      Quick read of the P10 / P50 / P90 path.
                    </p>
                  </div>
                  {preview ? (
                    <Badge
                      variant={previewStatusVariant(
                        preview.successProbability,
                        preview.trustedTotals,
                      )}
                    >
                      {percentPoints(preview.successProbability)} odds
                    </Badge>
                  ) : null}
                </div>
                <div className="mt-3 h-40">
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={220}
                    minHeight={140}
                    initialDimension={{ width: 360, height: 160 }}
                  >
                    <AreaChart
                      data={projectionData}
                      margin={{ top: 8, right: 4, left: 4, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--color-border)"
                      />
                      <XAxis dataKey="age" tickLine={false} minTickGap={18} />
                      <YAxis hide />
                      <Tooltip formatter={currencyTooltip} />
                      <Area
                        type="monotone"
                        dataKey="p90"
                        name="P90"
                        stroke="var(--color-chart-3)"
                        fill="var(--color-chart-3)"
                        fillOpacity={0.08}
                        dot={false}
                      />
                      <Area
                        type="monotone"
                        dataKey="p50"
                        name="P50"
                        stroke="var(--color-chart-1)"
                        fill="var(--color-chart-1)"
                        fillOpacity={0.18}
                        dot={false}
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
                {terminalProjection ? (
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-text-muted">
                    <div>
                      <p>P10</p>
                      <p className="font-mono text-text">
                        {formatCurrencyWhole(terminalProjection.p10)}
                      </p>
                    </div>
                    <div>
                      <p>P50</p>
                      <p className="font-mono text-text">
                        {formatCurrencyWhole(terminalProjection.p50)}
                      </p>
                    </div>
                    <div>
                      <p>P90</p>
                      <p className="font-mono text-text">
                        {formatCurrencyWhole(terminalProjection.p90)}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {(preview?.leverImpacts ?? []).length > 0 ? (
              <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                  Sensitivity checks
                </p>
                <div className="mt-3 grid gap-2">
                  {(preview?.leverImpacts ?? []).map((lever) => (
                    <div
                      key={lever.id}
                      className="rounded-xl border border-border/30 bg-bg/25 p-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-text">
                            {lever.label}
                          </p>
                          <p className="mt-1 text-xs uppercase tracking-wide text-text-muted">
                            {lever.value}
                          </p>
                        </div>
                        <p className="font-mono text-lg font-semibold text-text">
                          {formatPercent(lever.deltaSuccessProbability * 100, {
                            decimals: 1,
                            sign: true,
                          })}
                        </p>
                      </div>
                      <p className="mt-2 text-xs text-text-muted">
                        {lever.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {bucketTotals.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-5 text-sm text-text-muted xl:col-span-5">
              No account buckets are available yet.
            </div>
          ) : (
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4 xl:col-span-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                Account / tax buckets
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {bucketTotals.map((bucket) => (
                  <div
                    key={bucket.bucket}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border/25 bg-bg/25 px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{
                          backgroundColor: bucketColors[bucket.bucket],
                        }}
                      />
                      <p className="truncate text-sm font-semibold text-text">
                        {bucketLabel(bucket.bucket)}
                      </p>
                    </div>
                    <p className="font-mono text-sm tabular-nums text-text">
                      {formatCurrencyWhole(bucket.value)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {holdingsCoverage ? (
            <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4 xl:col-span-7">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Holdings coverage
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Exact positions improve bucket allocation accuracy.
                  </p>
                </div>
                <Badge
                  variant={holdingsCoverageVariant(holdingsCoverage.status)}
                >
                  {holdingsCoverage.label}
                </Badge>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(9rem,0.7fr)_minmax(0,1.3fr)]">
                <div>
                  <p className="font-mono text-3xl text-text">
                    {formatPercent(holdingsCoverage.exactShare * 100, {
                      decimals: 0,
                    })}
                  </p>
                  <p className="mt-2 text-xs text-text-muted">
                    {holdingsCoverage.detail}
                  </p>
                </div>
                <div className="grid gap-2 text-xs text-text-muted sm:grid-cols-3">
                  <div className="rounded-xl border border-border/25 bg-bg/25 p-3">
                    <p>Exact holdings/cash</p>
                    <p className="mt-1 font-mono text-sm text-text">
                      {formatCurrencyWhole(holdingsCoverage.exactValue)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-border/25 bg-bg/25 p-3">
                    <p>Account-value-only</p>
                    <p className="mt-1 font-mono text-sm text-text">
                      {formatCurrencyWhole(holdingsCoverage.inferredValue)}
                    </p>
                  </div>
                  {accountAllocationCoverage ? (
                    <div className="rounded-xl border border-border/25 bg-bg/25 p-3">
                      <p>Account allocation</p>
                      <p className="mt-1 text-sm text-text">
                        {accountAllocationCoverage.label}
                      </p>
                      <p className="text-xs text-text-muted">
                        {formatPercent(
                          accountAllocationCoverage.exactShare * 100,
                          {
                            decimals: 0,
                          },
                        )}{' '}
                        exact
                      </p>
                    </div>
                  ) : null}
                </div>
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
                    <div className="mt-4 grid gap-2 lg:grid-cols-2">
                      {holdingsCoverage.accounts.map((account, index) => (
                        <div
                          key={`${account.label}-${account.bucketType}-${index}`}
                          className="rounded-xl border border-border/25 bg-bg/25 px-3 py-2"
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

      <SectionCard
        variant="surface"
        title="Planning & assumptions"
        description="A cleaner workspace for the numbers that move the plan. Open a section, adjust values, then run preview."
        padding={plannerOpen ? 'md' : 'none'}
        contentClassName={plannerOpen ? 'space-y-4' : undefined}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setPlannerOpen((open) => !open)}
            >
              {plannerOpen ? 'Collapse planning' : 'Expand planner'}
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
          <Accordion
            type="multiple"
            defaultValue={['core']}
            className="space-y-3"
          >
            <AccordionItem
              value="core"
              className="rounded-2xl border border-border/40 bg-surface-muted/10 px-0"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <PlannerAccordionHeader
                  title="Core assumptions"
                  detail="Retirement ages, spend target, savings, inflation, Social Security, and any one-spouse-working bridge."
                  meta={
                    <>
                      <Badge
                        variant={hasPendingChanges ? 'warning' : 'success'}
                      >
                        {hasPendingChanges ? 'Preview pending' : 'In sync'}
                      </Badge>
                      <InfoBadge
                        label="How to use"
                        interactive={false}
                        detail="Keep this open for common edits. The deeper sections below stay collapsed until you need income audits, withdrawal rules, property treatment, or allocation what-ifs."
                      />
                    </>
                  }
                />
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-5">
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
                    <PlannerFieldLabel help="Manual retirement spending target. The Spending & income section compares it with complete-month Money data.">
                      Spend / month
                    </PlannerFieldLabel>
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
                    {retirementContributionEstimate ? (
                      <p className="mt-2 text-xs text-text-muted">
                        Detected retirement contribution source:{' '}
                        {retirementContributionEstimate.sources
                          .map((source) => source.label)
                          .join(', ')}{' '}
                        ≈{' '}
                        {formatCurrency(
                          retirementContributionEstimate.monthlyAmount,
                          { decimals: 0 },
                        )}
                        /mo
                        {contributionAutoActive
                          ? ' — auto-fed into this plan until edited.'
                          : '.'}
                      </p>
                    ) : null}
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
                    <PlannerFieldLabel help="Percent of scheduled Social Security benefits modeled after projected trust fund depletion.">
                      SS payable %
                    </PlannerFieldLabel>
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
                          updatePartialDraft(
                            'spouseNetMonthly',
                            event.target.value,
                          )
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
                      ? 'Off until spouse take-home is entered.'
                      : partialWindowYears > 0
                        ? `Window: age ${partialWindowStartAge}–${fullRetirementAge - 1}; portfolio covers spend above spouse take-home.`
                        : 'No window — both retirements land in the same year.'}
                    {partialDraft.spouseNetMonthly.trim() !== '' &&
                    partialWindowYears > 0 ? (
                      <>
                        {' '}
                        <InfoBadge
                          label="Details"
                          detail="The model is penalty-aware. Spouse gross wages set tax brackets but their payroll taxes are assumed already removed from net take-home. Save/month continues through the window; surplus take-home is not auto-invested."
                        />
                      </>
                    ) : null}
                  </p>
                  {detectedTakeHome ? (
                    <p className="mt-1 text-xs text-text-muted">
                      Detected from Money transactions: {detectedTakeHome.label}
                      {detectedTakeHome.owner
                        ? ` (${detectedTakeHome.owner})`
                        : ''}{' '}
                      ≈{' '}
                      {formatCurrency(detectedTakeHome.runRateMonthly, {
                        decimals: 0,
                      })}
                      /mo
                      {detectedTakeHome.active
                        ? ''
                        : `, last deposit ${detectedTakeHome.lastDate}`}{' '}
                      — auto-fed into this plan until edited.
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
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  <span>
                    Social Security:{' '}
                    <span className="font-mono text-text">
                      {formatCurrency(socialSecurityEstimate.primary ?? 0, {
                        decimals: 0,
                      })}
                      /mo @ {socialSecurityEstimate.primaryClaimAge}
                    </span>{' '}
                    +{' '}
                    <span className="font-mono text-text">
                      {formatCurrency(socialSecurityEstimate.spouse ?? 0, {
                        decimals: 0,
                      })}
                      /mo @ {socialSecurityEstimate.spouseClaimAge}
                    </span>
                    ; payable at{' '}
                    {formatPercent(socialSecurityEstimate.payableRatio * 100, {
                      decimals: 0,
                    })}
                    .
                  </span>
                  <InfoBadge
                    label="SSA assumptions"
                    detail={`Primary: ${socialSecurityEstimate.primarySource}; spouse: ${socialSecurityEstimate.spouseSource}. Salary estimates assume earnings start at 22 and stop at retirement, with zeros filling the rest of the 35-year average. For planning-grade accuracy, enter the monthly benefit from ssa.gov with average future annual salary set to $0.`}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="spending"
              className="rounded-2xl border border-border/40 bg-surface-muted/10 px-0"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <PlannerAccordionHeader
                  title="Spending & income"
                  detail="Compare actual Money data against the manual retirement spend target."
                  meta={
                    <Badge variant="outline">
                      {spendingActuals?.coverageMonths ?? 0} complete mo
                    </Badge>
                  }
                />
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-5">
                <SectionCard variant="ghost" padding="none">
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
                              ? `${formatCurrency(
                                  spendingActuals.totalMonthlySpend,
                                  {
                                    decimals: 0,
                                  },
                                )}/mo`
                              : '—'}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            Monte Carlo:{' '}
                            <span className="font-mono text-text">
                              {actualSpendPreview
                                ? percentPoints(
                                    actualSpendPreview.successProbability,
                                  )
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
                            {formatCurrency(
                              parseNumber(draft.monthlySpend, 0),
                              {
                                decimals: 0,
                              },
                            )}
                            /mo
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            Monte Carlo:{' '}
                            <span className="font-mono text-text">
                              {preview
                                ? percentPoints(preview.successProbability)
                                : '—'}
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
                              ? `${spendingActuals.firstMonth ?? '—'}–${spendingActuals.lastMonth ?? '—'} complete months.`
                              : 'No complete spending window yet.'}
                            {spendingActuals ? (
                              <>
                                {' '}
                                <InfoBadge
                                  label="Source"
                                  detail={spendingActuals.sourceLabel}
                                />
                              </>
                            ) : null}
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
                          . Either the income ended or newer bank statements
                          have not been imported — only active streams count
                          toward the take-home figure above.
                        </div>
                      ) : null}
                      <div className="mt-4 overflow-x-auto">
                        <table className="w-full min-w-[58rem] text-sm">
                          <thead>
                            <tr className="text-left text-xs uppercase tracking-[0.12em] text-text-muted">
                              <th className="py-1.5 pr-3">Stream</th>
                              <th className="py-1.5 pr-3">Owner</th>
                              <th className="py-1.5 pr-3">Cadence</th>
                              <th className="py-1.5 pr-3 text-right">
                                Run-rate / mo
                              </th>
                              <th className="py-1.5 pr-3">Months</th>
                              <th className="py-1.5 pr-3">Last deposit</th>
                              <th className="py-1.5">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(incomeActuals?.streams ?? []).map((stream) => {
                              const status = incomeStreamStatus(stream)
                              const mergeTargets =
                                activeIncomeMergeTargets.filter(
                                  (target) =>
                                    target.streamKey !== stream.streamKey,
                                )
                              const selectedMergeTarget =
                                incomeActuals?.streams.find(
                                  (candidate) =>
                                    candidate.streamKey ===
                                    stream.mergedIntoStreamKey,
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
                                      disabled={
                                        updateIncomeStreamOverride.isPending
                                      }
                                      onValueChange={(value) =>
                                        saveIncomeStreamOverride(stream, {
                                          ownerName:
                                            value === incomeOwnerAutoValue
                                              ? null
                                              : value,
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
                                        <SelectItem
                                          value={incomeOwnerAutoValue}
                                        >
                                          Auto
                                          {stream.owner
                                            ? ` · ${stream.owner}`
                                            : ''}
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
                                          stream.statusOverride ??
                                          incomeStatusAutoValue
                                        }
                                        disabled={
                                          updateIncomeStreamOverride.isPending
                                        }
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
                                          <SelectItem
                                            value={incomeStatusAutoValue}
                                          >
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
                                          <Badge variant="outline">
                                            Manual
                                          </Badge>
                                        ) : null}
                                      </div>
                                      {stream.status === 'merged' ? (
                                        <Select
                                          value={
                                            stream.mergedIntoStreamKey ??
                                            incomeMergeTargetNoneValue
                                          }
                                          disabled={
                                            updateIncomeStreamOverride.isPending
                                          }
                                          onValueChange={(value) => {
                                            if (
                                              value ===
                                              incomeMergeTargetNoneValue
                                            ) {
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
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-muted">
                        <InfoBadge
                          label="Run-rate math"
                          detail={`${incomeActuals?.sourceLabel ?? ''} Weekly and biweekly deposits are normalized to monthly run-rates; observed $/mo averages over each stream's own active months.`}
                        />
                        {(incomeActuals?.aliasRowsCollapsed ?? 0) > 0 ? (
                          <InfoBadge
                            label={`${incomeActuals?.aliasRowsCollapsed} duplicates collapsed`}
                            detail="Duplicate statement rows from the same deposit imported under two account labels were excluded from the income run-rate."
                          />
                        ) : null}
                      </div>
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
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="withdrawal"
              className="rounded-2xl border border-border/40 bg-surface-muted/10 px-0"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <PlannerAccordionHeader
                  title="Withdrawal, healthcare & college"
                  detail="Guardrails, bridge sizing, child drop-offs, ACA/Medicare, LTC, and education schedules."
                  meta={
                    <InfoBadge
                      label="Method"
                      interactive={false}
                      detail="Floor-and-upside model: guaranteed income and bridge assets cover the floor; portfolio withdrawals fund discretionary spend and adjust with guardrails."
                    />
                  }
                />
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-5">
                <SectionCard
                  variant="ghost"
                  padding="none"
                  actions={
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void saveDraftDefaults()}
                      disabled={
                        updateProfile.isPending || updatePlanning.isPending
                      }
                    >
                      {updateProfile.isPending || updatePlanning.isPending
                        ? 'Saving…'
                        : 'Save plan'}
                    </Button>
                  }
                >
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                        Baseline strategy
                      </p>
                      <div className="mt-2 rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                        <Badge variant="success">Guardrails</Badge>
                        <div className="mt-2">
                          <InfoBadge
                            label="Annual guardrails"
                            detail="One retirement paycheck is adjusted annually when the portfolio crosses raise/cut guardrails."
                          />
                        </div>
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
                          updateWithdrawalDraft(
                            'declineRate',
                            values[0] ?? 0.01,
                          )
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
                            <label
                              key={key}
                              className="text-xs text-text-muted"
                            >
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
                            onClick={() =>
                              updateWithdrawalDraft('bridgeMode', value)
                            }
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
                      <div className="mt-2">
                        <InfoBadge
                          label="Bridge logic"
                          detail="Auto size covers essential-floor gaps from retirement until Social Security starts. The sleeve uses a conservative fixed real return to avoid equity sequence risk."
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                          Child cost drop-offs
                        </p>
                        <div className="mt-1">
                          <InfoBadge
                            label="Separate from college"
                            detail="Reduces base living spend when each child is expected to be self-funded. Healthcare and college stay modeled in their own schedules."
                          />
                        </div>
                        {childCostDropEstimate ? (
                          <p className="mt-2 text-xs text-text-muted">
                            Auto-fed from child-owned Money categories:{' '}
                            {childCostDropEstimate.categories.join(', ')} ≈{' '}
                            {formatCurrency(
                              childCostDropEstimate.perChildMonthly,
                              { decimals: 0 },
                            )}
                            /child/mo. Shared groceries, retail, healthcare, and
                            college stay separate unless categorized to the
                            children.
                          </p>
                        ) : null}
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
                        No child reductions yet. Add one if retirement spending
                        should fall when a child gets a job or moves out.
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
                                {row.amountSource === 'money_actuals'
                                  ? ' (auto)'
                                  : ''}
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
                          variant={
                            acaDraft.tier === value ? 'default' : 'outline'
                          }
                          onClick={() => updateAcaDraft('tier', value)}
                        >
                          {label}
                        </Button>
                      ))}
                    </div>
                    {acaDraft.tier === 'none' ? (
                      <p className="mt-2 text-xs text-text-muted">
                        Healthcare stream off — only the manual schedule lines
                        below hit the essential floor.
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
                              onClick={() =>
                                updateAcaDraft('coveredLives', value)
                              }
                            >
                              {label}
                            </Button>
                          ))}
                        </div>
                        <div className="mt-2">
                          <InfoBadge
                            label="Coverage household"
                            detail={
                              acaDraft.coveredLives === 'adultsOnly'
                                ? 'Kids are assumed covered elsewhere (e.g. FL KidCare) and leave the subsidy household, which can understate the credit.'
                                : 'Dependents count toward the subsidy household while covered; adults stay on marketplace coverage until Medicare at 65.'
                            }
                          />
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-3">
                          <label className="text-xs text-text-muted">
                            Premium override $/mo (age 21)
                            <Input
                              className="mt-1"
                              inputMode="decimal"
                              aria-label="ACA age-21 monthly premium override"
                              placeholder={
                                preview?.inputs.aca?.chosenAge21Monthly != null
                                  ? String(
                                      preview.inputs.aca.chosenAge21Monthly,
                                    )
                                  : 'marketplace anchor'
                              }
                              value={acaDraft.premiumOverride}
                              onChange={(event) =>
                                updateAcaDraft(
                                  'premiumOverride',
                                  event.target.value,
                                )
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
                              placeholder={String(
                                medicareDefaultMonthlyPerPerson,
                              )}
                              value={acaDraft.medicareMonthly}
                              onChange={(event) =>
                                updateAcaDraft(
                                  'medicareMonthly',
                                  event.target.value,
                                )
                              }
                            />
                          </label>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <InfoBadge
                            label={
                              preview?.inputs.aca?.planYear
                                ? `PY${preview.inputs.aca.planYear} ACA anchor`
                                : 'ACA inactive'
                            }
                            detail={
                              preview?.inputs.aca?.planYear
                                ? `Benchmark Silver ${formatCurrency(
                                    preview.inputs.aca.benchmarkAge21Monthly ??
                                      0,
                                    { decimals: 0 },
                                  )}/mo at age 21; modeling ${formatCurrency(
                                    preview.inputs.aca.chosenAge21Monthly ?? 0,
                                    { decimals: 0 },
                                  )}/mo. Premiums scale by the CMS age curve and grow +2%/yr real.`
                                : 'Marketplace plan data has not been ingested, so the ACA stream is inactive.'
                            }
                          />
                          <InfoBadge
                            label="OOP seed"
                            detail="Out-of-pocket is added on top of premiums each retired year. The seed comes from deduped Money spend excluding ortho; employer coverage absorbs most OOP today, so it may understate retirement costs."
                          />
                          <InfoBadge
                            label="Medicare default"
                            detail={`Blank tracks published rates: 2026 Part B $202.90 + Part D $38.99 + Medigap Plan G $164/mo ≈ $${medicareDefaultMonthlyPerPerson}/person. Florida Medigap can be pricier; enter 0 to turn it off.`}
                          />
                          <InfoBadge
                            label="MAGI repricing"
                            detail="Net premiums and out-of-pocket costs ride the essential floor until Medicare at 65. Premium tax credit reprices from modeled MAGI each year; inspect the MAGI column in drawdown."
                          />
                        </div>
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
                        No manual lines. Add only extras the ACA/Medicare stream
                        does not cover, like LTC reserves.
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
                    <div className="mt-2">
                      <InfoBadge
                        label={`529 excluded${preview?.inputs.college529Value ? ` · ${formatCurrencyWhole(preview.inputs.college529Value)}` : ''}`}
                        detail="529 accounts are earmarked for college and excluded from the retirement portfolio; each year's college spend drains them first and only overflow hits retirement money."
                      />
                    </div>
                    {withdrawalDraft.college.length === 0 ? (
                      <p className="mt-2 text-xs text-text-muted">
                        No college lines yet. Add a line per spend year.
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
                        {preview
                          ? percentPoints(preview.successProbability)
                          : '—'}
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
                          : formatPercent(
                              withdrawalSummary.firstYearRate * 100,
                              {
                                decimals: 1,
                              },
                            )}
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
                      <ResponsiveContainer
                        width="100%"
                        height="100%"
                        minWidth={240}
                        minHeight={260}
                        initialDimension={{ width: 520, height: 280 }}
                      >
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
                    <div className="mt-2">
                      <InfoBadge
                        label="Read the chart"
                        detail="Bars show each funding source. The floor line is essentials plus healthcare; discretionary spend above it declines with age."
                      />
                    </div>
                  </div>
                </SectionCard>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="real-estate"
              className="rounded-2xl border border-border/40 bg-surface-muted/10 px-0"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <PlannerAccordionHeader
                  title="Real estate & family assets"
                  detail="Track property value, ownership, income, or planned sale proceeds without accidentally inflating success."
                  meta={
                    <Badge variant="outline">
                      {formatCurrencyWhole(realEstateSummary.trackedEquity)}
                    </Badge>
                  }
                />
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-5">
                <SectionCard variant="ghost" padding="none">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                        Tracked equity
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-text">
                        {formatCurrencyWhole(realEstateSummary.trackedEquity)}
                      </p>
                      <div className="mt-1">
                        <InfoBadge
                          label="Track-only"
                          detail="Value × ownership minus mortgage. Track-only equity is not spendable in Monte Carlo."
                        />
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                        Modeled sale proceeds
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-text">
                        {formatCurrencyWhole(
                          realEstateSummary.modeledLiquidity,
                        )}
                      </p>
                      <div className="mt-1">
                        <InfoBadge
                          label="Sale year only"
                          detail="Added to taxable assets only in the listed sale year."
                        />
                      </div>
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
                      <div className="mt-1">
                        <InfoBadge
                          label="Inflation-adjusted"
                          detail="Added as inflation-adjusted retirement income."
                        />
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <InfoBadge
                      label="Saving"
                      detail="Property edits are saved by Save properties or the broader Save assumptions button. Save & refresh persists a new row first, then pulls the latest county valuation."
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={updatePlanning.isPending}
                        onClick={() => void saveRealEstateAssets()}
                      >
                        Save properties
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={addRealEstateAsset}
                      >
                        Add property
                      </Button>
                    </div>
                  </div>
                  {realEstateDraft.length === 0 ? (
                    <p className="mt-3 text-sm text-text-muted">
                      No real estate rows yet. Add the Tampa house, note
                      receivable, or other family property here. Leave treatment
                      as Track only until the value/date/cash path is reliable.
                    </p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      {realEstateDraft.map((row, index) => {
                        const propertyKey = row.id ?? `new-${index}`
                        const expanded =
                          expandedPropertyKeys.includes(propertyKey)
                        const history = row.id
                          ? valuationHistoryByProperty.get(row.id)
                          : undefined
                        const trendPoints = propertyTrendPoints(history?.points)
                        const value = parseOptionalAmount(row.propertyValue)
                        const stale = valuationStale(row.valueAsOf)
                        return (
                          <div
                            key={propertyKey}
                            className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4"
                          >
                            <div
                              role="button"
                              tabIndex={0}
                              className="w-full text-left"
                              onClick={() =>
                                togglePropertyExpanded(propertyKey)
                              }
                              onKeyDown={(event) => {
                                if (
                                  event.key === 'Enter' ||
                                  event.key === ' '
                                ) {
                                  event.preventDefault()
                                  togglePropertyExpanded(propertyKey)
                                }
                              }}
                              aria-expanded={expanded}
                            >
                              <div className="grid gap-3 md:grid-cols-[1.3fr_0.8fr_1.2fr_auto] md:items-start">
                                <div>
                                  <p className="text-sm font-semibold text-text">
                                    {row.label.trim() ||
                                      `Property ${index + 1}`}
                                  </p>
                                  <p className="mt-1 text-xs text-text-muted">
                                    {row.propertyAddress.trim() ||
                                      'Address not set'}
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    <Badge
                                      variant={stale ? 'warning' : 'success'}
                                    >
                                      {stale ? 'Stale / manual' : 'Fresh'}
                                    </Badge>
                                    {!row.id ? (
                                      <Badge variant="outline">Unsaved</Badge>
                                    ) : null}
                                    <Badge variant="outline">
                                      {valuationSourceLabel(
                                        row.valuationSource,
                                      )}
                                    </Badge>
                                  </div>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                                    Value
                                  </p>
                                  <p className="mt-1 text-2xl font-semibold text-text">
                                    {value == null
                                      ? '—'
                                      : formatCurrencyWhole(value)}
                                  </p>
                                  <p className="mt-1 text-xs text-text-muted">
                                    As of {formatShortDate(row.valueAsOf)}
                                  </p>
                                </div>
                                <div>
                                  {trendPoints.length >= 2 ? (
                                    <NetWorthTrendLine
                                      points={trendPoints}
                                      loading={
                                        propertyValuationsQuery.isLoading
                                      }
                                      ariaLabel={`${row.label || 'Property'} value trend`}
                                      tooltipTestId="property-value-trend-tooltip"
                                    />
                                  ) : (
                                    <div className="rounded-xl border border-border/30 bg-surface/50 px-3 py-2 text-xs text-text-muted">
                                      Trendline starts after two saved
                                      valuations.
                                    </div>
                                  )}
                                </div>
                                <div className="flex items-center justify-end gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    disabled={
                                      !(
                                        row.propertyAddress || row.label
                                      ).trim() ||
                                      refreshPropertyValuation.isPending ||
                                      updatePlanning.isPending
                                    }
                                    onClick={(event) => {
                                      event.stopPropagation()
                                      void refreshPropertyValue(row)
                                    }}
                                  >
                                    {row.id ? 'Refresh' : 'Save & refresh'}
                                  </Button>
                                  <span className="text-xs text-text-muted">
                                    {expanded ? 'Hide details' : 'Details'}
                                  </span>
                                </div>
                              </div>
                            </div>
                            {expanded ? (
                              <div className="mt-4 border-t border-border/30 pt-4">
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
                                  <label className="text-xs text-text-muted md:col-span-2">
                                    Address
                                    <Input
                                      className="mt-1"
                                      placeholder="3636 Avocado Road, Largo, FL 33770"
                                      value={row.propertyAddress}
                                      onChange={(event) =>
                                        updateRealEstateDraft(
                                          index,
                                          'propertyAddress',
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
                                </div>
                                <div className="mt-3 grid gap-3 md:grid-cols-4">
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
                                  <label className="text-xs text-text-muted">
                                    Valuation source
                                    <Input
                                      className="mt-1"
                                      disabled
                                      value={valuationSourceLabel(
                                        row.valuationSource,
                                      )}
                                    />
                                  </label>
                                  <label className="text-xs text-text-muted">
                                    Range
                                    <Input
                                      className="mt-1"
                                      disabled
                                      value={
                                        row.valuationRangeLow &&
                                        row.valuationRangeHigh
                                          ? `${formatCurrencyWhole(
                                              Number(row.valuationRangeLow),
                                            )}–${formatCurrencyWhole(
                                              Number(row.valuationRangeHigh),
                                            )}`
                                          : '—'
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
                                        <SelectItem value="track_only">
                                          Track only
                                        </SelectItem>
                                        <SelectItem value="income">
                                          Income stream
                                        </SelectItem>
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
                                      disabled={
                                        row.retirementTreatment !== 'income'
                                      }
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
                                      disabled={
                                        row.retirementTreatment !==
                                        'planned_sale'
                                      }
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
                                      disabled={
                                        row.retirementTreatment !==
                                        'planned_sale'
                                      }
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
                                <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
                                  <Input
                                    aria-label={`Real estate notes for ${row.label}`}
                                    placeholder="ownership, inheritance, sibling split, valuation source"
                                    value={row.notes}
                                    onChange={(event) =>
                                      updateRealEstateDraft(
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
                                    onClick={() => removeRealEstateAsset(index)}
                                  >
                                    Remove
                                  </Button>
                                </div>
                                {history?.latest?.methodology ? (
                                  <p className="mt-3 text-xs text-text-muted">
                                    {history.latest.methodology}
                                  </p>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </SectionCard>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="allocation"
              className="rounded-2xl border border-border/40 bg-surface-muted/10 px-0"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <PlannerAccordionHeader
                  title="Allocation sandbox"
                  detail="Compare current holdings, asset-class sliders, or ticker baskets without changing real accounts."
                  meta={
                    <Badge variant="outline">
                      {modeledExpectedReturn == null
                        ? 'Return pending'
                        : formatPercent(modeledExpectedReturn * 100, {
                            decimals: 1,
                          })}
                    </Badge>
                  }
                />
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-5">
                <SectionCard variant="ghost" padding="none">
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
                        variant={
                          allocationMode === mode ? 'default' : 'outline'
                        }
                        onClick={() =>
                          setAllocationMode(mode as AllocationMode)
                        }
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
                          : formatPercent(modeledIncomeYield * 100, {
                              decimals: 1,
                            })}
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
                      <div className="mt-2">
                        <InfoBadge
                          label="No double count"
                          detail="Income yield and tax drag are shown separately. Success odds use total return, so dividends and interest are not added twice."
                        />
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                        Taxable income
                      </p>
                      <p className="mt-2 font-mono text-2xl text-text">
                        {modeledTaxableIncome == null
                          ? '—'
                          : formatCurrency(modeledTaxableIncome, {
                              decimals: 0,
                            })}
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
                        {formatPercent(modeledCashYield * 100, { decimals: 2 })}
                        .
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
                                : formatPercent(row.value * 100, {
                                    decimals: 0,
                                  })}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3">
                        <InfoBadge
                          label="Ticker mapping"
                          detail="VTI, VOO, SPY, SCHD, VYM, DGRO, JEPI and common stocks map to US stocks; SPAXX/FDRXX/VMFXX/SWVXX map to cash."
                        />
                      </div>
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
                            Percentages are normalized automatically when you
                            run the preview.
                          </p>
                        </div>
                      ) : allocationMode === 'tickers' ? (
                        <div className="space-y-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                            Ticker weights
                          </p>
                          <Textarea
                            value={tickerMix}
                            onChange={(event) =>
                              setTickerMix(event.target.value)
                            }
                            rows={6}
                            placeholder={
                              'VTI 70\nSCHD 10 3.6\nBND 10 4.0\nSPAXX 10'
                            }
                          />
                          <p className="text-xs text-text-muted">
                            Enter symbol, weight, and optional income yield %
                            per line. Unknown tickers fall back to US stocks.
                          </p>
                        </div>
                      ) : (
                        <div className="rounded-xl border border-dashed border-border/40 p-4 text-sm text-text-muted">
                          Current portfolio mode uses live holdings. Switch
                          modes, then Run preview, to compare a what-if
                          allocation.
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
                    <div className="mt-1">
                      <InfoBadge
                        label="Scenario lab"
                        detail="Save ticker mixes as named scenarios, then compare them side-by-side against your real account allocation. Each scenario keeps its own bridge style."
                      />
                    </div>
                    <div className="mt-3 flex flex-wrap items-end gap-2">
                      <label className="text-xs text-text-muted">
                        Scenario name
                        <Input
                          className="mt-1 w-56"
                          aria-label="Scenario name"
                          value={scenarioName}
                          onChange={(event) =>
                            setScenarioName(event.target.value)
                          }
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
                        No saved scenarios yet. Enter a ticker mix above and
                        save it here to start comparing.
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
                              <span className="font-medium">
                                {scenario.name}
                              </span>
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
                          Same seed and knob set per run — only the allocation
                          and bridge style differ.
                        </p>
                      </div>
                    ) : null}
                  </div>
                </SectionCard>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : null}
      </SectionCard>

      <RetirementResults
        preview={preview}
        previewError={previewQuery.error}
        onRetry={() => void previewQuery.refetch()}
        isFetching={previewQuery.isFetching}
        hasPendingChanges={hasPendingChanges}
        projectionData={projectionData}
        fullRetirementAge={fullRetirementAge}
        drawdownBasis={drawdownBasis}
        setDrawdownBasis={setDrawdownBasis}
      />
    </div>
  )
}
