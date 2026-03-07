export function getPnlColor(value: number | null | undefined): string {
  if (value === undefined || value === null) return 'text-text'
  return value >= 0 ? 'text-gain' : 'text-loss'
}

export function formatPct(value: number | null | undefined): string {
  if (value === undefined || value === null) return '0.00%'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === undefined || value === null) return '$0.00'
  const prefix = value >= 0 ? '+$' : '-$'
  return `${prefix}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
