import type { Account, PositionWithValue } from '@/lib/api/portfolio'

export const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

export const formatPercent = (value: number) => {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

export const formatCurrencyWhole = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export const formatPnlDollars = (value: number) => {
  const prefix = value >= 0 ? '+$' : '-$'
  return `${prefix}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export const formatDisplayLabel = (value: string) => {
  const withSpaces = value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
  return withSpaces.charAt(0).toUpperCase() + withSpaces.slice(1)
}

export const getAccountPositions = (
  accountId: string,
  positions: PositionWithValue[] | undefined,
) => {
  return positions?.filter((p) => p.accountId === accountId) || []
}

export const getAccountTotalValue = (
  account: Account,
  positions: PositionWithValue[] | undefined,
) => {
  const accountPositions = getAccountPositions(account.id, positions)
  return (
    account.cashBalance +
    accountPositions.reduce((sum, p) => sum + (p.currentValue || 0), 0)
  )
}

export const getAccountTotalCostBasis = (
  accountId: string,
  cashBalance: number,
  positions: PositionWithValue[] | undefined,
) => {
  const accountPositions = getAccountPositions(accountId, positions)
  return (
    cashBalance +
    accountPositions.reduce((sum, p) => sum + p.shares * p.costBasis, 0)
  )
}

export const getAccountTotalGain = (
  account: Account,
  positions: PositionWithValue[] | undefined,
) => {
  const totalValue = getAccountTotalValue(account, positions)
  const totalCost = getAccountTotalCostBasis(
    account.id,
    account.cashBalance,
    positions,
  )
  return totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0
}
