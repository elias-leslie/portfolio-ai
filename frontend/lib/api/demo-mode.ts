/**
 * Demo mode — serve synthetic, non-personal data for the Daily Brief, Investing
 * & Holdings views so the app can be screenshotted or screen-recorded for a
 * public README without exposing the owner's real accounts, balances, net worth,
 * or positions.
 *
 * Runtime toggle (no rebuild required):
 *   - visit any page with `?demo=1` to turn demo data ON (persisted in localStorage)
 *   - visit with `?demo=0` to turn it OFF
 * Demo mode is OFF by default; every other request returns real data.
 *
 * Scope: intercepts the personal endpoints behind the Today / Daily Brief and
 * Holdings views — portfolio, accounts, household dashboard, net-worth trend, and
 * portfolio analytics — replacing them with one coherent fake household. Market
 * and macro data (watchlist signals, prices, conditions, news) stays real because
 * it is not personal.
 */

import type {
  HouseholdFinanceDashboard,
  HouseholdNetWorthTrend,
} from './household/types'
import type { PortfolioAnalytics } from './portfolio'

const DEMO_FLAG_KEY = 'pa_demo_mode'

export function isDemoMode(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  try {
    const flag = new URLSearchParams(window.location.search).get('demo')
    if (flag === '1') {
      window.localStorage.setItem(DEMO_FLAG_KEY, '1')
      return true
    }
    if (flag === '0') {
      window.localStorage.removeItem(DEMO_FLAG_KEY)
      return false
    }
    return window.localStorage.getItem(DEMO_FLAG_KEY) === '1'
  } catch {
    return false
  }
}

const round2 = (n: number) => Math.round(n * 100) / 100
const sum = (nums: number[]) => nums.reduce((a, b) => a + b, 0)

function position(
  id: string,
  accountId: string,
  symbol: string,
  shares: number,
  costBasis: number,
  currentPrice: number,
) {
  const currentValue = round2(shares * currentPrice)
  const gain = round2(currentValue - shares * costBasis)
  const gainPct = round2((gain / (shares * costBasis)) * 100)
  return {
    id,
    accountId,
    symbol,
    shares,
    costBasis,
    positionType: 'long',
    createdAt: '2024-02-01T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
    currentPrice,
    currentValue,
    gain,
    gainPct,
    priceUpdatedAt: '2026-06-07T20:00:00Z',
    priceSource: 'demo',
  }
}

const DEMO_POSITIONS = [
  position('demo-pos-1', 'demo-acct-1', 'AAPL', 40, 245, 307.78),
  position('demo-pos-2', 'demo-acct-1', 'NVDA', 15, 130, 178.5),
  position('demo-pos-3', 'demo-acct-1', 'AMD', 30, 180, 158.66),
  position('demo-pos-4', 'demo-acct-2', 'MSFT', 20, 380, 442.1),
  position('demo-pos-5', 'demo-acct-2', 'GOOGL', 12, 165, 191.2),
  position('demo-pos-6', 'demo-acct-3', 'VOO', 25, 500, 565.3),
]

