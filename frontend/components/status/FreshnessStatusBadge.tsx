'use client'

import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Wifi,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { DataFreshnessDetail } from '@/lib/api/health'
import { useLiveFreshness, useRefreshAllFreshness } from '@/lib/hooks/useHealth'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import {
  usePreferences,
  useUpdatePreferences,
} from '@/lib/hooks/usePreferences'
import { cn, formatRelativeTime } from '@/lib/utils'

const FIRST_OPEN_REFRESH_KEY = 'portfolio-ai:first-open-freshness-refresh'
const FIRST_OPEN_MIN_SECONDS = 15 * 60
const POLL_OPTIONS = [
  { value: 0, label: 'Manual' },
  { value: 10, label: '10 sec' },
  { value: 30, label: '30 sec' },
  { value: 60, label: '1 min' },
  { value: 300, label: '5 min' },
  { value: 900, label: '15 min' },
  { value: 1800, label: '30 min' },
  { value: 3600, label: '1 hr' },
  { value: 7200, label: '2 hr' },
  { value: 14400, label: '4 hr' },
]

function statusTone(status: string | undefined) {
  switch (status) {
    case 'success':
      return {
        label: 'Live',
        variant: 'success' as const,
        icon: CheckCircle2,
        dot: 'bg-gain',
      }
    case 'critical':
      return {
        label: 'Overdue',
        variant: 'error' as const,
        icon: AlertTriangle,
        dot: 'bg-loss',
      }
    case 'warning':
      return {
        label: 'Aging',
        variant: 'warning' as const,
        icon: AlertTriangle,
        dot: 'bg-warning',
      }
    default:
      return {
        label: 'Checking',
        variant: 'secondary' as const,
        icon: Wifi,
        dot: 'bg-text-muted',
      }
  }
}

function ageLabel(detail: DataFreshnessDetail) {
  if (detail.ageHours == null) return 'unknown age'
  if (detail.ageHours < 1) return `${Math.round(detail.ageHours * 60)}m old`
  return `${detail.ageHours.toFixed(1)}h old`
}

function sortDetails(details: DataFreshnessDetail[]) {
  return [...details].sort((a, b) => {
    const rank = (detail: DataFreshnessDetail) =>
      detail.isCritical ? 0 : detail.isStale ? 1 : 2
    return rank(a) - rank(b) || a.tableName.localeCompare(b.tableName)
  })
}

function accountControlTone(status: string | undefined) {
  switch (status) {
    case 'clear':
      return { label: 'Clear', variant: 'success' as const }
    case 'blocked':
      return { label: 'Blocked', variant: 'error' as const }
    case 'review':
      return { label: 'Review', variant: 'warning' as const }
    default:
      return { label: 'Unknown', variant: 'secondary' as const }
  }
}

function accountControlMessage(accountControl: {
  status: string
  summary: string
  issueCount: number
  blockingIssueCount: number
}) {
  if (accountControl.blockingIssueCount > 0) {
    return `${accountControl.blockingIssueCount} account source issue${
      accountControl.blockingIssueCount === 1 ? '' : 's'
    } can affect totals. Fix before trusting Money and retirement totals.`
  }
  if (accountControl.issueCount > 0) {
    return `${accountControl.issueCount} account source review item${
      accountControl.issueCount === 1 ? '' : 's'
    }. Totals use one controlled value per account, so duplicate source rows are not counted twice.`
  }
  return accountControl.summary
}

function shouldKickFirstOpenRefresh(
  status: string | undefined,
  intervalSeconds: number,
) {
  if (status !== 'warning' && status !== 'critical') return false
  if (intervalSeconds <= 0) return false
  try {
    const last = Number(
      localStorage.getItem(FIRST_OPEN_REFRESH_KEY) ??
        sessionStorage.getItem(FIRST_OPEN_REFRESH_KEY) ??
        '0',
    )
    return (
      Date.now() - last >
      Math.max(intervalSeconds, FIRST_OPEN_MIN_SECONDS) * 1000
    )
  } catch {
    return true
  }
}

function rememberFirstOpenRefresh() {
  try {
    const now = String(Date.now())
    localStorage.setItem(FIRST_OPEN_REFRESH_KEY, now)
    sessionStorage.setItem(FIRST_OPEN_REFRESH_KEY, now)
  } catch {
    // Ignore private-mode storage failures.
  }
}

