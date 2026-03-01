'use client'

import { PaperTradesTable } from '@/components/trading/PaperTradesTable'
import { SectionCard } from '@/components/shared/SectionCard'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { usePaperTrades } from '@/lib/hooks/usePaperTrades'

type TradesData = NonNullable<ReturnType<typeof usePaperTrades>['data']>

interface TradesTabsSectionProps {
  activeTab: 'open' | 'closed'
  onTabChange: (tab: 'open' | 'closed') => void
  openTrades: TradesData | undefined
  closedTrades: TradesData | undefined
  openLoading: boolean
  closedLoading: boolean
}

export function TradesTabsSection({
  activeTab,
  onTabChange,
  openTrades,
  closedTrades,
  openLoading,
  closedLoading,
}: TradesTabsSectionProps) {
  return (
    <SectionCard variant="surface" padding="none">
      <Tabs
        value={activeTab}
        onValueChange={(val) => onTabChange(val as 'open' | 'closed')}
      >
        <div className="border-b border-border px-6 pt-6">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="open">
              Open Positions ({openTrades?.totalCount || 0})
            </TabsTrigger>
            <TabsTrigger value="closed">
              Closed Trades ({closedTrades?.totalCount || 0})
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="open" className="mt-0">
          {openLoading ? (
            <div className="p-8 text-center text-text-muted">
              Loading open positions...
            </div>
          ) : openTrades && openTrades.trades.length > 0 ? (
            <PaperTradesTable trades={openTrades.trades} type="open" />
          ) : (
            <div className="p-8 text-center text-text-muted">
              No open positions. AI agents will create trades when opportunities are identified.
            </div>
          )}
        </TabsContent>

        <TabsContent value="closed" className="mt-0">
          {closedLoading ? (
            <div className="p-8 text-center text-text-muted">
              Loading closed trades...
            </div>
          ) : closedTrades && closedTrades.trades.length > 0 ? (
            <PaperTradesTable trades={closedTrades.trades} type="closed" />
          ) : (
            <div className="p-8 text-center text-text-muted">
              No closed trades yet. Trades will appear here once positions are exited.
            </div>
          )}
        </TabsContent>
      </Tabs>
    </SectionCard>
  )
}
