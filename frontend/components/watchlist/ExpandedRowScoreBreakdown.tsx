'use client'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { ScoreComponent, WatchlistItem } from '@/lib/api/watchlist'
import { formatTimestamp, getScoreBadgeVariant } from './ExpandedRowUtils'

interface ExpandedRowScoreBreakdownProps {
  item: WatchlistItem
  userTimezone: string
}

// Pillar configuration with labels, tooltips, and display settings
const PILLAR_CONFIG = {
  price: {
    label: 'Price',
    icon: '💰',
    defaultWeight: 22,
    tooltip:
      'Price momentum based on recent price changes, volatility (beta), and relative volume. Higher scores indicate positive momentum.',
  },
  technical: {
    label: 'Technical',
    icon: '📊',
    defaultWeight: 22,
    tooltip:
      'Technical indicator analysis including RSI, MACD, trend strength, and Bollinger Bands. Higher scores indicate bullish technical setup.',
  },
  fundamental: {
    label: 'Fundamental',
    icon: '🏢',
    defaultWeight: 26,
    tooltip:
      'Financial health score combining valuation (P/E, PEG), growth metrics, balance sheet health, and analyst sentiment.',
  },
  catalyst: {
    label: 'Catalyst',
    icon: '📰',
    defaultWeight: 17,
    tooltip:
      'News catalyst impact score based on recent material events, earnings, and market-moving announcements.',
  },
  optionsFlow: {
    label: 'Options Flow',
    icon: '📈',
    defaultWeight: 8,
    tooltip:
      'Options market sentiment from call/put ratios, near-term positioning, and institutional flow concentration.',
  },
  performanceFactor: {
    label: 'Performance',
    icon: '🎯',
    defaultWeight: 5,
    tooltip:
      'Active strategy performance based on 30-day Sharpe ratio. Only shown when an active strategy exists.',
  },
} as const

type PillarKey = keyof typeof PILLAR_CONFIG

// Format metadata key for display
function formatMetadataKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/Pct/g, '%')
    .replace(/Rsi/g, 'RSI')
    .replace(/Macd/g, 'MACD')
    .replace(/Bb /g, 'BB ')
}

// Format value based on type
function formatValue(value: unknown): string {
  if (typeof value === 'number') {
    // Percentages
    if (Math.abs(value) <= 1 && value !== 0) {
      return `${(value * 100).toFixed(1)}%`
    }
    return value.toFixed(2)
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }
  return String(value ?? '—')
}

// Get score bar color class based on score value
function getScoreBarColor(score: number): string {
  if (score >= 70) return 'bg-gain'
  if (score >= 50) return 'bg-primary'
  if (score >= 30) return 'bg-warning'
  return 'bg-loss'
}

interface PillarCardProps {
  pillarKey: PillarKey
  pillar: ScoreComponent
  userTimezone: string
}

