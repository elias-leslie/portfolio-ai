import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { WeightConfigurator } from '../../WeightConfigurator'

interface Weight {
  id: string
  label: string
  value: number
  description?: string
}

interface CollapsibleWeightCardProps {
  title: string
  weights: Weight[]
  onChange: (weights: Weight[]) => void
}

export function CollapsibleWeightCard({
  title,
  weights,
  onChange,
}: CollapsibleWeightCardProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card>
        <CardContent className="pt-6">
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-between p-0 hover:bg-transparent"
            >
              <h4 className="text-sm font-medium text-text">{title}</h4>
              <span className="text-xs text-text-muted">
                {isOpen ? '▼' : '▶'}
              </span>
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4">
            <WeightConfigurator
              title=""
              weights={weights}
              onChange={onChange}
            />
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  )
}
