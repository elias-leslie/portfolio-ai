import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

function createQueryResult<T>(
  overrides: Partial<Record<string, unknown>> & { data?: T } = {},
) {
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
    window.history.replaceState({}, '', '/status')
  })

  it('shows empty-state copy for cards with no live rows and keeps zero latency visible', async () => {
    const user = userEvent.setup()
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          version: '2026.03.10',
          uptimeSeconds: 14400,
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
          cacheStats: {
            totalCached: 12,
            cacheAgeMinutes: 90,
          },
          recentRemediations: [],
          workflowHealth: {
            status: 'healthy',
            successRate: 100,
            totalWorkflows24H: 1,
            successfulWorkflows: 1,
            failedWorkflows: 0,
            blockedWorkflows: 0,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: {},
          },
          dataFreshnessStatus: {
            status: 'success',
            lastCheck: '2026-03-10T22:00:00.000000Z',
            fresh: 4,
            stale: 0,
            critical: 0,
            remediationsTriggered: 0,
          },
          watchlistStats: {
            totalItems: 8,
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
          status: 'down',
          message:
            'No fresh news in 24h. No successful news refresh is recorded.',
          headlines24H: 0,
          fallbackHeadlines24H: 0,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: null,
          watchlistLastRefreshedAt: null,
          latestRefreshedAt: null,
          latestRefreshAgeHours: null,
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('0ms')).toBeInTheDocument()
    expect(screen.getByText('62.5%')).toBeInTheDocument()
    expect(screen.getByText('5 of 8 symbols scored')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('4.0h')).toBeInTheDocument()
    expect(screen.getByText('Version 2026.03.10')).toBeInTheDocument()
    expect(screen.getByText('Cached prices 12 · age 1.5h')).toBeInTheDocument()
    expect(
      screen.getByText(
        'No fresh news in 24h. No successful news refresh is recorded.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'No app-service status entries are available right now.',
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sources/i }))
    expect(
      screen.getByText('No provider health checks yet'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'No data-source health signals are available right now.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('No news-source diagnostics are available right now.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('No API-limit data is available right now.'),
    ).toBeInTheDocument()
  })

  it('shows recent vendor activity when runtime success timestamps are unavailable', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-10T23:30:00.000Z'))
    window.history.replaceState({}, '', '/status?tab=sources')

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
            successfulWorkflows: 1,
            failedWorkflows: 0,
            blockedWorkflows: 0,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: {},
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

  it('uses calculated news health when headlines are stale or empty', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-04-10T16:00:00.000Z'))
    window.history.replaceState({}, '', '/status?tab=calendar')

    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-04-10T16:00:00.000Z',
          checks: {},
          sources: {},
          services: {},
          apiQuotas: [],
          recentRemediations: [],
          workflowHealth: null,
          dataFreshnessStatus: {
            status: 'critical',
            lastCheck: '2026-04-10T15:00:00.000000Z',
            fresh: 8,
            stale: 1,
            critical: 1,
          },
          watchlistStats: {
            totalItems: 8,
            itemsWithScores: 8,
            lastRefresh: '2026-04-10T15:30:00.000Z',
          },
        },
      }),
    )
    useMarketStatusMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'open',
          currentTimeEt: '12:00 PM ET',
          expectedDataDate: '2026-04-09',
          lastTradingDay: '2026-04-10',
          nextTradingDay: '2026-04-13',
          isHoliday: false,
          isEarlyClose: false,
        },
      }),
    )
    useNewsHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'down',
          message:
            'No fresh news in 24h. Latest refresh 30d ago; expected every 6h.',
          headlines24H: 0,
          fallbackHeadlines24H: 0,
          fallbackRate24H: 0,
          marketLastRefreshedAt: '2026-03-11T13:25:00.173907Z',
          watchlistLastRefreshedAt: '2026-03-11T13:25:11.593648Z',
          latestRefreshedAt: '2026-03-11T13:25:11.593648Z',
          latestRefreshAgeHours: 722.58,
          vendors: {},
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(
      screen.getByText(
        'No fresh news in 24h. Latest refresh 30d ago; expected every 6h.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('News Feed')).toBeInTheDocument()
    expect(screen.getByText('Down')).toBeInTheDocument()
    expect(
      screen.queryByText(/primary news source handled/i),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(/backup news source stepped in/i),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Daily Data Through')).toBeInTheDocument()
    expect(
      screen.getByText('Current trading day 2026-04-10'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Expected Market Date')).not.toBeInTheDocument()
  })

  it('describes overdue automation without pretending unfinished runs failed the success rate', () => {
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
            status: 'warning',
            successRate: 0,
            totalWorkflows24H: 2,
            successfulWorkflows: 0,
            failedWorkflows: 0,
            blockedWorkflows: 2,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: { jenny_daily_operator: 2 },
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

    expect(screen.getByText('0 failed · 2 stuck')).toBeInTheDocument()
  })

  it('shows resolved remediation history without duplicating cards', async () => {
    const user = userEvent.setup()
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
              resolved: true,
              resolvedAt: '2026-03-10T23:00:00.000000Z',
            },
          ],
          workflowHealth: {
            status: 'healthy',
            successRate: 100,
            totalWorkflows24H: 1,
            successfulWorkflows: 1,
            failedWorkflows: 0,
            blockedWorkflows: 0,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: {},
          },
          dataFreshnessStatus: {
            status: 'success',
            lastCheck: '2026-03-10T23:00:00.000000Z',
            fresh: 9,
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

    await user.click(screen.getByRole('button', { name: /automation/i }))
    expect(screen.getAllByText('technical_indicators')).toHaveLength(1)
    expect(screen.getByText('resolved')).toBeInTheDocument()
    expect(
      screen.getByText('This happened 2 times in the last 24h.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Cleared during the latest data-recency check at/i),
    ).toBeInTheDocument()
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
            successfulWorkflows: 1,
            failedWorkflows: 0,
            blockedWorkflows: 0,
            lastSuccessfulType: 'daily_operator',
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: {},
          },
          dataFreshnessStatus: {
            status: 'success',
            lastCheck: '2026-03-10T22:00:00.000000Z',
            fresh: 4,
            stale: 1,
            critical: 0,
            remediationsTriggered: 1,
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
    expect(
      screen.queryByText('Failed to load the operations snapshot.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('12ms')).toBeInTheDocument()
    expect(
      screen.getByText(
        /completed automation runs finished successfully in the last 24h/i,
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/0 failed · 0 stuck/i)).toBeInTheDocument()
    expect(
      screen.getByText(/last successful automation: daily operator/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/auto-fixes ran 1 time in the latest check/i),
    ).toBeInTheDocument()
  })

  it('renders partial status while the slower health query is still loading', async () => {
    const user = userEvent.setup()
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: undefined,
        isLoading: true,
        isFetching: true,
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
          status: 'healthy',
          message:
            '737 headlines refreshed in 24h. Article quality scoring is running in heuristic mode.',
          headlines24H: 737,
          fallbackHeadlines24H: 0,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
          watchlistLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
          latestRefreshedAt: '2026-03-10T23:25:00.160242Z',
          latestRefreshAgeHours: 0.08,
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(
      screen.queryByText('Collecting live operating signals...'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Loading system health...')).toBeInTheDocument()
    expect(screen.getAllByText('Market Closed').length).toBeGreaterThan(0)
    expect(screen.getByText('737')).toBeInTheDocument()
    expect(
      screen.getByText(
        /737 headlines refreshed in 24h. Article quality scoring is running in heuristic mode./i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Loading core connection checks...'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Loading runtime and data-recency checks...'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sources/i }))
    expect(
      screen.getByText('Loading provider health signals...'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Loading market timing signals...'),
    ).not.toBeInTheDocument()
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

    expect(
      screen.getByText('Failed to load the operations snapshot.'),
    ).toBeInTheDocument()
  })

  it('refreshes all live status queries from the header action', async () => {
    const user = userEvent.setup()
    const healthRefetch = vi.fn()
    const marketRefetch = vi.fn()
    const newsRefetch = vi.fn()

    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        refetch: healthRefetch,
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
            successfulWorkflows: 1,
            failedWorkflows: 0,
            blockedWorkflows: 0,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: {},
            blockedByType: {},
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
            totalItems: 5,
            lastRefresh: '2026-03-10T23:14:01.484006Z',
          },
        },
      }),
    )
    useMarketStatusMock.mockReturnValue(
      createQueryResult({
        refetch: marketRefetch,
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
        refetch: newsRefetch,
        data: {
          headlines24H: 0,
          fallbackHeadlines24H: 0,
          fallbackRate24H: 0,
          vendors: {},
          marketLastRefreshedAt: null,
        },
      }),
    )

    render(<StatusWorkspace />)

    await user.click(screen.getByRole('button', { name: 'Refresh' }))

    expect(healthRefetch).toHaveBeenCalled()
    expect(marketRefetch).toHaveBeenCalled()
    expect(newsRefetch).toHaveBeenCalled()
  })

  it('surfaces source cooldown and vendor notes when present', async () => {
    const user = userEvent.setup()
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: '2026-03-10T23:26:56.894882+00:00',
          checks: {},
          sources: {
            alphavantage: {
              status: 'down',
              statusReason: 'Last good update is older than 24h.',
              lastSuccess: '2026-03-10T23:20:00.000Z',
              successRate: 62,
              avgLatencyMs: 240,
              rateLimitHits: 3,
              inCooldown: true,
              cooldownRemainingSeconds: 180,
            },
          },
          services: {},
          apiQuotas: [
            {
              sourceName: 'AlphaVantage',
              configured: true,
              estimatedCapacity: 500,
              rateLimit: '5/min',
              dailyLimit: '500/day',
            },
          ],
          recentRemediations: [],
          workflowHealth: {
            status: 'warning',
            successRate: 82,
            totalWorkflows24H: 11,
            successfulWorkflows: 9,
            failedWorkflows: 1,
            blockedWorkflows: 1,
            lastSuccessfulWorkflow: '2026-03-10T22:18:27.574496Z',
            failuresByType: { jenny_daily_operator: 1 },
            blockedByType: { check_all_data_freshness: 1 },
          },
          dataFreshnessStatus: {
            status: 'critical',
            lastCheck: '2026-03-10T22:00:00.000000Z',
            fresh: 4,
            stale: 1,
            critical: 1,
            message: '1 table overdue; 1 table getting old',
            error: 'One table was overdue.',
          },
          watchlistStats: {
            itemsWithScores: 5,
            totalItems: 5,
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
          status: 'healthy',
          message:
            '1916 headlines refreshed in 24h. 14 used backup sentiment scoring.',
          headlines24H: 1916,
          fallbackHeadlines24H: 14,
          fallbackRate24H: 0.7,
          marketLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
          watchlistLastRefreshedAt: '2026-03-10T23:25:00.160242Z',
          latestRefreshedAt: '2026-03-10T23:25:00.160242Z',
          latestRefreshAgeHours: 0.08,
          vendors: {
            polygon: {
              configured: true,
              enabled: true,
              active: false,
              lastAttemptAt: '2026-03-10T23:25:00.160242Z',
              lastSuccessAt: '2026-03-10T23:24:30.000Z',
              lastErrorAt: null,
              lastError: null,
              articlesLastFetch: 5,
              articlesLast24H: 1106,
              lastArticleAt: '2026-03-10T23:24:00.000Z',
              notes: 'Fallback engaged briefly during ingest.',
              reason: null,
            },
          },
        },
      }),
    )

    render(<StatusWorkspace />)

    expect(screen.getByText('Overdue')).toBeInTheDocument()
    expect(
      screen.getByText('1 table overdue; 1 table getting old'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/data recency issue: one table was overdue/i),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sources/i }))
    expect(screen.getByText('0/1 healthy')).toBeInTheDocument()
    expect(screen.getByText('1 feed needs review · 1 down')).toBeInTheDocument()
    expect(screen.getByText('Request success: 62.0%')).toBeInTheDocument()
    expect(
      screen.getByText('Why: Last good update is older than 24h.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/rate-limit hits: 3/i)).toBeInTheDocument()
    expect(screen.getByText(/pause remaining: 3m/i)).toBeInTheDocument()
    expect(
      screen.getByText(/1 of 1 data provider connected/i),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/last (good update|success):/i)).toHaveLength(2)
    expect(
      screen.getByText(/notes: fallback engaged briefly during ingest/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /1916 headlines refreshed in 24h. 14 used backup sentiment scoring/i,
      ),
    ).toBeInTheDocument()
  })

  it('uses explicit unavailable copy when status timestamps are missing', async () => {
    const user = userEvent.setup()
    useDetailedHealthMock.mockReturnValue(
      createQueryResult({
        data: {
          status: 'healthy',
          timestamp: null,
          checks: {},
          sources: {
            polygon: {
              status: 'degraded',
              statusReason: 'No successful fetch recorded.',
              lastSuccess: null,
              successRate: 25,
              avgLatencyMs: 1800,
            },
          },
          services: {},
          apiQuotas: [],
          recentRemediations: [],
          workflowHealth: {
            status: 'warning',
            successRate: 70,
            totalWorkflows24H: 10,
            successfulWorkflows: 7,
            failedWorkflows: 2,
            blockedWorkflows: 1,
            lastSuccessfulWorkflow: null,
            failuresByType: { jenny_daily_operator: 2 },
            blockedByType: { jenny_daily_operator: 1 },
          },
          dataFreshnessStatus: {
            status: 'warning',
            lastCheck: '2026-03-10T23:00:00.000000Z',
            fresh: 7,
            stale: 2,
            critical: 0,
          },
          watchlistStats: {
            itemsWithScores: 5,
            totalItems: 8,
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

    expect(screen.getByText('Update time unavailable')).toBeInTheDocument()
    expect(
      screen.getByText('No successful automation run recorded yet.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sources/i }))
    expect(
      screen.getByText('1 feed needs review · 1 degraded'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Why: No successful fetch recorded.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Last good update: No successful fetch recorded'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Updated Never/i)).not.toBeInTheDocument()
  })
})
