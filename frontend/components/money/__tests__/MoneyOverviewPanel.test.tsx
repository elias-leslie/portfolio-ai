'use client'

import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { MoneyOverviewPanel } from '../MoneyOverviewPanel'

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdNetWorthTrend: () => ({ data: undefined, isLoading: false }),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolioAnalytics: () => ({ data: undefined, isLoading: false }),
}))

vi.mock('recharts', () => {
  const MockChart = ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  )

  return {
    ResponsiveContainer: MockChart,
    PieChart: MockChart,
    Pie: MockChart,
    BarChart: MockChart,
    Bar: MockChart,
    LineChart: MockChart,
    Line: MockChart,
    XAxis: MockChart,
    YAxis: MockChart,
    Cell: MockChart,
    Tooltip: () => null,
  }
})

const dashboard = {
  generatedAt: '2026-04-11T00:00:00Z',
  overview: {
    investedAssets: 100000,
    retirementAssets: 250000,
    taxableAssets: 50000,
    cashReserve: 12000,
    totalTrackedAssets: 412000,
    liabilitiesTotal: 0,
    netWorth: 412000,
    netWorthStatus: 'current',
    netWorthDetail: 'Net worth reflects 3 covered accounts through 2026-04-09.',
    trackedAccountCount: 3,
    needsRefreshCount: 0,
    candidateAccountCount: 0,
    gapCount: 0,
    inboxCount: 0,
    coverageMonths: 4,
    lastTransactionDate: '2026-04-09',
    visibilityScore: 91,
    visibilityLabel: 'Strong',
    monthlySpendStatus: 'current',
    monthlySpendDetail:
      'Monthly spend reflects 1 covered spending account through 2026-04-09.',
    nextBestAction: 'Review the budget pulse.',
    assetAllocation: [
      { assetGroup: 'retirement', totalValue: 250000 },
      { assetGroup: 'taxable', totalValue: 50000 },
      { assetGroup: 'cash', totalValue: 12000 },
    ],
  },
  accountControl: {
    status: 'clear',
    summary: 'Account source controls are clear.',
    issueCount: 0,
    blockingIssueCount: 0,
    checkedAt: '2026-04-11T00:00:00Z',
    issues: [],
  },
  profile: {
    id: 'profile-1',
    householdName: 'Household',
    monthlyNetIncomeTarget: 9000,
    monthlyEssentialTarget: 5000,
    monthlyDiscretionaryTarget: 1500,
    monthlySavingsTarget: 1500,
    targetRetirementAge: 60,
    targetRetirementSpend: 6000,
    notes: null,
    createdAt: '2026-04-11T00:00:00Z',
    updatedAt: '2026-04-11T00:00:00Z',
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
    status: 'discretionary_above_plan',
    summary: 'Discretionary spending is above plan.',
    monthlyIncomeTarget: 9000,
    monthlyPlanTotal: 8000,
    monthlyPlanSource: 'household_profile_targets',
    monthlyPlanSourceLabel: 'Household profile targets',
    essentialTarget: 5000,
    discretionaryTarget: 1500,
    savingsTarget: 1500,
    actualMonthlySpend: 8200,
    actualEssentialMonthlySpend: 5100,
    actualDiscretionaryMonthlySpend: 1900,
    monthToDateSpend: 3100,
    monthToDatePlan: 2600,
    paceStatus: 'running_hot',
    paceDetail: 'Month-to-date spend is ahead of plan by $500.',
    planIsPartial: false,
    missingPlanComponents: [],
    remainingCashAfterPlan: 1000,
    discretionaryHeadroom: -400,
    // Deliberately NOT derivable from the raw fixture inputs above — the
    // backend owns these numbers and the UI must render them verbatim.
    safeToSpend: 240,
    safeToSpendConstraint: 'cash_after_commitments' as const,
    dueSoonBillsTotal: 245,
    operatingCushion: 5200,
    affordability: {
      freeToSpend: 240,
      cashOnHand: 8000,
      billsDue: 245,
      billsDueThrough: '2026-09-06',
      remainingEssentials: 1515,
      essentialsBasis:
        '3,685 of the 5,200 essentials baseline is covered so far in August.',
      committedFunds: 0,
      cardBalances: 6000,
      missingInputs: ['sinking_fund_balances'],
      status: 'tight',
      headline: '$240 left once everything owed through Sep 6 is covered.',
      detail:
        "Cash on hand, less bills due through Sep 6, the rest of this month's essentials, and what is owed on cards.",
    },
  },
  retirementPreparedness: {
    status: 'baseline_visible',
    summary: 'Visible',
    retirementAccountShare: 61,
    strengths: [],
    blockers: [],
    nextSteps: [],
  },
  jennyNeeds: [],
  reports: {
    executive: {
      headline: 'Ledger ready',
      summary: 'Summary',
      averageMonthlySpend: 6500,
      averageMonthlyEssentials: 4700,
      averageMonthlyDiscretionary: 1500,
      averageMonthlyMixed: 300,
      recent30DaySpend: 6200,
      recurringMerchantCount: 3,
      trackedExpenseCount: 18,
      coverageMonths: 4,
    },
    categoryBreakdown: [
      {
        category: 'Bills',
        essentiality: 'essential',
        monthlyAverage: 2400,
        shareOfSpend: 0.36,
        totalSpend: 9600,
      },
      {
        category: 'Groceries',
        essentiality: 'essential',
        monthlyAverage: 1200,
        shareOfSpend: 0.18,
        totalSpend: 4800,
      },
    ],
    merchantHighlights: [
      {
        merchant: 'Amazon',
        category: 'Retail',
        totalSpend: 950,
        averageTicket: 79,
        transactionCount: 12,
        cadence: 'likely weekly',
        recommendation:
          'Track repeat Amazon items against Walmart, Target, and Subscribe & Save so Jenny can flag cheaper substitutions.',
      },
    ],
    priceInsights: [
      {
        merchant: 'Amazon',
        itemName: "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
        signalType: 'price_up',
        latestPrice: 14.26,
        previousPrice: 13.99,
        priceChange: 0.27,
        priceChangePct: 1.9,
        latestDate: '2026-03-02',
        previousDate: '2026-02-05',
        latestUnitLabel: '32 oz',
        previousUnitLabel: '32 oz',
        unitMeasure: 'weight_oz',
        latestUnitPrice: 0.4456,
        previousUnitPrice: 0.4372,
        unitPriceChangePct: 1.9,
        sizeChangePct: 0,
        shrinkflationFlag: false,
        confidence: 0.94,
        recommendation:
          'Price is up versus the prior buy. Compare Amazon against Walmart, Target, or local alternatives before reordering.',
      },
    ],
    monthlySpendTrend: [
      {
        month: '2025-01',
        totalSpend: 4200,
        transactionCount: 12,
      },
      {
        month: '2025-02',
        totalSpend: 5100,
        transactionCount: 14,
      },
    ],
    monthComparison: {
      latestMonth: '2025-02',
      previousMonth: '2025-01',
      latestTotal: 5100,
      previousTotal: 4200,
      change: 900,
      changePct: 21.4,
    },
    recentTransactions: [
      {
        date: '2026-04-09',
        merchant: 'Publix',
        description: 'Groceries',
        amount: 122,
        category: 'Groceries',
        essentiality: 'essential',
        accountLabel: 'Joint checking',
        sourceDocumentId: 'doc-1',
      },
    ],
  },
  categorizationQueue: [],
  recurringCommitments: [
    {
      merchant: 'Duke Energy',
      category: 'Bills',
      cadence: 'likely monthly',
      averageAmount: 178,
      annualizedCost: 2136,
      lastSeen: '2026-04-01',
      nextExpected: '2026-04-15',
      daysUntilDue: 4,
      dueStatus: 'due_soon',
      dueConfidence: 0.82,
      commitmentType: 'bill',
      evidence:
        '8 charges across 8 months, about 30 days apart, typically 178.00.',
    },
  ],
  transactionDateIssues: [],
  sinkingFunds: [],
  spendExclusions: {
    excludedCount: 0,
    excludedAmount: 0,
    includedCount: 0,
    includedAmount: 0,
    overriddenCount: 0,
    rules: [],
    summary: '',
  },
  retirementContributionTracker: {
    status: 'gap',
    monthlyTarget: 1500,
    estimatedMonthlyContributions: 1100,
    monthlyGap: 400,
    detail: 'Gap remains.',
    phase: 'accumulating_contributions_binding',
    phaseLabel: 'Accumulating - 16 years to 65',
    headline: 'Today\u2019s assets support $4,167/mo against a $6,000/mo plan.',
    currentAge: 49,
    targetRetirementAge: 65,
    yearsToTarget: 16,
    investableAssets: 1000000,
    withdrawalRate: 0.05,
    sustainableMonthlySpend: 4166.67,
    targetMonthlySpend: 6000,
    assetGap: 440000,
    spendPhase: null,
    yearsToNextSpendPhase: null,
    blindSpots: [],
  },
  retirementScenarios: [],
  importCenter: {
    headline: 'Import',
    trackedDocuments: 3,
    parsedDocuments: 3,
    suggestedFirstUploads: [],
    automations: [],
    supportedDocuments: [],
  },
  evidenceAccounts: [],
  accounts: [
    {
      id: 'account-1',
      label: 'Joint Checking',
      assetGroup: 'cash',
      accountType: 'checking',
      sourceType: 'bank',
      institutionName: 'Wells Fargo',
      ownerName: null,
      accountMask: '4421',
      notes: null,
      currency: 'USD',
      currentValue: 12000,
      balance: 12000,
      holdingsValue: null,
      cashBalance: 12000,
      evidenceCount: 1,
      documentIds: ['doc-1'],
      latestDocumentId: 'doc-1',
      sourceTypes: ['bank'],
      linkedPortfolioAccountId: null,
      linkedPortfolioAccountName: null,
      trackedAccountId: null,
      accountOrigin: 'evidence',
      moneyRole: 'spend_driver',
      lastEvidenceAt: '2026-04-09T00:00:00Z',
      daysSinceEvidence: 2,
      lastBalanceAt: '2026-04-09T00:00:00Z',
      daysSinceBalance: 2,
      balanceFreshnessStatus: 'fresh',
      balanceFreshnessLabel: 'Fresh',
      lastTransactionAt: '2026-04-09T00:00:00Z',
      daysSinceTransaction: 2,
      transactionFreshnessStatus: 'fresh',
      transactionFreshnessLabel: 'Fresh',
      freshnessStatus: 'fresh',
      freshnessLabel: 'Fresh',
      matchStatus: 'linked',
      matchConfidence: 0.95,
      gapFlags: [],
    },
  ],
  discoveredAccounts: [],
  inbox: [],
  questions: [],
  jennyBrief: {
    headline: 'Jenny',
    body: 'Body',
    prompts: [],
  },
  planning: {
    summary: {
      completionScore: 0,
      readySections: 0,
      totalSections: 0,
      missingDocumentCount: 0,
      highPriorityDocumentCount: 0,
      sections: [],
    },
    members: [],
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
} as HouseholdFinanceDashboard

describe('MoneyOverviewPanel', () => {
  it('renders the pulse, categories, bills and levers, and no Decision Board', () => {
    render(<MoneyOverviewPanel dashboard={dashboard} />)

    expect(screen.getByText('Budget Pulse')).toBeInTheDocument()
    expect(screen.getByText('Latest full-month change')).toBeInTheDocument()
    expect(screen.getByText('+$900')).toBeInTheDocument()
    // Once, not twice: the Decision Board printed the same pace detail.
    // Once, not twice: the Decision Board and the watch list both echoed it.
    expect(
      screen.getAllByText(/month-to-date spend is ahead of plan/i),
    ).toHaveLength(1)
    expect(screen.getAllByText(/household profile targets/i)).not.toHaveLength(
      0,
    )
    expect(screen.getByText('Where Money Went')).toBeInTheDocument()
    expect(screen.getByText('Recurring Bills')).toBeInTheDocument()
    expect(screen.getByText('Duke Energy')).toBeInTheDocument()
    expect(screen.getAllByText('Savings Levers').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/honey - 32oz/i)).toHaveLength(1)
    expect(
      screen.getByText(/track repeat amazon items against walmart/i),
    ).toBeInTheDocument()
  })

  it('no longer answers questions the review screen owns', () => {
    // Budget pace, Free to spend and the needs/wants/mixed split were four
    // cards here, one tab away from the screen where the household reads the
    // month. Account Allocation went to Investing, where the assets are.
    render(<MoneyOverviewPanel dashboard={dashboard} />)

    for (const retired of [
      'Decision Board',
      'Budget Pace',
      'Free to spend',
      'Needs, wants and mixed',
      'Account Allocation',
    ]) {
      expect(screen.queryByText(retired)).not.toBeInTheDocument()
    }
  })

  it('keeps review-only account controls out of the main dashboard surface', () => {
    render(
      <MoneyOverviewPanel
        dashboard={{
          ...dashboard,
          accountControl: {
            status: 'review',
            summary:
              '1 account control review item found; totals are not double-counting it.',
            issueCount: 1,
            blockingIssueCount: 0,
            checkedAt: '2026-04-11T00:00:00Z',
            issues: [
              {
                id: 'duplicate_source_alias:cash',
                code: 'duplicate_source_alias',
                severity: 'medium',
                title: 'Duplicate source aliases collapsed',
                detail:
                  'Cash Management is represented by two matching source rows.',
                householdAccountId: 'cash',
                accountLabel: 'Cash Management',
                source: 'snaptrade',
                sourceAccountIds: ['source-1', 'source-2'],
                affectsTotals: false,
              },
            ],
          },
        }}
      />,
    )

    expect(screen.queryByText('Account Controls')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Duplicate source aliases collapsed'),
    ).not.toBeInTheDocument()
  })

  it('marks spend decisions as estimated when coverage is incomplete', () => {
    render(
      <MoneyOverviewPanel
        dashboard={{
          ...dashboard,
          overview: {
            ...dashboard.overview,
            monthlySpendStatus: 'estimated',
            monthlySpendDetail:
              'Monthly spend estimate: 1 spending account stale.',
          },
          inbox: [
            {
              id: 'account-checking-stale',
              category: 'account',
              priority: 'high',
              title: 'Refresh transactions for Joint Checking',
              detail:
                'This spending account is too old to trust for current monthly-spend, budget, or safe-to-spend calculations.',
              actionLabel: 'Add statements',
              actionHref: '/money?tab=intake',
              relatedAccountId: 'account-1',
              relatedQuestionId: null,
              relatedDocumentIds: ['doc-1'],
              affects: [],
            },
          ],
        }}
      />,
    )

    expect(
      screen.getAllByRole('button', { name: /estimate: more detail/i }),
    ).not.toHaveLength(0)
    expect(screen.queryByText('Safe')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/estimate from current coverage/i),
    ).not.toBeInTheDocument()
    expect(screen.getByText('+$900')).toBeInTheDocument()
  })
})