function PillarCard({ pillarKey, pillar, userTimezone }: PillarCardProps) {
  const config = PILLAR_CONFIG[pillarKey]
  const hasSubScores =
    pillar.subScores && Object.keys(pillar.subScores).length > 0
  const hasMetadata = pillar.metadata && Object.keys(pillar.metadata).length > 0
  const weightPercent = (
    (pillar.weight ?? config.defaultWeight / 100) * 100
  ).toFixed(0)

  return (
    <AccordionItem value={pillarKey} className="border-border">
      <AccordionTrigger className="hover:no-underline px-3 py-2">
        <div className="flex items-center gap-2 flex-1">
          <span className="text-lg">{config.icon}</span>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="font-medium cursor-help">{config.label}</span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-xs">{config.tooltip}</p>
            </TooltipContent>
          </Tooltip>
          {/* Score and bar - visible when collapsed */}
          <div className="flex items-center gap-2 ml-auto mr-2 flex-1 max-w-[200px]">
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-sm font-semibold min-w-[28px] text-right cursor-help">
                  {pillar.score.toFixed(0)}
                </span>
              </TooltipTrigger>
              <TooltipContent side="top">
                <p className="text-xs">Score: {pillar.score.toFixed(1)}/100</p>
              </TooltipContent>
            </Tooltip>
            <div className="flex-1 h-2 bg-surface-muted rounded-full overflow-hidden">
              <div
                className={cn('h-full transition-all', getScoreBarColor(pillar.score))}
                style={{
                  width: `${Math.max(0, Math.min(100, pillar.score))}%`,
                }}
              />
            </div>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-xs text-text-muted cursor-help">
                {weightPercent}%
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p className="text-xs">
                Weight: {weightPercent}% of overall score
              </p>
            </TooltipContent>
          </Tooltip>
          {pillar.stale && (
            <Badge variant="outline" className="text-xs font-normal">
              Stale
            </Badge>
          )}
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-3">
        <div className="space-y-3 pt-2">
          {/* Sub-scores */}
          {hasSubScores && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-text">Sub-scores:</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(pillar.subScores!).map(([key, value]) => (
                  <div
                    key={key}
                    className="bg-surface-muted/50 rounded px-2 py-1"
                  >
                    <p className="text-xs text-text-muted">
                      {formatMetadataKey(key)}
                    </p>
                    <p className="text-sm font-medium">
                      {typeof value === 'number' ? value.toFixed(1) : value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          {hasMetadata && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-text">Details:</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-xs">
                {Object.entries(pillar.metadata!)
                  .filter(
                    ([key]) =>
                      !['source', 'cached_at', 'formula'].includes(key),
                  )
                  .map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-text-muted">
                        {formatMetadataKey(key)}:
                      </span>
                      <span className="font-medium">{formatValue(value)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Updated timestamp */}
          {pillar.updatedAt && (
            <p className="text-xs text-text-muted pt-1 border-t border-border">
              Updated: {formatTimestamp(pillar.updatedAt, userTimezone)}
            </p>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}

/**
 * Score breakdown with expandable pillar cards
 *
 * Displays all 6 scoring pillars:
 * - Price (22%) - Price momentum and volatility
 * - Technical (22%) - Technical indicators
 * - Fundamental (26%) - Financial health (optional)
 * - Catalyst (17%) - News sentiment (optional)
 * - Options Flow (8%) - Options activity (optional)
 * - Performance Factor (5%) - Strategy performance (optional)
 *
 * Each pillar shows:
 * - Score badge with color coding
 * - Weight percentage
 * - Stale indicator if data is outdated
 * - Expandable details with sub-scores and metadata
 */
export function ExpandedRowScoreBreakdown({
  item,
  userTimezone,
}: ExpandedRowScoreBreakdownProps) {
  const score = item.currentScore

  if (!score) {
    return null
  }

  // Build list of available pillars
  const pillars: { key: PillarKey; data: ScoreComponent }[] = []

  // Always present pillars
  if (score.price) pillars.push({ key: 'price', data: score.price })
  if (score.technical) pillars.push({ key: 'technical', data: score.technical })

  // Optional pillars
  if (score.fundamental)
    pillars.push({ key: 'fundamental', data: score.fundamental })
  if (score.catalyst) pillars.push({ key: 'catalyst', data: score.catalyst })
  if (score.optionsFlow)
    pillars.push({ key: 'optionsFlow', data: score.optionsFlow })
  if (score.performanceFactor)
    pillars.push({ key: 'performanceFactor', data: score.performanceFactor })

  if (pillars.length === 0) {
    return null
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="border border-border rounded-lg bg-surface">
        <div className="px-3 py-2 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-medium">Score Breakdown</h3>
          <Badge variant={getScoreBadgeVariant(score.overall)}>
            Overall: {score.overall.toFixed(0)}
          </Badge>
        </div>
        <Accordion type="multiple" className="divide-y divide-border">
          {pillars.map(({ key, data }) => (
            <PillarCard
              key={key}
              pillarKey={key}
              pillar={data}
              userTimezone={userTimezone}
            />
          ))}
        </Accordion>
      </div>
    </TooltipProvider>
  )
}
