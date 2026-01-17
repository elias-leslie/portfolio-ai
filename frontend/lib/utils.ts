import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a timestamp as relative time ("2m ago", "1h ago") or absolute time for older dates
 * @param timestamp ISO 8601 timestamp string
 * @returns Formatted time string
 */
/**
 * Format a date string consistently across the app (MM/DD/YYYY style)
 * @param dateStr ISO 8601 date string or date-only string (YYYY-MM-DD)
 * @param includeYear Whether to include the year (default: true)
 * @returns Formatted date string like "Nov 18, 2025" or "Nov 18"
 */
export function formatDate(
  dateStr: string | undefined | null,
  includeYear: boolean = true,
): string {
  if (!dateStr) return '-'
  // Append T12:00:00 to avoid timezone issues when parsing date-only strings
  const normalizedStr = dateStr.includes('T') ? dateStr : `${dateStr}T12:00:00`
  const date = new Date(normalizedStr)
  if (Number.isNaN(date.getTime())) return '-'

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(includeYear && { year: 'numeric' }),
  })
}

/**
 * Format a datetime string with time component
 * @param dateStr ISO 8601 timestamp string
 * @returns Formatted string like "Nov 18, 10:30 AM"
 */
export function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatRelativeTime(
  timestamp: string | null | undefined,
): string {
  if (!timestamp) return 'Never'

  try {
    const now = new Date()
    const then = new Date(timestamp)
    const diffMs = now.getTime() - then.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`

    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`

    // Format as absolute time for > 7d
    return then.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return 'Unknown'
  }
}

/**
 * Check if data is fresh compared to expected data date
 * @param dataDate The date of the data (YYYY-MM-DD format)
 * @param expectedDataDate The expected data date from market status API
 * @returns Object with freshness status and display info
 */
export function checkDataFreshness(
  dataDate: string | null | undefined,
  expectedDataDate: string | null | undefined,
): { isFresh: boolean; indicator: string; tooltip: string } {
  if (!dataDate || !expectedDataDate) {
    return {
      isFresh: false,
      indicator: '⚠️',
      tooltip: 'Unable to verify data freshness',
    }
  }

  // Extract just the date part (YYYY-MM-DD) for comparison
  // This avoids timezone issues by comparing strings directly
  const dataDateStr = dataDate.split('T')[0]
  const expectedDateStr = expectedDataDate.split('T')[0]

  // String comparison works for ISO date format (YYYY-MM-DD)
  const isFresh = dataDateStr >= expectedDateStr

  return {
    isFresh,
    indicator: isFresh ? '✓' : '⚠️',
    tooltip: isFresh
      ? `Data is current (${formatDate(dataDate, false)})`
      : `Data may be stale - expected ${formatDate(expectedDataDate, false)}, have ${formatDate(dataDate, false)}`,
  }
}

/**
 * Format data date with freshness indicator
 * @param dataDate The date of the data
 * @param expectedDataDate The expected data date from market status API
 * @returns Formatted string like "Dec 10 ✓" or "Dec 10 ⚠️"
 */
export function formatDataDateWithFreshness(
  dataDate: string | null | undefined,
  expectedDataDate: string | null | undefined,
): string {
  if (!dataDate) return '-'

  const { indicator } = checkDataFreshness(dataDate, expectedDataDate)
  return `${formatDate(dataDate, false)} ${indicator}`
}