const DEMO_ACCOUNTS = [
  {
    id: 'demo-acct-1',
    name: 'Summit Brokerage',
    accountType: 'taxable',
    householdAccountId: null,
    householdLinkageState: 'standalone_by_design',
    cashBalance: 4200,
    createdAt: '2024-01-15T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
  {
    id: 'demo-acct-2',
    name: 'Summit Roth IRA',
    accountType: 'retirement',
    householdAccountId: null,
    householdLinkageState: 'standalone_by_design',
    cashBalance: 1500,
    createdAt: '2023-03-10T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
  {
    id: 'demo-acct-3',
    name: 'Summit 401(k)',
    accountType: 'retirement',
    householdAccountId: null,
    householdLinkageState: 'standalone_by_design',
    cashBalance: 800,
    createdAt: '2022-07-01T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
]

const DEMO_CASH_TOTAL = sum(DEMO_ACCOUNTS.map((a) => a.cashBalance))
const DEMO_POSITIONS_VALUE = sum(DEMO_POSITIONS.map((p) => p.currentValue))
const DEMO_POSITIONS_COST = sum(
  DEMO_POSITIONS.map((p) => p.shares * p.costBasis),
)
const DEMO_TOTAL_VALUE = round2(DEMO_POSITIONS_VALUE + DEMO_CASH_TOTAL)
const DEMO_TOTAL_COST = round2(DEMO_POSITIONS_COST + DEMO_CASH_TOTAL)
const DEMO_TOTAL_GAIN = round2(DEMO_POSITIONS_VALUE - DEMO_POSITIONS_COST)
const DEMO_TOTAL_GAIN_PCT = round2(
  (DEMO_TOTAL_GAIN / DEMO_POSITIONS_COST) * 100,
)

const DEMO_PORTFOLIO = {
  positions: DEMO_POSITIONS,
  cashBalanceTotal: DEMO_CASH_TOTAL,
  totalValue: DEMO_TOTAL_VALUE,
  totalCostBasis: DEMO_TOTAL_COST,
  totalGain: DEMO_TOTAL_GAIN,
  totalGainPct: DEMO_TOTAL_GAIN_PCT,
  effectiveTotalValue: DEMO_TOTAL_VALUE,
  householdTotalValue: null,
  householdInvestedTotalValue: null,
  householdCashReserve: null,
  householdInvestmentAccountsCount: null,
  quotesUpdatedAt: '2026-06-07T20:00:00Z',
  quoteFreshnessStatus: 'fresh',
  quoteFreshnessLabel: 'Updated moments ago',
}

// demo-acct-1 is the taxable Summit Brokerage; acct-2/3 are retirement. Split
// the invested total so the household overview tells the same story as Holdings.
const DEMO_TAXABLE_INVESTED = round2(
  sum(
    DEMO_POSITIONS.filter((p) => p.accountId === 'demo-acct-1').map(
      (p) => p.currentValue,
    ),
  ),
)
const DEMO_RETIREMENT_INVESTED = round2(
  DEMO_POSITIONS_VALUE - DEMO_TAXABLE_INVESTED,
)

const DAY_MS = 24 * 60 * 60 * 1000
const DEMO_TREND_ANCHOR = Date.parse('2026-06-08T00:00:00Z')

// 13 biweekly net-worth marks rising into the current total — drives the Net
// Worth tile's sparkline. The final mark equals the live demo total so the tile
// number and the trend line agree.
const DEMO_NET_WORTH_SERIES = [
  46180,
  46720,
  47010,
  46890,
  47550,
  48120,
  48030,
  49240,
  49880,
  50310,
  50190,
  51020,
  DEMO_TOTAL_VALUE,
]

const DEMO_NET_WORTH_POINTS = DEMO_NET_WORTH_SERIES.map((netWorth, index) => {
  const daysAgo = (DEMO_NET_WORTH_SERIES.length - 1 - index) * 14
  const date = new Date(DEMO_TREND_ANCHOR - daysAgo * DAY_MS)
    .toISOString()
    .slice(0, 10)
  return {
    date,
    netWorth: round2(netWorth),
    totalAssets: round2(netWorth),
    liabilities: 0,
    pricedHoldingsValue: round2(netWorth - DEMO_CASH_TOTAL),
    fixedAssets: 0,
  }
})

// Full, valid dashboard carrying fake numbers so the Daily Brief renders without
// crashing (the Net Worth / Invested / Cash / Spend tiles read nested fields) and
// never reaches the real backend. `accounts` stays empty so Holdings linkage rows
// stay generic — no institution labels are asserted against the portfolio.
const DEMO_HOUSEHOLD_DASHBOARD: HouseholdFinanceDashboard = {
  generatedAt: '2026-06-08T12:00:00Z',
  overview: {
    investedAssets: round2(DEMO_POSITIONS_VALUE),
    retirementAssets: DEMO_RETIREMENT_INVESTED,
    taxableAssets: DEMO_TAXABLE_INVESTED,
    cashReserve: DEMO_CASH_TOTAL,
    totalTrackedAssets: round2(DEMO_TOTAL_VALUE),
    liabilitiesTotal: 0,
    netWorth: round2(DEMO_TOTAL_VALUE),
    netWorthStatus: 'current',
    netWorthDetail: 'Live holdings priced with the latest quotes, plus cash.',
    trackedAccountCount: DEMO_ACCOUNTS.length,
    needsRefreshCount: 0,
    candidateAccountCount: 0,
    gapCount: 0,
    inboxCount: 0,
    coverageMonths: 6,
    lastTransactionDate: '2026-06-06',
    visibilityScore: 92,
    visibilityLabel: 'Strong coverage',
    monthlySpendStatus: 'on_track',
    monthlySpendDetail: 'Spending is tracking close to plan this month.',
    nextBestAction: 'Review the watchlist for new ideas.',
  },
  accountControl: {
    status: 'clear',
    summary: 'All tracked accounts are reconciled.',
    issueCount: 0,
    blockingIssueCount: 0,
    checkedAt: '2026-06-08T12:00:00Z',
    issues: [],
  },
  profile: {
    id: 'demo-household',
    householdName: 'Summit Demo Household',
    monthlyNetIncomeTarget: 9000,
    monthlyEssentialTarget: 4200,
    monthlyDiscretionaryTarget: 1400,
    monthlySavingsTarget: 1800,
    targetRetirementAge: 62,
    targetRetirementSpend: 6500,
    notes: null,
    createdAt: '2024-01-15T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
  resolvedValues: [],
  budgetReadiness: {
    status: 'ready',
    summary: 'A confirmed monthly plan is in place.',
    priorities: [],
    missingInputs: [],
    starterLanes: [],
  },
  budgetSnapshot: {
    status: 'on_track',
    summary: 'Spending is on plan this month.',
    monthlyIncomeTarget: 9000,
    monthlyPlanTotal: 6200,
    monthlyPlanSource: 'confirmed',
    monthlyPlanSourceLabel: 'Confirmed plan',
    essentialTarget: 4200,
    discretionaryTarget: 1400,
    savingsTarget: 1800,
    actualMonthlySpend: 6050,
    actualEssentialMonthlySpend: 4100,
    actualDiscretionaryMonthlySpend: 1350,
    monthToDateSpend: 1480,
    monthToDatePlan: 1550,
    paceStatus: 'on_track',
    paceDetail: 'Month-to-date spending is just under plan.',
    planIsPartial: false,
    missingPlanComponents: [],
    remainingCashAfterPlan: 2800,
    discretionaryHeadroom: 50,
  },
  retirementPreparedness: {
    status: 'on_track',
    summary: 'On track toward the retirement target.',
    retirementAccountShare: 0.56,
    strengths: [],
    blockers: [],
    nextSteps: [],
  },
  jennyNeeds: [],
  importCenter: {
    headline: 'Import your statements to deepen coverage',
    trackedDocuments: 0,
    parsedDocuments: 0,
    suggestedFirstUploads: [],
    automations: [],
    supportedDocuments: [],
  },
  evidenceAccounts: [],
  accounts: [],
  discoveredAccounts: [],
  inbox: [],
  questions: [],
  jennyBrief: {
    headline: "You're on track",
    body: 'Holdings and cash reserves are healthy and spending is on plan.',
    prompts: [],
    progression: null,
  },
  reports: {
    executive: {
      headline: 'Steady month',
      summary: 'Spending is on plan and net worth is rising.',
      averageMonthlySpend: 6050,
      averageMonthlyEssentials: 4100,
      averageMonthlyDiscretionary: 1350,
      recent30DaySpend: 6020,
      recurringMerchantCount: 6,
      trackedExpenseCount: 128,
      coverageMonths: 6,
    },
    categoryBreakdown: [],
    merchantHighlights: [],
    monthlySpendTrend: [],
    recentTransactions: [],
  },
  categorizationQueue: [],
  recurringCommitments: [],
  transactionDateIssues: [],
  sinkingFunds: [],
  retirementContributionTracker: {
    status: 'on_track',
    monthlyTarget: 1800,
    estimatedMonthlyContributions: 1750,
    monthlyGap: 50,
    detail: 'Contributions are close to the monthly target.',
  },
  retirementScenarios: [],
  portfolioContext: {
    totalPortfolioValue: round2(DEMO_TOTAL_VALUE),
    cashReservesMonths: 6,
    portfolioToAnnualSpendRatio: 0.7,
    insights: [],
  },
  planning: null,
}

const DEMO_NET_WORTH_TREND: HouseholdNetWorthTrend = {
  generatedAt: '2026-06-08T12:00:00Z',
  asOfDate: '2026-06-08',
  status: 'current',
  detail: 'Net worth is tracked from linked holdings and cash balances.',
  methodology:
    'Live holdings priced with the latest quotes, plus cash reserves; no debt tracked.',
  points: DEMO_NET_WORTH_POINTS,
  holdingsSymbolCount: DEMO_POSITIONS.length,
  holdingsPositionCount: DEMO_POSITIONS.length,
  gapCount: 0,
  needsRefreshCount: 0,
  missingBalanceAccountCount: 0,
  staleAccountCount: 0,
}

const DEMO_ANALYTICS: PortfolioAnalytics = {
  portfolioValue: {
    totalValue: round2(DEMO_POSITIONS_VALUE),
    totalCostBasis: round2(DEMO_POSITIONS_COST),
    totalGain: DEMO_TOTAL_GAIN,
    totalGainPct: DEMO_TOTAL_GAIN_PCT,
  },
  cashBalanceTotal: DEMO_CASH_TOTAL,
  cashInclusiveTotalValue: round2(DEMO_TOTAL_VALUE),
  effectiveTotalValue: round2(DEMO_TOTAL_VALUE),
  householdTotalValue: null,
  householdInvestedTotalValue: null,
  householdCashReserve: null,
  householdInvestmentAccountsCount: null,
  quotesUpdatedAt: '2026-06-07T20:00:00Z',
  quoteFreshnessStatus: 'fresh',
  quoteFreshnessLabel: 'Updated moments ago',
  portfolioBeta: 1.08,
  portfolioVolatility: 0.18,
  sharpeRatio: 1.42,
  concentration: {
    topHoldingPct: 31.4,
    top3Pct: 78.4,
    top10Pct: 100,
    herfindahlIndex: 0.23,
    topHoldingName: 'VOO',
  },
  sectorExposure: {
    Technology: 0.55,
    'Broad Market': 0.31,
    Semiconductors: 0.14,
  },
  riskProfile: null,
  diversificationScore: null,
  topPerformers: [],
  bottomPerformers: [],
  numPositions: DEMO_POSITIONS.length,
  numSymbols: DEMO_POSITIONS.length,
}

const DEMO_FIXTURES: Record<string, unknown> = {
  '/api/portfolio': DEMO_PORTFOLIO,
  '/api/portfolio/accounts': DEMO_ACCOUNTS,
  '/api/portfolio/analytics': DEMO_ANALYTICS,
  '/api/household/dashboard': DEMO_HOUSEHOLD_DASHBOARD,
  '/api/household/net-worth-trend': DEMO_NET_WORTH_TREND,
}

/**
 * Returns a synthetic fixture for a sensitive GET path when demo mode is on,
 * or undefined to let the request proceed to the real backend.
 */
export function demoResponseForPath(path: string): unknown | undefined {
  const clean = path.split('?')[0].replace(/\/+$/, '') || '/'
  return DEMO_FIXTURES[clean]
}
