import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { FeatureOverrideSection } from './FeatureOverrideSection'

interface AdvancedOverridesCardProps {
  defaultRefreshMinutes: number
  watchlistOverride: number | null
  newsOverride: number | null
  onWatchlistOverrideChange: (value: number | null) => void
  onNewsOverrideChange: (value: number | null) => void
}

export function AdvancedOverridesCard({
  defaultRefreshMinutes,
  watchlistOverride,
  newsOverride,
  onWatchlistOverrideChange,
  onNewsOverrideChange,
}: AdvancedOverridesCardProps) {
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
              <span className="text-sm font-medium">
                Advanced: Per-Feature Overrides
              </span>
              <span className="text-xs text-text-muted">
                {isOpen ? '▼' : '▶'}
              </span>
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4 space-y-4">
            <FeatureOverrideSection
              featureName="Watchlist"
              overrideValue={watchlistOverride}
              defaultValue={defaultRefreshMinutes}
              onChange={onWatchlistOverrideChange}
              idPrefix="watchlist"
            />
            <FeatureOverrideSection
              featureName="News"
              overrideValue={newsOverride}
              defaultValue={defaultRefreshMinutes}
              onChange={onNewsOverrideChange}
              idPrefix="news"
            />
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  )
}
