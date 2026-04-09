import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { chatWithJenny, fetchPortfolio } from './portfolio'

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
      '/api/portfolio',
      expect.objectContaining({
        method: 'GET',
      }),
    )
  })

  it('posts a message to Jenny chat', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        reply: 'Jenny says AMD still looks constructive.',
        session_id: 'session-1',
        resolved_questions: [],
        updated_fields: [],
        referenced_symbols: ['AMD'],
      }),
    }) as unknown as typeof fetch

    await chatWithJenny({
      message: 'What do you think about AMD?',
      sessionId: null,
    })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/portfolio/jenny/chat',
      expect.objectContaining({
        method: 'POST',
      }),
    )
  })
})
