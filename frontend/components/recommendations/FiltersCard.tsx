import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface FiltersCardProps {
  minStrength: number
  onMinStrengthChange: (value: number) => void
  portfolioSize: number
  onPortfolioSizeChange: (value: number) => void
}

export function FiltersCard({
  minStrength,
  onMinStrengthChange,
  portfolioSize,
  onPortfolioSizeChange,
}: FiltersCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Filters</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Min Signal Strength: {minStrength}</Label>
            <Slider
              value={[minStrength]}
              onValueChange={(v) => onMinStrengthChange(v[0])}
              min={1}
              max={10}
              step={1}
            />
          </div>
          <div className="space-y-2">
            <Label>Portfolio Size: ${portfolioSize.toLocaleString()}</Label>
            <Slider
              value={[portfolioSize]}
              onValueChange={(v) => onPortfolioSizeChange(v[0])}
              min={10000}
              max={1000000}
              step={10000}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
