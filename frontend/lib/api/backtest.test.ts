import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startBacktest } from './backtest'

describe('backtest api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('starts backtests using the backend contract', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        run_id: 'run-1',
        task_id: 'task-1',
        status: 'running',
        message: 'Backtest started for AAPL',
      }),
    }) as unknown as typeof fetch

    const result = await startBacktest({
      symbol: 'AAPL',
      strategy: 'enhanced',
      startDate: '2025-01-01',
      endDate: '2025-02-01',
      parameters: {
        stopLossAtrMultiplier: 2,
        maxHoldingDays: 30,
        targetProfitPct: 15,
        minConfirmations: 5,
      },
    })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/backtest/run',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          symbol: 'AAPL',
          strategy: 'enhanced',
          start_date: '2025-01-01',
          end_date: '2025-02-01',
          parameters: {
            stop_loss_atr_multiplier: 2,
            max_holding_days: 30,
            target_profit_pct: 15,
            min_confirmations: 5,
          },
        }),
      }),
    )
    expect(result).toEqual({
      runId: 'run-1',
      taskId: 'task-1',
      status: 'running',
      message: 'Backtest started for AAPL',
    })
  })
})
