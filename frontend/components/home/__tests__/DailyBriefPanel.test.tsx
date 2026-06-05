import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DailyBriefPanel } from '../DailyBriefPanel'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdNetWorthTrendMock = vi.fn()
const useMarketStatusMock = vi.fn()
const usePortfolioAnalyticsMock = vi.fn()
const useMacroCurrentMock = vi.fn()
const useMacroConditionsMock = vi.fn()
const useTodayRefreshMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdNetWorthTrend: (args: { days: number }) =>
    useHouseholdNetWorthTrendMock(args),
}))

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketStatus: () => useMarketStatusMock(),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolioAnalytics: () => usePortfolioAnalyticsMock(),
}))

vi.mock('@/lib/hooks/useMacro', () => ({
  useMacroCurrent: () => useMacroCurrentMock(),
  useMacroConditions: () => useMacroConditionsMock(),
}))

vi.mock('@/lib/hooks/useTodayRefresh', () => ({
  useTodayRefresh: () => useTodayRefreshMock(),
}))

const macroSnapshot = {
  snapshotDate: '2026-05-28',
  computedAt: '2026-05-28T21:45:00Z',
  deploymentScore: 59,
  zone: 'REDUCED',
  coverage: 1,
  components: {
    vix: 88,
    term: 60,
    breadth: 54,
    credit: 80,
    putcall: 70,
    crowding: 32,
  },
  raw: {
    vixClose: 17,
    termSpreadBps: 49,
    breadthPct: 59,
    hySpread: 2.7,
    putCallRatio: 0.86,
    factorCrowdingCorr: 0.22,
  },
  weights: {
    vix: 0.2,
    term: 0.2,
    breadth: 0.2,
    credit: 0.2,
    putcall: 0.1,
    crowding: 0.1,
  },
  componentQuality: {},
}

const stressTrend = {
  key: 'stress',
  label: 'Stress',
  direction: 'worsening',
  tone: 'warning',
  delta: 7,
  changeLabel: '7D +7',
  summary: 'Reversed worse over 7D',
  windowDays: 7,
  latestDate: '2026-05-28',
  priorDate: '2026-05-21',
  reversal: true,
  reversalLabel: 'Reversed worse',
  sparkline: [44, 34, 41],
}

const calmTrend = {
  key: 'vix',
  label: 'VIX',
  direction: 'improving',
  tone: 'gain',
  delta: -3,
  changeLabel: '7D -3.00',
  summary: 'Improving over 7D',
  windowDays: 7,
  latestDate: '2026-05-28',
  priorDate: '2026-05-21',
  reversal: false,
  reversalLabel: null,
  sparkline: [18, 20, 17],
}

const conditions = {
  snapshotDate: '2026-05-28',
  computedAt: '2026-05-28T21:45:00Z',
  state: 'Caution',
  stressScore: 41,
  deploymentScore: 59,
  macroZone: 'REDUCED',
  coverage: 1,
  summary: 'Market stress is low-to-moderate.',
  actionText:
    'Stay invested according to plan. Be selective with new buys. Do not chase broad market strength just because indexes are up.',
  whatMatters: [
    'Credit and volatility are calm, so this is not a panic tape.',
    'Breadth is middling; the rally is not broad enough to call conditions fully strong.',
    'Crowding is the main warning sign; avoid chasing the same narrow winners late.',
  ],
  whatToDo: [
    'Keep long-term allocation unless your plan says otherwise.',
    'If adding money, favor only highest-conviction setups.',
    'Review concentration before adding more to crowded areas.',
  ],
  watchItems: [
    'VIX above 30 would move volatility from calm to stressed.',
    'HY OAS above 5 or widening 100 bps would make credit a real warning.',
    'Risk budget below 40 would turn the brief defensive.',
  ],
  trend: {
    stress: stressTrend,
    vix: calmTrend,
    hyOas: calmTrend,
    tenYearThreeMonth: calmTrend,
  },
  marketShifts: [
    {
      key: 'stress',
      label: 'Stress reversed worse',
      detail: '7D +7 · Reversed worse over 7D',
      tone: 'warning',
      reversal: true,
    },
    {
      key: 'vix',
      label: 'Volatility easing',
      detail: '7D -3.00 · Improving over 7D',
      tone: 'gain',
      reversal: false,
    },
  ],
  flags: [],
  alert: {
    active: false,
    priority: null,
    reason: null,
  },
  bondSignals: {
    asOf: '2026-05-28',
    tenYearTwoYearBps: 49,
    tenYearThreeMonthBps: 98,
  },
  creditSignal: {
    latestDate: '2026-05-28',
    latestValue: 2.7,
    priorDate: '2026-02-28',
    priorValue: 3.1,
    changeBps: -40,
  },
  evidence: [
    {
      key: 'stress',
      label: 'Stress',
      value: '41',
      detail: 'Low-to-moderate',
      tone: 'warning',
      tooltip: 'Higher means market conditions are less supportive.',
      trend: stressTrend,
    },
    {
      key: 'vix',
      label: 'VIX',
      value: '17.00',
      detail: 'Volatility calm',
      tone: 'gain',
      tooltip: 'VIX estimates expected S&P 500 volatility.',
      trend: calmTrend,
    },
    {
      key: 'hy_oas',
      label: 'HY OAS',
      value: '2.70',
      detail: '3M change -40 bps',
      tone: 'gain',
      tooltip: 'High-yield OAS is a credit stress check.',
      trend: calmTrend,
    },
    {
      key: 'ten_year_three_month',
      label: '10Y-3M',
      value: '+98 bps',
      detail: 'Recession-risk check',
      tone: 'gain',
      tooltip: 'Another recession-risk curve check.',
      trend: calmTrend,
    },
  ],
}

