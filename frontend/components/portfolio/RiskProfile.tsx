'use client'

import { AlertTriangle, Shield } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { RiskProfile as RiskProfileType } from '@/lib/api/portfolio'
import { cn } from '@/lib/utils'

interface RiskProfileProps {
  riskProfile: RiskProfileType
}

export function RiskProfile({ riskProfile }: RiskProfileProps) {
  const getLevelColor = (level: string) => {
    switch (level) {
      case 'Conservative':
        return 'text-gain'
      case 'Moderate':
        return 'text-accent'
      case 'Aggressive':
        return 'text-warning'
      case 'Very Aggressive':
        return 'text-loss'
      default:
        return 'text-text-muted'
    }
  }

  const getBgColor = (level: string) => {
    switch (level) {
      case 'Conservative':
        return 'bg-gain/20'
      case 'Moderate':
        return 'bg-accent/20'
      case 'Aggressive':
        return 'bg-warning/20'
      case 'Very Aggressive':
        return 'bg-loss/20'
      default:
        return 'bg-surface-muted'
    }
  }

  const getIcon = (level: string) => {
    if (level === 'Conservative' || level === 'Moderate') {
      return <Shield className="h-4 w-4" />
    }
    return <AlertTriangle className="h-4 w-4" />
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={getLevelColor(riskProfile.level)}>
            {getIcon(riskProfile.level)}
          </span>
          <h3 className="text-sm font-semibold text-text">Risk Profile</h3>
        </div>
        <span
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium',
            getBgColor(riskProfile.level),
            getLevelColor(riskProfile.level),
          )}
        >
          {riskProfile.level}
        </span>
      </div>

      {/* Risk Score */}
      <div className="mb-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="font-display text-3xl text-text">
            {riskProfile.score.toFixed(0)}
          </span>
          <span className="text-xs text-text-muted">/ 100</span>
        </div>
      </div>

      {/* Risk Factors */}
      <div className="space-y-2 border-t border-border/40 pt-4">
        {Object.entries(riskProfile.factors).map(([key, value]) => (
          <div key={key} className="flex justify-between items-start gap-2">
            <span className="text-xs font-medium capitalize text-text-muted">
              {key}:
            </span>
            <span className="text-xs text-right text-text">{value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
