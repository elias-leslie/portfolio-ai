'use client'

import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { useDecisionBoard } from '../useDecisionBoard'

/**
 * Every raw input below CONTRADICTS the backend-owned summary fields on
 * purpose: if the hook ever re-derives allocation, month comparison, due-soon
 * totals, the cushion, or safe-to-spend from raw accounts/trend/commitments,
 * these tests fail.
 */
const dashboard = {
  generatedAt: '2026-06-01T00:00:00Z',
  overview: {
    investedAssets: 0,
    retirementAssets: 0,
    taxableAssets: 0,
    // Raw cash math would say 99999 - cushion - bills; the backend says 321.
    cashReserve: 99999,
    totalTrackedAssets: 0,
    liabilitiesTotal: 0,
    netWorth: 0,
    netWorthStatus: 'current',
    netWorthDetail: 'Current.',
    trackedAccountCount: 1,
    needsRefreshCount: 0,
    candidateAccountCount: 0,
    gapCount: 0,
    inboxCount: 0,
    coverageMonths: 6,
    lastTransactionDate: '2026-05-30',
    visibilityScore: 90,
    visibilityLabel: 'Strong',
    monthlySpendStatus: 'current',
    monthlySpendDetail: 'Current.',
    nextBestAction: 'None.',
    // Backend-owned allocation: a group no raw account has.
    assetAllocation: [{ assetGroup: 'real_estate', totalValue: 777 }],
  },
  profile: {
    id: 'profile-1',
    householdName: 'Household',
    monthlyNetIncomeTarget: 9000,
    // Old client math used this for the cushion; backend says 4321.
    monthlyEssentialTarget: 5000,
    monthlyDiscretionaryTarget: 1500,
    monthlySavingsTarget: 1500,
    targetRetirementAge: 60,
    targetRetirementSpend: 6000,
    notes: null,
    createdAt: '2026-06-01T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
  budgetSnapshot: {
    status: 'on_track',
    summary: 'On track.',
    monthlyIncomeTarget: 9000,
    monthlyPlanTotal: 8000,
    monthlyPlanSource: 'household_profile_targets',
    monthlyPlanSourceLabel: 'Household profile targets',
    essentialTarget: 5000,
    discretionaryTarget: 1500,
    savingsTarget: 1500,
    actualMonthlySpend: 7000,
    actualEssentialMonthlySpend: 4800,
    actualDiscretionaryMonthlySpend: 1400,
    monthToDateSpend: 3000,
    monthToDatePlan: 3200,
    paceStatus: 'on_track',
    paceDetail: 'On track.',
    planIsPartial: false,
    missingPlanComponents: [],
    // Old client math min()'d these in; backend already did.
    remainingCashAfterPlan: 12,
    discretionaryHeadroom: 34,
    safeToSpend: 321,
    safeToSpendConstraint: 'cash_after_commitments' as const,
    dueSoonBillsTotal: 222,
    operatingCushion: 4321,
    affordability: {
      freeToSpend: 321,
      cashOnHand: 9000,
      billsDue: 222,
      billsDueThrough: '2026-09-06',
      remainingEssentials: 2457,
      essentialsBasis:
        '1,864 of the 4,321 essentials baseline is covered so far in August.',
      committedFunds: 0,
      cardBalances: 6000,
      missingInputs: [],
    },
  },
  // Raw account would put 99999 of cash in play; allocation must ignore it.
  accounts: [
    {
      id: 'account-1',
      label: 'Checking',
      assetGroup: 'cash',
      currentValue: 99999,
    },
    {
      id: 'account-2',
      label: 'Rental',
      assetGroup: 'real_estate',
      currentValue: 1,
    },
  ],
  inbox: [],
  jennyBrief: { headline: 'Jenny', body: 'Body', prompts: [] },
  reports: {
    executive: {
      headline: 'Ready',
      summary: 'Summary',
      averageMonthlySpend: 7000,
      averageMonthlyEssentials: 4800,
      averageMonthlyDiscretionary: 1400,
      recent30DaySpend: 6900,
      recurringMerchantCount: 1,
      trackedExpenseCount: 10,
      coverageMonths: 6,
    },
    // Unsorted and 7 entries: the hook must NOT sort or slice to top-6.
    categoryBreakdown: ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'].map(
      (category, index) => ({
        category,
        essentiality: 'mixed',
        monthlyAverage: index + 1,
        shareOfSpend: 0.1,
        totalSpend: [10, 90, 30, 70, 50, 20, 60][index],
      }),
    ),
    merchantHighlights: [],
    priceInsights: [],
    // Trend implies a -5000 swing; the backend comparison says +123.
    monthlySpendTrend: [
      { month: '2026-04', totalSpend: 9000, transactionCount: 10 },
      { month: '2026-05', totalSpend: 4000, transactionCount: 10 },
    ],
    monthComparison: {
      latestMonth: '2026-05',
      previousMonth: '2026-04',
      latestTotal: 4000,
      previousTotal: 9000,
      change: 123,
      changePct: 1.4,
    },
    recentTransactions: [],
  },
  // Sums to 9999 inside 14 days; backend says 222.
  recurringCommitments: [
    {
      merchant: 'Rent Co',
      category: 'Bills',
      cadence: 'monthly',
      averageAmount: 9999,
      annualizedCost: 119988,
      lastSeen: '2026-05-30',
      nextExpected: '2026-06-05',
      daysUntilDue: 4,
      dueStatus: 'due_soon',
      dueConfidence: 0.9,
      commitmentType: 'bill',
    },
  ],
} as unknown as HouseholdFinanceDashboard

