import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HouseholdOperationsPanel } from '../HouseholdOperationsPanel'

const categorizeMutate = vi.fn()
const useCategorizeHouseholdTransactionMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useAnswerHouseholdQuestion: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useCategorizeHouseholdTransaction: () =>
    useCategorizeHouseholdTransactionMock() ?? {
      mutate: categorizeMutate,
      isPending: false,
    },
}))

describe('HouseholdOperationsPanel', () => {
  beforeEach(() => {
    useCategorizeHouseholdTransactionMock.mockReset()
  })

  it('applies a categorization decision across similar merchant rows', async () => {
    const user = userEvent.setup()

    render(
      <HouseholdOperationsPanel
        dashboard={{
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
          opportunities: [],
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
        } as any}
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

  it('renders household action items as navigable links', () => {
    render(
      <HouseholdOperationsPanel
        dashboard={{
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
          actionItems: [
            {
              title: 'Review imported transactions',
              detail: 'Confirm whether the latest uploads were categorized correctly.',
              actionLabel: 'Open intake',
              href: '/money?tab=intake',
              priority: 'high',
              source: 'documents',
            },
          ],
          opportunities: [],
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
        } as any}
      />,
    )

    expect(screen.getByRole('link', { name: 'Open intake' })).toHaveAttribute(
      'href',
      '/money?tab=intake',
    )
  })

  it('marks categorization actions busy while a save is in flight', () => {
    useCategorizeHouseholdTransactionMock.mockReturnValue({
      mutate: categorizeMutate,
      isPending: true,
    })

    render(
      <HouseholdOperationsPanel
        dashboard={{
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
          opportunities: [],
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
        } as any}
      />,
    )

    expect(screen.getByRole('button', { name: /save this row/i })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: /apply to similar/i })).toHaveAttribute('aria-busy', 'true')
  })
})
