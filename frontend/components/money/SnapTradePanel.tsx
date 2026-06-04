'use client'

import {
  ArrowDownCircle,
  ArrowUpCircle,
  Clock3,
  ExternalLink,
  Landmark,
  ListFilter,
  ReceiptText,
  RefreshCw,
} from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  formatDataServiceTime,
  MoneyDataServiceConfigForm,
  MoneyDataServicePanel,
  MoneyDataServiceSecretInput,
  type MoneyDataServiceTile,
} from '@/components/money/MoneyDataServicePanel'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { SnapTradeAccount, SnapTradeOrder } from '@/lib/api/snaptrade'
import {
  useConfigureSnapTrade,
  useCreateSnapTradeConnectionPortal,
  useSnapTradeOrders,
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

function formatCurrencyWithCents(
  value?: number | null,
  currency?: string | null,
) {
  if (value === null || value === undefined) return 'Not reported'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatQuantity(value?: number | null) {
  if (value === null || value === undefined) return 'Not reported'
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 6,
  }).format(value)
}

function orderAccountLabel(account: SnapTradeAccount | SnapTradeOrder) {
  const accountName =
    'name' in account ? account.name : (account.accountName ?? 'Account')
  const institutionName = account.institutionName
  const label = institutionName
    ? `${institutionName} - ${accountName}`
    : accountName
  return account.accountMask ? `${label} *${account.accountMask}` : label
}

function orderValue(order: SnapTradeOrder) {
  if (order.filledQuantity === null || order.executionPrice === null) {
    return null
  }
  return Math.abs(order.filledQuantity * order.executionPrice)
}

function signedOrderCashFlow(order: SnapTradeOrder) {
  const value = orderValue(order)
  if (value === null) return 0
  const action = order.action?.toUpperCase()
  if (action?.includes('BUY')) return -value
  if (action?.includes('SELL')) return value
  return 0
}

function orderStatusVariant(status?: string | null): BadgeProps['variant'] {
  const normalized = status?.toUpperCase()
  if (normalized === 'EXECUTED') return 'success'
  if (normalized === 'CANCELLED' || normalized === 'REJECTED') return 'warning'
  return 'secondary'
}

function orderActionLabel(action?: string | null) {
  return action?.replaceAll('_', ' ').toUpperCase() || 'ORDER'
}

function orderTimestamp(order: SnapTradeOrder) {
  return order.timeExecuted ?? order.timeUpdated ?? order.timePlaced
}

export function SnapTradePanel() {
  const { data: status, isLoading } = useSnapTradeStatus()
  const configureSnapTrade = useConfigureSnapTrade()
  const createPortal = useCreateSnapTradeConnectionPortal()
  const syncSnapTrade = useSyncSnapTrade()
  const [selectedOrderAccountId, setSelectedOrderAccountId] = useState('all')
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

  useEffect(() => {
    if (
      selectedOrderAccountId !== 'all' &&
      status?.accounts.every(
        (account) => account.accountId !== selectedOrderAccountId,
      )
    ) {
      setSelectedOrderAccountId('all')
    }
  }, [selectedOrderAccountId, status?.accounts])

  const configured = status?.configured === true
  const canConfigure = status?.encryptionReady !== false
  const redirectConfigured = Boolean(status?.redirectUri)
  const hasConnection = (status?.connectionCount ?? 0) > 0
  const portalReady = configured && redirectConfigured
  const selectedOrderAccount =
    selectedOrderAccountId === 'all' ? null : selectedOrderAccountId
  const {
    data: ordersData,
    isLoading: ordersLoading,
    error: ordersError,
  } = useSnapTradeOrders({
    accountId: selectedOrderAccount,
    enabled: configured && hasConnection,
    limit: 25,
  })
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
      id: 'orders',
      label: 'Orders',
      value: status?.orderCount ?? 0,
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
      <div className="space-y-4">
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
                    {formatCurrency(
                      account.marketValue ?? account.balance,
                      account.currency,
                    )}
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

        {configured && hasConnection ? (
          <SnapTradeOrdersTimeline
            accounts={status?.accounts ?? []}
            orders={ordersData?.orders ?? []}
            loading={ordersLoading}
            error={ordersError}
            selectedAccountId={selectedOrderAccountId}
            onSelectedAccountIdChange={setSelectedOrderAccountId}
          />
        ) : null}
      </div>
    </MoneyDataServicePanel>
  )
}

