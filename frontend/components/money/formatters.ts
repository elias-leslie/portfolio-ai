export function formatCurrency(value: number | null | undefined): string {
  if (value == null) {
    return 'Not set'
  }

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatEnumLabel(
  value: string | null | undefined,
  fallback = 'Awaiting review',
): string {
  if (!value) {
    return fallback
  }
  return value.replaceAll('_', ' ')
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) {
    return 'Not set'
  }

  return `${value.toFixed(0)}%`
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
