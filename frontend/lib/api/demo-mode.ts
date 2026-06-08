/**
 * Demo mode — serve synthetic, non-personal data for the Investing & Holdings
 * views so the app can be screenshotted or screen-recorded for a public README
 * without exposing the owner's real accounts, balances, or positions.
 *
 * Runtime toggle (no rebuild required):
 *   - visit any page with `?demo=1` to turn demo data ON (persisted in localStorage)
 *   - visit with `?demo=0` to turn it OFF
 * Demo mode is OFF by default; every other request returns real data.
 *
 * Scope: this only intercepts the portfolio/holdings endpoints plus the
 * household dashboard (neutralised to empty so no real account labels leak into
 * the Holdings linkage rows). Market data (watchlist signals, prices, news)
 * stays real because it is not personal.
 */

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

// Neutralised dashboard: empty accounts so Holdings linkage rows show generic
// "Unmapped" labels instead of any real household/institution name.
const DEMO_HOUSEHOLD_DASHBOARD = { accounts: [] }

const DEMO_FIXTURES: Record<string, unknown> = {
  '/api/portfolio': DEMO_PORTFOLIO,
  '/api/portfolio/accounts': DEMO_ACCOUNTS,
  '/api/household/dashboard': DEMO_HOUSEHOLD_DASHBOARD,
}

/**
 * Returns a synthetic fixture for a sensitive GET path when demo mode is on,
 * or undefined to let the request proceed to the real backend.
 */
export function demoResponseForPath(path: string): unknown | undefined {
  const clean = path.split('?')[0].replace(/\/+$/, '') || '/'
  return DEMO_FIXTURES[clean]
}
