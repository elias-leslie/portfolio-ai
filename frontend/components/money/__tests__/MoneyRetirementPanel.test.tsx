'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  HouseholdFinanceDashboard,
  RetirementPreview,
} from '@/lib/api/household'
import {
  useRetirementPreview,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'
import { MoneyRetirementPanel } from '../MoneyRetirementPanel'

vi.mock('@/lib/hooks/useHousehold', () => ({
  useRetirementPreview: vi.fn(),
  useUpdateHouseholdProfile: vi.fn(),
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
    CartesianGrid: MockPart,
    Legend: MockPart,
    LineChart: MockChart,
    Line: MockPart,
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
    remainingCashAfterPlan: 1500,
    discretionaryHeadroom: 0,
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
        displayName: 'Elias',
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
        displayName: 'Mariana',
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
  returnAssumptions: {
    expectedReturn: 0.052,
    incomeYield: 0.024,
    cashYield: 0.0328,
    cashYieldSource: 'Fidelity SPAXX 7-day yield as of 2026-05-07',
  },
  taxAssumptions: {
    filingStatusLabel: 'Married filing jointly',
    standardDeduction: 32200,
    capitalGainsZeroRateLimit: 98900,
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
      withdrawalsByBucket: {
        taxable: 74000,
        governmental457b: 0,
        preTax: 0,
        roth: 0,
      },
      balancesByBucket: {
        taxable: 200000,
        governmental457b: 95000,
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
      withdrawalsByBucket: {
        taxable: 20000,
        governmental457b: 0,
        preTax: 45000,
        roth: 0,
      },
      balancesByBucket: {
        taxable: 0,
        governmental457b: 90000,
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
  firstDepletionAge: null,
  estimatedMonthlyContributionGap: 0,
}

const usePreviewMock = vi.mocked(useRetirementPreview)
const useUpdateProfileMock = vi.mocked(useUpdateHouseholdProfile)
const updateProfileMutateAsync = vi.fn()

describe('MoneyRetirementPanel', () => {
  beforeEach(() => {
    usePreviewMock.mockReset()
    updateProfileMutateAsync.mockReset()
    updateProfileMutateAsync.mockResolvedValue({})
    useUpdateProfileMock.mockReturnValue({
      mutateAsync: updateProfileMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateHouseholdProfile>)
  })

  it('renders visual retirement readiness, buckets, levers, and drawdown rows', () => {
    usePreviewMock.mockReturnValue({
      data: preview,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRetirementPreview>)

    render(<MoneyRetirementPanel dashboard={dashboard} />)

    expect(screen.getByText('Retirement planner')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /expand planner/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /expand allocation/i }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Your retire age')).not.toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('$1,250,000')).toBeInTheDocument()
    expect(screen.getAllByText('Taxable').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Gov 457(b)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pre-tax').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Roth').length).toBeGreaterThan(0)
    expect(screen.getByText('Tax model')).toBeInTheDocument()
    expect(screen.getByText('Married filing jointly')).toBeInTheDocument()
    expect(screen.getByText('Allocation sandbox')).toBeInTheDocument()
    expect(screen.getByText('Retire 2 years later')).toBeInTheDocument()
    expect(screen.getByText('Drawdown schedule')).toBeInTheDocument()
    expect(screen.getByText('$18,000')).toBeInTheDocument()
    expect(screen.getByText('$45,000')).toBeInTheDocument()
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

    await user.click(screen.getByRole('button', { name: /expand allocation/i }))

    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
    expect(screen.getByDisplayValue('3.28')).toBeInTheDocument()
    expect(
      screen.getByText(/success odds use total return/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Fidelity SPAXX 7-day yield as of 2026-05-07/i),
    ).toBeInTheDocument()
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
    await user.click(screen.getByRole('button', { name: /run preview/i }))

    expect(usePreviewMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        retirementAge: 66,
        primaryAge: 49,
        spouseAge: 43,
      }),
    )
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

    await user.click(screen.getByRole('button', { name: /expand allocation/i }))
    await user.click(screen.getByRole('button', { name: /ticker basket/i }))
    const tickerInput = screen.getByDisplayValue(/SCHD 10/)
    await user.clear(tickerInput)
    await user.type(
      tickerInput,
      'VTI 70{enter}SCHD 10 3.6{enter}BND 10 4.0{enter}SPAXX 10',
    )
    await user.click(screen.getByRole('button', { name: /run preview/i }))

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
    expect(
      screen.getByText(/primary: rough salary estimate/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/spouse: rough salary estimate/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Replace rough salary estimates with exact SSA/i),
    ).toBeInTheDocument()
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
})
