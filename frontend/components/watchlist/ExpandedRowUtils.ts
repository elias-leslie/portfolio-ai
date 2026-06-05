/**
 * Utility functions for ExpandedRow components
 *
 * Extracted from ExpandedRow.tsx to reduce file size and improve modularity.
 */

import { getTimezoneAbbreviation } from './watchlistTableUtils'

export { getTimezoneAbbreviation }

/**
 * Sanitize HTML/text input to prevent XSS
 */
export function sanitizeText(input?: string | null): string {
  if (!input) return ''
  const value = input.trim()
  if (!value) return ''
  try {
    if (
      typeof window !== 'undefined' &&
      typeof window.DOMParser !== 'undefined'
    ) {
      const parser = new window.DOMParser()
      const doc = parser.parseFromString(value, 'text/html')
      return (doc.body?.textContent ?? '').replace(/\s+/g, ' ').trim()
    }
  } catch {
    // fallthrough to regex
  }
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Format score change with +/- sign
 */
export function formatScoreChange(change?: number | null): string | null {
  if (change === null || change === undefined || Number.isNaN(change)) {
    return null
  }
  const formatted = change.toFixed(2)
  return change >= 0 ? `+${formatted}` : formatted
}

/**
 * Get score badge variant based on score value
 */
export function getScoreBadgeVariant(
  score: number,
): 'viz-0' | 'viz-1' | 'viz-2' | 'viz-3' | 'viz-4' | 'viz-5' {
  if (score >= 80) return 'viz-5'
  if (score >= 60) return 'viz-4'
  if (score >= 40) return 'viz-3'
  if (score >= 20) return 'viz-2'
  if (score >= 10) return 'viz-1'
  return 'viz-0'
}

/**
 * Get score bar fill color class based on score value.
 * Shared by the scanner score meter and the expanded pillar bars.
 */
export function getScoreBarColor(score: number): string {
  if (score >= 70) return 'bg-gain'
  if (score >= 50) return 'bg-primary'
  if (score >= 30) return 'bg-warning'
  return 'bg-loss'
}

/**
 * Format timestamp with user's timezone
 */
export function formatTimestamp(
  timestamp: string | undefined,
  userTimezone: string,
): string {
  if (!timestamp) return 'Never'
  const date = new Date(timestamp)
  const formatted = date.toLocaleString('en-US', {
    timeZone: userTimezone,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
  const tzAbbr = getTimezoneAbbreviation(userTimezone)
  return `${formatted} ${tzAbbr}`
}

/**
 * Format model coverage display string
 */
export function formatModelCoverage(
  totalModelCoverage: number,
  finbertCoverage: number,
): string {
  if (totalModelCoverage === 0) {
    return 'No articles scored'
  }
  if (finbertCoverage === totalModelCoverage) {
    return 'FinBERT coverage'
  }
  if (finbertCoverage === 0) {
    return 'Fallback sentiment (VADER)'
  }
  return `FinBERT ${finbertCoverage}/${totalModelCoverage}`
}

/**
 * Get data quality text color based on percentage
 */
export function getDataQualityColor(pct: number): string {
  if (pct >= 80) return 'text-gain'
  if (pct >= 60) return 'text-warning'
  if (pct >= 40) return 'text-neutral'
  return 'text-loss'
}

/**
 * Get data quality background color based on percentage
 */
export function getDataQualityBgColor(pct: number): string {
  if (pct >= 80) return 'bg-gain/10'
  if (pct >= 60) return 'bg-warning/10'
  if (pct >= 40) return 'bg-neutral/10'
  return 'bg-loss/10'
}

/**
 * Format the user-facing data quality label.
 */
export function formatDataQualityLabel(pct: number): string {
  return `Data quality ${pct.toFixed(0)}%`
}

/**
 * Get signal display configuration
 */
export function getSignalDisplay(signalType: 'BUY' | 'HOLD' | 'AVOID') {
  switch (signalType) {
    case 'BUY':
      return {
        icon: '🟢',
        color:
          'bg-status-success/10 text-status-success border-status-success/20',
        // Solid, high-contrast chip for the primary scanner row anchor.
        solidColor: 'bg-status-success text-white border-status-success',
        label: 'BUY',
      }
    case 'HOLD':
      return {
        icon: '🟡',
        color:
          'bg-status-warning/10 text-status-warning border-status-warning/20',
        solidColor: 'bg-status-warning text-white border-status-warning',
        label: 'HOLD',
      }
    case 'AVOID':
      return {
        icon: '🔴',
        color: 'bg-status-error/10 text-status-error border-status-error/20',
        solidColor: 'bg-status-error text-white border-status-error',
        label: 'AVOID',
      }
  }
}

/**
 * Risk level display configuration
 */
export const RISK_LEVELS: Record<
  string,
  { label: string; icon: string; color: string }
> = {
  Low: { label: 'Low', icon: '✓', color: 'text-gain' },
  'Medium-Low': { label: 'Medium-Low', icon: '⚠', color: 'text-warning' },
  Medium: { label: 'Medium', icon: '⚠', color: 'text-neutral' },
  High: { label: 'High', icon: '⚠⚠', color: 'text-loss' },
}

/**
 * Get risk level display configuration
 */
export function getRiskLevelConfig(riskLevel: string): {
  label: string
  icon: string
  color: string
} {
  return (
    RISK_LEVELS[riskLevel] || {
      label: riskLevel,
      icon: '',
      color: 'text-text-muted',
    }
  )
}
