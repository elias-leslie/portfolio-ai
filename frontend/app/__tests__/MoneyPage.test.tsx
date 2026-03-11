import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdDocumentsMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdDocuments: () => useHouseholdDocumentsMock(),
}))

vi.mock('@/components/money/HouseholdOverviewGrid', () => ({
  HouseholdOverviewGrid: () => <div>Overview Grid</div>,
}))
vi.mock('@/components/money/HouseholdOperationsPanel', () => ({
  HouseholdOperationsPanel: () => <div>Operations Panel</div>,
}))
vi.mock('@/components/money/HouseholdReportsPanel', () => ({
  HouseholdReportsPanel: () => <div>Reports Panel</div>,
}))
vi.mock('@/components/money/HouseholdDocumentCenter', () => ({
  HouseholdDocumentCenter: () => <div>Document Center</div>,
}))
vi.mock('@/components/money/HouseholdProfileCard', () => ({
  HouseholdProfileCard: () => <div>Profile Card</div>,
}))
vi.mock('@/components/money/HouseholdPlanningPanels', () => ({
  HouseholdPlanningPanels: () => <div>Planning Panels</div>,
}))
vi.mock('@/components/money/JennyQuestionInbox', () => ({
  JennyQuestionInbox: () => <div>Jenny Question Inbox</div>,
}))
vi.mock('@/components/money/JennyChatPanel', () => ({
  JennyChatPanel: () => <div>Jenny Chat Panel</div>,
}))
vi.mock('@/components/money/JennyMoneyBoard', () => ({
  JennyMoneyBoard: () => <div>Jenny Money Board</div>,
}))

