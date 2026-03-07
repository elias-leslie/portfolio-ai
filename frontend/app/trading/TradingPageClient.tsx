'use client'

import { ExternalLink, Plus, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { NewOrderDialog } from '@/components/trading/NewOrderDialog'
import { PipelineControls } from '@/components/trading/PipelineControls'
import { TransactionsList } from '@/components/trading/TransactionsList'
import { Button } from '@/components/ui/button'
import {
  usePaperTradeSummary,
  usePaperTrades,
  useResetPaperAccount,
} from '@/lib/hooks/usePaperTrades'
import { useGenerateStrategiesBatch } from '@/lib/hooks/useStrategies'
import { PortfolioBalanceCards } from './_components/PortfolioBalanceCards'
import { TradingSummaryCards } from './_components/TradingSummaryCards'
import { TradesTabsSection } from './_components/TradesTabsSection'

function TradingPageContent() {
  const searchParams = useSearchParams()
  const tabParam = searchParams?.get('tab')
  const initialTab =
    tabParam === 'open' || tabParam === 'closed' ? tabParam : 'open'
  const [activeTab, setActiveTab] = useState<'open' | 'closed'>(initialTab)
  const [isNewOrderOpen, setIsNewOrderOpen] = useState(false)
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false)

  const { data: openTrades, isLoading: openLoading } = usePaperTrades({
    status: 'open',
    limit: 100,
  })
  const { data: closedTrades, isLoading: closedLoading } = usePaperTrades({
    status: 'closed',
    limit: 100,
  })
  const { data: summary, isLoading: summaryLoading } = usePaperTradeSummary()
  const generateBatch = useGenerateStrategiesBatch()
  const resetAccount = useResetPaperAccount()

  const unrealizedPnl =
    openTrades?.trades.reduce((sum, trade) => {
      const shares = trade.shares || 0
      const entry = trade.entryPrice || 0
      const current = trade.currentPrice || entry
      return sum + (current - entry) * shares
    }, 0) || 0

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Paper Trading"
        description="AI-driven paper trades with real-time performance tracking"
        size="md"
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => generateBatch.mutate({ topN: 20 })}
              disabled={generateBatch.isPending}
            >
              <Sparkles className="mr-2 h-4 w-4" suppressHydrationWarning />
              {generateBatch.isPending ? 'Generating...' : 'Generate Strategies'}
            </Button>
            <Link href="/strategies">
              <Button variant="ghost">
                <ExternalLink className="mr-2 h-4 w-4" suppressHydrationWarning />
                View Strategies
              </Button>
            </Link>
            <Button onClick={() => setIsNewOrderOpen(true)}>
              <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
              New Order
            </Button>
          </div>
        }
      />

      <NewOrderDialog open={isNewOrderOpen} onOpenChange={setIsNewOrderOpen} />

      <PortfolioBalanceCards
        summary={summary}
        summaryLoading={summaryLoading}
        isResetPending={resetAccount.isPending}
        onResetClick={() => setIsResetDialogOpen(true)}
      />

      <PipelineControls />

      <TradingSummaryCards
        summary={summary}
        summaryLoading={summaryLoading}
        openLoading={openLoading}
        unrealizedPnl={unrealizedPnl}
      />

      <TradesTabsSection
        activeTab={activeTab}
        onTabChange={setActiveTab}
        openTrades={openTrades}
        closedTrades={closedTrades}
        openLoading={openLoading}
        closedLoading={closedLoading}
      />

      <SectionCard variant="surface" padding="none">
        <div className="border-b border-border px-6 py-4">
          <h2 className="text-xl font-semibold">Transaction History</h2>
          <p className="text-sm text-text-muted">
            Complete log of all entry and exit transactions
          </p>
        </div>
        <div className="p-6">
          <TransactionsList limit={50} />
        </div>
      </SectionCard>

      <ConfirmActionDialog
        open={isResetDialogOpen}
        onOpenChange={setIsResetDialogOpen}
        onConfirm={() => {
          resetAccount.mutate(
            { closeOpenTrades: true },
            { onSuccess: () => setIsResetDialogOpen(false) },
          )
        }}
        title="Reset Paper Trading Account?"
        description={`This will close all ${summary?.totalOpen || 0} open positions at current prices and reset your cash balance to $${(summary?.startingBalance || 100000).toLocaleString()}. This action cannot be undone.`}
        confirmLabel="Reset Account"
        tone="destructive"
      />
    </PageContainer>
  )
}

export function TradingPageClient() {
  return (
    <Suspense fallback={<div className="p-10">Loading...</div>}>
      <TradingPageContent />
    </Suspense>
  )
}
