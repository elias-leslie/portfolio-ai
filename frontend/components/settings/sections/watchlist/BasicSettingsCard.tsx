import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RadioGroupOptions } from './RadioGroupOptions'
import { RefreshIntervalSlider } from './RefreshIntervalSlider'

interface BasicSettingsCardProps {
  defaultRefreshMinutes: number
  newsLookbackHours: number
  newsMaxArticles: number
  showNews: boolean
  autoExpand: boolean
  onDefaultRefreshMinutesChange: (value: number) => void
  onNewsLookbackHoursChange: (value: number) => void
  onNewsMaxArticlesChange: (value: number) => void
  onShowNewsChange: (value: boolean) => void
  onAutoExpandChange: (value: boolean) => void
}

export function BasicSettingsCard({
  defaultRefreshMinutes,
  newsLookbackHours,
  newsMaxArticles,
  showNews,
  autoExpand,
  onDefaultRefreshMinutesChange,
  onNewsLookbackHoursChange,
  onNewsMaxArticlesChange,
  onShowNewsChange,
  onAutoExpandChange,
}: BasicSettingsCardProps) {
  return (
    <Card>
      <CardContent className="space-y-6 pt-6">
        <h4 className="text-sm font-medium text-text">Basic Settings</h4>

        <RefreshIntervalSlider
          value={defaultRefreshMinutes}
          onChange={onDefaultRefreshMinutesChange}
          id="default-refresh-interval"
          label={`Default Refresh Interval: ${defaultRefreshMinutes} minutes`}
          description="Global default for all features (watchlist, portfolio, news). Each feature can override this in Advanced settings below."
        />

        <RadioGroupOptions
          label="News Lookback Window"
          value={newsLookbackHours}
          options={[
            { value: 6, label: '6 hours' },
            { value: 12, label: '12 hours' },
            { value: 24, label: '24 hours' },
            { value: 48, label: '48 hours' },
          ]}
          onChange={onNewsLookbackHoursChange}
          idPrefix="news-lookback"
          description="Controls how far back the News service samples headlines before calculating sentiment scores."
        />

        <RadioGroupOptions
          label="Max Headlines Per Symbol"
          value={newsMaxArticles}
          options={[
            { value: 5, label: '5 headlines' },
            { value: 10, label: '10 headlines' },
            { value: 15, label: '15 headlines' },
            { value: 20, label: '20 headlines' },
          ]}
          onChange={onNewsMaxArticlesChange}
          idPrefix="news-max"
          description="Sets the default number of headlines returned for each symbol and the Market view."
        />

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox
              id="toggle-news-visibility"
              checked={showNews}
              onCheckedChange={(checked) => onShowNewsChange(checked === true)}
            />
            <Label htmlFor="toggle-news-visibility" className="cursor-pointer">
              Show news sentiment and headlines in watchlist
            </Label>
          </div>
          <p className="text-xs text-text-muted">
            Disable this to hide the news expansion section for each symbol.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="auto-expand"
            checked={autoExpand}
            onCheckedChange={(checked) => onAutoExpandChange(checked === true)}
          />
          <Label
            htmlFor="auto-expand"
            className="cursor-pointer text-sm font-normal"
          >
            Auto-expand watchlist rows to show details
          </Label>
        </div>
      </CardContent>
    </Card>
  )
}
