import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { RefreshIntervalSlider } from './RefreshIntervalSlider'

interface FeatureOverrideSectionProps {
  featureName: string
  overrideValue: number | null
  defaultValue: number
  onChange: (value: number | null) => void
  idPrefix: string
}

export function FeatureOverrideSection({
  featureName,
  overrideValue,
  defaultValue,
  onChange,
  idPrefix,
}: FeatureOverrideSectionProps) {
  return (
    <div className="space-y-3 rounded-md border border-border bg-surface-muted/30 p-4">
      <Label className="text-sm font-medium">{featureName} Refresh</Label>
      <RadioGroup
        value={overrideValue === null ? 'default' : 'custom'}
        onValueChange={(value) =>
          onChange(value === 'custom' ? defaultValue : null)
        }
      >
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="default" id={`${idPrefix}-default`} />
          <Label
            htmlFor={`${idPrefix}-default`}
            className="cursor-pointer font-normal"
          >
            Use Default ({defaultValue} min)
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="custom" id={`${idPrefix}-custom`} />
          <Label
            htmlFor={`${idPrefix}-custom`}
            className="cursor-pointer font-normal"
          >
            Custom Interval
          </Label>
        </div>
      </RadioGroup>

      {overrideValue !== null && (
        <div className="mt-3">
          <RefreshIntervalSlider
            value={overrideValue}
            onChange={onChange}
            id={`${idPrefix}-override-slider`}
            label={`${featureName} Interval: ${overrideValue} minutes`}
          />
        </div>
      )}
      <p className="text-xs text-text-muted">
        Effective interval: {overrideValue ?? defaultValue} minutes
      </p>
    </div>
  )
}
