import type { PositionWithValue } from '@/lib/api/portfolio'

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

export const formatPnlDollars = (value: number) => {
  const prefix = value >= 0 ? '+$' : '-$'
  return `${prefix}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export const getAccountPositions = (
  accountId: string,
  positions: PositionWithValue[] | undefined,
) => {
  return positions?.filter((p) => p.accountId === accountId) || []
}

export const getAccountTotalValue = (
  accountId: string,
  positions: PositionWithValue[] | undefined,
) => {
  const accountPositions = getAccountPositions(accountId, positions)
  return accountPositions.reduce((sum, p) => sum + (p.currentValue || 0), 0)
}

export const getAccountTotalGain = (
  accountId: string,
  positions: PositionWithValue[] | undefined,
) => {
  const accountPositions = getAccountPositions(accountId, positions)
  const totalValue = accountPositions.reduce(
    (sum, p) => sum + (p.currentValue || 0),
    0,
  )
  const totalCost = accountPositions.reduce(
    (sum, p) => sum + p.shares * p.costBasis,
    0,
  )
  return totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0
}
