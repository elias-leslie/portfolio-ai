/**
 * Trading Rules Viewer Component
 *
 * Displays all trading rules from rules.yaml in expandable sections
 */

'use client'

import { Download, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { buildApiUrl } from '@/lib/api-config'
import { useRules } from '@/lib/hooks/useRules'
import { CatalystImpactsCard } from './CatalystImpactsCard'
import { RuleSectionCard } from './RuleSectionCard'

interface ExpandedSections {
  [key: string]: boolean
}

export function RulesViewer() {
  const { data: rules, isLoading, error, refetch, isFetching } = useRules()
  const [expandedSections, setExpandedSections] = useState<ExpandedSections>({})
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = async (format: 'yaml' | 'json') => {
    setIsExporting(true)
    try {
      const response = await fetch(
        buildApiUrl(`/api/rules/export?format=${format}`),
      )
      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const filename =
        response.headers
          .get('Content-Disposition')
          ?.match(/filename="(.+)"/)?.[1] || `trading_rules.${format}`

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast.success(`Rules exported as ${format.toUpperCase()}`)
    } catch {
      toast.error('Failed to export rules')
    } finally {
      setIsExporting(false)
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load trading rules."
        detail="Retry to refresh the current risk, sizing, and watchlist rules."
        onRetry={() => { void refetch() }}
        isRetrying={isFetching}
      />
    )
  }

  if (!rules) return null

  const sections: [string, Record<string, unknown>][] = [
    ['position_sizing', rules.positionSizing as Record<string, unknown>],
    ['risk_management', rules.riskManagement as Record<string, unknown>],
    ['technical_thresholds', rules.technicalThresholds as Record<string, unknown>],
    ['scoring', rules.scoring as Record<string, unknown>],
    ['fundamentals', rules.fundamentals as Record<string, unknown>],
    ['signals', rules.signals as Record<string, unknown>],
    ['fees', rules.fees as Record<string, unknown>],
    ['compliance', rules.compliance as Record<string, unknown>],
    ['market', rules.market as Record<string, unknown>],
    ['paper_trading', rules.paperTrading as Record<string, unknown>],
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Trading Rules</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Version {rules.version} - Updated {rules.updated} by {rules.updatedBy}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={isExporting}>
              {isExporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Export
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleExport('yaml')}>
              Export as YAML
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport('json')}>
              Export as JSON
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-gain">
            {(rules.positionSizing.defaultRiskPercent * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-muted-foreground">Default Risk/Trade</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-loss">
            {rules.riskManagement.portfolioDrawdownHaltPct.toFixed(0)}%
          </div>
          <div className="text-sm text-muted-foreground">Drawdown Halt</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-accent">
            {rules.watchlistManagement.maxWatchlistSize}
          </div>
          <div className="text-sm text-muted-foreground">Max Watchlist</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-accent">
            {Object.keys(rules.catalystImpacts).length}
          </div>
          <div className="text-sm text-muted-foreground">Catalyst Events</div>
        </div>
      </div>

      {/* Rule Sections */}
      <div className="space-y-3">
        {sections.map(([title, data]) => (
          <RuleSectionCard
            key={title}
            title={title}
            data={data}
            isExpanded={!!expandedSections[title]}
            onToggle={toggleSection}
          />
        ))}
        <CatalystImpactsCard
          data={rules.catalystImpacts}
          isExpanded={!!expandedSections.catalyst_impacts}
          onToggle={toggleSection}
        />
        <RuleSectionCard
          title="watchlist_management"
          data={rules.watchlistManagement as Record<string, unknown>}
          isExpanded={!!expandedSections.watchlist_management}
          onToggle={toggleSection}
        />
      </div>
    </div>
  )
}
