'use client'

import { ExternalLink, Landmark, RefreshCw } from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  formatDataServiceTime,
  MoneyDataServiceConfigForm,
  MoneyDataServicePanel,
  MoneyDataServiceSecretInput,
  type MoneyDataServiceTile,
} from '@/components/money/MoneyDataServicePanel'
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

  useEffect(() => {
    if (!status) return
    setForm((current) => ({
      ...current,
      redirectUri:
        status.redirectUri ?? (current.redirectUri || defaultRedirectUri()),
      defaultBroker: current.defaultBroker || status.defaultBroker,
    }))
  }, [status])

  const configured = status?.configured === true
  const canConfigure = status?.encryptionReady !== false
  const redirectConfigured = Boolean(status?.redirectUri)
  const hasConnection = (status?.connectionCount ?? 0) > 0
  const portalReady = configured && redirectConfigured
  const connectionStatus = hasConnection
    ? 'Linked'
    : portalReady
      ? 'Ready'
      : 'Pending'
  const connectionDetail = hasConnection
    ? 'Sync enabled'
    : portalReady
      ? 'Portal connection pending'
      : 'Needs redirect URI'
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
    if (!status.userRegistered)
      return 'Credentials configured; brokerage connection pending'
    return `${status.accountCount} account${status.accountCount === 1 ? '' : 's'} linked`
  }, [configured, isLoading, status])

  const handleConfigure = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const clientId = form.clientId.trim()
    const consumerKey = form.consumerKey.trim()
    await configureSnapTrade.mutateAsync({
      ...(clientId ? { clientId } : {}),
      ...(consumerKey ? { consumerKey } : {}),
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

  const statusTiles: MoneyDataServiceTile[] = [
    {
      id: 'credentials',
      label: 'Credentials',
      value: status?.clientIdConfigured
        ? 'Client ID saved'
        : 'Client ID missing',
      detail: status?.consumerKeyConfigured
        ? 'Consumer key saved'
        : 'Consumer key missing',
      badge: {
        label: configured ? 'Saved' : 'Missing',
        variant: configured ? 'success' : 'secondary',
      },
    },
    {
      id: 'access',
      label: 'Access',
      value: 'Read only',
      detail: selectedBroker,
      badge: {
        label: 'Read only',
        variant: 'secondary',
      },
    },
    {
      id: 'redirect',
      label: 'OAuth Redirect',
      value: status?.redirectUri ?? 'Not set',
      title: status?.redirectUri ?? undefined,
      detail: formatDataServiceTime(status?.configurationUpdatedAt),
      badge: {
        label: redirectConfigured ? 'Ready' : 'Missing',
        variant: redirectConfigured ? 'success' : 'secondary',
      },
    },
    {
      id: 'connection',
      label: 'Brokerage',
      value: connectionDetail,
      icon: <Landmark className="h-4 w-4 text-primary" />,
      badge: {
        label: connectionStatus,
        variant: hasConnection
          ? 'success'
          : portalReady
            ? 'warning'
            : 'secondary',
      },
    },
  ]

  const metricTiles: MoneyDataServiceTile[] = [
    {
      id: 'connections',
      label: 'Connections',
      value: status?.connectionCount ?? 0,
    },
    {
      id: 'accounts',
      label: 'Accounts',
      value: status?.accountCount ?? 0,
    },
    {
      id: 'positions',
      label: 'Positions',
      value: status?.positionCount ?? 0,
    },
    {
      id: 'activities',
      label: 'Activities',
      value: status?.activityCount ?? 0,
    },
    {
      id: 'last-sync',
      label: 'Last Sync',
      value: formatDataServiceTime(status?.lastSuccessfulSyncAt),
    },
    {
      id: 'default-broker',
      label: 'Default Broker',
      value: status?.defaultBroker ?? 'FIDELITY',
    },
  ]

  const configForm = (
    <MoneyDataServiceConfigForm
      isPending={configureSnapTrade.isPending}
      canConfigure={canConfigure}
      onSubmit={(event) => void handleConfigure(event)}
      onCancel={() => setConfigOpen(false)}
    >
      <MoneyDataServiceSecretInput
        id="snaptrade-client-id"
        label="Client ID"
        value={form.clientId}
        saved={configured}
        onChange={(clientId) =>
          setForm((current) => ({
            ...current,
            clientId,
          }))
        }
      />
      <MoneyDataServiceSecretInput
        id="snaptrade-consumer-key"
        label="Consumer key"
        value={form.consumerKey}
        saved={configured}
        onChange={(consumerKey) =>
          setForm((current) => ({
            ...current,
            consumerKey,
          }))
        }
      />
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
    </MoneyDataServiceConfigForm>
  )

  return (
    <MoneyDataServicePanel
      title="SnapTrade"
      summary={summary}
      configured={configured}
      canConfigure={canConfigure}
      configOpen={configOpen}
      onToggleConfig={() => setConfigOpen((open) => !open)}
      configForm={configForm}
      statusTiles={statusTiles}
      metricTiles={metricTiles}
      metricColumns={4}
      alerts={[portalError, status?.lastError]}
      syncAction={{
        label: 'Sync',
        icon: <RefreshCw className="h-4 w-4" />,
        pending: syncSnapTrade.isPending,
        disabled: !configured || isBusy || !status?.userRegistered,
        variant: 'outline',
        onClick: () => void syncSnapTrade.mutateAsync(),
      }}
      connectAction={{
        label: 'Connect brokerage',
        icon: <ExternalLink className="h-4 w-4" />,
        pending: createPortal.isPending,
        disabled: !configured || isBusy,
        onClick: () => void handleConnect(),
      }}
    >
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
                  {formatCurrency(account.marketValue ?? account.balance, account.currency)}
                </p>
                <p className="text-xs text-text-muted">
                  {account.valuationSource === 'live' && account.quoteAsOf
                    ? `Live · ${formatDataServiceTime(account.quoteAsOf)}`
                    : formatDataServiceTime(account.lastSyncedAt)}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </MoneyDataServicePanel>
  )
}
