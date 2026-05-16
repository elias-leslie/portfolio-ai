'use client'

import {
  ExternalLink,
  KeyRound,
  Landmark,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useConfigureSnapTrade,
  useCreateSnapTradeConnectionPortal,
  useSnapTradeStatus,
  useSyncSnapTrade,
} from '@/lib/hooks/useSnapTrade'

function defaultRedirectUri() {
  if (typeof window === 'undefined') return ''
  return `${window.location.origin}/money`
}

function formatSyncTime(value?: string | null) {
  if (!value) return 'Never synced'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

function formatCurrency(value?: number | null, currency?: string | null) {
  if (value === null || value === undefined) return 'Not reported'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function SnapTradePanel() {
  const { data: status, isLoading } = useSnapTradeStatus()
  const configureSnapTrade = useConfigureSnapTrade()
  const createPortal = useCreateSnapTradeConnectionPortal()
  const syncSnapTrade = useSyncSnapTrade()
  const [configOpen, setConfigOpen] = useState(false)
  const [portalError, setPortalError] = useState<string | null>(null)
  const [form, setForm] = useState({
    clientId: '',
    consumerKey: '',
    redirectUri: '',
    defaultBroker: '',
  })

  useEffect(() => {
    setForm((current) =>
      current.redirectUri
        ? current
        : { ...current, redirectUri: defaultRedirectUri() },
    )
  }, [])

  const configured = status?.configured === true
  const canConfigure = status?.encryptionReady !== false
  const isBusy =
    configureSnapTrade.isPending ||
    createPortal.isPending ||
    syncSnapTrade.isPending
  const selectedBroker =
    form.defaultBroker.trim().toUpperCase() ||
    status?.defaultBroker ||
    'FIDELITY'

  const summary = useMemo(() => {
    if (isLoading) return 'Loading SnapTrade status'
    if (!status?.encryptionReady) return 'App secret key required'
    if (!configured) return 'Credentials not configured'
    return `${status.accountCount} account${status.accountCount === 1 ? '' : 's'} linked`
  }, [configured, isLoading, status])

  const handleConfigure = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await configureSnapTrade.mutateAsync({
      clientId: form.clientId.trim(),
      consumerKey: form.consumerKey.trim(),
      redirectUri: form.redirectUri.trim() || null,
      defaultBroker: selectedBroker,
    })
    setForm((current) => ({ ...current, clientId: '', consumerKey: '' }))
    setConfigOpen(false)
  }

  const handleConnect = async () => {
    setPortalError(null)
    const response = await createPortal.mutateAsync({
      broker: selectedBroker,
    })
    if (typeof window === 'undefined') return
    const opened = window.open(
      response.portalUrl,
      '_blank',
      'noopener,noreferrer',
    )
    if (!opened && document.hasFocus()) {
      setPortalError('Connection portal was blocked by the browser.')
    }
  }

  return (
    <SectionCard
      variant="surface"
      title="SnapTrade"
      description={summary}
      actions={
        <>
          <Badge variant="secondary" className="gap-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            Read only
          </Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setConfigOpen((open) => !open)}
            disabled={!canConfigure}
          >
            <KeyRound className="h-4 w-4" />
            Configure
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void syncSnapTrade.mutateAsync()}
            disabled={!configured || isBusy || !status?.userRegistered}
          >
            <RefreshCw
              className={
                syncSnapTrade.isPending ? 'h-4 w-4 animate-spin' : 'h-4 w-4'
              }
            />
            Sync
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => void handleConnect()}
            disabled={!configured || isBusy}
          >
            {createPortal.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ExternalLink className="h-4 w-4" />
            )}
            Connect brokerage
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {!canConfigure && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            PORTFOLIO_SECRET_KEY is required before encrypted credentials can be
            saved.
          </div>
        )}

        {configOpen && (
          <form
            className="grid gap-3 rounded-md border border-border/40 bg-bg/70 p-4 md:grid-cols-2"
            autoComplete="off"
            onSubmit={(event) => void handleConfigure(event)}
          >
            <div className="space-y-2">
              <Label htmlFor="snaptrade-client-id">Client ID</Label>
              <Input
                id="snaptrade-client-id"
                type="password"
                value={form.clientId}
                autoComplete="off"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    clientId: event.target.value,
                  }))
                }
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="snaptrade-consumer-key">Consumer key</Label>
              <Input
                id="snaptrade-consumer-key"
                type="password"
                value={form.consumerKey}
                autoComplete="off"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    consumerKey: event.target.value,
                  }))
                }
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="snaptrade-broker">Broker slug</Label>
              <Input
                id="snaptrade-broker"
                value={form.defaultBroker}
                placeholder={status?.defaultBroker ?? 'FIDELITY'}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    defaultBroker: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="snaptrade-redirect-uri">Redirect URI</Label>
              <Input
                id="snaptrade-redirect-uri"
                value={form.redirectUri}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    redirectUri: event.target.value,
                  }))
                }
              />
            </div>
            <div className="flex items-center gap-2 md:col-span-2">
              <Button
                type="submit"
                disabled={configureSnapTrade.isPending || !canConfigure}
              >
                {configureSnapTrade.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Save credentials
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConfigOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        )}

        {(portalError || status?.lastError) && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {portalError || status?.lastError}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Connections</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.connectionCount ?? 0}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Accounts</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.accountCount ?? 0}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Positions</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.positionCount ?? 0}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Activities</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.activityCount ?? 0}
            </p>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Last Sync</p>
            <p className="mt-1 text-sm font-medium text-text">
              {formatSyncTime(status?.lastSuccessfulSyncAt)}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Default Broker</p>
            <p className="mt-1 text-sm font-medium text-text">
              {status?.defaultBroker ?? 'FIDELITY'}
            </p>
          </div>
        </div>

        {status?.accounts.length ? (
          <div className="space-y-2">
            {status.accounts.map((account) => (
              <div
                key={account.accountId}
                className="flex flex-col gap-2 rounded-md border border-border/35 bg-bg/60 p-3 md:flex-row md:items-center md:justify-between"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Landmark className="h-4 w-4 text-primary" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text">
                      {account.institutionName
                        ? `${account.institutionName} - ${account.name}`
                        : account.name}
                    </p>
                    <p className="text-xs text-text-muted">
                      {account.accountMask
                        ? `*${account.accountMask} - ${account.portfolioAccountType}`
                        : account.portfolioAccountType}
                    </p>
                  </div>
                </div>
                <div className="text-left md:text-right">
                  <p className="text-sm font-semibold text-text">
                    {formatCurrency(account.balance, account.currency)}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatSyncTime(account.lastSyncedAt)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </SectionCard>
  )
}
