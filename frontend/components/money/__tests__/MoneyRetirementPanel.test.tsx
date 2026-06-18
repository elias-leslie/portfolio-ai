'use client'

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  HouseholdFinanceDashboard,
  RetirementIncomeActuals,
  RetirementPreview,
  RetirementSpendingActuals,
} from '@/lib/api/household'
import {
  useRetirementIncomeActuals,
  useRetirementPreview,
  useRetirementSpendingActuals,
  useUpdateHouseholdPlanning,
  useUpdateHouseholdProfile,
  useUpdateRetirementIncomeStreamOverride,
} from '@/lib/hooks/useHousehold'
import { MoneyRetirementPanel } from '../MoneyRetirementPanel'

vi.mock('@/lib/hooks/useHousehold', () => ({
  useRetirementPreview: vi.fn(),
  useRetirementIncomeActuals: vi.fn(),
  useRetirementSpendingActuals: vi.fn(),
  useUpdateHouseholdPlanning: vi.fn(),
  useUpdateHouseholdProfile: vi.fn(),
  useUpdateRetirementIncomeStreamOverride: vi.fn(),
  useHouseholdAccountHoldings: vi.fn(() => ({
    data: undefined,
    isLoading: false,
  })),
  useReplaceHouseholdAccountHoldings: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useAllocationScenarios: vi.fn(() => ({
    data: [
      {
        id: 'scenario-1',
        name: 'Equity bridge',
        holdings: [{ symbol: 'VTI', weight: 100 }],
        bridgeGrowth: 'portfolio',
        bridgeRealReturn: null,
        notes: null,
        createdAt: '2026-06-11T00:00:00Z',
        updatedAt: '2026-06-11T00:00:00Z',
      },
    ],
    isLoading: false,
  })),
  useReplaceAllocationScenarios: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useHouseholdPropertyValuations: vi.fn(() => ({
    data: { items: [] },
    isLoading: false,
  })),
  useRefreshHouseholdPropertyValuation: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
}))

vi.mock('@/lib/api/household', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/household')>()),
  fetchRetirementPreview: vi.fn(),
}))

vi.mock('recharts', () => {
  const MockChart = ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  )
  const MockPart = () => null

  return {
    ResponsiveContainer: MockChart,
    AreaChart: MockChart,
    Area: MockPart,
    BarChart: MockChart,
    Bar: MockPart,
    Cell: MockPart,
    CartesianGrid: MockPart,
    ComposedChart: MockChart,
    Legend: MockPart,
    LineChart: MockChart,
    Line: MockPart,
    PieChart: MockChart,
    Pie: MockChart,
    Tooltip: MockPart,
    XAxis: MockPart,
    YAxis: MockPart,
  }
})

const dashboard = {
  generatedAt: '2026-05-25T00:00:00Z',
  overview: {
    investedAssets: 900000,
    retirementAssets: 600000,
    taxableAssets: 250000,
    cashReserve: 50000,
    totalTrackedAssets: 900000,
    liabilitiesTotal: 0,
    netWorth: 900000,
    netWorthStatus: 'current',
    netWorthDetail: 'Current.',
    assetAllocation: [],
    trackedAccountCount: 4,
    needsRefreshCount: 0,
    candidateAccountCount: 0,
    gapCount: 0,
    inboxCount: 0,
    coverageMonths: 6,
    lastTransactionDate: '2026-05-25',
    visibilityScore: 90,
    visibilityLabel: 'Strong',
    monthlySpendStatus: 'current',
    monthlySpendDetail: 'Current.',
    nextBestAction: 'Run retirement preview.',
  },
  accountControl: {
    status: 'clear',
    summary: 'Account source controls are clear.',
    issueCount: 0,
    blockingIssueCount: 0,
    checkedAt: '2026-05-25T00:00:00Z',
    issues: [],
  },
  profile: {
    id: 'hh-test',
    householdName: 'Household',
    monthlyNetIncomeTarget: 10000,
    monthlyEssentialTarget: 5000,
    monthlyDiscretionaryTarget: 2000,
    monthlySavingsTarget: 1500,
    targetRetirementAge: 65,
    targetRetirementSpend: 6000,
    notes: null,
    createdAt: '2026-05-25T00:00:00Z',
    updatedAt: '2026-05-25T00:00:00Z',
  },
  resolvedValues: [],
  budgetReadiness: {
    status: 'ready_for_budgeting',
    summary: 'Ready',
    priorities: [],
    missingInputs: [],
    starterLanes: [],
  },
  budgetSnapshot: {
    status: 'on_track',
    summary: 'On track',
    monthlyIncomeTarget: 10000,
    monthlyPlanTotal: 8500,
    monthlyPlanSource: 'household_profile_targets',
    monthlyPlanSourceLabel: 'Household profile targets',
    essentialTarget: 5000,
    discretionaryTarget: 2000,
    savingsTarget: 1500,
    actualMonthlySpend: 7000,
    actualEssentialMonthlySpend: 5000,
    actualDiscretionaryMonthlySpend: 2000,
    monthToDateSpend: 3000,
    monthToDatePlan: 3200,
    paceStatus: 'on_track',
    paceDetail: 'On track.',
    planIsPartial: false,
    missingPlanComponents: [],
    remainingCashAfterPlan: 1500,
    discretionaryHeadroom: 0,
    safeToSpend: null,
    safeToSpendConstraint: null,
    dueSoonBillsTotal: null,
    operatingCushion: 0,
  },
  retirementPreparedness: {
    status: 'scenario_ready',
    summary: 'Retirement planning is ready.',
    retirementAccountShare: 66,
    strengths: [],
    blockers: [],
    nextSteps: [],
  },
  jennyNeeds: [],
  reports: {
    executive: {
      headline: 'Ready',
      summary: 'Summary',
      averageMonthlySpend: 7000,
      averageMonthlyEssentials: 5000,
      averageMonthlyDiscretionary: 2000,
      recent30DaySpend: 6900,
      recurringMerchantCount: 3,
      trackedExpenseCount: 20,
      coverageMonths: 6,
    },
    categoryBreakdown: [],
    merchantHighlights: [],
    priceInsights: [],
    monthlySpendTrend: [],
    monthComparison: null,
    recentTransactions: [],
  },
  categorizationQueue: [],
  recurringCommitments: [],
  transactionDateIssues: [],
  sinkingFunds: [],
  retirementContributionTracker: {
    status: 'on_track',
    monthlyTarget: 1500,
    estimatedMonthlyContributions: 1500,
    monthlyGap: 0,
    detail: 'On track.',
  },
  retirementScenarios: [],
  planning: {
    summary: {
      completionScore: 100,
      readySections: 1,
      totalSections: 1,
      missingDocumentCount: 0,
      highPriorityDocumentCount: 0,
      sections: [],
    },
    members: [
      {
        id: 'member-primary',
        displayName: 'Alex Demo',
        role: 'adult',
        relationship: 'father',
        birthYear: 1977,
        isDependent: false,
        livesInHousehold: true,
        notes: 'DOB: 1977-01-11',
        createdAt: '2026-05-25T00:00:00Z',
        updatedAt: '2026-05-25T00:00:00Z',
      },
      {
        id: 'member-spouse',
        displayName: 'Jordan Demo',
        role: 'adult',
        relationship: 'mother',
        birthYear: 1982,
        isDependent: false,
        livesInHousehold: true,
        notes: 'DOB: 1982-06-05',
        createdAt: '2026-05-25T00:00:00Z',
        updatedAt: '2026-05-25T00:00:00Z',
      },
    ],
    incomeSources: [],
    debtObligations: [],
    housingCosts: [],
    insurancePolicies: [],
    retirementIncomeSources: [],
    retirementHealthcareSchedule: [],
    retirementCollegeSchedule: [],
    plannedExpenses: [],
    documentRequirements: [],
  },
  importCenter: {
    headline: 'Import',
    trackedDocuments: 0,
    parsedDocuments: 0,
    suggestedFirstUploads: [],
    automations: [],
    supportedDocuments: [],
  },
  evidenceAccounts: [],
  accounts: [],
  discoveredAccounts: [],
  inbox: [],
  questions: [],
  jennyBrief: { headline: 'Jenny', body: 'Body', prompts: [] },
} as HouseholdFinanceDashboard

