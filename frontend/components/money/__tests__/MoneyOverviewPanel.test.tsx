'use client'

import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { MoneyOverviewPanel } from '../MoneyOverviewPanel'

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
    remainingCashAfterPlan: 1000,
    discretionaryHeadroom: -400,
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
      averageMonthlyDiscretionary: 1800,
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
    },
  ],
  transactionDateIssues: [],
  sinkingFunds: [],
  retirementContributionTracker: {
    status: 'gap',
    monthlyTarget: 1500,
    estimatedMonthlyContributions: 1100,
    monthlyGap: 400,
    detail: 'Gap remains.',
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
    plannedExpenses: [],
    documentRequirements: [],
  },
} as HouseholdFinanceDashboard

describe('MoneyOverviewPanel', () => {
  it('surfaces decision-board answers, budget pulse, recurring bills, and savings levers', () => {
    render(<MoneyOverviewPanel dashboard={dashboard} />)

    expect(screen.getByText('Decision Board')).toBeInTheDocument()
    expect(screen.getByText('Why this month feels tight')).toBeInTheDocument()
    expect(screen.getByText('Safe to spend this weekend')).toBeInTheDocument()
    expect(screen.getByText('Want vs need')).toBeInTheDocument()
    expect(screen.getByText('Where to save next')).toBeInTheDocument()
    expect(screen.getByText('+$500')).toBeInTheDocument()
    expect(screen.getByText('$0')).toBeInTheDocument()
    expect(screen.getByText('$4,700 / $1,800')).toBeInTheDocument()
    expect(screen.getByText('Wants are $400 above the current cap.')).toBeInTheDocument()
    expect(screen.getByText(/operating cushion: \$5,000/i)).toBeInTheDocument()
    expect(screen.getByText(/merchant to attack first: amazon/i)).toBeInTheDocument()
    expect(screen.getByText('Budget Pulse')).toBeInTheDocument()
    expect(screen.getByText('Latest full-month change')).toBeInTheDocument()
    expect(
      screen.getAllByText(/month-to-date spend is ahead of plan/i),
    ).toHaveLength(2)
    expect(screen.getByText('Where Money Went')).toBeInTheDocument()
    expect(screen.getByText('Recurring Bills')).toBeInTheDocument()
    expect(screen.getByText('Duke Energy')).toBeInTheDocument()
    expect(screen.getByText('Savings Levers')).toBeInTheDocument()
    expect(
      screen.getAllByText(/honey - 32oz/i),
    ).toHaveLength(2)
    expect(
      screen.getByText(/track repeat amazon items against walmart/i),
    ).toBeInTheDocument()
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
              actionHref: '/money?utility=evidence',
              relatedAccountId: 'account-1',
              relatedQuestionId: null,
              relatedDocumentIds: ['doc-1'],
            },
          ],
        }}
      />,
    )

    expect(
      screen.getAllByText('Monthly spend estimate: 1 spending account stale.'),
    ).not.toHaveLength(0)
    expect(
      screen.getAllByText('Refresh transactions for Joint Checking'),
    ).not.toHaveLength(0)
    expect(screen.getAllByText('Estimate')).not.toHaveLength(0)
    expect(screen.getByText('$0')).toBeInTheDocument()
    expect(screen.getByText('$4,700 / $1,800')).toBeInTheDocument()
    expect(
      screen.getByText(/weekend spend room is estimate until spending coverage is current/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/needs versus wants is estimate until spending coverage is current/i),
    ).toBeInTheDocument()
    expect(screen.getByText('+$900')).toBeInTheDocument()
  })
})
