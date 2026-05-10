'use client'

import { RelativeTime } from '@/components/shared/RelativeTime'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { ApiQuotaInfo } from '@/lib/api/health'
import type { NewsHealthResponse } from '@/lib/api/news'
import { formatInteger } from '@/lib/formatters'
import { EmptyPanelMessage } from './StatusPanelPrimitives'
import {
  formatLabel,
  getVendorActivityTimestamp,
  vendorVariant,
} from './statusUtils'

export function NewsVendorsPanel({
  vendorRows,
}: {
  vendorRows: Array<[string, NewsHealthResponse['vendors'][string]]>
}) {
  return (
    <SectionCard
      variant="surface"
      title="News Sources"
      description="Which news feeds are connected and when they last produced articles."
    >
      <div className="grid gap-3">
        {vendorRows.length === 0 ? (
          <EmptyPanelMessage message="No news-source diagnostics are available right now." />
        ) : (
          vendorRows.map(([name, vendor]) => (
            <div
              key={name}
              className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold uppercase tracking-wide text-text">
                  {formatLabel(name)}
                </p>
                <Badge variant={vendorVariant(vendor)}>
                  {vendor.active
                    ? 'active'
                    : vendor.enabled
                      ? 'idle'
                      : 'disabled'}
                </Badge>
              </div>
              <div className="mt-3 grid gap-2 text-sm text-text-muted">
                <p>Connected: {vendor.configured ? 'Yes' : 'No'}</p>
                <p>
                  Last activity:{' '}
                  <RelativeTime value={getVendorActivityTimestamp(vendor)} />
                </p>
                {vendor.lastSuccessAt ? (
                  <p>
                    Last success: <RelativeTime value={vendor.lastSuccessAt} />
                  </p>
                ) : null}
                <p>Articles in 24h: {formatInteger(vendor.articlesLast24H)}</p>
                <p>
                  Articles in latest pull:{' '}
                  {formatInteger(vendor.articlesLastFetch)}
                </p>
                <p>
                  Latest issue:{' '}
                  {vendor.lastError
                    ? vendor.lastError
                    : (vendor.reason ?? 'No recent error')}
                </p>
                {vendor.notes ? <p>Notes: {vendor.notes}</p> : null}
              </div>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  )
}

export function QuotaCoveragePanel({
  apiQuotas,
  configuredCount,
  totalCount,
}: {
  apiQuotas: ApiQuotaInfo[]
  configuredCount: number
  totalCount: number
}) {
  return (
    <SectionCard
      variant="surface"
      title="API Limits"
      description="Which data providers are connected and the limits they advertise."
    >
      {totalCount > 0 ? (
        <div className="mb-3 rounded-2xl border border-border/40 bg-surface/40 px-4 py-3 text-sm text-text-muted">
          {formatInteger(configuredCount)} of {formatInteger(totalCount)} data
          provider
          {totalCount === 1 ? '' : 's'} connected
        </div>
      ) : null}
      <div className="grid gap-3">
        {apiQuotas.length === 0 ? (
          <EmptyPanelMessage message="No API-limit data is available right now." />
        ) : (
          apiQuotas.map((quota) => (
            <div
              key={quota.sourceName}
              className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  {quota.sourceName}
                </p>
                <Badge variant={quota.configured ? 'success' : 'secondary'}>
                  {quota.configured ? 'connected' : 'disabled'}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-text-muted">
                Rate limit {quota.rateLimit ?? '—'} · Daily{' '}
                {quota.dailyLimit ?? '—'} · Estimated capacity{' '}
                {formatInteger(quota.estimatedCapacity)}
              </p>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  )
}