describe('useDecisionBoard', () => {
  it('renders backend-owned numbers verbatim instead of re-deriving them', () => {
    const { result } = renderHook(() => useDecisionBoard(dashboard))

    expect(result.current.allocationData).toEqual([
      { assetGroup: 'real_estate', label: 'Real Estate', value: 777 },
    ])
    expect(result.current.categoryData).toBe(
      dashboard.reports.categoryBreakdown,
    )
    expect(result.current.monthComparison).toBe(
      dashboard.reports.monthComparison,
    )
    expect(result.current.monthComparison?.change).toBe(123)
    expect(result.current.dueSoonTotal).toBe(222)
    expect(result.current.operatingCushion).toBe(4321)
    expect(result.current.weekendSpendAllowance).toBe(321)
    // Never "safe". The figure is an estimate about a month that has not
    // finished, and a green badge over a number the card itself disclaims was
    // the most dangerous element on the page.
    expect(result.current.safeSpendStatus).toBe('estimate')
    expect(result.current.safeSpendBindingLabel).toBe(
      'visible cash after bills due, the rest of the month\u2019s essentials and card balances',
    )
  })

  it('leaves recurring purchases out of the recurring bills list', () => {
    // A merchant the household visits on a rhythm owes nothing on a date. The
    // reference case is the Airbnb stay that billed weekly for a fortnight and
    // was read as the household's largest recurring bill.
    const withVacation = {
      ...dashboard,
      recurringCommitments: [
        ...dashboard.recurringCommitments,
        {
          merchant: 'Airbnb',
          category: 'Travel',
          cadence: 'likely weekly',
          averageAmount: 744,
          annualizedCost: 38688,
          lastSeen: '2026-06-30',
          nextExpected: '2026-06-07',
          daysUntilDue: 1,
          dueStatus: 'due_soon',
          dueConfidence: 0.7,
          commitmentType: 'recurring_purchase',
          evidence: null,
        },
      ],
    } as unknown as HouseholdFinanceDashboard

    const { result } = renderHook(() => useDecisionBoard(withVacation))

    expect(
      result.current.dueSoonCommitments.map(
        (commitment) => commitment.merchant,
      ),
    ).toEqual(['Rent Co'])
  })

  it('keeps the drilldown filter on raw accounts for the selected backend group', () => {
    const { result } = renderHook(() => useDecisionBoard(dashboard))

    expect(result.current.selectedAssetGroup).toBe('real_estate')
    expect(
      result.current.selectedAccounts.map((account) => account.id),
    ).toEqual(['account-2'])
  })

  it('words the one constraint the figure can have, and nothing else', () => {
    // There used to be three, and the one that usually won was `plan_residual`:
    // monthly income target minus monthly plan total, which is arithmetic on two
    // assumptions rather than on cash. It is gone.
    const withConstraint = (
      constraint: HouseholdFinanceDashboard['budgetSnapshot']['safeToSpendConstraint'],
    ) =>
      ({
        ...dashboard,
        budgetSnapshot: {
          ...dashboard.budgetSnapshot,
          safeToSpendConstraint: constraint,
        },
      }) as HouseholdFinanceDashboard

    const cash = renderHook(() =>
      useDecisionBoard(withConstraint('cash_after_commitments')),
    )
    expect(cash.result.current.safeSpendBindingLabel).toBe(
      'visible cash after bills due, the rest of the month\u2019s essentials and card balances',
    )
    const none = renderHook(() => useDecisionBoard(withConstraint(null)))
    expect(none.result.current.safeSpendBindingLabel).toBeNull()
  })

  it('treats a null backend safe-to-spend as unanswered, not zero', () => {
    const nullSafeToSpend = {
      ...dashboard,
      budgetSnapshot: {
        ...dashboard.budgetSnapshot,
        safeToSpend: null,
        safeToSpendConstraint: null,
        dueSoonBillsTotal: null,
      },
    } as HouseholdFinanceDashboard
    const { result } = renderHook(() => useDecisionBoard(nullSafeToSpend))

    expect(result.current.weekendSpendAllowance).toBeNull()
    expect(result.current.safeSpendStatus).toBe('mixed')
    expect(result.current.safeSpendBindingLabel).toBeNull()
    expect(result.current.dueSoonTotal).toBeNull()
    expect(
      result.current.whyShortDrivers.some((driver) =>
        driver.includes('recurring bills'),
      ),
    ).toBe(false)
  })
})
