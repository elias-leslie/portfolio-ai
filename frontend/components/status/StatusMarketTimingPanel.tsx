'use client'

import { RelativeTime } from '@/components/shared/RelativeTime'
import { SectionCard } from '@/components/shared/SectionCard'
import type { MarketStatusResponse } from '@/lib/api/market'
import type { NewsHealthResponse } from '@/lib/api/news'
import { EmptyPanelMessage, SummaryStat } from './StatusPanelPrimitives'
import { marketLabel } from './statusUtils'

export function MarketTimingPanel({
  marketData,
  newsHealth,
}: {
  marketData: MarketStatusResponse | undefined
  newsHealth: NewsHealthResponse | undefined
}) {
  const newsFeedValue =
    newsHealth?.status === 'healthy'
      ? 'Current'
      : newsHealth?.status === 'degraded'
        ? 'Stale'
        : newsHealth?.status === 'down'
          ? 'Down'
          : 'Idle'
  const newsFeedDetail = newsHealth?.latestRefreshedAt ? (
    <>
      Last news refresh <RelativeTime value={newsHealth.latestRefreshedAt} />
    </>
  ) : (
    'No successful news refresh recorded'
  )

  return (
    <SectionCard
      variant="surface"
      title="Market Calendar"
      description="Useful when deciding whether today's prices and alerts should already be moving."
    >
      {!marketData && !newsHealth ? (
        <EmptyPanelMessage message="Market timing data is unavailable right now." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <SummaryStat
            label="Market Session"
            value={marketLabel(marketData?.status)}
            detail={
              marketData?.isHoliday
                ? (marketData.holidayName ?? 'Holiday session')
                : 'Regular session'
            }
          />
          <SummaryStat
            label="Daily Data Through"
            value={marketData?.expectedDataDate ?? '—'}
            detail={`Latest close through ${marketData?.lastTradingDay ?? '—'} · expected daily data date`}
          />
          <SummaryStat
            label="Next Trading Day"
            value={marketData?.nextTradingDay ?? '—'}
            detail={
              marketData?.isEarlyClose
                ? (marketData.earlyCloseName ?? 'Early close')
                : 'Standard close schedule'
            }
          />
          <SummaryStat
            label="News Feed"
            value={newsFeedValue}
            detail={newsFeedDetail}
          />
        </div>
      )}
    </SectionCard>
  )
}
