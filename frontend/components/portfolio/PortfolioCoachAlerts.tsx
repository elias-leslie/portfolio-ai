'use client'

import { AlertTriangle, CheckCircle2, ScissorsLineDashed } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { PortfolioAnalytics, PortfolioResponse } from '@/lib/api/portfolio'
import { formatDisplayLabel } from './portfolio-utils'

interface PortfolioCoachAlertsProps {
  portfolio: PortfolioResponse
  analytics: PortfolioAnalytics
}

type CoachAlert = {
  title: string
  detail: string
  tone: 'warning' | 'caution' | 'calm'
}

function buildCoachAlerts(
  portfolio: PortfolioResponse,
  analytics: PortfolioAnalytics,
): CoachAlert[] {
  const alerts: CoachAlert[] = []
  const positions = [...portfolio.positions].sort(
    (left, right) => right.currentValue - left.currentValue,
  )
  const largestPosition = positions[0]
  const strongestWinner = [...positions]
    .filter((position) => position.gainPct >= 15)
    .sort((left, right) => right.gainPct - left.gainPct)[0]
  const weakestLoser = [...positions]
    .filter((position) => position.gainPct <= -10)
    .sort((left, right) => left.gainPct - right.gainPct)[0]

  const topSector = Object.entries(analytics.sectorExposure).sort(
    ([, left], [, right]) => right - left,
  )[0]

  if (
    analytics.concentration.topHoldingPct >= 15 &&
    largestPosition
  ) {
    alerts.push({
      title: `Trim candidate: ${largestPosition.symbol}`,
      detail: `${largestPosition.symbol} is ${analytics.concentration.topHoldingPct.toFixed(1)}% of your portfolio. If that is larger than you intended, scale it back instead of letting one stock decide your month.`,
      tone: 'warning',
    })
  }

  if (topSector && topSector[1] >= 35) {
    const sectorLabel = formatDisplayLabel(topSector[0])
    alerts.push({
      title: `Too much in one area: ${sectorLabel}`,
      detail: `${sectorLabel} now makes up ${topSector[1].toFixed(1)}% of your portfolio. A good stock can still hurt you if too many positions depend on the same story.`,
      tone: 'caution',
    })
  }

  if (strongestWinner) {
    const weightPct =
      portfolio.totalValue > 0
        ? (strongestWinner.currentValue / portfolio.totalValue) * 100
        : 0
    if (weightPct >= 10) {
      alerts.push({
        title: `Lock in discipline on ${strongestWinner.symbol}`,
        detail: `${strongestWinner.symbol} is up ${strongestWinner.gainPct.toFixed(1)}% and now weighs ${weightPct.toFixed(1)}% of the portfolio. Decide now whether to keep riding it or trim some profit.`,
        tone: 'caution',
      })
    }
  }

  if (weakestLoser) {
    alerts.push({
      title: `Recheck the thesis on ${weakestLoser.symbol}`,
      detail: `${weakestLoser.symbol} is down ${Math.abs(weakestLoser.gainPct).toFixed(1)}% from your cost basis. Before adding more, confirm the reason you bought it still holds.`,
      tone: 'warning',
    })
  }

  if (alerts.length === 0) {
    alerts.push({
      title: 'No urgent action',
      detail:
        'Nothing stands out as oversized or badly off track right now. Staying put is a valid decision.',
      tone: 'calm',
    })
  }

  return alerts.slice(0, 4)
}

function toneClasses(tone: CoachAlert['tone']) {
  switch (tone) {
    case 'warning':
      return {
        border: 'border-loss/30 bg-loss/10',
        icon: 'text-loss',
        iconNode: <AlertTriangle className="h-4 w-4" />,
      }
    case 'caution':
      return {
        border: 'border-warning/30 bg-warning/10',
        icon: 'text-warning',
        iconNode: <ScissorsLineDashed className="h-4 w-4" />,
      }
    default:
      return {
        border: 'border-gain/30 bg-gain/10',
        icon: 'text-gain',
        iconNode: <CheckCircle2 className="h-4 w-4" />,
      }
  }
}

export function PortfolioCoachAlerts({
  portfolio,
  analytics,
}: PortfolioCoachAlertsProps) {
  const alerts = buildCoachAlerts(portfolio, analytics)

  return (
    <Card className="p-6">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-text">Coach Alerts</h3>
        <p className="mt-1 text-sm text-text-muted">
          Simple prompts for when to trim, review, or do nothing.
        </p>
      </div>

      <div className="space-y-3">
        {alerts.map((alert) => {
          const styles = toneClasses(alert.tone)
          return (
            <div
              key={alert.title}
              className={`rounded-xl border p-4 ${styles.border}`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 ${styles.icon}`}>{styles.iconNode}</div>
                <div>
                  <p className="text-sm font-semibold text-text">{alert.title}</p>
                  <p className="mt-1 text-sm text-text-muted">{alert.detail}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