function SnapTradeOrdersTimeline({
  accounts,
  orders,
  loading,
  error,
  selectedAccountId,
  onSelectedAccountIdChange,
}: {
  accounts: SnapTradeAccount[]
  orders: SnapTradeOrder[]
  loading: boolean
  error: unknown
  selectedAccountId: string
  onSelectedAccountIdChange: (accountId: string) => void
}) {
  const executedOrders = orders.filter(
    (order) => order.status?.toUpperCase() === 'EXECUTED',
  )
  const latestOrder = orders[0]
  const latestTimestamp = latestOrder ? orderTimestamp(latestOrder) : null
  const netCashFlow = executedOrders.reduce(
    (total, order) => total + signedOrderCashFlow(order),
    0,
  )
  const displayCurrency =
    orders.find((order) => order.currency)?.currency ??
    accounts.find((account) => account.currency)?.currency ??
    'USD'

  return (
    <div className="rounded-md border border-border/35 bg-bg/60 p-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <ReceiptText className="h-4 w-4 text-primary" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text">Trade history</p>
            <p className="text-xs text-text-muted">
              {loading
                ? 'Loading orders'
                : `${orders.length} recent order${orders.length === 1 ? '' : 's'}`}
            </p>
          </div>
        </div>
        <Select
          value={selectedAccountId}
          onValueChange={onSelectedAccountIdChange}
        >
          <SelectTrigger size="sm" className="w-full min-w-0 md:w-[260px]">
            <ListFilter className="h-4 w-4" />
            <SelectValue placeholder="All accounts" />
          </SelectTrigger>
          <SelectContent align="end">
            <SelectItem value="all">All accounts</SelectItem>
            {accounts.map((account) => (
              <SelectItem key={account.accountId} value={account.accountId}>
                {orderAccountLabel(account)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <div className="rounded-md border border-border/25 bg-surface/45 px-3 py-2">
          <p className="text-xs uppercase text-text-muted">Executed</p>
          <p className="mt-1 text-sm font-semibold text-text">
            {executedOrders.length}
          </p>
        </div>
        <div className="rounded-md border border-border/25 bg-surface/45 px-3 py-2">
          <p className="text-xs uppercase text-text-muted">Net Flow</p>
          <p
            className={
              netCashFlow > 0
                ? 'mt-1 text-sm font-semibold text-gain'
                : netCashFlow < 0
                  ? 'mt-1 text-sm font-semibold text-loss'
                  : 'mt-1 text-sm font-semibold text-text'
            }
          >
            {formatCurrencyWithCents(netCashFlow, displayCurrency)}
          </p>
        </div>
        <div className="rounded-md border border-border/25 bg-surface/45 px-3 py-2">
          <p className="text-xs uppercase text-text-muted">Latest</p>
          <p className="mt-1 text-sm font-semibold text-text">
            {formatDataServiceTime(latestTimestamp)}
          </p>
        </div>
      </div>

      {error ? (
        <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error instanceof Error
            ? error.message
            : 'Failed to load SnapTrade orders.'}
        </div>
      ) : null}

      <div className="mt-3 space-y-2">
        {orders.map((order) => {
          const action = order.action?.toUpperCase()
          const isSell = action?.includes('SELL')
          const timestamp = orderTimestamp(order)
          const value = orderValue(order)
          const ActionIcon = isSell ? ArrowUpCircle : ArrowDownCircle
          return (
            <div
              key={`${order.accountId}:${order.brokerageOrderId}`}
              className="grid gap-3 rounded-md border border-border/25 bg-surface/35 p-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)_minmax(0,0.85fr)_auto] md:items-center"
            >
              <div className="flex min-w-0 items-center gap-3">
                <ActionIcon
                  className={`h-4 w-4 ${isSell ? 'text-gain' : 'text-primary'}`}
                />
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-text">
                      {order.symbol ?? order.rawSymbol ?? 'Unknown'}
                    </p>
                    <Badge variant={orderStatusVariant(order.status)}>
                      {order.status ?? 'Unknown'}
                    </Badge>
                  </div>
                  <p className="truncate text-xs text-text-muted">
                    {orderAccountLabel(order)}
                  </p>
                </div>
              </div>

              <div className="min-w-0">
                <p className="text-xs uppercase text-text-muted">Order</p>
                <p className="truncate text-sm text-text">
                  {orderActionLabel(order.action)}
                  {order.orderType ? ` · ${order.orderType}` : ''}
                </p>
              </div>

              <div className="min-w-0">
                <p className="text-xs uppercase text-text-muted">Fill</p>
                <p className="truncate text-sm text-text">
                  {formatQuantity(order.filledQuantity)}
                  {order.executionPrice !== null
                    ? ` @ ${formatCurrencyWithCents(order.executionPrice, order.currency)}`
                    : ''}
                </p>
              </div>

              <div className="flex min-w-0 items-start justify-between gap-3 md:block md:text-right">
                <div>
                  <p className="text-xs uppercase text-text-muted">Value</p>
                  <p className="text-sm font-semibold text-text">
                    {formatCurrencyWithCents(value, order.currency)}
                  </p>
                </div>
                <div className="min-w-0 md:mt-1">
                  <p className="flex items-center gap-1 text-xs text-text-muted md:justify-end">
                    <Clock3 className="h-3.5 w-3.5" />
                    {formatDataServiceTime(timestamp)}
                  </p>
                </div>
              </div>
            </div>
          )
        })}

        {!loading && !orders.length && !error ? (
          <div className="rounded-md border border-border/25 bg-surface/35 px-3 py-6 text-center text-sm text-text-muted">
            No SnapTrade orders synced yet.
          </div>
        ) : null}
      </div>
    </div>
  )
}
