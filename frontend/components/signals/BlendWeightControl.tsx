'use client'

import { Sliders } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

const STORAGE_KEY = 'signals:blend-weight-scanner'
const DEFAULT_SCANNER_PCT = 60

export function loadStoredScannerPct(): number {
  if (typeof window === 'undefined') return DEFAULT_SCANNER_PCT
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw === null) return DEFAULT_SCANNER_PCT
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) return DEFAULT_SCANNER_PCT
    return Math.max(0, Math.min(100, Math.round(parsed)))
  } catch {
    return DEFAULT_SCANNER_PCT
  }
}

export interface BlendWeightControlProps {
  /** Scanner weight as 0-100 (committee weight = 100 - this). */
  value: number
  onChange: (scannerPct: number) => void
  /** Hide the helper label below the slider (compact contexts). */
  compact?: boolean
  className?: string
}

export function BlendWeightControl({
  value,
  onChange,
  compact = false,
  className,
}: BlendWeightControlProps) {
  const [local, setLocal] = useState(value)

  useEffect(() => {
    setLocal(value)
  }, [value])

  const commit = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(100, Math.round(next)))
      setLocal(clamped)
      onChange(clamped)
      try {
        window.localStorage.setItem(STORAGE_KEY, String(clamped))
      } catch {
        // localStorage may be unavailable (private mode, etc.) — ignore
      }
    },
    [onChange],
  )

  const committeePct = 100 - local

  return (
    <div
      className={cn(
        'rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-text-muted">
          <Sliders className="h-3.5 w-3.5" />
          Blend weight
        </div>
        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="text-[#00f5ff]">Scanner {local}%</span>
          <span className="text-text-muted">/</span>
          <span className="text-[#a855f7]">Committee {committeePct}%</span>
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={local}
        onChange={(e) => setLocal(Number(e.target.value))}
        onMouseUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
        onTouchEnd={(e) => commit(Number((e.target as HTMLInputElement).value))}
        onKeyUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
        className="mt-3 w-full accent-primary"
        aria-label="Scanner versus committee blend weight"
      />
      {!compact ? (
        <p className="mt-2 text-[11px] text-text-muted">
          Scanner weight / committee weight
        </p>
      ) : null}
    </div>
  )
}