const preview: RetirementPreview = {
  schemaVersion: 1,
  trustedTotals: true,
  accountControlStatus: 'clear',
  accountControlSummary: 'Account source controls are clear.',
  inputs: {
    schemaVersion: 1,
    householdId: 'hh-test',
    primaryAge: 50,
    spouseAge: null,
    retirementAge: 65,
    horizonYears: 35,
    annualExpenses: 72000,
    annualContribution: 18000,
    portfolioValue: 900000,
    assetAllocation: { usEquity: 0.6, bonds: 0.4 },
    cashYield: 0.0328,
    incomeSources: [],
    inflationRate: 0.025,
    socialSecurityPayableRatio: 0.77,
    socialSecurityDepletionYear: 2033,
    asOfDate: '2026-05-25',
  },
  successProbability: 0.82,
  medianEndingBalance: 1250000,
  sequenceOfReturnsRisk: 0.04,
  percentiles: { p10: 100000, p50: 1250000, p90: 3000000 },
  endingBalancePaths: {
    p10: [900000, 850000],
    p50: [900000, 950000],
    p90: [900000, 1100000],
  },
  accountBuckets: [
    {
      bucketType: 'taxable',
      label: 'Brokerage',
      accountType: 'brokerage',
      taxTreatment: 'taxable_capital_gains_estimate',
      currentValue: 250000,
      withdrawalPriority: 2,
    },
    {
      bucketType: 'governmental_457b',
      label: 'PCSB 457(b)',
      accountType: 'governmental_457b',
      taxTreatment: 'ordinary_income_no_10pct_early_penalty',
      currentValue: 95000,
      withdrawalPriority: 3,
    },
    {
      bucketType: 'pre_tax',
      label: 'IRA',
      accountType: 'ira',
      taxTreatment: 'ordinary_income',
      currentValue: 400000,
      withdrawalPriority: 3,
    },
    {
      bucketType: 'roth',
      label: 'Roth IRA',
      accountType: 'roth_ira',
      taxTreatment: 'tax_free_if_qualified',
      currentValue: 200000,
      withdrawalPriority: 5,
    },
  ],
  holdingsCoverage: {
    status: 'partial',
    label: 'Partial holdings',
    detail:
      'Some account value has exact holdings or cash; the rest uses account-level assumptions.',
    totalValue: 650000,
    exactValue: 250000,
    inferredValue: 400000,
    cashValue: 0,
    exactShare: 0.384615,
    accounts: [
      {
        label: 'Brokerage',
        bucketType: 'taxable',
        accountType: 'brokerage',
        householdAccountId: 'hh-brokerage',
        manualHoldingsEditable: false,
        currentValue: 250000,
        exactValue: 250000,
        inferredValue: 0,
        cashValue: 0,
        pricedPositionCount: 1,
        coverageStatus: 'exact_holdings',
        coverageLabel: 'Exact holdings',
        detail: '1 priced position linked to this account.',
      },
      {
        label: 'IRA',
        bucketType: 'pre_tax',
        accountType: 'ira',
        householdAccountId: 'hh-ira',
        manualHoldingsEditable: true,
        currentValue: 400000,
        exactValue: 0,
        inferredValue: 400000,
        cashValue: 0,
        pricedPositionCount: 0,
        coverageStatus: 'account_value_only',
        coverageLabel: 'Account value only',
        detail:
          'No exact holdings are linked; allocation uses portfolio-level assumptions.',
      },
    ],
  },
  accountAllocationCoverage: {
    status: 'partial',
    label: 'Partial account allocation',
    detail:
      'Exact holdings and cash are used first; account-value-only balances use fallback assumptions.',
    totalValue: 650000,
    exactValue: 250000,
    inferredValue: 400000,
    cashValue: 0,
    exactShare: 0.384615,
    assetAllocation: {
      usEquity: 0.753846,
      bonds: 0.246154,
    },
    accounts: [
      {
        label: 'Brokerage',
        bucketType: 'taxable',
        accountType: 'brokerage',
        currentValue: 250000,
        exactValue: 250000,
        inferredValue: 0,
        cashValue: 0,
        pricedPositionCount: 1,
        allocationStatus: 'exact_allocation',
        allocationLabel: 'Exact allocation',
        allocation: { usEquity: 1 },
        detail: '1 priced position drives this account allocation.',
      },
      {
        label: 'IRA',
        bucketType: 'pre_tax',
        accountType: 'ira',
        currentValue: 400000,
        exactValue: 0,
        inferredValue: 400000,
        cashValue: 0,
        pricedPositionCount: 0,
        allocationStatus: 'account_value_only',
        allocationLabel: 'Account value only',
        allocation: { usEquity: 0.6, bonds: 0.4 },
        detail:
          'No exact holdings are linked; allocation uses account-level fallback assumptions.',
      },
    ],
  },
  bucketStrategy: {
    strategyType: 'dynamic_three_bucket',
    label: 'Dynamic 3-bucket strategy',
    status: 'underfilled',
    statusLabel: 'Needs bucket funding',
    detail:
      'Targets are based on 15 years from full household retirement and modeled portfolio withdrawals.',
    yearsToRetirement: 15,
    retirementAge: 65,
    annualPortfolioNeed: 72000,
    targetTotal: 650000,
    currentTotal: 650000,
    alignmentScore: 0.72,
    buckets: [
      {
        bucketId: 'now',
        label: 'Now / liquidity',
        timeHorizon: 'Retirement year 1',
        purpose: 'Cash and cash equivalents.',
        currentValue: 0,
        targetValue: 0,
        targetYears: 0,
        currentShare: 0,
        targetShare: 0,
        fillRatio: 0,
        gapValue: 0,
        status: 'aligned',
        statusLabel: 'Not needed yet',
        action: 'No current target under this retirement timeline.',
        assetAllocation: {},
        holdings: [],
      },
      {
        bucketId: 'soon',
        label: 'Soon / stability',
        timeHorizon: 'Retirement years 2-6',
        purpose: 'High-quality bond exposure.',
        currentValue: 160000,
        targetValue: 240000,
        targetYears: 1,
        currentShare: 0.246154,
        targetShare: 0.369231,
        fillRatio: 0.666667,
        gapValue: -80000,
        status: 'underfilled',
        statusLabel: 'Needs funding',
        action: 'Increase by about $80,000.',
        assetAllocation: { bonds: 1 },
        holdings: [
          {
            symbol: 'INFERRED_BONDS',
            label: 'Inferred bonds',
            assetClass: 'bonds',
            currentValue: 160000,
            shareOfBucket: 1,
            source: 'inferred',
            accountLabel: 'IRA',
          },
        ],
      },
      {
        bucketId: 'later',
        label: 'Later / growth',
        timeHorizon: 'Years 7+',
        purpose: 'Growth exposure.',
        currentValue: 490000,
        targetValue: 410000,
        targetYears: 0,
        currentShare: 0.753846,
        targetShare: 0.630769,
        fillRatio: 1.195122,
        gapValue: 80000,
        status: 'overfilled',
        statusLabel: 'Above target',
        action: 'Decrease by about $80,000.',
        assetAllocation: { usEquity: 1 },
        holdings: [
          {
            symbol: 'VTI',
            label: 'VTI',
            assetClass: 'us_equity',
            currentValue: 250000,
            shareOfBucket: 0.510204,
            source: 'exact',
            accountLabel: 'Brokerage',
          },
        ],
      },
    ],
    rebalanceActions: ['Soon / stability: Increase by about $80,000.'],
    methodology: ['Three dynamic buckets.'],
    monteCarloDetail:
      'Success odds use the same current account buckets and allocation mix.',
  },
  returnAssumptions: {
    expectedReturn: 0.052,
    incomeYield: 0.024,
    incomeYieldFreshnessStatus: 'fresh',
    incomeYieldFreshnessLabel: 'Yields are current',
    cashYield: 0.0328,
    cashYieldSource: 'Fidelity SPAXX 7-day yield',
    cashYieldAsOf: '2026-05-07',
    cashYieldFreshnessStatus: 'aging',
    cashYieldFreshnessLabel: '19 days old (as of May 7, 2026)',
    dividendTaxCharacter: {
      basis: 'assumption',
      detail:
        'Qualified vs. ordinary dividend treatment is assumed from fund type; no per-fund tax-character source is available.',
    },
  },
  taxAssumptions: {
    filingStatusLabel: 'Married filing jointly',
    standardDeduction: 32200,
    capitalGainsZeroRateLimit: 98900,
    taxableWithdrawalGainRatio: 0.42,
    taxableWithdrawalGainRatioSource: 'tax_lots',
    taxableWithdrawalGainRatioDetail:
      'Embedded gain estimated from your taxable cost basis (42% of taxable withdrawals taxed as long-term gains).',
    warnings: [],
  },
  drawdownSchedule: [
    {
      yearIndex: 15,
      calendarYear: 2041,
      primaryAge: 65,
      spendingNeed: 72000,
      income: 0,
      grossWithdrawal: 74000,
      taxEstimate: 2000,
      penaltyEstimate: 0,
      netWithdrawal: 72000,
      endingBalance: 950000,
      rmdAmount: 0,
      rmdApplied: false,
      spendingTarget: 72000,
      floorAmount: 45000,
      discretionaryTarget: 27000,
      spendingReduction: 0,
      guaranteedIncome: 0,
      bridgeDraw: 0,
      portfolioDraw: 72000,
      bridgeBalance: 0,
      withdrawalRate: 0.045,
      collegeCost: 0,
      college529Draw: 0,
      college529Balance: 0,
      acaPremiumGross: 0,
      acaSubsidy: 0,
      acaOop: 0,
      acaNet: 0,
      acaPlanningNet: 0,
      magi: 0,
      medicarePremium: 0,
      partialRetirementYear: false,
      spouseNetIncome: 0,
      withdrawalsByBucket: {
        taxable: 50000,
        // es-toolkit camelizes governmental_457b with a capital B.
        governmental457B: 24000,
        preTax: 0,
        roth: 0,
      },
      balancesByBucket: {
        taxable: 200000,
        governmental457B: 95000,
        preTax: 500000,
        roth: 250000,
      },
    },
    {
      yearIndex: 23,
      calendarYear: 2049,
      primaryAge: 73,
      spendingNeed: 88000,
      income: 30000,
      grossWithdrawal: 65000,
      taxEstimate: 7000,
      penaltyEstimate: 0,
      netWithdrawal: 58000,
      endingBalance: 800000,
      rmdAmount: 18000,
      rmdApplied: true,
      spendingTarget: 72000,
      floorAmount: 45000,
      discretionaryTarget: 27000,
      spendingReduction: 0,
      guaranteedIncome: 0,
      bridgeDraw: 0,
      portfolioDraw: 72000,
      bridgeBalance: 0,
      withdrawalRate: 0.045,
      collegeCost: 0,
      college529Draw: 0,
      college529Balance: 0,
      acaPremiumGross: 0,
      acaSubsidy: 0,
      acaOop: 0,
      acaNet: 0,
      acaPlanningNet: 0,
      magi: 0,
      medicarePremium: 0,
      partialRetirementYear: false,
      spouseNetIncome: 0,
      withdrawalsByBucket: {
        taxable: 20000,
        governmental457B: 0,
        preTax: 45000,
        roth: 0,
      },
      balancesByBucket: {
        taxable: 0,
        governmental457B: 90000,
        preTax: 560000,
        roth: 240000,
      },
    },
  ],
  leverImpacts: [
    {
      id: 'retire_later',
      label: 'Retire 2 years later',
      value: 'Age 67',
      successProbability: 0.9,
      deltaSuccessProbability: 0.08,
      detail: '+8.0 percentage points versus the current preview.',
    },
  ],
  accountRules: [
    {
      bucketType: 'governmental_457b',
      label: 'Governmental 457(b)',
      taxTreatment: 'Ordinary income, no early-withdrawal penalty',
      earlyAccess:
        'Penalty-free at any age after you separate from service; taxed as ordinary income.',
      rmd: 'Required minimum distributions begin at 73.',
    },
    {
      bucketType: 'roth',
      label: 'Roth',
      taxTreatment: 'Tax-free if qualified',
      earlyAccess:
        'Contributions withdrawable anytime; earnings tax-free after 59½ and the 5-year rule.',
      rmd: 'Roth IRAs have no lifetime RMDs for the original owner.',
    },
  ],
  firstDepletionAge: null,
  medianDiscretionaryPath: [],
  failureAgeDistribution: {},
  outcomeFraming: {
    medianYearsShort: 3,
    medianFloorGapReal: 41250,
    tailFloorGapReal: 180400,
    medianWarningYears: 4,
    penaltyTrialsShare: 0.12,
    medianPenaltyPaidReal: 8150,
    endAboveStartShare: 0.41,
    startBalanceReal: 900000,
  },
}

