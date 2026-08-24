'use client'

import { cn } from '@/lib/utils'

export interface CapBarProps {
  /** What the reported month actually spent in this category. */
  actual: number
  /** The cap that governs it, or null when nothing does. */
  cap: number | null
  label: string
}

/**
 * This month's spend against its cap, as a length.
 *
 * The fill stops at the cap: a category at 300% of its cap draws the same full
 * bar as one at 101%, and the overflow is stated in money beside it rather than
 * drawn as a bar three times longer than every other row. A bar that can run off
 * the end makes the biggest breach the least legible one, which is backwards.
 *
 * The tick sits where the cap is, so an under-budget row reads as a distance
 * from the mark rather than as an unlabelled fraction.
 */
export function CapBar({ actual, cap, label }: CapBarProps) {
  if (cap == null || cap <= 0) {
    return null
  }
  const ratio = actual / cap
  const filled = Math.max(0, Math.min(ratio, 1))
  const isOver = ratio > 1

  return (
    <div
      className="relative mt-1.5 h-1.5 w-full max-w-[220px] overflow-hidden rounded-full bg-surface-muted/40"
      role="img"
      aria-label={`${label}: ${Math.round(ratio * 100)}% of cap`}
    >
      <div
        className={cn(
          'h-full rounded-full transition-[width]',
          isOver ? 'bg-loss' : 'bg-gain',
        )}
        style={{ width: `${filled * 100}%` }}
      />
      {/* The cap itself, drawn where the fill would end at exactly 100%. */}
      <div className="absolute inset-y-0 right-0 w-px bg-border" />
    </div>
  )
}
