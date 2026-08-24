import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { buildHouseholdDashboard } from '@/app/__tests__/householdDashboardFixture'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { useDecisionBoard } from '../useDecisionBoard'

/**
 * The split used to show $3,217 / $4,074 against $8,103 of average monthly
 * spend: two shares summing to 90%, with the $811 `mixed` bucket invisible.
 * After task 1.6 the hidden bucket is far larger -- Household alone is a
 * quarter of spend -- so the three have to account for all of it.
 */
function withSplit(
  essentials: number,
  discretionary: number,
  mixed: number,
): HouseholdFinanceDashboard {
  const base = buildHouseholdDashboard()
  return {
    ...base,
    // The shared fixture is built for panels that never read allocation.
    overview: { ...base.overview, assetAllocation: [] },
    reports: {
      ...base.reports,
      executive: {
        ...base.reports.executive,
        averageMonthlySpend: essentials + discretionary + mixed,
        averageMonthlyEssentials: essentials,
        averageMonthlyDiscretionary: discretionary,
        averageMonthlyMixed: mixed,
      },
      categoryBreakdown: [
        {
          category: 'Groceries',
          essentiality: 'essential',
          monthlyAverage: essentials,
          shareOfSpend: 0,
          totalSpend: essentials,
        },
        {
          category: 'Retail',
          essentiality: 'discretionary',
          monthlyAverage: discretionary,
          shareOfSpend: 0,
          totalSpend: discretionary,
        },
        {
          category: 'Household',
          essentiality: 'mixed',
          monthlyAverage: mixed,
          shareOfSpend: 0,
          totalSpend: mixed,
        },
      ],
    },
  } as unknown as HouseholdFinanceDashboard
}

describe('needs / wants / mixed', () => {
  it('accounts for every tracked dollar rather than 90% of them', () => {
    const { result } = renderHook(() =>
      useDecisionBoard(withSplit(3217, 4074, 811)),
    )

    expect(
      result.current.needsAmount +
        result.current.wantsAmount +
        result.current.mixedAmount,
    ).toBe(8102)
    const shares =
      (result.current.needsShare ?? 0) +
      (result.current.wantsShare ?? 0) +
      (result.current.mixedShare ?? 0)
    expect(shares).toBeCloseTo(100, 6)
  })

  it('puts a mixed category in the mixed bucket, not in neither', () => {
    const { result } = renderHook(() =>
      useDecisionBoard(withSplit(3217, 4074, 811)),
    )

    expect(result.current.needCategories.map((c) => c.category)).toEqual([
      'Groceries',
    ])
    expect(result.current.wantCategories.map((c) => c.category)).toEqual([
      'Retail',
    ])
    expect(result.current.mixedCategories.map((c) => c.category)).toEqual([
      'Household',
    ])
  })

  it('still sums to 100% when nothing is mixed', () => {
    const { result } = renderHook(() =>
      useDecisionBoard(withSplit(3000, 2000, 0)),
    )

    expect(result.current.mixedAmount).toBe(0)
    expect(result.current.mixedShare).toBe(0)
    expect(
      (result.current.needsShare ?? 0) + (result.current.wantsShare ?? 0),
    ).toBeCloseTo(100, 6)
  })

  it('reports no shares at all rather than a false split with no spend', () => {
    const { result } = renderHook(() => useDecisionBoard(withSplit(0, 0, 0)))

    expect(result.current.needsShare).toBeNull()
    expect(result.current.wantsShare).toBeNull()
    expect(result.current.mixedShare).toBeNull()
  })
})
