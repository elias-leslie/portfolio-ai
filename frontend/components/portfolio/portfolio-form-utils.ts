export type PositionType = 'long' | 'short'
export type AccountType = 'IRA' | 'Taxable' | '401k' | 'Roth' | 'HSA'

export interface PositionFormValues {
  accountId: string
  symbol: string
  shares: string
  costBasis: string
}

export interface PositionFormErrors {
  accountId?: string
  symbol?: string
  shares?: string
  costBasis?: string
}

export function normalizeSymbol(value: string) {
  return value.trim().toUpperCase()
}

export function normalizeAccountName(value: string) {
  return value.trim().replace(/\s+/g, ' ')
}

export function getAccountNameError(value: string) {
  return normalizeAccountName(value) ? undefined : 'Enter an account name.'
}

function getPositiveNumberError(value: string, label: string) {
  if (!value.trim()) {
    return `Enter ${label}.`
  }

  const numericValue = Number(value)
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return `${label.charAt(0).toUpperCase() + label.slice(1)} must be greater than 0.`
  }

  return undefined
}

export function getPositionFormErrors({
  accountId,
  symbol,
  shares,
  costBasis,
}: PositionFormValues): PositionFormErrors {
  return {
    accountId: accountId.trim() ? undefined : 'Select an account.',
    symbol: normalizeSymbol(symbol) ? undefined : 'Enter a stock symbol.',
    shares: getPositiveNumberError(shares, 'shares'),
    costBasis: getPositiveNumberError(costBasis, 'cost basis'),
  }
}

export function isPositionFormValid(errors: PositionFormErrors) {
  return Object.values(errors).every((value) => !value)
}
