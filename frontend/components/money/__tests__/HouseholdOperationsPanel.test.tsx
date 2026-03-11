import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HouseholdOperationsPanel } from '../HouseholdOperationsPanel'

const categorizeMutate = vi.fn()
const useCategorizeHouseholdTransactionMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useCategorizeHouseholdTransaction: () =>
    useCategorizeHouseholdTransactionMock() ?? {
      mutate: categorizeMutate,
      isPending: false,
    },
  useConfirmFact: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useUpdateHouseholdProfile: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('../JennyQuestionInbox', () => ({
  JennyQuestionInbox: () => <div>Jenny Question Inbox</div>,
}))

vi.mock('../JennyChatPanel', () => ({
  JennyChatPanel: () => <div>Jenny Chat Panel</div>,
}))

function buildDashboard(overrides: Record<string, unknown> = {}) {
  return {
    generatedAt: '2026-03-10T00:00:00Z',
    overview: {
      investedAssets: 0,
      retirementAssets: 0,
      taxableAssets: 0,
      cashReserve: 0,
      totalTrackedAssets: 0,
      visibilityScore: 72,
      visibilityLabel: 'Good',
      nextBestAction: 'Review uncategorized spending.',
    },
    profile: {
      id: 'profile-1',
      householdName: 'Household',
      monthlyNetIncomeTarget: 10000,
      monthlyEssentialTarget: 4000,
      monthlyDiscretionaryTarget: 1500,
      monthlySavingsTarget: 1500,
      targetRetirementAge: null,
      targetRetirementSpend: null,
      notes: null,
      createdAt: '2026-03-10T00:00:00Z',
      updatedAt: '2026-03-10T00:00:00Z',
    },
    resolvedValues: [],
    budgetReadiness: {
      status: 'ready_for_budgeting',
      summary: 'Ready',
      priorities: [],
      missingInputs: [],
      starterLanes: [],
    },
    questions: [],
    actionItems: [],
    jennyNeeds: [],
    reports: {
      executive: {
        headline: 'Ledger ready',
        summary: 'Summary',
        averageMonthlySpend: 5000,
        averageMonthlyEssentials: 3200,
        averageMonthlyDiscretionary: 1800,
        recent30DaySpend: 4900,
        recurringMerchantCount: 1,
        trackedExpenseCount: 10,
        coverageMonths: 3,
      },
      categoryBreakdown: [],
      merchantHighlights: [],
      monthlySpendTrend: [],
      recentTransactions: [],
    },
    categorizationQueue: [],
    recurringCommitments: [],
    sinkingFunds: [],
    retirementPreparedness: {
      status: 'baseline_visible',
      summary: 'Ready',
      retirementAccountShare: 0,
      strengths: [],
      blockers: [],
      nextSteps: [],
    },
    retirementContributionTracker: {
      status: 'target_missing',
      monthlyTarget: null,
      estimatedMonthlyContributions: 0,
      monthlyGap: 0,
      detail: 'Set a target.',
    },
    retirementScenarios: [],
    importCenter: {
      headline: 'Import',
      trackedDocuments: 0,
      parsedDocuments: 0,
      suggestedFirstUploads: [],
      automations: [],
      supportedDocuments: [],
    },
    jennyBrief: {
      headline: 'Jenny',
      body: 'Body',
      prompts: [],
    },
    budgetSnapshot: {
      summary: 'On track',
      status: 'on_track',
      monthlyIncomeTarget: 10000,
      monthlyPlanTotal: 7000,
      essentialTarget: 4000,
      discretionaryTarget: 1500,
      savingsTarget: 1500,
      actualMonthlySpend: 5000,
      actualEssentialMonthlySpend: 3200,
      actualDiscretionaryMonthlySpend: 1800,
      monthToDateSpend: 2400,
      monthToDatePlan: 2500,
      paceStatus: 'on_track',
      paceDetail: 'Month-to-date spend is tracking close to the plan.',
      remainingCashAfterPlan: 3000,
      discretionaryHeadroom: -300,
    },
    ...overrides,
  } as any
}

