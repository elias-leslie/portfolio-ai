'use client'

/**
 * Expanded row display for watchlist scanner items.
 *
 * Keep this detail view focused on scanner evidence: score inputs, trend/VWAP
 * context, data freshness, and the current Today market posture. Long-form
 * thesis, notes, and news remain out of this scanner surface.
 */

import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { usePreferences } from '@/lib/hooks/usePreferences'
import { ExpandedRowRefreshStatus } from './ExpandedRowRefreshStatus'
import { ExpandedRowScoreBreakdown } from './ExpandedRowScoreBreakdown'
import {
  DataHealthBadge,
  FreshnessBadge,
  PriceTrendStrip,
  type TodayGate,
  TodayGateBadge,
  VwapBadge,
} from './ScannerMetricBadges'

interface ExpandedRowProps {
  item: WatchlistItem
  refreshStatus?: RefreshStatus
  todayGate?: TodayGate
}

function ScannerEvidencePanel({
  item,
  todayGate,
  userTimezone,
}: {
  item: WatchlistItem
  todayGate?: TodayGate
  userTimezone: string
}) {
  return (
    <div className="rounded-xl border border-border/50 bg-surface/80 p-4 surface-highlight">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text">Scanner Evidence</h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">
            Use this row to decide what deserves a closer look. D/W/Q/Y trends
            are rolling close windows (1M daily, then 3M/6M/1Y weekly) from
            cached daily bars. VWAP is latest-session context, not realtime
            execution data; keep TradingView for live price action.
          </p>
        </div>
        <TodayGateBadge gate={todayGate} />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border/35 bg-surface-muted/20 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Data status
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <FreshnessBadge item={item} userTimezone={userTimezone} />
            <DataHealthBadge item={item} vwapSignal={item.vwapSignal} />
          </div>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            Quote freshness and per-pillar data health for this scanner row.
          </p>
        </div>
        <div className="rounded-lg border border-border/35 bg-surface-muted/20 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Price trend
          </p>
          <PriceTrendStrip trends={item.priceTrends} />
        </div>
        <div className="rounded-lg border border-border/35 bg-surface-muted/20 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            VWAP check
          </p>
          <VwapBadge signal={item.vwapSignal} />
          <p className="mt-2 text-xs leading-5 text-text-muted">
            Above VWAP can confirm demand; far above VWAP can mean chase risk.
            Missing VWAP degrades the technical score and data health.
          </p>
        </div>
        <div className="rounded-lg border border-border/35 bg-surface-muted/20 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Today gate
          </p>
          {todayGate ? (
            <p className="text-xs leading-5 text-text-muted">
              {todayGate.detail} This qualifies position aggressiveness; it does
              not hide otherwise interesting setups.
            </p>
          ) : (
            <p className="text-xs leading-5 text-text-muted">
              Today market posture is unavailable, so scan setup quality without
              a broad-market overlay.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function ExpandedRow({
  item,
  refreshStatus,
  todayGate,
}: ExpandedRowProps) {
  const { data: preferences } = usePreferences()
  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'

  return (
    <div className="space-y-4">
      {refreshStatus ? (
        <ExpandedRowRefreshStatus
          refreshStatus={refreshStatus}
          symbol={item.symbol}
        />
      ) : null}

      <ExpandedRowScoreBreakdown item={item} userTimezone={userTimezone} />
      <ScannerEvidencePanel
        item={item}
        todayGate={todayGate}
        userTimezone={userTimezone}
      />
    </div>
  )
}
