import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  useSectorHistory: () => ({ data: undefined, isLoading: false, error: null }),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolioAnalytics: () => usePortfolioAnalyticsMock(),
}))

vi.mock('@/lib/hooks/useMacro', () => ({
  useMacroCurrent: () => useMacroCurrentMock(),
  useMacroConditions: () => useMacroConditionsMock(),
  useMacroConditionsHistory: () => ({
    data: undefined,
    isLoading: false,
    error: null,
  }),
}))

vi.mock('@/lib/hooks/useTodayRefresh', () => ({
  useTodayRefresh: () => useTodayRefreshMock(),
}))

vi.mock('@/lib/hooks/useMarketEvents', () => ({
  useMarketEventsWindow: () => {
    const meeting = new Date()
    meeting.setDate(meeting.getDate() + 7)
    return {
      data: {
        events: [
          {
            id: 1,
            eventType: 'fomc_decision',
            eventDate: meeting.toISOString().slice(0, 10),
            eventTime: null,
            title: 'FOMC Meeting',
            impactScore: 5,
            actualValue: null,
            expectedValue: null,
            surprisePct: null,
          },
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
    }
  },
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
  macroStressScore: 41,
  tapePressureScore: 62,
  overallCautionScore: 62,
  overallRead: 'selective',
  primaryDriver: 'tape',
  driverDetail:
    'Tape pressure is the main caution; macro stress is not severe.',
  deploymentScore: 59,
  macroZone: 'REDUCED',
  coverage: 1,
  summary:
    'Selective — tape pressure is elevated, but macro stress is not severe.',
  actionText:
    'Stay invested, but be selective. Do not chase short-term tape moves; scale only into highest-conviction buys while the tape stabilizes.',
  driving: {
    headline:
      'Cautious — stocks broadly lower (Technology -4.1%, 6/11 sectors down).',
    tone: 'caution',
  },
  nextCatalyst: {
    eventType: 'cpi_release',
    eventDate: '2026-06-10',
    eventTime: '08:30:00',
    title: 'Consumer Price Index',
    impactScore: 5,
  },
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
    'Buying conditions below 40 would turn the brief defensive.',
  ],
  triggers: [
    {
      key: 'vix',
      label: 'VIX',
      current: 22.2,
      currentDisplay: '22.2',
      trigger: 30,
      triggerDisplay: '30',
      baseline: 12,
      watch: 20,
      direction: 'above',
      unit: '',
      progress: 0.567,
      fired: false,
      tone: 'warning',
      note: 'Above 20 volatility is elevated; above 30 the read flips to Elevated.',
    },
    {
      key: 'buy_score',
      label: 'Buying conditions',
      current: 56,
      currentDisplay: '56',
      trigger: 40,
      triggerDisplay: '40',
      baseline: 75,
      watch: 50,
      direction: 'below',
      unit: '',
      progress: 0.543,
      fired: false,
      tone: 'gain',
      note: 'Below 50 conditions are thinning; below 40 the brief turns defensive.',
    },
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
      label: 'Macro stress reversed worse',
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
      key: 'overall_caution',
      label: 'Overall Caution',
      value: '62',
      detail: 'Selective',
      tone: 'warning',
      tooltip: 'Higher means slow down new risk.',
      trend: null,
    },
    {
      key: 'equity_tape',
      label: 'Tape Pressure',
      value: '62',
      detail: 'S&P -1.2%, Technology -4.1%, 6/11 sectors down',
      tone: 'warning',
      tooltip: 'Current tape pressure uses fresh quotes.',
      trend: null,
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
        accountControl: { blockingIssueCount: 0, issues: [] },
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
      data: {
        quoteFreshnessStatus: 'current',
        householdInvestedTotalValue: 625_000,
        householdTotalsTrusted: true,
        accountControlBlockingIssueCount: 0,
        accountControlSummary: 'Household totals reconcile.',
      },
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
    expect(screen.getAllByText('Selective').length).toBeGreaterThan(0)
    expect(screen.getByText('Overall Read')).toBeInTheDocument()
    expect(screen.getByText('Overall Caution 62/100')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Selective — tape pressure is elevated, but macro stress is not severe.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText("What's driving")).toBeInTheDocument()
    expect(
      screen.getByText(
        'Cautious — stocks broadly lower (Technology -4.1%, 6/11 sectors down).',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Buying Conditions')).toBeInTheDocument()
    expect(screen.getAllByText('Tape Pressure').length).toBeGreaterThan(0)
    expect(screen.getByText('Driver')).toBeInTheDocument()
    expect(screen.getAllByText('Coverage').length).toBeGreaterThan(0)
    expect(screen.getByText('Next Catalyst')).toBeInTheDocument()
    expect(
      screen.getByText('Inflation report (CPI) · Jun 10'),
    ).toBeInTheDocument()
    expect(screen.getByText('Tape')).toBeInTheDocument()
    expect(screen.queryByText('7D +7')).not.toBeInTheDocument()

    expect(screen.getByText('What would change the read')).toBeInTheDocument()
    expect(screen.getByText('Buying conditions')).toBeInTheDocument()
    expect(screen.getByText('≥ 30')).toBeInTheDocument()
    expect(screen.getByText('Elevated — watch')).toBeInTheDocument()
    expect(screen.getByText('54% of the way')).toBeInTheDocument()
    expect(screen.getByText('Market shifts')).toBeInTheDocument()
    expect(screen.getByText('Macro stress reversed worse')).toBeInTheDocument()

    expect(screen.getByText('HY OAS')).toBeInTheDocument()
    expect(screen.getByText('10Y-3M')).toBeInTheDocument()
    expect(screen.getByText('+98 bps')).toBeInTheDocument()
    expect(screen.queryByText(/Action Queue/i)).not.toBeInTheDocument()
  })

  it('marks the invested total for reconciliation when account control blocks totals', () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        generatedAt: '2026-05-28T21:45:00Z',
        overview: {
          netWorth: 850_000,
          netWorthStatus: 'blocked',
          investedAssets: 620_000,
          cashReserve: 55_000,
        },
        accountControl: {
          status: 'blocked',
          summary: 'A material source account is not linked.',
          blockingIssueCount: 1,
          issues: [
            {
              id: 'unlinked-source',
              title: 'Unlinked source account',
              affectsTotals: true,
            },
          ],
        },
        portfolioContext: { cashReservesMonths: 7.2 },
        budgetSnapshot: {
          paceStatus: 'on_track',
          monthToDateSpend: 4_000,
          monthToDatePlan: 4_500,
        },
      },
      isLoading: false,
    })

    render(<DailyBriefPanel />)

    expect(screen.getAllByText('Totals need reconciliation').length).toBe(3)
  })

  it('uses analytics account control when the household dashboard is unavailable', async () => {
    const user = userEvent.setup()
    useHouseholdDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: false,
    })
    usePortfolioAnalyticsMock.mockReturnValue({
      data: {
        quoteFreshnessStatus: 'current',
        householdInvestedTotalValue: 625_000,
        householdTotalsTrusted: false,
        accountControlBlockingIssueCount: 1,
        accountControlSummary: 'A material source account is not linked.',
      },
      isLoading: false,
    })

    render(<DailyBriefPanel />)

    const investedTile = screen.getByText('Invested').closest('article')
    expect(investedTile).not.toBeNull()
    expect(
      within(investedTile as HTMLElement).getByText('$625,000'),
    ).toBeVisible()
    expect(
      within(investedTile as HTMLElement).getByText(
        'Totals need reconciliation',
      ),
    ).toBeVisible()
    expect(
      within(investedTile as HTMLElement).getByText('Unavailable'),
    ).toBeVisible()
    expect(
      within(investedTile as HTMLElement).queryByText('Current'),
    ).not.toBeInTheDocument()
    await user.hover(
      within(investedTile as HTMLElement).getByRole('button', {
        name: 'Unavailable: more detail',
      }),
    )
    expect(
      (
        await screen.findAllByText('A material source account is not linked.')
      )[0],
    ).toBeVisible()
  })

  it('uses the market-refreshed invested total on Today', () => {
    render(<DailyBriefPanel />)

    expect(screen.getByText('$625,000')).toBeInTheDocument()
    expect(screen.queryByText('$620,000')).not.toBeInTheDocument()
  })

  it('renders available macro data while richer conditions are still loading', () => {
    useMacroConditionsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: new Error('Conditions refresh still running'),
    })

    render(<DailyBriefPanel />)

    expect(screen.getByText('Overall Read')).toBeInTheDocument()
    expect(
      screen.queryByText('Conditions refresh still running'),
    ).not.toBeInTheDocument()
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

  it('shows FedWatch odds on the FOMC catalyst tile and timeline tooltip', () => {
    const meeting = new Date()
    meeting.setDate(meeting.getDate() + 7)
    const meetingDate = meeting.toISOString().slice(0, 10)
    useMacroConditionsMock.mockReturnValue({
      data: {
        ...conditions,
        nextCatalyst: {
          eventType: 'fomc_decision',
          eventDate: meetingDate,
          eventTime: null,
          title: 'FOMC Meeting',
          impactScore: 5,
        },
        fedOdds: {
          meetingDate,
          effr: 3.62,
          impliedPostRate: 3.63,
          pCut: 0,
          pHold: 98,
          pHike: 2,
          yearEndRate: 3.88,
          cutsPricedByYearEnd: -1.0,
          asOf: '2026-06-11T04:42:18+00:00',
        },
      },
      isLoading: false,
      error: null,
    })

    render(<DailyBriefPanel />)

    // Next Catalyst tile carries the odds line when the catalyst is FOMC.
    expect(screen.getByText(/Cut 0% · Hold 98% · Hike 2%/)).toBeInTheDocument()

    // Timeline FOMC dot tooltip carries the odds plus the year-end pricing.
    fireEvent.focus(screen.getByRole('button', { name: /fed rate decision/i }))
    expect(
      screen.getAllByText(/Futures price: Cut 0% · Hold 98% · Hike 2%/).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByText(/~1 hike priced by Dec \(3\.88% implied\)/).length,
    ).toBeGreaterThan(0)
  })
})