describe('DailyBriefPanel', () => {
  beforeEach(() => {
    useMacroCurrentMock.mockReturnValue({
      data: macroSnapshot,
      isLoading: false,
      error: null,
    })
    useMacroConditionsMock.mockReturnValue({
      data: conditions,
      isLoading: false,
      error: null,
    })
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        generatedAt: '2026-05-28T21:45:00Z',
        overview: {
          netWorth: 850_000,
          netWorthStatus: 'current',
          investedAssets: 620_000,
          cashReserve: 55_000,
        },
        accountControl: { blockingIssueCount: 0 },
        portfolioContext: { cashReservesMonths: 7.2 },
        budgetSnapshot: {
          paceStatus: 'on_track',
          monthToDateSpend: 4_000,
          monthToDatePlan: 4_500,
        },
      },
      isLoading: false,
    })
    useHouseholdNetWorthTrendMock.mockReturnValue({
      data: {
        points: [{ netWorth: 850_000 }],
        status: 'current',
      },
    })
    usePortfolioAnalyticsMock.mockReturnValue({
      data: { quoteFreshnessStatus: 'current' },
    })
    useMarketStatusMock.mockReturnValue({
      data: { isOpen: false },
    })
    useTodayRefreshMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
  })

  it('leads Today with market conditions, plain-language guidance, and evidence', () => {
    render(<DailyBriefPanel />)

    expect(screen.getByText('Daily Brief')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument()
    expect(screen.getByText('Caution, not emergency')).toBeInTheDocument()
    expect(screen.getByText('Market Stress')).toBeInTheDocument()
    expect(screen.getAllByText('41').length).toBeGreaterThan(0)
    expect(
      screen.getByText('Market stress is low-to-moderate.'),
    ).toBeInTheDocument()

    expect(screen.getByText('What matters')).toBeInTheDocument()
    expect(screen.getByText('What to do')).toBeInTheDocument()
    expect(screen.getByText('What changes this')).toBeInTheDocument()
    expect(screen.getByText(/highest-conviction setups/i)).toBeInTheDocument()
    expect(screen.getByText('Market shifts')).toBeInTheDocument()
    expect(screen.getByText('Stress reversed worse')).toBeInTheDocument()
    expect(screen.getAllByText('7D +7').length).toBeGreaterThan(0)

    expect(screen.getByText('HY OAS')).toBeInTheDocument()
    expect(screen.getByText('10Y-3M')).toBeInTheDocument()
    expect(screen.getByText('+98 bps')).toBeInTheDocument()
    expect(screen.queryByText(/Action Queue/i)).not.toBeInTheDocument()
  })

  it('forces a Today data refresh from the header action', () => {
    const mutate = vi.fn()
    useTodayRefreshMock.mockReturnValue({
      mutate,
      isPending: false,
    })

    render(<DailyBriefPanel />)

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }))

    expect(mutate).toHaveBeenCalledTimes(1)
  })
})
