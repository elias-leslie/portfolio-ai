'use client'

import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Key,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { SourceDetail, SourceProvider } from '@/lib/api/sources'
import {
  formatRateLimit,
  getCapabilityIcon,
  getPriorityBadge,
  getTierColor,
} from './apiSourcesHelpers'
import { ProviderExpandedDetail } from './ProviderExpandedDetail'

interface ProviderCardProps {
  provider: SourceProvider
  isExpanded: boolean
  detail: SourceDetail | null | undefined
  detailLoading: boolean
  onToggle: (name: string) => void
}

export function ProviderCard({
  provider,
  isExpanded,
  detail,
  detailLoading,
  onToggle,
}: ProviderCardProps) {
  const priorityBadge = getPriorityBadge(provider.priority)

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      {/* Header */}
      <button
        onClick={() => onToggle(provider.name)}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${provider.displayName} details`}
      >
        <div className="flex items-center gap-4">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          )}

          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-foreground">
                {provider.displayName}
              </span>
              <Badge
                variant="outline"
                className={getTierColor(provider.tier)}
              >
                {provider.tier}
              </Badge>
              <Badge variant="outline" className={priorityBadge.color}>
                {priorityBadge.label}
              </Badge>
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              {provider.apiKeyRequired ? (
                <span className="flex items-center gap-1">
                  <Key className="h-3 w-3" /> API Key Required
                </span>
              ) : (
                <span className="flex items-center gap-1 text-status-success">
                  <CheckCircle2 className="h-3 w-3" /> No API Key Needed
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right Side Info */}
        <div className="flex items-center gap-6">
          {/* Rate Limits */}
          <div className="text-right">
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <Clock className="h-3 w-3" />
              {formatRateLimit(provider.rateLimits?.perMinute, 'min')}
            </div>
            <div className="text-xs text-muted-foreground">
              {formatRateLimit(provider.rateLimits?.perDay, 'day')}
            </div>
          </div>

          {/* Capabilities */}
          <div className="flex gap-1">
            {provider.capabilities?.map((cap) => (
              <div
                key={cap}
                className="flex items-center justify-center w-6 h-6 rounded bg-surface-muted"
                title={cap}
              >
                {getCapabilityIcon(cap)}
              </div>
            ))}
          </div>

          {/* GAP Coverage */}
          {(provider.gapCoverage?.length ?? 0) > 0 && (
            <div className="flex gap-1 flex-wrap max-w-[200px]">
              {provider.gapCoverage?.slice(0, 3).map((gap) => (
                <Badge
                  key={gap}
                  variant="outline"
                  className="text-xs bg-accent/10 text-accent border-accent/20"
                >
                  {gap}
                </Badge>
              ))}
              {(provider.gapCoverage?.length ?? 0) > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{(provider.gapCoverage?.length ?? 0) - 3}
                </Badge>
              )}
            </div>
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <ProviderExpandedDetail
          provider={provider}
          detail={detail}
          detailLoading={detailLoading}
        />
      )}
    </div>
  )
}
