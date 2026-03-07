'use client'

import { ExternalLink, Plus, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { BacktestDetails } from '@/components/backtest/BacktestDetails'
import { BacktestRunsList } from '@/components/backtest/BacktestRunsList'
import { NewBacktestDialog } from '@/components/backtest/NewBacktestDialog'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { useBacktestRuns } from '@/lib/hooks/useBacktest'
import { useGenerateStrategiesBatch } from '@/lib/hooks/useStrategies'

function BacktestPageContent() {
  const searchParams = useSearchParams()
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [newBacktestOpen, setNewBacktestOpen] = useState(false)
  const [comparisonMode, setComparisonMode] = useState(false)
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set())

  const { data: runs, isLoading } = useBacktestRuns()

  useEffect(() => {
    const runIdParam = searchParams?.get('runId')
    if (runIdParam && runs && runs.length > 0 && !selectedRunId) {
      const targetRun = runs.find((run) => run.id === runIdParam)
      if (targetRun) {
        setSelectedRunId(runIdParam)
      } else if (runIdParam === 'first' || runIdParam === 'latest') {
        setSelectedRunId(runs[0].id)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, runs, selectedRunId])
  const generateBatch = useGenerateStrategiesBatch()

  const handleSelectRun = (runId: string) => {
    if (comparisonMode) {
      setSelectedRunIds((previous) => {
        const next = new Set(previous)
        if (next.has(runId)) {
          next.delete(runId)
        } else if (next.size < 5) {
          next.add(runId)
        }
        return next
      })
    } else {
      setSelectedRunId(runId)
    }
  }

  const toggleComparisonMode = () => {
    if (!comparisonMode) {
      setSelectedRunIds(new Set())
      setSelectedRunId(null)
    } else {
      setSelectedRunIds(new Set())
    }
    setComparisonMode(!comparisonMode)
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Backtesting"
        description="Strategy validation with historical data"
        size="md"
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => generateBatch.mutate({ topN: 20 })}
              disabled={generateBatch.isPending}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {generateBatch.isPending
                ? 'Generating...'
                : 'Generate Strategies'}
            </Button>
            <Link href="/strategies">
              <Button variant="ghost">
                <ExternalLink className="mr-2 h-4 w-4" />
                View Strategies
              </Button>
            </Link>
            <Button onClick={() => setNewBacktestOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New Backtest
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4 xl:col-span-3">
          <BacktestRunsList
            runs={runs || []}
            isLoading={isLoading}
            selectedRunId={selectedRunId}
            comparisonMode={comparisonMode}
            selectedRunIds={selectedRunIds}
            onSelectRun={handleSelectRun}
            onToggleComparison={toggleComparisonMode}
          />
        </div>

        <div className="lg:col-span-8 xl:col-span-9">
          <BacktestDetails
            runId={selectedRunId}
            comparisonMode={comparisonMode}
            comparisonRunIds={Array.from(selectedRunIds)}
          />
        </div>
      </div>

      <NewBacktestDialog
        open={newBacktestOpen}
        onOpenChange={setNewBacktestOpen}
      />
    </PageContainer>
  )
}

export function BacktestPageClient() {
  return (
    <Suspense fallback={<div className="p-10">Loading...</div>}>
      <BacktestPageContent />
    </Suspense>
  )
}
