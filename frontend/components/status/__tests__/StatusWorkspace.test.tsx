import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StatusWorkspace } from '../StatusWorkspace'

const useDetailedHealthMock = vi.fn()
const useMarketStatusMock = vi.fn()
const useNewsHealthMock = vi.fn()

vi.mock('@/lib/hooks/useHealth', () => ({
  useDetailedHealth: () => useDetailedHealthMock(),
}))

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketStatus: () => useMarketStatusMock(),
}))

vi.mock('@/lib/hooks/useNewsHealth', () => ({
  useNewsHealth: () => useNewsHealthMock(),
}))

function createQueryResult<T>(overrides: Partial<Record<string, unknown>> & { data?: T } = {}) {
  return {
    data: undefined,
    error: null,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
    ...overrides,
  }
}

describe('StatusWorkspace', () => {
  it('keeps the workspace visible when one live signal fails', () => {
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          checks: {
            database: {
              status: 'ok',
              message: null,
              latencyMs: 12,
            },
          },
          sources: {},
          services: {
            portfolioBackend: {
              serviceName: 'portfolio-backend',
              status: 'running',
              message: '',
            },
          },
          apiQuotas: [],
          recentRemediations: [],
          workflowHealth: {
            status: 'healthy',
            successRate: 100,
            totalWorkflows24H: 1,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
          },
          dataFreshnessStatus: {
            status: 'success',
            lastCheck: '2026-03-10T22:00:00.000000Z',
            fresh: 4,
            stale: 1,
            critical: 0,
          },
          watchlistStats: {
            itemsWithScores: 5,
            lastRefresh: '2026-03-10T23:14:01.484006Z',
          },
        },
      }),
    )

    useMarketStatusMock.mockReturnValue(
      createQueryResult({
        error: new Error('timeout'),
      }),
    )

    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          headlines24H: 1916,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('Partial snapshot')).toBeInTheDocument()
    expect(screen.getByText('System Checks')).toBeInTheDocument()
    expect(screen.queryByText('Failed to load the operations snapshot.')).not.toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('12ms')).toBeInTheDocument()
    expect(screen.getByText(/100.0% success rate over 1 workflows/i)).toBeInTheDocument()
  })

  it('shows the fatal error state only when every live signal fails', () => {
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        error: new Error('health down'),
      }),
    )
    useMarketStatusMock.mockReturnValue(
      createQueryResult({
        error: new Error('market down'),
      }),
    )
    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        error: new Error('news down'),
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('Failed to load the operations snapshot.')).toBeInTheDocument()
  })
})