const incomeActuals: RetirementIncomeActuals = {
  generatedAt: '2026-06-12T00:00:00Z',
  firstMonth: '2026-01',
  lastMonth: '2026-05',
  coverageMonths: 5,
  totalMonthlyIncome: 5509.23,
  activeMonthlyIncome: 0,
  sourceLabel:
    'Detected from Money income transactions, 2026-01 to 2026-05 (5 complete months). Amounts are take-home deposits.',
  aliasRowsCollapsed: 9,
  streams: [
    {
      streamKey: 'payroll-stream',
      label: 'PINELLAS COUNTY PAYROLL LESLIE MARIANA',
      owner: 'Mariana',
      ownerOverride: false,
      cadence: 'biweekly',
      monthlyAverage: 5999.94,
      runRateMonthly: 6499.93,
      total: 23999.75,
      transactionCount: 8,
      firstDate: '2026-01-09',
      lastDate: '2026-04-17',
      monthsSeen: 4,
      monthsSpanned: 4,
      active: false,
      portfolioYield: false,
      status: 'stopped',
      statusOverride: null,
      mergedIntoStreamKey: null,
    },
    {
      streamKey: 'dividend-stream',
      label: 'DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX)',
      owner: null,
      ownerOverride: false,
      cadence: 'monthly',
      monthlyAverage: 84.02,
      runRateMonthly: 84.02,
      total: 252.05,
      transactionCount: 3,
      firstDate: '2026-02-27',
      lastDate: '2026-04-30',
      monthsSeen: 3,
      monthsSpanned: 3,
      active: true,
      portfolioYield: true,
      status: 'portfolio_yield',
      statusOverride: null,
      mergedIntoStreamKey: null,
    },
    {
      streamKey: 'prog-stream',
      label: 'PROG SELECT INS INS PREM Elias Leslie',
      owner: 'Elias',
      ownerOverride: false,
      cadence: 'one-off',
      monthlyAverage: 276.99,
      runRateMonthly: 276.99,
      total: 276.99,
      transactionCount: 1,
      firstDate: '2026-02-17',
      lastDate: '2026-02-17',
      monthsSeen: 1,
      monthsSpanned: 1,
      active: false,
      portfolioYield: false,
      status: 'one_off',
      statusOverride: null,
      mergedIntoStreamKey: null,
    },
  ],
}

