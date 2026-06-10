'use client'

import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { CardIntakeResult, CreditCardProduct } from '@/lib/api/cards'
import { formatCurrencyWhole, formatInteger } from '@/lib/formatters'
import { useCreateCard, useIntakeCardOffer } from '@/lib/hooks/useCards'
import { cn } from '@/lib/utils'

export interface LinkableAccount {
  householdAccountId: string
  label: string
}

type AddCardMode = 'manual' | 'screenshot'

const NONE_ACCOUNT = 'none'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function deriveWelcomeDeadline(
  openedDate: string,
  product: CreditCardProduct | null | undefined,
): string | null {
  if (!openedDate || !product?.welcomeWindowDays) return null
  const opened = new Date(`${openedDate}T00:00:00`)
  if (Number.isNaN(opened.getTime())) return null
  const deadline = new Date(
    opened.getTime() + product.welcomeWindowDays * 86_400_000,
  )
  return deadline.toISOString().slice(0, 10)
}

function ExtractedTermField({
  label,
  value,
  unreadable,
}: {
  label: string
  value: string
  unreadable: boolean
}) {
  return (
    <div
      className={cn(
        'rounded-xl border px-3 py-2',
        unreadable
          ? 'border-warning/50 bg-warning/10'
          : 'border-border/40 bg-surface-muted/20',
      )}
    >
      <p className="text-xs text-text-muted">
        {label}
        {unreadable ? ' · unreadable' : ''}
      </p>
      <p
        className={cn(
          'text-sm font-medium',
          unreadable ? 'text-warning' : 'text-text',
        )}
      >
        {unreadable ? 'Could not read — verify manually' : value}
      </p>
    </div>
  )
}

