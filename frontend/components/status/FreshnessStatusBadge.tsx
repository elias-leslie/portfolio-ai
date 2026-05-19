'use client'

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  Wifi,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { DataFreshnessDetail } from '@/lib/api/health'
import type { ScannerFanoutSettings } from '@/lib/api/preferences'
import { useLiveFreshness, useRefreshAllFreshness } from '@/lib/hooks/useHealth'
import {
  usePreferences,
  useScannerFanoutSettings,
  useUpdatePreferences,
  useUpdateScannerFanoutSettings,
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

const SCANNER_FANOUT_BOUNDS = {
  topN: { min: 1, max: 100 },
  tier1Keep: { min: 1, max: 100 },
  maxDaily: { min: 0, max: 100 },
  cacheTtlHours: { min: 1, max: 168 },
} as const

const SCANNER_FANOUT_FIELDS: ReadonlyArray<{
  key: 'topN' | 'tier1Keep' | 'maxDaily' | 'cacheTtlHours'
  label: string
  helper: string
}> = [
  {
    key: 'topN',
    label: 'top_n',
    helper: 'Scanner candidates considered (default 25)',
  },
  {
    key: 'tier1Keep',
    label: 'tier1_keep',
    helper: 'Survivors that go to deep runs (default 8)',
  },
  {
    key: 'maxDaily',
    label: 'max_daily',
    helper: 'Hard daily cap on deep runs (default 25)',
  },
  {
    key: 'cacheTtlHours',
    label: 'cache_ttl_hours',
    helper: 'Per-symbol dedup window in hours (default 24)',
  },
]

function ScannerFanoutControls() {
  const { data: serverSettings } = useScannerFanoutSettings()
  const updateSettings = useUpdateScannerFanoutSettings()
  const [draft, setDraft] = useState<ScannerFanoutSettings | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (serverSettings && !draft) {
      setDraft(serverSettings)
    }
  }, [serverSettings, draft])

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    },
    [],
  )

  if (!draft) return null

  const persist = (next: ScannerFanoutSettings) => {
    updateSettings.mutate(next, {
      onError: (error) => {
        toast.error(
          error instanceof Error
            ? error.message
            : 'Failed to save signal stack settings',
        )
        if (serverSettings) setDraft(serverSettings)
      },
    })
  }

  const onMasterToggle = (checked: boolean) => {
    const next = { ...draft, enabled: checked }
    setDraft(next)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    persist(next)
  }

  const onNumericChange = (
    key: 'topN' | 'tier1Keep' | 'maxDaily' | 'cacheTtlHours',
    rawValue: string,
  ) => {
    const parsed = Number.parseInt(rawValue, 10)
    if (Number.isNaN(parsed)) return
    const { min, max } = SCANNER_FANOUT_BOUNDS[key]
    const clamped = Math.max(min, Math.min(max, parsed))
    const next = { ...draft, [key]: clamped }
    // tier1_keep ≤ top_n is enforced server-side; clamp client-side too so
    // the optimistic update doesn't show a value the server will reject.
    if (key === 'topN' && next.tier1Keep > next.topN) {
      next.tier1Keep = next.topN
    }
    if (key === 'tier1Keep' && next.tier1Keep > next.topN) {
      next.tier1Keep = next.topN
    }
    setDraft(next)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => persist(next), 400)
  }

  const disabledInputs = !draft.enabled

  return (
    <div className="grid gap-2 pt-1">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-text">
          Signal stack (L3 committee)
        </p>
        <Switch checked={draft.enabled} onCheckedChange={onMasterToggle} />
      </div>
      <button
        type="button"
        onClick={() => setAdvancedOpen((open) => !open)}
        className="flex items-center gap-1 self-start text-[11px] font-medium text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:text-text"
        aria-expanded={advancedOpen}
      >
        {advancedOpen ? (
          <ChevronDown className="size-3" aria-hidden />
        ) : (
          <ChevronRight className="size-3" aria-hidden />
        )}
        Advanced…
      </button>
      {advancedOpen ? (
        <div
          className={cn(
            'grid gap-3 rounded-md border border-border/35 bg-background/30 p-2.5',
            disabledInputs && 'opacity-50',
          )}
        >
          {SCANNER_FANOUT_FIELDS.map((field) => (
            <div key={field.key} className="grid gap-1">
              <label
                htmlFor={`scanner-fanout-${field.key}`}
                className="text-[11px] font-medium text-text"
              >
                {field.label}
              </label>
              <Input
                id={`scanner-fanout-${field.key}`}
                type="number"
                className="h-8 text-xs"
                min={SCANNER_FANOUT_BOUNDS[field.key].min}
                max={SCANNER_FANOUT_BOUNDS[field.key].max}
                value={draft[field.key]}
                disabled={disabledInputs}
                onChange={(event) =>
                  onNumericChange(field.key, event.target.value)
                }
              />
              <p className="text-[10px] text-text-muted">{field.helper}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function FreshnessStatusBadge() {
  const [open, setOpen] = useState(false)
  const freshness = useLiveFreshness()
  const refreshAll = useRefreshAllFreshness()
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
              <p className="text-xs font-medium text-text">
                Auto-refresh open UI
              </p>
              <Switch
                checked={autoRefreshEnabled}
                onCheckedChange={(checked) =>
                  updatePreferences.mutate({
                    frontendPollInterval: checked ? 300 : 0,
                  })
                }
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-text">
                Open/focus cadence
              </p>
              <Select
                value={pollOption}
                onValueChange={(value) =>
                  updatePreferences.mutate({
                    frontendPollInterval: Number(value),
                  })
                }
              >
                <SelectTrigger size="sm" className="w-32">
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
            <ScannerFanoutControls />
            <div className="grid gap-2 pt-1">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium text-text">
                  Jenny scheduled runs
                </p>
                <Switch
                  checked={preferences?.scheduledJennyOperatorEnabled ?? false}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledJennyOperatorEnabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium text-text">Strategy agents</p>
                <Switch
                  checked={
                    preferences?.scheduledStrategyResearchEnabled ?? false
                  }
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledStrategyResearchEnabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium text-text">
                  ML labeling jobs
                </p>
                <Switch
                  checked={preferences?.scheduledMlLabelingEnabled ?? false}
                  onCheckedChange={(checked) =>
                    updatePreferences.mutate({
                      scheduledMlLabelingEnabled: checked,
                    })
                  }
                />
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
