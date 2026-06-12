import { describe, expect, it } from 'vitest'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import { buildLevers, trimRateForCategory } from '../lever-helpers'

function category(overrides = {}) {
  return {
    category: 'Retail',
    essentiality: 'discretionary',
    totalSpend: 3600,
    averageMonthlySpend: 1200,
    shareOfSpend: 0.3,
    transactionCount: 22,
    ...overrides,
  }
}

function priceSignal(
  overrides: Partial<HouseholdPriceInsight> = {},
): HouseholdPriceInsight {
  return {
    merchant: 'Walmart',
    itemName: 'Olive Oil',
    signalType: 'unit_price_up',
    latestPrice: 14.0,
    previousPrice: 11.5,
    priceChange: 2.5,
    priceChangePct: 21,
    latestDate: '2026-03-15',
    previousDate: '2026-01-10',
    unitPriceChangePct: 18,
    shrinkflationFlag: false,
    confidence: 0.8,
    recommendation: 'Compare equivalent pack sizes before reordering.',
    ...overrides,
  }
}

describe('lever-helpers', () => {
  it('caps the lever list at four, ranked by monthly savings', () => {
    const levers = buildLevers({
      subscriptionCategory: category({
        category: 'Subscriptions',
        averageMonthlySpend: 300,
      }),
      topDiscretionaryCategory: category({ averageMonthlySpend: 1200 }),
      topDiscretionaryMerchant: {
        merchant: 'Amazon',
        totalSpend: 600,
        transactionCount: 4,
        category: 'Retail',
        essentiality: 'discretionary',
      },
      topThreeShare: 0.2,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: null,
    })

    expect(levers.length).toBeLessThanOrEqual(4)
    // Retail category (1200 * 0.12 = 144) outranks the subscription sweep (60).
    expect(levers[0].id).toBe('category')
  })

  it('flags a merchant lever that overlaps its category lever as non-additive', () => {
    const levers = buildLevers({
      subscriptionCategory: null,
      topDiscretionaryCategory: category({ category: 'Retail' }),
      topDiscretionaryMerchant: {
        merchant: 'Amazon',
        totalSpend: 600,
        transactionCount: 4,
        category: 'Retail',
        essentiality: 'discretionary',
      },
      topThreeShare: 0.2,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: null,
    })

    const merchantLever = levers.find((lever) => lever.id === 'merchant')
    expect(merchantLever?.note).toMatch(/not additive/i)
  })

  it('uses essentiality-based trim rates', () => {
    expect(trimRateForCategory('Subscriptions', 'discretionary')).toBe(0.2)
    expect(trimRateForCategory('Unmapped', 'discretionary')).toBe(0.1)
    expect(trimRateForCategory('Unmapped', 'essential')).toBe(0)
  })

  it('exposes the modeled trimRate on every built lever', () => {
    const subscriptionAndCategoryLevers = buildLevers({
      subscriptionCategory: category({
        category: 'Subscriptions',
        averageMonthlySpend: 300,
      }),
      topDiscretionaryCategory: category({ averageMonthlySpend: 1200 }),
      topDiscretionaryMerchant: {
        merchant: 'Amazon',
        totalSpend: 600,
        transactionCount: 4,
        category: 'Dining',
        essentiality: 'discretionary',
      },
      topThreeShare: 0.2,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: null,
    })
    const byId = new Map(
      subscriptionAndCategoryLevers.map((lever) => [lever.id, lever]),
    )
    expect(byId.get('subscriptions')?.trimRate).toBe(0.2)
    // Retail category rate comes from trimRateForCategory.
    expect(byId.get('category')?.trimRate).toBe(0.12)
    expect(byId.get('merchant')?.trimRate).toBe(0.15)

    const signalLevers = buildLevers({
      subscriptionCategory: null,
      topDiscretionaryCategory: null,
      topDiscretionaryMerchant: null,
      topThreeShare: 0.4,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: priceSignal(),
    })
    const signalById = new Map(signalLevers.map((lever) => [lever.id, lever]))
    expect(signalById.get('concentration')?.trimRate).toBe(0.05)
    expect(signalById.get('price-signal')?.trimRate).toBe(0.02)
  })

  it('truncates long price-signal item names in the lever title', () => {
    // 47 chars, a space, then 53 more — the 48-char slice ends on the space,
    // which trimEnd removes before the ellipsis lands.
    const longName = `${'X'.repeat(47)} ${'Y'.repeat(53)}`
    const levers = buildLevers({
      subscriptionCategory: null,
      topDiscretionaryCategory: null,
      topDiscretionaryMerchant: null,
      topThreeShare: 0,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: priceSignal({ itemName: longName }),
    })

    const priceLever = levers.find((lever) => lever.id === 'price-signal')
    expect(priceLever?.title).toBe(
      `${'X'.repeat(47)}… price drift needs a check`,
    )
  })

  it('keeps short price-signal item names untouched', () => {
    const levers = buildLevers({
      subscriptionCategory: null,
      topDiscretionaryCategory: null,
      topDiscretionaryMerchant: null,
      topThreeShare: 0,
      averageMonthlySpend: 2000,
      coverageMonths: 3,
      bestPriceSignal: priceSignal({ itemName: 'Olive Oil' }),
    })

    expect(levers[0]?.title).toBe('Olive Oil price drift needs a check')
  })
})
