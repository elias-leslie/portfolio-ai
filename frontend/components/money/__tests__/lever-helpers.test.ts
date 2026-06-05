import { describe, expect, it } from 'vitest'
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
})
