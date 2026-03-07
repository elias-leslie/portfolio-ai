import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchPortfolio } from './portfolio'

describe('portfolio api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('requests the portfolio endpoint without a trailing slash', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        positions: [],
        cash_balance_total: 0,
        total_value: 0,
        total_cost_basis: 0,
        total_gain: 0,
        total_gain_pct: 0,
      }),
    }) as unknown as typeof fetch

    await fetchPortfolio()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/portfolio',
      expect.objectContaining({
        method: 'GET',
      }),
    )
  })
})
