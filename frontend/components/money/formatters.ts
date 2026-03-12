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
  const words = value.replaceAll('_', ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) {
    return 'Not set'
  }

  return `${value.toFixed(0)}%`
}

export function formatFileSize(bytes: number): string {
  if (bytes <= 0) {
    return '0 B'
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}