export function FreshnessStatusBadge() {
  const [open, setOpen] = useState(false)
  const freshness = useLiveFreshness()
  const refreshAll = useRefreshAllFreshness()
  const householdDashboard = useHouseholdDashboard({ enabled: open })
  const { data: preferences } = usePreferences()
  const updatePreferences = useUpdatePreferences()
  const tone = statusTone(
    refreshAll.isPending ? 'checking' : freshness.data?.status,
  )
  const Icon = refreshAll.isPending ? Loader2 : tone.icon
  const details = useMemo(
    () => sortDetails(freshness.data?.details ?? []).slice(0, 8),
    [freshness.data?.details],
  )
  const pollSeconds = preferences?.frontendPollInterval ?? 30
  const pollOption = POLL_OPTIONS.some((option) => option.value === pollSeconds)
    ? String(pollSeconds)
    : '300'
  const autoRefreshEnabled = pollSeconds > 0
  const accountControl = householdDashboard.data?.accountControl
  const accountControlStatus = accountControlTone(accountControl?.status)

  useEffect(() => {
    if (!preferences || !freshness.data || refreshAll.isPending) return
    if (!shouldKickFirstOpenRefresh(freshness.data.status, pollSeconds)) return
    rememberFirstOpenRefresh()
    refreshAll.mutate(undefined, {
      onSuccess: (result) => {
        toast.success(result.message)
      },
      onError: (error) => {
        toast.error(error.message)
      },
    })
  }, [freshness.data, pollSeconds, preferences, refreshAll])

  const runRefreshAll = () => {
    refreshAll.mutate(undefined, {
      onSuccess: (result) => {
        toast.success(result.message)
      },
      onError: (error) => {
        toast.error(error.message)
      },
    })
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-label="Open data freshness feed"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-2 rounded-full border border-border/40 bg-surface/70 px-2.5 py-1.5 text-xs font-medium text-text-muted transition-colors hover:border-border/70 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        <span className={cn('size-2 rounded-full', tone.dot)} />
        <Icon
          className={cn('size-3.5', refreshAll.isPending && 'animate-spin')}
          aria-hidden
        />
        <span className="hidden sm:inline">
          {refreshAll.isPending ? 'Syncing' : tone.label}
        </span>
      </button>

      {open ? (
        <div className="fixed left-3 right-3 top-16 z-50 max-h-[calc(100vh-5rem)] overflow-y-auto rounded-lg border border-border/50 bg-surface-elev p-4 shadow-xl sm:absolute sm:left-auto sm:right-0 sm:top-full sm:mt-2 sm:max-h-none sm:w-[min(92vw,28rem)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text">Data Feed</p>
              <p className="mt-1 text-xs text-text-muted">
                {freshness.data?.message ?? 'Checking data freshness'}
              </p>
              {freshness.data?.generatedAt ? (
                <p className="mt-1 text-[11px] text-text-muted">
                  Checked {formatRelativeTime(freshness.data.generatedAt)}
                </p>
              ) : null}
            </div>
            <Badge variant={tone.variant}>{tone.label}</Badge>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-md border border-border/35 bg-surface-muted/20 p-2">
              <p className="font-semibold text-text">
                {freshness.data?.fresh ?? '-'}
              </p>
              <p className="text-text-muted">Current</p>
            </div>
            <div className="rounded-md border border-border/35 bg-surface-muted/20 p-2">
              <p className="font-semibold text-text">
                {freshness.data?.stale ?? '-'}
              </p>
              <p className="text-text-muted">Aging</p>
            </div>
            <div className="rounded-md border border-border/35 bg-surface-muted/20 p-2">
              <p className="font-semibold text-text">
                {freshness.data?.critical ?? '-'}
              </p>
              <p className="text-text-muted">Overdue</p>
            </div>
          </div>

          {accountControl ? (
            <div className="mt-4 rounded-md border border-border/35 bg-background/20 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-text">
                  Money account controls
                </p>
                <Badge variant={accountControlStatus.variant}>
                  {accountControlStatus.label}
                </Badge>
              </div>
              <p className="mt-1 text-[11px] text-text-muted">
                {accountControlMessage(accountControl)}
              </p>
            </div>
          ) : null}

          <div className="mt-4 max-h-56 space-y-2 overflow-y-auto pr-1">
            {details.map((detail) => (
              <div
                key={detail.tableName}
                className="rounded-md border border-border/35 bg-background/20 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-text">
                    {detail.tableName.replaceAll('_', ' ')}
                  </p>
                  <Badge
                    variant={
                      detail.isCritical
                        ? 'error'
                        : detail.isStale
                          ? 'warning'
                          : 'success'
                    }
                  >
                    {detail.isCritical
                      ? 'Overdue'
                      : detail.isStale
                        ? 'Aging'
                        : 'Current'}
                  </Badge>
                </div>
                <p className="mt-1 text-[11px] text-text-muted">
                  {ageLabel(detail)}
                  {detail.lastUpdate
                    ? ` · ${formatRelativeTime(detail.lastUpdate)}`
                    : ''}
                </p>
                {detail.coverage?.staleSymbolCount ? (
                  <p className="mt-1 text-[11px] text-warning">
                    {detail.coverage.staleSymbolCount} symbol
                    {detail.coverage.staleSymbolCount === 1 ? '' : 's'} behind
                  </p>
                ) : null}
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              onClick={runRefreshAll}
              disabled={refreshAll.isPending}
            >
              <RefreshCw
                className={cn('size-4', refreshAll.isPending && 'animate-spin')}
              />
              Refresh All
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void freshness.refetch()}
            >
              Check Now
            </Button>
          </div>

          <div className="mt-4 space-y-3 rounded-md border border-border/35 bg-background/20 p-3">
            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="freshness-auto-refresh"
                className="text-xs font-medium text-text"
              >
                Auto-refresh open UI
              </label>
              <Switch
                id="freshness-auto-refresh"
                checked={autoRefreshEnabled}
                disabled={updatePreferences.isPending}
                onCheckedChange={(checked) =>
                  updatePreferences.mutate({
                    frontendPollInterval: checked ? 300 : 0,
                  })
                }
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="freshness-open-cadence"
                className="text-xs font-medium text-text"
              >
                Open/focus cadence
              </label>
              <Select
                value={pollOption}
                disabled={updatePreferences.isPending}
                onValueChange={(value) =>
                  updatePreferences.mutate({
                    frontendPollInterval: Number(value),
                  })
                }
              >
                <SelectTrigger
                  id="freshness-open-cadence"
                  size="sm"
                  className="w-32"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {POLL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={String(option.value)}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2 pt-1">
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="freshness-account-syncs"
                  className="text-xs font-medium text-text"
                >
                  Account syncs (SnapTrade, Plaid)
                </label>
                <Switch
                  id="freshness-account-syncs"
                  checked={preferences?.scheduledAccountSyncEnabled ?? false}
                  disabled={updatePreferences.isPending}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledAccountSyncEnabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="freshness-jenny-runs"
                  className="text-xs font-medium text-text"
                >
                  Jenny scheduled runs
                </label>
                <Switch
                  id="freshness-jenny-runs"
                  checked={preferences?.scheduledJennyOperatorEnabled ?? false}
                  disabled={updatePreferences.isPending}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledJennyOperatorEnabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="freshness-strategy-agents"
                  className="text-xs font-medium text-text"
                >
                  Strategy agents
                </label>
                <Switch
                  id="freshness-strategy-agents"
                  checked={
                    preferences?.scheduledStrategyResearchEnabled ?? false
                  }
                  disabled={updatePreferences.isPending}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledStrategyResearchEnabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="freshness-ml-labeling"
                  className="text-xs font-medium text-text"
                >
                  ML labeling jobs
                </label>
                <Switch
                  id="freshness-ml-labeling"
                  checked={preferences?.scheduledMlLabelingEnabled ?? false}
                  disabled={updatePreferences.isPending}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledMlLabelingEnabled: checked,
                    })
                  }
                />
              </div>
            </div>
            {updatePreferences.error ? (
              <p role="alert" className="text-xs text-loss">
                Could not save this preference. Check system status and try
                again.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