const spendingActuals: RetirementSpendingActuals = {
  generatedAt: '2026-06-12T00:00:00Z',
  firstMonth: '2026-01',
  lastMonth: '2026-05',
  coverageMonths: 5,
  totalMonthlySpend: 7484.06,
  healthcareMonthly: 363.74,
  sourceLabel:
    'Derived from deduped Money transactions, 2026-01 to 2026-05 (5 complete months).',
}

const usePreviewMock = vi.mocked(useRetirementPreview)
const useIncomeActualsMock = vi.mocked(useRetirementIncomeActuals)
const useSpendingActualsMock = vi.mocked(useRetirementSpendingActuals)
const useUpdateProfileMock = vi.mocked(useUpdateHouseholdProfile)
const useUpdatePlanningMock = vi.mocked(useUpdateHouseholdPlanning)
const useUpdateIncomeStreamMock = vi.mocked(
  useUpdateRetirementIncomeStreamOverride,
)
const updateProfileMutateAsync = vi.fn()
const updatePlanningMutateAsync = vi.fn()
const updateIncomeStreamMutateAsync = vi.fn()

function getRunPreviewButton() {
  return screen.getAllByRole('button', {
    name: /run preview/i,
  })[0] as HTMLElement
}

async function openPlannerSection(
  user: ReturnType<typeof userEvent.setup>,
  name: RegExp,
) {
  await user.click(screen.getByRole('button', { name }))
}

