import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { JennyMoneyBoard } from '../JennyMoneyBoard'

describe('JennyMoneyBoard', () => {
  it('shows summary telemetry for prompts, needs, resolved values, and evidence coverage', () => {
    render(
      <JennyMoneyBoard
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
          resolvedValues: [
            {
              fieldName: 'monthly_net_income_target',
              label: 'Monthly income',
              value: '$8,000',
              confidence: 0.8,
              status: 'resolved',
              source: 'document',
              rationale: null,
              question: null,
            },
          ],
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
            monthToDateSpend: 2100,
            monthToDatePlan: 2200,
            paceStatus: 'on_track',
            paceDetail: 'Month-to-date spend is tracking close to the plan.',
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
          jennyNeeds: [
            {
              id: 'need-1',
              needType: 'confirm',
              title: 'Tighten grocery lane',
              detail: 'Groceries are drifting above plan.',
              priority: 'high',
              status: 'unsatisfied',
              recurrence: 'one_time',
              satisfactionDetail: null,
              actionHref: null,
              relatedQuestionId: null,
              fieldName: null,
              questionFormat: null,
              options: null,
            },
          ],
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
            prompts: ['Confirm take-home pay.'],
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
            categoryBreakdown: [],
            merchantHighlights: [],
            monthlySpendTrend: [],
            recentTransactions: [],
          },
        }}
      />,
    )

    expect(screen.getByText('Prompts ready')).toBeInTheDocument()
    expect(screen.getByText('Open needs')).toBeInTheDocument()
    expect(screen.getByText('Evidence coverage')).toBeInTheDocument()
    expect(screen.getByText(/3 months of normalized spend evidence\./i)).toBeInTheDocument()
    expect(screen.getByText(/confirm take-home pay\./i)).toBeInTheDocument()
    expect(screen.getByText(/what jenny needs next/i)).toBeInTheDocument()
    expect(screen.getByText(/open questions/i)).toBeInTheDocument()
  })

  it('shows empty-state messages when prompts, needs, resolved values, and evidence coverage are zero', () => {
    render(
      <JennyMoneyBoard
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
            monthToDateSpend: 2100,
            monthToDatePlan: 2200,
            paceStatus: 'on_track',
            paceDetail: 'Month-to-date spend is tracking close to the plan.',
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
          jennyNeeds: [],
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
              coverageMonths: 0,
            },
            categoryBreakdown: [],
            merchantHighlights: [],
            monthlySpendTrend: [],
            recentTransactions: [],
          },
        }}
      />,
    )

    expect(screen.getByText(/no follow-up prompts right now\./i)).toBeInTheDocument()
    expect(screen.getByText(/no unresolved needs are currently blocking the system\./i)).toBeInTheDocument()
    expect(screen.getByText(/Jenny does not need a follow-up prompt right now\./i)).toBeInTheDocument()
    expect(screen.getByText(/upload statements to give jenny real household evidence/i)).toBeInTheDocument()
  })
})