describe('MoneyPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/money')
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        generatedAt: '2026-03-10T00:00:00Z',
        overview: {
          investedAssets: 0,
          retirementAssets: 0,
          taxableAssets: 0,
          cashReserve: 0,
          totalTrackedAssets: 0,
          visibilityScore: 60,
          visibilityLabel: 'Good',
          nextBestAction: 'Review uncategorized spending.',
        },
        profile: {
          id: 'profile-1',
          householdName: 'Household',
          monthlyNetIncomeTarget: 10000,
          monthlyEssentialTarget: 4000,
          monthlyDiscretionaryTarget: 1500,
          monthlySavingsTarget: 2000,
          targetRetirementAge: 60,
          targetRetirementSpend: 5000,
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
        budgetSnapshot: {
          status: 'on_track',
          summary: 'On track',
          monthlyIncomeTarget: 10000,
          monthlyPlanTotal: 7500,
          essentialTarget: 4000,
          discretionaryTarget: 1500,
          savingsTarget: 2000,
          actualMonthlySpend: 5200,
          actualEssentialMonthlySpend: 3400,
          actualDiscretionaryMonthlySpend: 1800,
          monthToDateSpend: 2400,
          monthToDatePlan: 2500,
          paceStatus: 'on_track',
          paceDetail: 'Month-to-date spend is tracking close to the plan.',
          remainingCashAfterPlan: 2500,
          discretionaryHeadroom: -300,
        },
        retirementPreparedness: {
          status: 'baseline_visible',
          summary: 'Retirement is visible.',
          retirementAccountShare: 42,
          strengths: [],
          blockers: [],
          nextSteps: [],
        },
        actionItems: [],
        jennyNeeds: [],
        reports: {
          executive: {
            headline: 'Ledger ready',
            summary: 'Summary',
            averageMonthlySpend: 5200,
            averageMonthlyEssentials: 3400,
            averageMonthlyDiscretionary: 1800,
            recent30DaySpend: 4900,
            recurringMerchantCount: 4,
            trackedExpenseCount: 24,
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
        retirementContributionTracker: {
          status: 'gap',
          monthlyTarget: 2000,
          estimatedMonthlyContributions: 1000,
          monthlyGap: 1000,
          detail: 'Gap remains.',
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
        questions: [],
        jennyBrief: {
          headline: 'Jenny',
          body: 'Body',
          prompts: [],
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    useHouseholdDocumentsMock.mockReturnValue({
      data: { items: [] },
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('offers retry when the household workspace fails to load', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    useHouseholdDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('down'),
      refetch,
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    await user.click(screen.getByRole('button', { name: 'Retry workspace' }))

    expect(refetch).toHaveBeenCalled()
  })

  it('shows retry for the intake tab when document loading fails', async () => {
    const user = userEvent.setup()
    const refetchDocuments = vi.fn()
    useHouseholdDocumentsMock.mockReturnValue({
      data: undefined,
      isFetching: false,
      error: new Error('docs down'),
      refetch: refetchDocuments,
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText(/next best action: review uncategorized spending\./i)).toBeInTheDocument()
    expect(screen.getByText(/0 needs · 0 documents/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Intake' }))
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(refetchDocuments).toHaveBeenCalled()
  })

  it('shows Jenny questions in Planning before Operate is unlocked', async () => {
    const user = userEvent.setup()
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        generatedAt: '2026-03-10T00:00:00Z',
        overview: {
          investedAssets: 0,
          retirementAssets: 0,
          taxableAssets: 0,
          cashReserve: 0,
          totalTrackedAssets: 0,
          visibilityScore: 40,
          visibilityLabel: 'Early',
          nextBestAction: 'Answer Jenny.',
        },
        profile: {
          id: 'profile-1',
          householdName: 'Household',
          monthlyNetIncomeTarget: null,
          monthlyEssentialTarget: null,
          monthlyDiscretionaryTarget: null,
          monthlySavingsTarget: null,
          targetRetirementAge: null,
          targetRetirementSpend: null,
          notes: null,
          createdAt: '2026-03-10T00:00:00Z',
          updatedAt: '2026-03-10T00:00:00Z',
        },
        resolvedValues: [],
        budgetReadiness: {
          status: 'setup_needed',
          summary: 'Needs setup',
          priorities: [],
          missingInputs: [],
          starterLanes: [],
        },
        budgetSnapshot: {
          status: 'setup_needed',
          summary: 'Need plan.',
          monthlyIncomeTarget: null,
          monthlyPlanTotal: null,
          essentialTarget: null,
          discretionaryTarget: null,
          savingsTarget: null,
          actualMonthlySpend: 0,
          actualEssentialMonthlySpend: 0,
          actualDiscretionaryMonthlySpend: 0,
          monthToDateSpend: 0,
          monthToDatePlan: null,
          paceStatus: 'on_track',
          paceDetail: 'Waiting for more data.',
          remainingCashAfterPlan: null,
          discretionaryHeadroom: null,
        },
        retirementPreparedness: {
          status: 'baseline_visible',
          summary: 'Needs more data',
          retirementAccountShare: 0,
          strengths: [],
          blockers: [],
          nextSteps: [],
        },
        actionItems: [],
        jennyNeeds: [
          {
            id: 'need-1',
            needType: 'confirm',
            title: 'Confirm account coverage',
            detail: 'Jenny needs to know whether all accounts are included.',
            priority: 'high',
            status: 'unsatisfied',
            recurrence: 'one_time',
            satisfactionDetail: null,
            actionHref: null,
            relatedQuestionId: 'question-1',
            fieldName: null,
          },
        ],
        reports: {
          executive: {
            headline: 'Partial',
            summary: 'Summary',
            averageMonthlySpend: 100,
            averageMonthlyEssentials: 100,
            averageMonthlyDiscretionary: 0,
            recent30DaySpend: 100,
            recurringMerchantCount: 0,
            trackedExpenseCount: 1,
            coverageMonths: 1,
          },
          categoryBreakdown: [],
          merchantHighlights: [],
          monthlySpendTrend: [],
          recentTransactions: [],
        },
        categorizationQueue: [],
        recurringCommitments: [],
        sinkingFunds: [],
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
          trackedDocuments: 1,
          parsedDocuments: 1,
          suggestedFirstUploads: [],
          automations: [],
          supportedDocuments: [],
        },
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
        jennyBrief: {
          headline: 'Jenny',
          body: 'Body',
          prompts: [],
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.queryByRole('button', { name: 'Operate' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Planning' }))
    expect(screen.getByText('Jenny Question Inbox')).toBeInTheDocument()
    expect(screen.getByText('Jenny Chat Panel')).toBeInTheDocument()
  })

  it('defaults mature users into Operate', async () => {
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Operations Panel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Operate' })).toHaveAttribute('aria-current', 'page')
  })
})
