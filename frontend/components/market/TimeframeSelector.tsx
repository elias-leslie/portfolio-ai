'use client'

import { cn } from '@/lib/utils'

export type Timeframe = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y'

interface TimeframeSelectorProps {
  value: Timeframe
  onChange: (value: Timeframe) => void
  className?: string
}

const TIMEFRAMES: { value: Timeframe; label: string; days: number }[] = [
  { value: '1M', label: '1M', days: 30 },
  { value: '3M', label: '3M', days: 90 },
  { value: '6M', label: '6M', days: 180 },
  { value: '1Y', label: '1Y', days: 365 },
  { value: '3Y', label: '3Y', days: 1095 },
  { value: '5Y', label: '5Y', days: 1825 },
]

export function timeframeToDays(tf: Timeframe): number {
  return TIMEFRAMES.find((t) => t.value === tf)?.days ?? 365
}

/**
 * Format date for X axis based on timeframe duration.
 * - Short (≤90 days): "Dec 15"
 * - Medium (≤365 days): "Jan '24"
 * - Long (>365 days): "Jan '22"
 */
export function formatChartDate(date: string, days: number): string {
  // Append T12:00:00 to avoid timezone shift
  const d = new Date(`${date}T12:00:00`)

  if (days <= 90) {
    // Short timeframes: "Dec 15"
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } else {
    // 1 year+: "Jan '24" - show month + year
    const month = d.toLocaleDateString('en-US', { month: 'short' })
    const year = d.getFullYear().toString().slice(-2)
    return `${month} '${year}`
  }
}

/**
 * Calculate tick interval to show ~6-8 ticks regardless of data density.
 */
export function calculateTickInterval(dataPoints: number): number {
  if (dataPoints <= 30) return 0 // Show all for short timeframes
  if (dataPoints <= 90) return Math.floor(dataPoints / 6)
  if (dataPoints <= 365) return Math.floor(dataPoints / 6)
  return Math.floor(dataPoints / 7) // ~7 ticks for multi-year
}

export function TimeframeSelector({
  value,
  onChange,
  className,
}: TimeframeSelectorProps) {
  return (
    <div className={cn('flex gap-1', className)}>
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf.value}
          type="button"
          aria-pressed={value === tf.value}
          onClick={() => onChange(tf.value)}
          className={cn(
            'px-2 py-0.5 text-xs font-medium rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
            value === tf.value
              ? 'bg-primary text-primary-foreground'
              : 'bg-surface-muted/50 text-text-muted hover:bg-surface-muted hover:text-text',
          )}
        >
          {tf.label}
        </button>
      ))}
    </div>
  )
}
