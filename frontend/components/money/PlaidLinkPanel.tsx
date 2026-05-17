'use client'

import {
  Banknote,
  CheckCircle2,
  Landmark,
  Link2,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  type PlaidLinkError,
  type PlaidLinkOnExitMetadata,
  type PlaidLinkOnSuccessMetadata,
  usePlaidLink,
} from 'react-plaid-link'
import {
  formatDataServiceList,
  formatDataServiceTime,
  MoneyDataServiceConfigForm,
  MoneyDataServicePanel,
  MoneyDataServiceSecretInput,
  type MoneyDataServiceTile,
  titleCaseDataServiceValue,
} from '@/components/money/MoneyDataServicePanel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useConfigurePlaid,
  useCreatePlaidLinkToken,
  useExchangePlaidPublicToken,
  usePlaidStatus,
  useRemovePlaidItem,
  useSyncPlaidItems,
} from '@/lib/hooks/usePlaid'

const LINK_TOKEN_STORAGE_KEY = 'portfolio-ai.plaid.link_token'

function defaultRedirectUri() {
  if (typeof window === 'undefined') return ''
  return `${window.location.origin}/money`
}

export function PlaidLinkPanel() {
  const { data: status, isLoading } = usePlaidStatus()
  const configurePlaid = useConfigurePlaid()
  const createLinkToken = useCreatePlaidLinkToken()
  const exchangePublicToken = useExchangePlaidPublicToken()
  const syncPlaid = useSyncPlaidItems()
  const removeItem = useRemovePlaidItem()
  const [configOpen, setConfigOpen] = useState(false)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [pendingOpen, setPendingOpen] = useState(false)
  const [linkError, setLinkError] = useState<string | null>(null)
  const [receivedRedirectUri, setReceivedRedirectUri] = useState<
    string | undefined
  >()
  const [form, setForm] = useState({
    clientId: '',
    secret: '',
    environment: 'sandbox',
    products: 'transactions',
    countryCodes: 'US',
    redirectUri: '',
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
      environment: status.environment ?? current.environment,
      products: status.products.length
        ? status.products.join(', ')
        : current.products,
      countryCodes: status.countryCodes.length
        ? status.countryCodes.join(', ')
        : current.countryCodes,
      redirectUri:
        status.redirectUri ?? (current.redirectUri || defaultRedirectUri()),
    }))
  }, [status])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!window.location.href.includes('oauth_state_id=')) return
    const storedToken = window.localStorage.getItem(LINK_TOKEN_STORAGE_KEY)
    if (!storedToken) return
    setLinkToken(storedToken)
    setReceivedRedirectUri(window.location.href)
    setPendingOpen(true)
  }, [])

  const configured = status?.configured === true
  const canConfigure = status?.encryptionReady !== false
  const redirectConfigured = Boolean(status?.redirectUri)
  const productionReady = status?.environment === 'production'
  const hasChaseItem =
    status?.items.some((item) => /chase/i.test(item.institutionName ?? '')) ??
    false
  const chaseReady = configured && productionReady && redirectConfigured
  const isBusy =
    createLinkToken.isPending ||
    exchangePublicToken.isPending ||
    syncPlaid.isPending ||
    configurePlaid.isPending

  const onSuccess = useCallback(
    async (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
      setLinkError(null)
      await exchangePublicToken.mutateAsync({
        publicToken,
        metadata: metadata as unknown as Record<string, unknown>,
      })
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(LINK_TOKEN_STORAGE_KEY)
        window.history.replaceState(window.history.state, '', '/money')
      }
    },
    [exchangePublicToken],
  )

  const onExit = useCallback(
    (error: PlaidLinkError | null, metadata: PlaidLinkOnExitMetadata) => {
      if (!error) return
      const parts = [
        error.error_code || error.error_type || 'Plaid Link error',
        error.error_message || error.display_message,
        metadata.request_id ? `request ${metadata.request_id}` : null,
      ].filter(Boolean)
      setLinkError(parts.join(' - '))
    },
    [],
  )

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit,
    receivedRedirectUri,
  })

  useEffect(() => {
    if (!pendingOpen || !ready) return
    open()
    setPendingOpen(false)
  }, [open, pendingOpen, ready])

  const handleConnect = async () => {
    setLinkError(null)
    const response = await createLinkToken.mutateAsync()
    setLinkToken(response.linkToken)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LINK_TOKEN_STORAGE_KEY, response.linkToken)
    }
    setPendingOpen(true)
  }

  const handleConfigure = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const clientId = form.clientId.trim()
    const secret = form.secret.trim()
    await configurePlaid.mutateAsync({
      ...(clientId ? { clientId } : {}),
      ...(secret ? { secret } : {}),
      environment: form.environment,
      products: form.products
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      countryCodes: form.countryCodes
        .split(',')
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
      redirectUri: form.redirectUri.trim() || null,
    })
    setForm((current) => ({ ...current, clientId: '', secret: '' }))
    setConfigOpen(false)
  }

  const summary = useMemo(() => {
    if (isLoading) return 'Loading Plaid status'
    if (!status?.encryptionReady) return 'App secret key required'
    if (!configured) return 'Credentials not configured'
    if (status.itemCount === 0) {
      return 'Credentials configured; Chase authorization pending'
    }
    return `${status.itemCount} item${status.itemCount === 1 ? '' : 's'} linked`
  }, [configured, isLoading, status])

  const chaseStatus = hasChaseItem ? 'Linked' : chaseReady ? 'Ready' : 'Pending'
  const chaseDetail = hasChaseItem
    ? 'Sync enabled'
    : chaseReady
      ? 'OAuth authorization pending'
      : 'Needs production redirect'

  const statusTiles: MoneyDataServiceTile[] = [
    {
      id: 'credentials',
      label: 'Credentials',
      value: status?.clientIdConfigured
        ? 'Client ID saved'
        : 'Client ID missing',
      detail: status?.secretConfigured ? 'Secret saved' : 'Secret missing',
      badge: {
        label: configured ? 'Saved' : 'Missing',
        variant: configured ? 'success' : 'secondary',
      },
    },
    {
      id: 'environment',
      label: 'Environment',
      value: titleCaseDataServiceValue(status?.environment),
      detail: formatDataServiceList(status?.products),
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
      id: 'chase',
      label: 'Chase',
      value: chaseDetail,
      icon: hasChaseItem ? (
        <CheckCircle2 className="h-4 w-4 text-gain" />
      ) : (
        <Landmark className="h-4 w-4 text-primary" />
      ),
      badge: {
        label: chaseStatus,
        variant: hasChaseItem
          ? 'success'
          : chaseReady
            ? 'warning'
            : 'secondary',
      },
    },
  ]

  const metricTiles: MoneyDataServiceTile[] = [
    {
      id: 'accounts',
      label: 'Accounts',
      value: status?.accountCount ?? 0,
    },
    {
      id: 'transactions',
      label: 'Transactions',
      value: status?.transactionCount ?? 0,
    },
    {
      id: 'last-sync',
      label: 'Last Sync',
      value: formatDataServiceTime(status?.lastSuccessfulSyncAt),
    },
  ]

  const configForm = (
    <MoneyDataServiceConfigForm
      isPending={configurePlaid.isPending}
      canConfigure={canConfigure}
      onSubmit={(event) => void handleConfigure(event)}
      onCancel={() => setConfigOpen(false)}
    >
      <MoneyDataServiceSecretInput
        id="plaid-client-id"
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
        id="plaid-secret"
        label="Secret"
        value={form.secret}
        saved={configured}
        onChange={(secret) =>
          setForm((current) => ({
            ...current,
            secret,
          }))
        }
      />
      <div className="space-y-2">
        <Label>Environment</Label>
        <Select
          value={form.environment}
          onValueChange={(environment) =>
            setForm((current) => ({ ...current, environment }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="sandbox">Sandbox</SelectItem>
            <SelectItem value="production">Production</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="plaid-countries">Countries</Label>
        <Input
          id="plaid-countries"
          value={form.countryCodes}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              countryCodes: event.target.value,
            }))
          }
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="plaid-products">Products</Label>
        <Input
          id="plaid-products"
          value={form.products}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              products: event.target.value,
            }))
          }
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="plaid-redirect-uri">Redirect URI</Label>
        <Input
          id="plaid-redirect-uri"
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
      title="Plaid"
      summary={summary}
      configured={configured}
      canConfigure={canConfigure}
      configOpen={configOpen}
      onToggleConfig={() => setConfigOpen((open) => !open)}
      configForm={configForm}
      statusTiles={statusTiles}
      metricTiles={metricTiles}
      alerts={[linkError]}
      syncAction={{
        label: 'Sync',
        icon: <RefreshCw className="h-4 w-4" />,
        pending: syncPlaid.isPending,
        disabled: !configured || isBusy,
        variant: 'outline',
        onClick: () => void syncPlaid.mutateAsync({}),
      }}
      connectAction={{
        label: hasChaseItem ? 'Connect bank' : 'Connect Chase',
        icon: <Link2 className="h-4 w-4" />,
        pending: createLinkToken.isPending || exchangePublicToken.isPending,
        disabled: !configured || isBusy,
        onClick: () => void handleConnect(),
      }}
    >
      {status?.items.length ? (
        <div className="space-y-2">
          {status.items.map((item) => (
            <div
              key={item.itemId}
              className="flex flex-col gap-2 rounded-md border border-border/35 bg-bg/60 p-3 md:flex-row md:items-center md:justify-between"
            >
              <div className="flex min-w-0 items-center gap-3">
                <Banknote className="h-4 w-4 text-primary" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-text">
                    {item.institutionName ?? 'Plaid item'}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatDataServiceTime(item.lastSuccessfulSyncAt)}
                  </p>
                  {item.lastError ? (
                    <p className="text-xs text-destructive">{item.lastError}</p>
                  ) : null}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  variant={item.status === 'active' ? 'default' : 'secondary'}
                >
                  {item.status}
                </Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Remove Plaid item"
                  onClick={() => void removeItem.mutateAsync(item.itemId)}
                  disabled={removeItem.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </MoneyDataServicePanel>
  )
}