describe('HouseholdOperationsPanel', () => {
  beforeEach(() => {
    useCategorizeHouseholdTransactionMock.mockReset()
    categorizeMutate.mockReset()
  })

  it('applies a categorization decision across similar merchant rows', async () => {
    const user = userEvent.setup()

    render(
      <HouseholdOperationsPanel
        dashboard={buildDashboard({
          categorizationQueue: [
            {
              id: 'txn-1',
              merchant: 'Netflix',
              description: 'Monthly streaming',
              amount: 19.99,
              transactionDate: '2026-03-10T00:00:00Z',
              currentCategory: 'Household',
              currentEssentiality: 'mixed',
              suggestedCategory: 'Subscriptions',
              suggestedEssentiality: 'discretionary',
              confidence: 0.72,
              similarTransactionCount: 3,
              reason: 'Needs a human pass.',
            },
          ],
          jennyNeeds: [
            {
              id: 'need-category',
              needType: 'review',
              title: 'Review spending categories',
              detail: '1 transaction needs a human pass.',
              priority: 'medium',
              status: 'unsatisfied',
              recurrence: 'as_needed',
              satisfactionDetail: null,
              actionHref: null,
              relatedQuestionId: null,
              fieldName: null,
            },
          ],
        })}
      />,
    )

    await user.click(screen.getByRole('button', { name: /apply to similar/i }))

    expect(categorizeMutate).toHaveBeenCalledWith({
      transactionId: 'txn-1',
      category: 'Subscriptions',
      essentiality: 'discretionary',
      applyToMerchant: true,
    })
  })

  it('renders the shared Jenny inbox when questions are present', () => {
    render(
      <HouseholdOperationsPanel
        dashboard={buildDashboard({
          questions: [
            {
              id: 'question-1',
              fieldName: null,
              status: 'open',
              priority: 'high',
              question: 'Are all accounts covered?',
              rationale: null,
              recommendation: null,
              answerText: null,
              sourceDocumentId: null,
              questionFormat: 'boolean',
              options: null,
              direction: 'jenny_to_user',
              metadata: {},
              createdAt: '2026-03-10T00:00:00Z',
              answeredAt: null,
            },
          ],
        })}
      />,
    )

    expect(screen.getByText('Jenny Question Inbox')).toBeInTheDocument()
    expect(screen.getByText('Jenny Chat Panel')).toBeInTheDocument()
  })

  it('marks categorization actions busy while a save is in flight', () => {
    useCategorizeHouseholdTransactionMock.mockReturnValue({
      mutate: categorizeMutate,
      isPending: true,
    })

    render(
      <HouseholdOperationsPanel
        dashboard={buildDashboard({
          categorizationQueue: [
            {
              id: 'txn-1',
              merchant: 'Netflix',
              description: 'Monthly streaming',
              amount: 19.99,
              transactionDate: '2026-03-10T00:00:00Z',
              currentCategory: 'Household',
              currentEssentiality: 'mixed',
              suggestedCategory: 'Subscriptions',
              suggestedEssentiality: 'discretionary',
              confidence: 0.72,
              similarTransactionCount: 3,
              reason: 'Needs a human pass.',
            },
          ],
          jennyNeeds: [
            {
              id: 'need-category',
              needType: 'review',
              title: 'Review spending categories',
              detail: '1 transaction needs a human pass.',
              priority: 'medium',
              status: 'unsatisfied',
              recurrence: 'as_needed',
              satisfactionDetail: null,
              actionHref: null,
              relatedQuestionId: null,
              fieldName: null,
            },
          ],
        })}
      />,
    )

    expect(screen.getByRole('button', { name: /looks right/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /apply to similar/i })).toBeDisabled()
  })
})
