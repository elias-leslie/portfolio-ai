import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HouseholdReportsPanel } from '../HouseholdReportsPanel'

describe('HouseholdReportsPanel', () => {
  it('renders the executive report and merchant insights', () => {
    render(
      <HouseholdReportsPanel
        dashboard={{
          generatedAt: '2026-03-09T00:00:00Z',
          overview: {
            investedAssets: 0,
            retirementAssets: 0,
            taxableAssets: 0,
            cashReserve: 0,
            totalTrackedAssets: 0,
            visibilityScore: 72,
            visibilityLabel: 'Good',
            nextBestAction: 'Upload one more bank statement.',
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
            createdAt: '2026-03-09T00:00:00Z',
            updatedAt: '2026-03-09T00:00:00Z',
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
            actualMonthlySpend: 4250,
            actualEssentialMonthlySpend: 2600,
            actualDiscretionaryMonthlySpend: 1650,
            remainingCashAfterPlan: null,
            discretionaryHeadroom: null,
          },
          retirementPreparedness: {
            status: 'baseline_visible',
            summary: 'Ready',
            retirementAccountShare: 42,
            strengths: [],
            blockers: [],
            nextSteps: [],
          },
          actionItems: [],
          opportunities: [],
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
          reports: {
            executive: {
              headline: 'Jenny now has a real household spending ledger to work from.',
              summary: 'The report is based on actual tracked expense evidence.',
              averageMonthlySpend: 4250,
              averageMonthlyEssentials: 2600,
              averageMonthlyDiscretionary: 1650,
              recent30DaySpend: 3980,
              recurringMerchantCount: 7,
              trackedExpenseCount: 58,
              coverageMonths: 3,
            },
            categoryBreakdown: [
              {
                category: 'Groceries',
                essentiality: 'essential',
                monthlyAverage: 980,
                shareOfSpend: 0.23,
                totalSpend: 2940,
              },
            ],
            merchantHighlights: [
              {
                merchant: 'Walmart',
                category: 'Groceries',
                totalSpend: 614,
                averageTicket: 153.5,
                transactionCount: 4,
                cadence: 'weekly',
                recommendation: 'Treat Walmart as a core essentials channel and compare it against Publix.',
              },
            ],
            monthlySpendTrend: [
              {
                month: '2026-01',
                totalSpend: 4100,
                transactionCount: 17,
              },
            ],
            recentTransactions: [
              {
                date: '2026-01-22T00:00:00Z',
                merchant: 'Walmart',
                description: 'WM SUPERCENTER #5831 LARGO FL',
                amount: 164.39,
                category: 'Groceries',
                essentiality: 'essential',
                accountLabel: 'Chase Amazon Prime',
              },
            ],
          },
        }}
      />,
    )

    expect(screen.getByText(/household cash-flow report/i)).toBeInTheDocument()
    expect(screen.getByText(/merchant intelligence/i)).toBeInTheDocument()
    expect(screen.getAllByText(/^Walmart$/i)).toHaveLength(2)
    expect(screen.getByText(/core essentials channel/i)).toBeInTheDocument()
    expect(screen.getByText(/\$4,250/)).toBeInTheDocument()
  })
})
