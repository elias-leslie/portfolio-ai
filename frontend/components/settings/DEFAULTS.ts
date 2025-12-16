export const DEFAULT_SCORE_WEIGHTS = {
  price: 33,
  technical: 33,
  fundamental: 34,
} as const;

export const DEFAULT_TECH_WEIGHTS = {
  rsi14: 33,
  trend: 34,
  macd: 33,
} as const;

export const DEFAULT_FUND_WEIGHTS = {
  valuation: 30,
  growth: 35,
  health: 25,
  sentiment: 10,
} as const;