function ExtractedTerms({ result }: { result: CardIntakeResult }) {
  const product = result.product
  const unreadable = new Set(result.unreadableFields)
  if (!product) {
    return (
      <p className="rounded-xl border border-warning/50 bg-warning/10 px-3 py-2 text-sm text-warning">
        Extraction did not produce a usable card product
        {result.extractionNotes ? ` — ${result.extractionNotes}` : '.'}
      </p>
    )
  }
  const lowConfidence = (result.confidence ?? 1) < 0.7
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-text">{product.productName}</span>
        <Badge variant="outline">{product.issuer}</Badge>
        {result.confidence != null ? (
          <Badge variant={lowConfidence ? 'warning' : 'success'}>
            {Math.round(result.confidence * 100)}% confidence
          </Badge>
        ) : null}
        {result.status === 'needs_review' ? (
          <Badge variant="warning">Needs review</Badge>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <ExtractedTermField
          label="Annual fee"
          value={formatCurrencyWhole(product.annualFee)}
          unreadable={unreadable.has('annual_fee')}
        />
        <ExtractedTermField
          label="Welcome bonus"
          value={
            product.welcomeBonusPoints > 0
              ? `${formatInteger(product.welcomeBonusPoints)} points`
              : product.welcomeBonusCash > 0
                ? formatCurrencyWhole(product.welcomeBonusCash)
                : 'None'
          }
          unreadable={
            unreadable.has('welcome_bonus_points') ||
            unreadable.has('welcome_bonus_cash')
          }
        />
        <ExtractedTermField
          label="Minimum spend"
          value={
            product.welcomeMinSpend
              ? formatCurrencyWhole(product.welcomeMinSpend)
              : '—'
          }
          unreadable={unreadable.has('welcome_min_spend')}
        />
        <ExtractedTermField
          label="Bonus window"
          value={
            product.welcomeWindowDays
              ? `${product.welcomeWindowDays} days`
              : '—'
          }
          unreadable={unreadable.has('welcome_window_days')}
        />
        <ExtractedTermField
          label="Point program"
          value={product.pointProgram ?? '—'}
          unreadable={unreadable.has('point_program')}
        />
        <ExtractedTermField
          label="Top multipliers"
          value={
            Object.entries(product.rewardMultipliers)
              .filter(([, multiplier]) => multiplier > 1)
              .map(([bucket, multiplier]) => `${multiplier}x ${bucket}`)
              .join(', ') || '1x everywhere'
          }
          unreadable={unreadable.has('reward_multipliers')}
        />
      </div>
      {result.extractionNotes ? (
        <p className="text-xs text-text-muted">{result.extractionNotes}</p>
      ) : null}
    </div>
  )
}

export function AddCardDialog({
  open,
  onOpenChange,
  catalog,
  accounts,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  catalog: CreditCardProduct[]
  accounts: LinkableAccount[]
}) {
  const [mode, setMode] = useState<AddCardMode>('manual')
  const [productId, setProductId] = useState('')
  const [openedDate, setOpenedDate] = useState(todayIso())
  const [player, setPlayer] = useState('p1')
  const [role, setRole] = useState('rotating')
  const [accountId, setAccountId] = useState(NONE_ACCOUNT)
  const [offerFile, setOfferFile] = useState<File | null>(null)
  const [intakeResult, setIntakeResult] = useState<CardIntakeResult | null>(
    null,
  )

  const createCard = useCreateCard()
  const intakeOffer = useIntakeCardOffer()

  const sortedCatalog = useMemo(
    () =>
      [...catalog].sort((left, right) =>
        left.productName.localeCompare(right.productName),
      ),
    [catalog],
  )

  const resolvedProduct =
    mode === 'screenshot'
      ? (intakeResult?.product ?? null)
      : (sortedCatalog.find((product) => product.id === productId) ?? null)

  const reset = () => {
    setProductId('')
    setOpenedDate(todayIso())
    setPlayer('p1')
    setRole('rotating')
    setAccountId(NONE_ACCOUNT)
    setOfferFile(null)
    setIntakeResult(null)
    intakeOffer.reset()
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) reset()
    onOpenChange(nextOpen)
  }

  const handleExtract = () => {
    if (!offerFile) return
    intakeOffer.mutate(
      { file: offerFile },
      { onSuccess: (result) => setIntakeResult(result) },
    )
  }

  const canSubmit = Boolean(resolvedProduct) && !createCard.isPending

  const handleSubmit = () => {
    if (!resolvedProduct) return
    createCard.mutate(
      {
        productId: resolvedProduct.id,
        status: 'active',
        player,
        role,
        openedDate: openedDate || null,
        welcomeDeadline: deriveWelcomeDeadline(openedDate, resolvedProduct),
        householdAccountId: accountId === NONE_ACCOUNT ? null : accountId,
      },
      { onSuccess: () => handleOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a card</DialogTitle>
          <DialogDescription>
            Pick a catalog product, or upload an offer screenshot and confirm
            the extracted terms.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-1.5">
          <Button
            type="button"
            size="sm"
            variant={mode === 'manual' ? 'default' : 'outline'}
            onClick={() => setMode('manual')}
          >
            From catalog
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === 'screenshot' ? 'default' : 'outline'}
            onClick={() => setMode('screenshot')}
          >
            Offer screenshot
          </Button>
        </div>

        <div className="space-y-4">
          {mode === 'manual' ? (
            <div className="space-y-1.5">
              <Label>Card product</Label>
              <Select value={productId} onValueChange={setProductId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a card" />
                </SelectTrigger>
                <SelectContent>
                  {sortedCatalog.map((product) => (
                    <SelectItem key={product.id} value={product.id}>
                      {product.productName} ({product.issuer},{' '}
                      {formatCurrencyWhole(product.annualFee)} AF)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="card-offer-file">Offer screenshot</Label>
                <div className="flex gap-2">
                  <Input
                    id="card-offer-file"
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(event) => {
                      setOfferFile(event.target.files?.[0] ?? null)
                      setIntakeResult(null)
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleExtract}
                    disabled={!offerFile || intakeOffer.isPending}
                  >
                    {intakeOffer.isPending ? 'Extracting…' : 'Extract terms'}
                  </Button>
                </div>
              </div>
              {intakeResult ? <ExtractedTerms result={intakeResult} /> : null}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="card-opened-date">Opened date</Label>
              <Input
                id="card-opened-date"
                type="date"
                value={openedDate}
                onChange={(event) => setOpenedDate(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Player</Label>
              <Select value={player} onValueChange={setPlayer}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="p1">Player 1</SelectItem>
                  <SelectItem value="p2">Player 2</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Role</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rotating">
                    Rotating (90-day cycle)
                  </SelectItem>
                  <SelectItem value="keeper">Keeper (permanent)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Linked account (optional)</Label>
              <Select value={accountId} onValueChange={setAccountId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE_ACCOUNT}>Not linked</SelectItem>
                  {accounts.map((account) => (
                    <SelectItem
                      key={account.householdAccountId}
                      value={account.householdAccountId}
                    >
                      {account.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
          >
            Cancel
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={!canSubmit}>
            {createCard.isPending ? 'Adding…' : 'Add card'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
