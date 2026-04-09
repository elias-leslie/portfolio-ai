import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HouseholdPlanningPanels } from '../HouseholdPlanningPanels'

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdPlanning: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

describe('HouseholdPlanningPanels', () => {
  it('shows blockers and empty-state planning copy when retirement details are sparse', () => {
    render(
      <HouseholdPlanningPanels
        dashboard={{
          generatedAt: '2026-03-10T00:00:00Z',
          overview: {
            investedAssets: 0,
            retirementAssets: 0,
            taxableAssets: 0,
            cashReserve: 0,
            totalTrackedAssets: 0,
            liabilitiesTotal: 0,
            netWorth: 0,
            trackedAccountCount: 0,
            needsRefreshCount: 0,
            candidateAccountCount: 0,
            gapCount: 0,
            inboxCount: 0,
            coverageMonths: 0,
            lastTransactionDate: null,
            visibilityScore: 60,
            visibilityLabel: 'Developing',
            nextBestAction: 'Upload more statements.',
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
            status: 'baseline_visible',
            summary: 'Ready',
            priorities: [],
            missingInputs: [],
            starterLanes: [],
          },
          budgetSnapshot: {
            status: 'on_track',
            summary: 'On track',
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
            paceDetail: 'On track.',
            remainingCashAfterPlan: null,
            discretionaryHeadroom: null,
          },
          retirementPreparedness: {
            status: 'baseline_visible',
            summary: 'Retirement needs more evidence.',
            retirementAccountShare: 12,
            strengths: [],
            blockers: ['Contribution rate is below target.'],
            nextSteps: [],
          },
          jennyNeeds: [],
          reports: {
            executive: {
              headline: 'Ledger ready',
              summary: 'Summary',
              averageMonthlySpend: 0,
              averageMonthlyEssentials: 0,
              averageMonthlyDiscretionary: 0,
              recent30DaySpend: 0,
              recurringMerchantCount: 0,
              trackedExpenseCount: 0,
              coverageMonths: 0,
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
          evidenceAccounts: [],
          accounts: [],
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
        }}
      />,
    )

    expect(screen.getByText(/no starter lanes yet/i)).toBeInTheDocument()
    expect(
      screen.getByText(
        /jenny has not identified a strong retirement edge yet/i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/contribution rate is below target/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/jenny does not have a next-step recommendation yet/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /retirement scenarios will appear once jenny has enough spending/i,
      ),
    ).toBeInTheDocument()
  })

  it('renders populated dashboard with starter lanes, strengths, next steps, and retirement scenarios', () => {
    render(
      <HouseholdPlanningPanels
        dashboard={{
          generatedAt: '2026-03-10T00:00:00Z',
          overview: {
            investedAssets: 100000,
            retirementAssets: 250000,
            taxableAssets: 50000,
            cashReserve: 25000,
            totalTrackedAssets: 425000,
            liabilitiesTotal: 0,
            netWorth: 425000,
            trackedAccountCount: 0,
            needsRefreshCount: 0,
            candidateAccountCount: 0,
            gapCount: 0,
            inboxCount: 0,
            coverageMonths: 12,
            lastTransactionDate: '2026-03-09',
            visibilityScore: 95,
            visibilityLabel: 'Excellent',
            nextBestAction: 'Review retirement strategies.',
          },
          profile: {
            id: 'profile-1',
            householdName: 'Household',
            monthlyNetIncomeTarget: 8000,
            monthlyEssentialTarget: 4000,
            monthlyDiscretionaryTarget: 2000,
            monthlySavingsTarget: 2000,
            targetRetirementAge: 65,
            targetRetirementSpend: 80000,
            notes: null,
            createdAt: '2026-03-10T00:00:00Z',
            updatedAt: '2026-03-10T00:00:00Z',
          },
          resolvedValues: [],
          budgetReadiness: {
            status: 'tracking_well',
            summary: 'On track',
            priorities: [],
            missingInputs: [],
            starterLanes: [
              {
                name: 'Emergency Fund',
                objective: 'Build 6 months of expenses',
                status: 'in_progress',
              },
              {
                name: 'Vacation Savings',
                objective: 'Save for annual trips',
                status: 'started',
              },
            ],
          },
          budgetSnapshot: {
            status: 'on_track',
            summary: 'On track',
            monthlyIncomeTarget: 8000,
            monthlyPlanTotal: 8000,
            essentialTarget: 4000,
            discretionaryTarget: 2000,
            savingsTarget: 2000,
            actualMonthlySpend: 7800,
            actualEssentialMonthlySpend: 3900,
            actualDiscretionaryMonthlySpend: 1950,
            monthToDateSpend: 7800,
            monthToDatePlan: 8000,
            paceStatus: 'on_track',
            paceDetail: 'On track.',
            remainingCashAfterPlan: 200,
            discretionaryHeadroom: 50,
          },
          retirementPreparedness: {
            status: 'on_track',
            summary: 'Retirement readiness is strong.',
            retirementAccountShare: 58,
            strengths: [
              'High savings rate relative to income',
              'Diverse retirement account types',
            ],
            blockers: [],
            nextSteps: [
              'Consider increasing contribution limits',
              'Review asset allocation annually',
            ],
          },
          jennyNeeds: [],
          reports: {
            executive: {
              headline: 'Ledger ready',
              summary: 'Summary',
              averageMonthlySpend: 7800,
              averageMonthlyEssentials: 3900,
              averageMonthlyDiscretionary: 1950,
              recent30DaySpend: 7800,
              recurringMerchantCount: 25,
              trackedExpenseCount: 156,
              coverageMonths: 12,
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
            status: 'on_track',
            monthlyTarget: 2000,
            estimatedMonthlyContributions: 2100,
            monthlyGap: 0,
            detail: 'Exceeding target contributions.',
          },
          retirementScenarios: [
            {
              name: 'Conservative',
              detail: 'Using 4% withdrawal rate',
              monthlySpend: 6400,
              annualSpend: 76800,
              fundedYears: 35,
              readiness: 'on_track',
            },
            {
              name: 'Moderate',
              detail: 'Using 5% withdrawal rate',
              monthlySpend: 8000,
              annualSpend: 96000,
              fundedYears: 28,
              readiness: 'needs_attention',
            },
          ],
          importCenter: {
            headline: 'Import',
            trackedDocuments: 24,
            parsedDocuments: 20,
            suggestedFirstUploads: [],
            automations: [],
            supportedDocuments: [],
          },
          evidenceAccounts: [],
          accounts: [],
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
        }}
      />,
    )

    expect(screen.getByText('Emergency Fund')).toBeInTheDocument()
    expect(screen.getByText('Vacation Savings')).toBeInTheDocument()
    expect(
      screen.getByText('High savings rate relative to income'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Diverse retirement account types'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Consider increasing contribution limits'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Review asset allocation annually'),
    ).toBeInTheDocument()
    expect(screen.getByText('Conservative')).toBeInTheDocument()
    expect(screen.getByText('Moderate')).toBeInTheDocument()
  })
})
