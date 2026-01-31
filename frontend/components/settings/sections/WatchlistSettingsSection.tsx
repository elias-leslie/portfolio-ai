'use client'

import { Card, CardContent } from '@/components/ui/card'
import type {
  FundamentalSubWeights,
  ScoreWeights,
  TechnicalSubWeights,
} from '@/lib/api/preferences'
import { WeightConfigurator } from '../WeightConfigurator'
import { BasicSettingsCard } from './watchlist/BasicSettingsCard'
import { AdvancedOverridesCard } from './watchlist/AdvancedOverridesCard'
import { CollapsibleWeightCard } from './watchlist/CollapsibleWeightCard'
import { StaticSchedulesCard } from './watchlist/StaticSchedulesCard'

interface WatchlistSettingsSectionProps {
  defaultRefreshMinutes: number
  watchlistOverride: number | null
  newsOverride: number | null
  newsLookbackHours: number
  newsMaxArticles: number
  showNews: boolean
  autoExpand: boolean
  scoreWeights: ScoreWeights
  technicalSubWeights: TechnicalSubWeights
  fundamentalSubWeights: FundamentalSubWeights
  onDefaultRefreshMinutesChange: (value: number) => void
  onWatchlistOverrideChange: (value: number | null) => void
  onNewsOverrideChange: (value: number | null) => void
  onNewsLookbackHoursChange: (value: number) => void
  onNewsMaxArticlesChange: (value: number) => void
  onShowNewsChange: (value: boolean) => void
  onAutoExpandChange: (value: boolean) => void
  onScoreWeightsChange: (value: ScoreWeights) => void
  onTechnicalSubWeightsChange: (value: TechnicalSubWeights) => void
  onFundamentalSubWeightsChange: (value: FundamentalSubWeights) => void
}

export function WatchlistSettingsSection({
  defaultRefreshMinutes,
  watchlistOverride,
  newsOverride,
  newsLookbackHours,
  newsMaxArticles,
  showNews,
  autoExpand,
  scoreWeights,
  technicalSubWeights,
  fundamentalSubWeights,
  onDefaultRefreshMinutesChange,
  onWatchlistOverrideChange,
  onNewsOverrideChange,
  onNewsLookbackHoursChange,
  onNewsMaxArticlesChange,
  onShowNewsChange,
  onAutoExpandChange,
  onScoreWeightsChange,
  onTechnicalSubWeightsChange,
  onFundamentalSubWeightsChange,
}: WatchlistSettingsSectionProps) {
  return (
    <div className="space-y-6">
      <BasicSettingsCard
        defaultRefreshMinutes={defaultRefreshMinutes}
        newsLookbackHours={newsLookbackHours}
        newsMaxArticles={newsMaxArticles}
        showNews={showNews}
        autoExpand={autoExpand}
        onDefaultRefreshMinutesChange={onDefaultRefreshMinutesChange}
        onNewsLookbackHoursChange={onNewsLookbackHoursChange}
        onNewsMaxArticlesChange={onNewsMaxArticlesChange}
        onShowNewsChange={onShowNewsChange}
        onAutoExpandChange={onAutoExpandChange}
      />

      <AdvancedOverridesCard
        defaultRefreshMinutes={defaultRefreshMinutes}
        watchlistOverride={watchlistOverride}
        newsOverride={newsOverride}
        onWatchlistOverrideChange={onWatchlistOverrideChange}
        onNewsOverrideChange={onNewsOverrideChange}
      />

      <Card>
        <CardContent className="pt-6">
          <WeightConfigurator
            title="Main Score Weights"
            weights={[
              { id: 'price', label: 'Price', value: scoreWeights.price },
              {
                id: 'technical',
                label: 'Technical',
                value: scoreWeights.technical,
              },
              {
                id: 'fundamental',
                label: 'Fundamental',
                value: scoreWeights.fundamental,
              },
            ]}
            onChange={(weights) => {
              onScoreWeightsChange({
                price: weights.find((w) => w.id === 'price')?.value ?? 33,
                technical:
                  weights.find((w) => w.id === 'technical')?.value ?? 33,
                fundamental:
                  weights.find((w) => w.id === 'fundamental')?.value ?? 34,
              })
            }}
          />
        </CardContent>
      </Card>

      <CollapsibleWeightCard
        title="Technical Sub-Weights (Advanced)"
        weights={[
          {
            id: 'rsi_14',
            label: 'RSI',
            value: technicalSubWeights.rsi14,
          },
          {
            id: 'trend',
            label: 'Trend',
            value: technicalSubWeights.trend,
          },
          {
            id: 'macd',
            label: 'MACD',
            value: technicalSubWeights.macd,
          },
        ]}
        onChange={(weights) => {
          onTechnicalSubWeightsChange({
            rsi14: weights.find((w) => w.id === 'rsi_14')?.value ?? 33,
            trend: weights.find((w) => w.id === 'trend')?.value ?? 34,
            macd: weights.find((w) => w.id === 'macd')?.value ?? 33,
          })
        }}
      />

      <CollapsibleWeightCard
        title="Fundamental Sub-Weights (Advanced)"
        weights={[
          {
            id: 'valuation',
            label: 'Valuation',
            value: fundamentalSubWeights.valuation,
            description: 'P/E, PEG, relative multiples',
          },
          {
            id: 'growth',
            label: 'Growth',
            value: fundamentalSubWeights.growth,
            description: 'Revenue/earnings growth metrics',
          },
          {
            id: 'health',
            label: 'Health',
            value: fundamentalSubWeights.health,
            description: 'Margins, ROIC, cash flow',
          },
          {
            id: 'sentiment',
            label: 'Sentiment',
            value: fundamentalSubWeights.sentiment,
            description: 'Analyst ratings, institutional activity',
          },
        ]}
        onChange={(weights) => {
          onFundamentalSubWeightsChange({
            valuation:
              weights.find((w) => w.id === 'valuation')?.value ?? 30,
            growth: weights.find((w) => w.id === 'growth')?.value ?? 35,
            health: weights.find((w) => w.id === 'health')?.value ?? 25,
            sentiment:
              weights.find((w) => w.id === 'sentiment')?.value ?? 10,
          })
        }}
      />

      <StaticSchedulesCard />
    </div>
  )
}
