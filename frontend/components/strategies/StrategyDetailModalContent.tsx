'use client'

import { Archive, CheckCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useUpdateStrategyStatus } from '@/lib/hooks/useStrategies'
import type { StrategyDetail } from '@/lib/api/strategies'
import { SeedEvolution } from './SeedEvolution'
import {
  BacktestMetricRow,
  CollapsibleSection,
  MetricCard,
  ResearchGrid,
  formatParamKey,
  statusColors,
} from './StrategyDetailModalHelpers'

interface StrategyDetailModalContentProps {
  strategy: StrategyDetail
}

export function StrategyDetailModalContent({
  strategy,
}: StrategyDetailModalContentProps) {
  const updateStatus = useUpdateStrategyStatus()
  const [researchOpen, setResearchOpen] = useState(false)
  const [parametersOpen, setParametersOpen] = useState(false)
  const [backtestOpen, setBacktestOpen] = useState(false)

  const handleActivate = () => {
    updateStatus.mutate({ strategyId: strategy.id, request: { status: 'active' } })
  }

  const handleArchive = () => {
    const reason = prompt('Enter archive reason:')
    if (reason) {
      updateStatus.mutate({
        strategyId: strategy.id,
        request: { status: 'archived', archiveReason: reason },
      })
    }
  }

  return (
    <>
      <DialogHeader>
        <div className="flex items-center gap-3">
          <DialogTitle className="text-xl">{strategy.name}</DialogTitle>
          <Badge variant="outline" className={statusColors[strategy.status]}>
            {strategy.status}
          </Badge>
        </div>
        <DialogDescription>
          {strategy.symbol} &bull; {strategy.strategyType} strategy &bull;
          v{strategy.version}
        </DialogDescription>
      </DialogHeader>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Expected Sharpe" value={strategy.expectedSharpe?.toFixed(2) || '-'} />
        <MetricCard
          label="Expected Win Rate"
          value={strategy.expectedWinRate != null ? `${(strategy.expectedWinRate * 100).toFixed(0)}%` : '-'}
        />
        <MetricCard
          label="Max Drawdown"
          value={strategy.expectedMaxDrawdown != null ? `${(strategy.expectedMaxDrawdown * 100).toFixed(1)}%` : '-'}
        />
        <MetricCard label="Live Trades" value={strategy.liveTradesCount.toString()} />
      </div>

      <SeedEvolution strategyId={strategy.id} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Generation Reasoning</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-muted">{strategy.generationReasoning}</p>
        </CardContent>
      </Card>

      <CollapsibleSection title="Research Summary" open={researchOpen} onOpenChange={setResearchOpen}>
        <ResearchGrid summary={strategy.researchSummary} />
      </CollapsibleSection>

      <CollapsibleSection title="Strategy Parameters" open={parametersOpen} onOpenChange={setParametersOpen}>
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
          {Object.entries(strategy.parameters).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span className="text-text-muted">{formatParamKey(key)}:</span>
              <span className="font-mono">
                {typeof value === 'number' ? value.toFixed(2) : String(value)}
              </span>
            </div>
          ))}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title={`Walk-Forward Backtest Results (${strategy.backtestMetrics.length} windows)`}
        open={backtestOpen}
        onOpenChange={setBacktestOpen}
      >
        <div className="space-y-2">
          {strategy.backtestMetrics.map((metric, i) => (
            <BacktestMetricRow key={i} metric={metric} />
          ))}
        </div>
      </CollapsibleSection>

      <div className="flex justify-end gap-2">
        {strategy.status === 'testing' && (
          <Button onClick={handleActivate} disabled={updateStatus.isPending}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Activate
          </Button>
        )}
        {strategy.status !== 'archived' && (
          <Button variant="outline" onClick={handleArchive} disabled={updateStatus.isPending}>
            <Archive className="mr-2 h-4 w-4" />
            Archive
          </Button>
        )}
      </div>
    </>
  )
}
