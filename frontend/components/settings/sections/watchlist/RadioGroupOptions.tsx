import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

interface RadioGroupOptionsProps {
  label: string
  value: number
  options: Array<{ value: number; label: string }>
  onChange: (value: number) => void
  description?: string
  idPrefix: string
}

export function RadioGroupOptions({
  label,
  value,
  options,
  onChange,
  description,
  idPrefix,
}: RadioGroupOptionsProps) {
  return (
    <div className="space-y-3">
      <Label>{label}</Label>
      <RadioGroup
        value={String(value)}
        onValueChange={(val) => onChange(Number(val))}
        className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3"
      >
        {options.map((option) => (
          <div
            key={option.value}
            className="flex items-center space-x-2 rounded-md border border-border/60 px-3 py-2"
          >
            <RadioGroupItem
              id={`${idPrefix}-${option.value}`}
              value={String(option.value)}
            />
            <Label
              htmlFor={`${idPrefix}-${option.value}`}
              className="cursor-pointer"
            >
              {option.label}
            </Label>
          </div>
        ))}
      </RadioGroup>
      {description && <p className="text-xs text-text-muted">{description}</p>}
    </div>
  )
}
