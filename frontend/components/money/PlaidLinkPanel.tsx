'use client'

import {
  Banknote,
  KeyRound,
  Link2,
  Loader2,
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
import { SectionCard } from '@/components/shared/SectionCard'
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
    const response = await createLinkToken.mutateAsync()
    setLinkToken(response.linkToken)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LINK_TOKEN_STORAGE_KEY, response.linkToken)
    }
    setPendingOpen(true)
  }

  const handleConfigure = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await configurePlaid.mutateAsync({
      clientId: form.clientId.trim(),
      secret: form.secret.trim(),
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
    return `${status.itemCount} item${status.itemCount === 1 ? '' : 's'} linked`
  }, [configured, isLoading, status])

  return (
    <SectionCard
      variant="surface"
      title="Plaid"
      description={summary}
      actions={
        <>
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
            onClick={() => void syncPlaid.mutateAsync({})}
            disabled={!configured || isBusy}
          >
            <RefreshCw
              className={
                syncPlaid.isPending ? 'h-4 w-4 animate-spin' : 'h-4 w-4'
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
            {createLinkToken.isPending || exchangePublicToken.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
            Connect bank
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
              <Label htmlFor="plaid-client-id">Client ID</Label>
              <Input
                id="plaid-client-id"
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
              <Label htmlFor="plaid-secret">Secret</Label>
              <Input
                id="plaid-secret"
                type="password"
                value={form.secret}
                autoComplete="off"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    secret: event.target.value,
                  }))
                }
                required
              />
            </div>
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
            <div className="flex items-center gap-2 md:col-span-2">
              <Button
                type="submit"
                disabled={configurePlaid.isPending || !canConfigure}
              >
                {configurePlaid.isPending && (
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

        {linkError && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {linkError}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Accounts</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.accountCount ?? 0}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Transactions</p>
            <p className="mt-1 text-lg font-semibold text-text">
              {status?.transactionCount ?? 0}
            </p>
          </div>
          <div className="rounded-md border border-border/35 bg-bg/60 p-3">
            <p className="text-xs uppercase text-text-muted">Last Sync</p>
            <p className="mt-1 text-sm font-medium text-text">
              {formatSyncTime(status?.lastSuccessfulSyncAt)}
            </p>
          </div>
        </div>

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
                      {formatSyncTime(item.lastSuccessfulSyncAt)}
                    </p>
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
      </div>
    </SectionCard>
  )
}
