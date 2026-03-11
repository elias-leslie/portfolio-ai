import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HouseholdPlanningPanels } from '../HouseholdPlanningPanels'

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
          actionItems: [],
          opportunities: [],
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
          questions: [],
          jennyBrief: {
            headline: 'Jenny',
            body: 'Body',
            prompts: [],
          },
        }}
      />,
    )

    expect(screen.getByText(/no starter lanes yet/i)).toBeInTheDocument()
    expect(screen.getByText(/jenny has not identified a strong retirement edge yet/i)).toBeInTheDocument()
    expect(screen.getByText(/contribution rate is below target/i)).toBeInTheDocument()
    expect(screen.getByText(/jenny does not have a next-step recommendation yet/i)).toBeInTheDocument()
    expect(screen.getByText(/retirement scenarios will appear once jenny has enough spending/i)).toBeInTheDocument()
  })
})
