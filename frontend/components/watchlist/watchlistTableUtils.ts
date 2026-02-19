// Utility functions for WatchlistTable

// Format pillar status
export function formatPillarStatus(status: string): string {
  const statusMap: Record<string, string> = {
    complete: '✓ Complete',
    partial: '◐ Partial',
    stale: '⏱ Stale',
    'n/a': '— N/A',
  }
  return statusMap[status] || status
}

// Get timezone abbreviation (EST, PST, etc.)
export function getTimezoneAbbreviation(timezone: string): string {
  const date = new Date()
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'short',
  })
  const parts = formatter.formatToParts(date)
  const timeZonePart = parts.find((part) => part.type === 'timeZoneName')
  return timeZonePart?.value ?? ''
}

// Format date with timezone
export function formatDate(dateStr: string, timezone: string): string {
  const date = new Date(dateStr)
  const formatted = date.toLocaleString('en-US', {
    timeZone: timezone,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
  const tzAbbr = getTimezoneAbbreviation(timezone)
  return `${formatted} ${tzAbbr}`
}
