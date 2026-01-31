import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface RefreshIntervalSliderProps {
  value: number
  onChange: (value: number) => void
  id?: string
  label?: string
  description?: string
}

export function RefreshIntervalSlider({
  value,
  onChange,
  id = 'refresh-interval',
  label = `Refresh Interval: ${value} minutes`,
  description,
}: RefreshIntervalSliderProps) {
  return (
    <div className="space-y-3">
      <Label htmlFor={id}>{label}</Label>
      <Slider
        id={id}
        min={1}
        max={60}
        step={1}
        value={[value]}
        onValueChange={(val) => onChange(val[0])}
        className="w-full"
        aria-label="Refresh interval in minutes"
      />
      {description && <p className="text-xs text-text-muted">{description}</p>}
    </div>
  )
}
