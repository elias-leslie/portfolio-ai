export type StyleFilter =
  | 'all'
  | 'Index'
  | 'Trend'
  | 'Value'
  | 'Swing'
  | 'Event'
export type SignalFilter = 'all' | 'BUY' | 'HOLD' | 'AVOID'
export type RiskFilter = 'all' | 'Low' | 'Medium-Low' | 'Medium' | 'High'

export const STYLE_FILTER_VALUES: StyleFilter[] = [
  'all',
  'Index',
  'Trend',
  'Value',
  'Swing',
  'Event',
]
export const SIGNAL_FILTER_VALUES: SignalFilter[] = [
  'all',
  'BUY',
  'HOLD',
  'AVOID',
]

export const SIGNAL_FILTER_LABELS: Record<SignalFilter, string> = {
  all: 'All setups',
  BUY: 'Setup BUY',
  HOLD: 'Setup HOLD',
  AVOID: 'Setup AVOID',
}

export const RISK_FILTER_VALUES: RiskFilter[] = [
  'all',
  'Low',
  'Medium-Low',
  'Medium',
  'High',
]

// Helper to safely read from localStorage (handles SSR)
export function getStoredFilter<T extends string>(
  key: string,
  validValues: T[],
  defaultValue: T,
): T {
  if (typeof window === 'undefined') return defaultValue
  const saved = localStorage.getItem(key)
  return saved && validValues.includes(saved as T) ? (saved as T) : defaultValue
}
