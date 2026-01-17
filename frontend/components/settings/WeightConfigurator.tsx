'use client'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'

interface WeightItem {
  id: string
  label: string
  value: number
  description?: string
}

interface WeightConfiguratorProps {
  title: string
  weights: WeightItem[]
  onChange: (weights: WeightItem[]) => void
  className?: string
  showTotal?: boolean
  allowManualInput?: boolean
}

export function WeightConfigurator({
  title,
  weights,
  onChange,
  className,
  showTotal = true,
  allowManualInput = false,
}: WeightConfiguratorProps) {
  const total = weights.reduce((sum, w) => sum + w.value, 0)
  const isValid = Math.abs(total - 100) < 0.1

  const handleEqualWeights = () => {
    const equalValue = 100 / weights.length
    const newWeights = weights.map((w, idx) => ({
      ...w,
      value: idx === 0 ? 100 - equalValue * (weights.length - 1) : equalValue,
    }))
    onChange(newWeights)
  }

  const handleSliderChange = (id: string, value: number) => {
    const newWeights = weights.map((w) => (w.id === id ? { ...w, value } : w))
    onChange(newWeights)
  }

  const handleInputChange = (id: string, value: string) => {
    const numValue = parseFloat(value)
    if (Number.isNaN(numValue)) return
    handleSliderChange(id, Math.max(0, Math.min(100, numValue)))
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-text">{title}</h4>
        <Button
          variant="outline"
          size="sm"
          onClick={handleEqualWeights}
          className="h-8"
        >
          Equal Weights
        </Button>
      </div>

      {weights.map((weight) => (
        <div key={weight.id} className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor={`weight-${weight.id}`} className="text-sm">
              {weight.label}
            </Label>
            {allowManualInput ? (
              <Input
                id={`weight-input-${weight.id}`}
                type="number"
                value={weight.value.toFixed(1)}
                onChange={(e) => handleInputChange(weight.id, e.target.value)}
                className="h-8 w-20 text-right"
                min={0}
                max={100}
                step={0.1}
              />
            ) : (
              <span className="text-sm font-medium text-text">
                {weight.value.toFixed(1)}%
              </span>
            )}
          </div>
          <Slider
            id={`weight-${weight.id}`}
            min={0}
            max={100}
            step={0.1}
            value={[weight.value]}
            onValueChange={(value) => handleSliderChange(weight.id, value[0])}
            className="w-full"
            aria-label={`${weight.label} weight percentage`}
          />
          {weight.description && (
            <p className="text-xs text-text-muted">{weight.description}</p>
          )}
        </div>
      ))}

      {showTotal && (
        <div className="flex items-center justify-between border-t border-border pt-3">
          <span className="text-sm text-text-muted">Total</span>
          <span
            className={cn(
              'text-sm font-semibold',
              isValid ? 'text-text' : 'text-loss',
            )}
          >
            {total.toFixed(1)}%{!isValid && ' (must be 100%)'}
          </span>
        </div>
      )}
    </div>
  )
}
