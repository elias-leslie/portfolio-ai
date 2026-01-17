'use client'

import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface WeightSliderProps {
  /** Unique identifier for the slider */
  id: string
  /** Display label for the weight */
  label: string
  /** Current value (0-100) */
  value: number
  /** Callback when value changes */
  onChange: (value: number) => void
  /** Optional description text below the slider */
  description?: string
}

/**
 * Reusable weight slider component for score weight configuration.
 *
 * Used in WatchlistPreferences for:
 * - Main score weights (Price, Technical, Fundamental)
 * - Technical sub-weights (RSI, Trend, MACD)
 * - Fundamental sub-weights (Valuation, Growth, Health, Sentiment)
 */
export function WeightSlider({
  id,
  label,
  value,
  onChange,
  description,
}: WeightSliderProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {label}: {value.toFixed(1)}%
      </Label>
      <Slider
        id={id}
        min={0}
        max={100}
        step={0.1}
        value={[value]}
        onValueChange={(values) => onChange(values[0])}
        className="w-full"
        aria-label={`${label} weight percentage`}
      />
      {description && <p className="text-xs text-text-muted">{description}</p>}
    </div>
  )
}
