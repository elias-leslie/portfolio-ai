import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('shows empty-state copy for cards with no live rows and keeps zero latency visible', () => {
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          checks: {
            database: {
              status: 'ok',
              message: null,
              latencyMs: 0,
            },
          },
          sources: {},
          services: {},
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
            stale: 0,
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
        data: {
          status: 'closed',
          currentTimeEt: '6:00 PM ET',
          expectedDataDate: '2026-03-10',
          lastTradingDay: '2026-03-10',
          nextTradingDay: '2026-03-11',
          isHoliday: false,
          isEarlyClose: false,
        },
      }),
    )

    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          headlines24H: 0,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: null,
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('0ms')).toBeInTheDocument()
    expect(screen.getByText('No service status entries are available right now.')).toBeInTheDocument()
    expect(screen.getByText('No source health signals are available right now.')).toBeInTheDocument()
    expect(screen.getByText('No news vendor diagnostics are available right now.')).toBeInTheDocument()
    expect(screen.getByText('No API quota configuration is available right now.')).toBeInTheDocument()
  })

  it('shows recent vendor activity when runtime success timestamps are unavailable', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-10T23:30:00.000Z'))

    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          checks: {},
          sources: {},
          services: {},
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
            stale: 0,
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
        data: {
          status: 'after_hours',
          currentTimeEt: '6:30 PM ET',
          expectedDataDate: '2026-03-10',
          lastTradingDay: '2026-03-10',
          nextTradingDay: '2026-03-11',
          isHoliday: false,
          isEarlyClose: false,
        },
      }),
    )

    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          headlines24H: 1916,
          fallbackRate24H: 0,
          marketLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
          vendors: {
            polygon: {
              configured: true,
              enabled: true,
              active: true,
              lastAttemptAt: '2026-03-10T23:25:00.160242Z',
              lastSuccessAt: null,
              lastErrorAt: null,
              lastError: null,
              articlesLastFetch: 5,
              articlesLast24H: 1106,
              lastArticleAt: '2026-03-10T23:24:00.000Z',
              notes: null,
              reason: null,
            },
          },
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('Last activity: 6m ago')).toBeInTheDocument()
    expect(screen.queryByText('Last success: Never')).not.toBeInTheDocument()
  })

  it('shows remediation occurrence counts without duplicating cards', () => {
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          checks: {},
          sources: {},
          services: {},
          apiQuotas: [],
          recentRemediations: [
            {
              tableName: 'technical_indicators',
              triggeredAt: '2026-03-10T22:00:00.000Z',
              status: 'error',
              ageHours: 52,
              thresholdHours: 48,
              reason: 'age',
              occurrenceCount: 2,
            },
          ],
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
            stale: 0,
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
        data: {
          status: 'closed',
          currentTimeEt: '6:00 PM ET',
          expectedDataDate: '2026-03-10',
          lastTradingDay: '2026-03-10',
          nextTradingDay: '2026-03-11',
          isHoliday: false,
          isEarlyClose: false,
        },
      }),
    )

    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          headlines24H: 0,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: null,
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getAllByText('technical_indicators')).toHaveLength(1)
    expect(screen.getByText('Repeated 2 times in the last 24h.')).toBeInTheDocument()
  })

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