describe('MoneyRetirementPanel', () => {
  beforeEach(() => {
    usePreviewMock.mockReset()
    useIncomeActualsMock.mockReset()
    useIncomeActualsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementIncomeActuals>)
    useSpendingActualsMock.mockReset()
    useSpendingActualsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementSpendingActuals>)
    updateProfileMutateAsync.mockReset()
    updateProfileMutateAsync.mockResolvedValue({})
    useUpdateProfileMock.mockReturnValue({
      mutateAsync: updateProfileMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateHouseholdProfile>)
    updatePlanningMutateAsync.mockReset()
    updatePlanningMutateAsync.mockResolvedValue({})
    useUpdatePlanningMock.mockReturnValue({
      mutateAsync: updatePlanningMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateHouseholdPlanning>)
    useUpdateIncomeStreamMock.mockReset()
    updateIncomeStreamMutateAsync.mockReset()
    updateIncomeStreamMutateAsync.mockResolvedValue(incomeActuals)
    useUpdateIncomeStreamMock.mockReturnValue({
      mutateAsync: updateIncomeStreamMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateRetirementIncomeStreamOverride>)
  })

  it('renders visual retirement readiness, buckets, levers, and collapsed account details', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
      dataUpdatedAt: new Date('2026-05-25T10:30:00').getTime(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Planning & assumptions')).toBeInTheDocument()
    expect(screen.getByText('Success rates')).toBeInTheDocument()
    expect(screen.getByText(/Last run/)).toBeInTheDocument()
    expect(screen.getByText('Invested assets')).toBeInTheDocument()
    expect(screen.getByText('Same source as Today.')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /expand planner/i }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Your retire age')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Spending used in the plan'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Allocation sandbox')).not.toBeInTheDocument()
    expect(screen.getAllByText('82%').length).toBeGreaterThan(0)
    expect(screen.getByText('$1,250,000')).toBeInTheDocument()
    expect(screen.getAllByText('Taxable').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Gov 457(b)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pre-tax').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Roth').length).toBeGreaterThan(0)
    expect(screen.getByText('Sensitivity checks')).toBeInTheDocument()
    expect(screen.queryByText('25x checkpoint')).not.toBeInTheDocument()
    expect(screen.queryByText(/save gap \/ month/i)).not.toBeInTheDocument()
    expect(screen.queryByText('Account buckets')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/current planner buckets/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Data confidence')).not.toBeInTheDocument()
    expect(screen.queryByText('Tax assumptions')).not.toBeInTheDocument()
    expect(screen.queryByText('Tax model')).not.toBeInTheDocument()
    expect(screen.queryByText('Married filing jointly')).not.toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: /tax est/i }),
    ).toHaveAttribute(
      'title',
      expect.stringContaining('Married filing jointly'),
    )
    expect(screen.getByText('Holdings coverage')).toBeInTheDocument()
    expect(screen.getByText('Partial holdings')).toBeInTheDocument()
    expect(screen.getByText('Exact holdings/cash')).toBeInTheDocument()
    expect(screen.getByText('Account-value-only')).toBeInTheDocument()
    expect(screen.getByText('Account allocation')).toBeInTheDocument()
    expect(
      screen.getAllByText(/Partial account allocation/).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getByRole('button', { name: /show 2 account details/i }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('1 priced position linked to this account.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Retire 2 years later')).toBeInTheDocument()
    expect(screen.getByText('Drawdown schedule')).toBeInTheDocument()
    // Default basis is today's dollars: nominal fixture values deflated by
    // (1 + 0.025) ** yearIndex (yearIndex 23 → factor ≈ 1.7646).
    expect(screen.getByText('$10,201')).toBeInTheDocument()
    expect(screen.getByText('$25,501')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Future dollars' }))
    expect(screen.getByText('$18,000')).toBeInTheDocument()
    expect(screen.getByText('$45,000')).toBeInTheDocument()
    // Gov 457(b) draw renders despite the governmental457B wire-key casing.
    expect(screen.getByText('$24,000')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: "Today's dollars" }))

    await user.click(
      screen.getByRole('button', { name: /show 2 account details/i }),
    )

    expect(
      screen.getByText('1 priced position linked to this account.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /hide account details/i }),
    ).toBeInTheDocument()
  })

  it('surfaces account rules, lots-derived gain ratio, and yield freshness', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    // Account-rule cards render without expanding any section.
    expect(screen.getByText('How each account is treated')).toBeInTheDocument()
    expect(
      screen.getByText(/Penalty-free at any age after you separate/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Roth IRAs have no lifetime RMDs/),
    ).toBeInTheDocument()

    // Lots-derived gain ratio is labeled as sourced from cost basis.
    expect(screen.getByText('From your cost basis')).toBeInTheDocument()
    expect(
      screen.getByText(/Embedded gain estimated from your taxable cost basis/),
    ).toBeInTheDocument()

    // Yield freshness badges live inside the allocation sandbox.
    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /allocation sandbox/i)
    expect(screen.getByText('Yields are current')).toBeInTheDocument()
    expect(
      screen.getByText('19 days old (as of May 7, 2026)'),
    ).toBeInTheDocument()
  })

  it('renders transformed current allocation keys instead of zeroing them out', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /allocation sandbox/i)

    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
    expect(screen.getByDisplayValue('3.28')).toBeInTheDocument()
    expect(screen.getByText('No double count')).toBeInTheDocument()
    expect(screen.getByText(/Fidelity SPAXX 7-day yield/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/Partial account allocation/).length,
    ).toBeGreaterThan(0)
  })

  it('lets local knobs update the preview request', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    const retireAgeInput = screen.getByDisplayValue('65')
    await user.clear(retireAgeInput)
    await user.type(retireAgeInput, '66')
    await user.click(getRunPreviewButton())

    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        retirementAge: 66,
        primaryAge: 49,
        spouseAge: 43,
      }),
    )
  })

  it('updates the success-rate plan spend as the manual spend changes', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    const spendInput = screen.getByRole('textbox', {
      name: /monthly spend in retirement/i,
    })
    await user.clear(spendInput)
    await user.type(spendInput, '6500')

    expect(
      screen.getByText((_content, element) =>
        Boolean(
          element?.tagName === 'SPAN' &&
            element.textContent?.includes('Plan $6,500/mo'),
        ),
      ),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(usePreviewMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          monthlySpend: 6500,
          annualExpenses: 78_000,
        }),
      ),
    )
  })

  it('labels 529 assets as included college funding', () => {
    usePreviewMock.mockReturnValue({
      data: {
        ...preview,
        inputs: {
          ...preview.inputs,
          college529Value: 2126,
        },
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(
      screen.getByText(/Includes 529 college sleeve \$2,126/),
    ).toBeInTheDocument()
  })

  it('sends ticker allocation what-ifs to the preview request', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /allocation sandbox/i)
    await user.click(screen.getByRole('button', { name: /^ticker basket$/i }))
    const tickerInput = screen.getByDisplayValue(/SCHD 10/)
    await user.clear(tickerInput)
    await user.type(
      tickerInput,
      'VTI 70{enter}SCHD 10 3.6{enter}BND 10 4.0{enter}SPAXX 10',
    )
    await user.click(getRunPreviewButton())

    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        allocationHoldings: [
          { symbol: 'VTI', weight: 70 },
          { symbol: 'SCHD', weight: 10, dividendYield: 3.6 },
          { symbol: 'BND', weight: 10, dividendYield: 4.0 },
          { symbol: 'SPAXX', weight: 10 },
        ],
      }),
    )
  })

  it('loads saved Social Security assumptions and persists the current knob set', async () => {
    const user = userEvent.setup()
    const savedDashboard = {
      ...dashboard,
      profile: {
        ...dashboard.profile,
        targetRetirementAge: 50,
        targetRetirementSpend: 7500,
        monthlySavingsTarget: 0,
        retirementInflationRate: 0.03,
        retirementHorizonYears: 40,
        primarySocialSecurityAnnualEarnings: 120000,
        primarySocialSecurityStartAge: 70,
        spouseSocialSecurityAnnualEarnings: 85000,
        spouseSocialSecurityStartAge: 67,
      },
    } as HouseholdFinanceDashboard
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={savedDashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    expect(screen.getByText('SSA assumptions')).toBeInTheDocument()
    const salaryInput = screen.getByDisplayValue('120000')
    await user.clear(salaryInput)
    await user.type(salaryInput, '125000')
    await user.click(screen.getByRole('button', { name: /save assumptions/i }))

    expect(updateProfileMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        targetRetirementAge: 50,
        targetRetirementSpend: 7500,
        monthlySavingsTarget: 0,
        retirementInflationRate: 0.03,
        retirementHorizonYears: 40,
        primarySocialSecurityAnnualEarnings: 125000,
        primarySocialSecurityStartAge: 70,
        spouseSocialSecurityAnnualEarnings: 85000,
        spouseSocialSecurityStartAge: 67,
      }),
    )
  })

  it('labels planner inputs for screen readers', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))

    expect(
      screen.getByRole('textbox', { name: /your retirement age/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: /monthly spend in retirement/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('textbox', {
        name: /your monthly social security benefit/i,
      }),
    ).toBeInTheDocument()
  })

  it('flags stale results after an edit until the preview is re-run', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.queryByText(/Inputs changed since this plan ran/i)).toBeNull()

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    const retireAgeInput = screen.getByRole('textbox', {
      name: /your retirement age/i,
    })
    await user.clear(retireAgeInput)
    await user.type(retireAgeInput, '66')

    expect(
      screen.getByText(/Inputs changed since this plan ran/i),
    ).toBeInTheDocument()

    await user.click(getRunPreviewButton())

    expect(screen.queryByText(/Inputs changed since this plan ran/i)).toBeNull()
    // Not fetching in this mock, so the live-refetch banner stays hidden.
    expect(screen.queryByText('Updating projection…')).toBeNull()
  })

  it('shows an updating banner while a refetch is in flight over previous results', () => {
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: true,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.getByText('Updating projection…')).toBeInTheDocument()
  })

  it('clamps Social Security claim ages to the API 62..70 window', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    const primaryClaimInput = screen.getByRole('textbox', {
      name: /your social security claim age/i,
    })
    await user.clear(primaryClaimInput)
    await user.type(primaryClaimInput, '75')
    const spouseClaimInput = screen.getByRole('textbox', {
      name: /spouse social security claim age/i,
    })
    await user.clear(spouseClaimInput)
    await user.type(spouseClaimInput, '50')

    // The caption never shows a claim age the API would reject.
    expect(screen.getAllByText(/\/mo @ 70/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/\/mo @ 62/).length).toBeGreaterThan(0)

    await user.click(getRunPreviewButton())
    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        primarySocialSecurityStartAge: 70,
        spouseSocialSecurityStartAge: 62,
      }),
    )

    // Empty stays null so the server resolves the saved start age.
    await user.clear(primaryClaimInput)
    await user.click(getRunPreviewButton())
    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ primarySocialSecurityStartAge: null }),
    )
  })

  it('renders the preview error state with retry while the planner stays reachable', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    usePreviewMock.mockReturnValue({
      data: undefined,
      error: new Error('422: claim age out of range'),
      isFetching: false,
      refetch,
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(
      screen.getByText('Failed to run retirement preview.'),
    ).toBeInTheDocument()
    expect(screen.getByText('422: claim age out of range')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(refetch).toHaveBeenCalledTimes(1)

    expect(
      screen.getByRole('button', { name: /expand planner/i }),
    ).toBeInTheDocument()
  })

  it('lists saved allocation scenarios and compares them against the current allocation', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)
    const fetchPreviewMock = vi.mocked(
      (await import('@/lib/api/household')).fetchRetirementPreview,
    )
    fetchPreviewMock.mockReset()
    fetchPreviewMock.mockResolvedValue({
      successProbability: 0.71,
      medianEndingBalance: 512_000,
      firstDepletionAge: null,
    } as unknown as RetirementPreview)

    render(<MoneyRetirementPanel dashboard={dashboard} />)
    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /allocation sandbox/i)

    expect(screen.getAllByText('Scenario lab').length).toBeGreaterThan(0)
    expect(screen.getByText('Equity bridge')).toBeInTheDocument()
    expect(screen.getByText('bridge: invested')).toBeInTheDocument()

    await user.click(
      screen.getByRole('checkbox', { name: /compare equity bridge/i }),
    )
    await user.click(
      screen.getByRole('button', { name: /compare current \+ 1 selected/i }),
    )

    expect(await screen.findByText('Current accounts')).toBeInTheDocument()
    expect(fetchPreviewMock).toHaveBeenCalledTimes(2)
    const scenarioRequest = fetchPreviewMock.mock.calls[1][0]
    expect(scenarioRequest.allocationHoldings).toEqual([
      { symbol: 'VTI', weight: 100 },
    ])
    expect(scenarioRequest.withdrawal?.bridge.growth).toBe('portfolio')
    expect(screen.getAllByText('71%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('$512,000')).toHaveLength(2)
  })

  it('sends ACA/Medicare levers to the preview request and persists them', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(
      <MoneyRetirementPanel
        dashboard={
          {
            ...dashboard,
            profile: { ...dashboard.profile, acaOopMonthly: 99.58 },
          } as HouseholdFinanceDashboard
        }
      />,
    )

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /withdrawal, healthcare & college/i)
    await user.click(
      screen.getByRole('button', { name: /bronze \(lowest premium\)/i }),
    )
    await user.click(
      screen.getByRole('button', { name: /kids covered to 26/i }),
    )
    // Blank tracks the published default; an explicit 0 is "line off".
    const medicareInput = screen.getByRole('textbox', {
      name: /medicare monthly premium per person/i,
    })
    await user.type(medicareInput, '0')
    await user.click(getRunPreviewButton())

    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        aca: {
          tier: 'bronze',
          premiumAge21MonthlyOverride: null,
          oopMonthly: 99.58,
          medicareMonthlyPerPerson: 0,
          dependentsCoveredUntilAge: 26,
        },
      }),
    )

    await user.click(screen.getByRole('button', { name: /save assumptions/i }))
    expect(updateProfileMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        acaTier: 'bronze',
        acaPremiumAge21Override: null,
        acaOopMonthly: 99.58,
        medicareMonthlyPerPerson: 0,
      }),
    )

    // Off hides the covered-lives and override knobs entirely.
    await user.click(screen.getByRole('button', { name: /^off$/i }))
    expect(
      screen.queryByRole('textbox', {
        name: /medicare monthly premium per person/i,
      }),
    ).toBeNull()
    expect(
      screen.getByText(/healthcare stream off — only the manual schedule/i),
    ).toBeInTheDocument()
  })

  it('renders healthcare and MAGI drawdown columns with cliff attribution', async () => {
    usePreviewMock.mockReturnValue({
      data: {
        ...preview,
        drawdownSchedule: [
          {
            ...preview.drawdownSchedule[0],
            // Real dollars; the default today's-dollars basis displays
            // them unscaled, so the cells assert exactly.
            acaPremiumGross: 20000,
            acaSubsidy: 0,
            acaOop: 1200,
            acaNet: 21200,
            acaPlanningNet: 800,
            magi: 90000,
            medicarePremium: 0,
          },
          preview.drawdownSchedule[1],
        ],
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(
      screen.getByRole('columnheader', { name: 'Healthcare' }),
    ).toHaveAttribute('title', expect.stringContaining('essential floor'))
    expect(screen.getByRole('columnheader', { name: 'MAGI' })).toHaveAttribute(
      'title',
      expect.stringContaining('400%'),
    )
    const healthcareCell = screen.getByText('$21,200')
    expect(healthcareCell).toHaveAttribute(
      'title',
      expect.stringContaining('the MAGI true-up repriced the subsidy'),
    )
    // Cliff year: gross premium with zero subsidy marks MAGI in amber.
    const magiCell = screen.getByText('$90,000')
    expect(magiCell).toHaveAttribute(
      'title',
      expect.stringContaining('400% FPL cliff'),
    )
    expect(
      screen.getByText(/rides the essential floor inside Spend/i),
    ).toBeInTheDocument()
  })

  it('renders income plan-vs-actual streams with stale warning and alias note', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)
    useIncomeActualsMock.mockReturnValue({
      data: incomeActuals,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementIncomeActuals>)
    useSpendingActualsMock.mockReturnValue({
      data: spendingActuals,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementSpendingActuals>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /spending & income/i)
    expect(screen.getByText('Spending & income')).toBeInTheDocument()
    expect(screen.getByText('Current spend scenario')).toBeInTheDocument()
    expect(screen.getAllByText('$7,484/mo').length).toBeGreaterThan(0)
    expect(screen.getByText('Manual planning scenario')).toBeInTheDocument()
    // Stale recurring stream warning names the stream and last deposit.
    expect(
      screen.getByText(/Some income streams have stopped/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /PINELLAS COUNTY PAYROLL LESLIE MARIANA \(last deposit Apr 17, 2026\)/,
      ),
    ).toBeInTheDocument()
    // Stream table: cadence, run-rate, owner, status badges.
    expect(screen.getByText('Every 2 weeks')).toBeInTheDocument()
    expect(screen.getByText('$6,500')).toBeInTheDocument()
    expect(screen.getByText('$6,000 observed')).toBeInTheDocument()
    expect(screen.getByText(/Auto · Mariana/)).toBeInTheDocument()
    expect(screen.getByText('Stopped?')).toBeInTheDocument()
    expect(screen.getByText('Portfolio yield')).toBeInTheDocument()
    // Cadence cell + status badge for the single-transaction stream.
    expect(screen.getAllByText('One-off')).toHaveLength(2)
    // No fabricated net line when no active take-home streams exist.
    expect(
      screen.queryByText(/Actual net while working/),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/9 duplicates collapsed/)).toBeInTheDocument()
  })

  it('shows the actual-net line when active take-home income exists', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)
    useIncomeActualsMock.mockReturnValue({
      data: {
        ...incomeActuals,
        activeMonthlyIncome: 5999.94,
        streams: [
          { ...incomeActuals.streams[0], active: true, status: 'active' },
          ...incomeActuals.streams.slice(1),
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementIncomeActuals>)
    useSpendingActualsMock.mockReturnValue({
      data: spendingActuals,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementSpendingActuals>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    await openPlannerSection(user, /spending & income/i)
    expect(screen.getByText(/Actual net while working/)).toBeInTheDocument()
    // 5999.94 - 7484.06 = -1484.12 → whole-dollar formatting.
    expect(screen.getByText(/-\$1,484\/mo/)).toBeInTheDocument()
    expect(
      screen.queryByText(/Some income streams have stopped/),
    ).not.toBeInTheDocument()
  })

  it('renders the beyond-the-success-number framing card', () => {
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.getByText('Beyond the success number')).toBeInTheDocument()
    expect(screen.getByText('How plans fail')).toBeInTheDocument()
    expect(screen.getByText('$41,250')).toBeInTheDocument()
    expect(screen.getByText(/misses the floor in 3 years/)).toBeInTheDocument()
    expect(screen.getByText(/\$180,400/)).toBeInTheDocument()
    expect(screen.getByText('Warning time')).toBeInTheDocument()
    expect(screen.getByText('4 years')).toBeInTheDocument()
    expect(screen.getByText('Penalty backstop')).toBeInTheDocument()
    expect(screen.getByText('12% of trials')).toBeInTheDocument()
    expect(screen.getByText(/\$8,150/)).toBeInTheDocument()
    expect(screen.getByText('The other side')).toBeInTheDocument()
    expect(screen.getByText('41% of trials')).toBeInTheDocument()
    expect(screen.getByText(/today's \$900,000/)).toBeInTheDocument()
  })

  it('shows the no-floor-miss framing when no trial fails', () => {
    usePreviewMock.mockReturnValue({
      data: {
        ...preview,
        successProbability: 1,
        outcomeFraming: {
          medianYearsShort: null,
          medianFloorGapReal: null,
          tailFloorGapReal: null,
          medianWarningYears: null,
          penaltyTrialsShare: 0,
          medianPenaltyPaidReal: null,
          endAboveStartShare: 0.97,
          startBalanceReal: 900000,
        },
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.getByText('No floor misses')).toBeInTheDocument()
    expect(screen.queryByText('Warning time')).not.toBeInTheDocument()
    expect(screen.getByText('0% of trials')).toBeInTheDocument()
    expect(
      screen.getByText(/No trial pays an early-access penalty/),
    ).toBeInTheDocument()
    expect(screen.getByText('97% of trials')).toBeInTheDocument()
  })

  it('sends partial-retirement levers to the preview request and persists them', async () => {
    const user = userEvent.setup()
    usePreviewMock.mockReturnValue({
      data: {
        ...preview,
        inputs: {
          ...preview.inputs,
          // Spouse retires 5 years after the primary: window 50-54.
          retirementAge: 50,
          spouseAge: 45,
          spouseRetirementAge: 50,
        },
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)
    useIncomeActualsMock.mockReturnValue({
      data: {
        ...incomeActuals,
        streams: [
          { ...incomeActuals.streams[0], active: true, status: 'active' },
          ...incomeActuals.streams.slice(1),
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useRetirementIncomeActuals>)

    render(
      <MoneyRetirementPanel
        dashboard={
          {
            ...dashboard,
            profile: {
              ...dashboard.profile,
              spouseNetMonthlyIncome: 5300,
              partialRetirementMonthlySpend: 7200,
              spouseGrossAnnualIncome: 84000,
            },
          } as HouseholdFinanceDashboard
        }
      />,
    )

    await user.click(screen.getByRole('button', { name: /expand planner/i }))
    const netInput = screen.getByRole('textbox', {
      name: /spouse net monthly take-home during partial retirement/i,
    })
    await waitFor(() => expect(netInput).toHaveValue('6499.93'))
    expect(screen.getByText(/window: age 50–54/i)).toBeInTheDocument()
    // Largest recurring non-yield stream auto-feeds the partial window until edited.
    expect(
      screen.getByText(/detected from money transactions:/i),
    ).toHaveTextContent('Mariana')
    expect(screen.getByText(/auto-fed into this plan/i)).toBeInTheDocument()

    // Levers re-project live through the debounce — no Run preview click.
    await user.clear(netInput)
    await user.type(netInput, '5400')
    await waitFor(() =>
      expect(usePreviewMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          spouseNetMonthlyIncome: 5400,
          partialRetirementMonthlySpend: 7200,
          spouseGrossAnnualIncome: 84000,
        }),
      ),
    )

    await user.click(screen.getByRole('button', { name: /save assumptions/i }))
    expect(updateProfileMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        spouseNetMonthlyIncome: 5400,
        partialRetirementMonthlySpend: 7200,
        spouseGrossAnnualIncome: 84000,
      }),
    )

    // Blank turns the feature off and persists explicit nulls.
    await user.clear(netInput)
    expect(
      await screen.findByText(/off until spouse take-home is entered/i),
    ).toBeInTheDocument()
  })

  it('renders partial window rows with badge and spouse take-home income', () => {
    usePreviewMock.mockReturnValue({
      data: {
        ...preview,
        inputs: {
          ...preview.inputs,
          retirementAge: 50,
          spouseAge: 45,
          spouseRetirementAge: 50,
        },
        drawdownSchedule: [
          {
            ...preview.drawdownSchedule[0],
            yearIndex: 0,
            calendarYear: 2027,
            primaryAge: 50,
            partialRetirementYear: true,
            spendingNeed: 90000,
            spouseNetIncome: 63600,
            income: 0,
            grossWithdrawal: 26400,
            taxEstimate: 0,
            penaltyEstimate: 0,
            netWithdrawal: 26400,
            spendingTarget: 0,
            rmdAmount: 0,
            rmdApplied: false,
          },
          ...preview.drawdownSchedule,
        ],
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    const badge = screen.getByText('Partial')
    expect(badge).toHaveAttribute(
      'title',
      expect.stringContaining('spouse still working'),
    )
    // Income cell folds her take-home into the window row.
    const incomeCell = screen.getByText('$63,600')
    expect(incomeCell).toHaveAttribute(
      'title',
      'Includes spouse take-home $63,600.',
    )
    // Spend shows the window target (engine target stays zero).
    expect(screen.getByText('$90,000')).toBeInTheDocument()
  })
})
