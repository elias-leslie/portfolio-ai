'use client'

import { useMemo } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdCreditCard, SoftCharge } from '@/lib/api/cards'
import type { HouseholdConfirmedFact } from '@/lib/api/household'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'
import { useActivateCard, useDeleteCard } from '@/lib/hooks/useCards'
import { cn } from '@/lib/utils'
import { CardBonusControls } from './CardBonusControls'
import { CardHistoryEditor } from './CardHistoryEditor'
import {
  daysBetween,
  formatShortDate,
  isInCurrentMonth,
  parseIsoDate,
  playerLabel,
  resolveMonthlyCardCap,
} from './cards-helpers'

function roleBadge(card: HouseholdCreditCard) {
  if (card.isPrimaryActive) {
    return <Badge variant="success">Primary rotating</Badge>
  }
  if (card.role === 'keeper') {
    return <Badge variant="secondary">Keeper</Badge>
  }
  return <Badge variant="outline">Rotating</Badge>
}

/**
 * Whose card this is, and which one. Two cards of the same product render as the
 * same row twice otherwise -- the issuer names both of them identically, so the
 * owner and the last four digits are the only things that tell them apart.
 */
function cardIdentity(card: HouseholdCreditCard): string {
  return [
    card.accountOwner,
    card.accountMask ? `····${card.accountMask}` : null,
  ]
    .filter(Boolean)
    .join(' ')
}

function CardRow({
  card,
  onActivate,
  onDelete,
  isActivating,
  isDeleting,
}: {
  card: HouseholdCreditCard
  onActivate: () => void
  onDelete: () => void
  isActivating: boolean
  isDeleting: boolean
}) {
  const product = card.product
  return (
    <div
      id={`card-${card.id}`}
      className="flex flex-col gap-2 rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 md:flex-row md:flex-wrap md:items-center md:justify-between"
    >
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-text">
            {product?.productName ?? 'Unknown product'}
          </span>
          {roleBadge(card)}
          <Badge variant="outline">{playerLabel(card.player)}</Badge>
        </div>
        <p className="text-xs text-text-muted">
          {cardIdentity(card) ? `${cardIdentity(card)} · ` : ''}
          {product?.issuer ?? '—'} · Annual fee{' '}
          {formatCurrencyWhole(product?.annualFee ?? 0)} · Opened{' '}
          {formatShortDate(card.openedDate)}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {!card.closedDate &&
        !card.isPrimaryActive &&
        card.role === 'rotating' ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onActivate}
            disabled={isActivating}
          >
            Make primary
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="text-text-muted hover:text-destructive"
          onClick={onDelete}
          disabled={isDeleting}
        >
          {card.status === 'candidate'
            ? 'Remove candidate'
            : 'Record closed today'}
        </Button>
      </div>
      <CardHistoryEditor card={card} />
      <CardBonusControls card={card} />
    </div>
  )
}

function BudgetGauge({
  softMtd,
  hardMtd,
  cap,
}: {
  softMtd: number
  hardMtd: number
  cap: number
}) {
  const total = softMtd + hardMtd
  const hardPct = cap > 0 ? Math.min(100, (hardMtd / cap) * 100) : 0
  const softPct = cap > 0 ? Math.min(100 - hardPct, (softMtd / cap) * 100) : 0
  const overCap = total > cap

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-text-muted">Month-to-date card budget</span>
        <span
          className={cn(
            'font-medium tabular-nums',
            overCap ? 'text-destructive' : 'text-text',
          )}
        >
          {formatCurrencyWhole(total)} / {formatCurrencyWhole(cap)}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-surface-muted/40">
        <div className="flex h-full">
          <div
            className="h-full bg-primary"
            style={{ width: `${hardPct}%` }}
            title={`Hard (posted): ${formatCurrency(hardMtd)}`}
          />
          <div
            className="h-full bg-warning/70"
            style={{ width: `${softPct}%` }}
            title={`Soft / pending: ${formatCurrency(softMtd)}`}
          />
        </div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Hard (posted) {formatCurrencyWhole(hardMtd)}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-warning/70" />
          Soft / pending {formatCurrencyWhole(softMtd)}
        </span>
        {overCap ? (
          <span className="font-medium text-destructive">
            Over the monthly cap
          </span>
        ) : null}
      </div>
    </div>
  )
}

function WelcomeBonusBar({ card }: { card: HouseholdCreditCard }) {
  const minSpend = card.product?.welcomeMinSpend ?? 0
  if (card.welcomeStatus !== 'in_progress' || minSpend <= 0) return null

  const progress = card.welcomeProgressAmount
  const pct = Math.min(100, (progress / minSpend) * 100)
  const deadline = parseIsoDate(card.welcomeDeadline)
  const daysLeft = deadline ? daysBetween(new Date(), deadline) : null

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-text-muted">Welcome bonus progress</span>
        <span className="font-medium tabular-nums text-text">
          {formatCurrencyWhole(progress)} / {formatCurrencyWhole(minSpend)}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-surface-muted/40">
        <div
          className={cn(
            'h-full rounded-full',
            daysLeft != null && daysLeft <= 14 && pct < 100
              ? 'bg-warning'
              : 'bg-gain',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-text-muted">
        {pct.toFixed(0)}% of minimum spend
        {daysLeft != null
          ? ` · ${daysLeft >= 0 ? `${daysLeft} days remaining` : `deadline passed ${-daysLeft} days ago`} (${formatShortDate(card.welcomeDeadline)})`
          : ''}
      </p>
    </div>
  )
}

export interface ActiveCardPanelProps {
  cards: HouseholdCreditCard[]
  softCharges: SoftCharge[]
  facts: HouseholdConfirmedFact[]
  /** Canonical card-account purchases, including provisional rows. */
  monthToDateSpend?: number | null
  provisionalSpend?: number | null
  actions?: React.ReactNode
}

export function ActiveCardPanel({
  cards,
  softCharges,
  facts,
  monthToDateSpend,
  provisionalSpend,
  actions,
}: ActiveCardPanelProps) {
  const activateCard = useActivateCard()
  const deleteCard = useDeleteCard()

  const openCards = useMemo(
    () => cards.filter((card) => !card.closedDate),
    [cards],
  )
  const primary = openCards.find((card) => card.isPrimaryActive) ?? null
  const keepers = openCards.filter(
    (card) => card.role === 'keeper' && card.id !== primary?.id,
  )
  const otherRotating = openCards.filter(
    (card) => card.role === 'rotating' && card.id !== primary?.id,
  )

  const localSoftMtd = useMemo(
    () =>
      softCharges
        .filter(
          (charge) =>
            charge.status === 'pending' && isInCurrentMonth(charge.occurredAt),
        )
        .reduce((sum, charge) => sum + charge.amount, 0),
    [softCharges],
  )
  const softMtd = provisionalSpend ?? localSoftMtd
  const totalMtd = monthToDateSpend ?? softMtd
  const hardMtd = Math.max(0, totalMtd - softMtd)
  const cap = resolveMonthlyCardCap(facts, primary?.id)

  return (
    <SectionCard
      variant="surface"
      title="Household wallet"
      description="The active primary rotating card plus permanently held keeper cards."
      actions={actions}
    >
      {openCards.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
          No owned cards yet. Add the household's current cards to start
          tracking welcome bonuses and the 90-day rotation.
        </div>
      ) : (
        <div className="space-y-5">
          {primary ? (
            <div className="space-y-4">
              <CardRow
                card={primary}
                onActivate={() => activateCard.mutate(primary.id)}
                onDelete={() => deleteCard.mutate(primary.id)}
                isActivating={activateCard.isPending}
                isDeleting={deleteCard.isPending}
              />
              {monthToDateSpend == null ? (
                <p className="text-sm text-text-muted">
                  Card spending total is not available yet.
                </p>
              ) : (
                <BudgetGauge softMtd={softMtd} hardMtd={hardMtd} cap={cap} />
              )}
              <p className="text-xs text-text-muted">
                Recorded card accounts only. Refunds and duplicate evidence are
                netted; provisional purchases may change when posted.
              </p>
              <WelcomeBonusBar card={primary} />
            </div>
          ) : (
            <p className="text-sm text-text-muted">
              No primary rotating card is active. Use “Make primary” on a
              rotating card below.
            </p>
          )}

          {[...otherRotating, ...keepers].map((card) => (
            <CardRow
              key={card.id}
              card={card}
              onActivate={() => activateCard.mutate(card.id)}
              onDelete={() => deleteCard.mutate(card.id)}
              isActivating={activateCard.isPending}
              isDeleting={deleteCard.isPending}
            />
          ))}
        </div>
      )}
      {cards.some((card) => card.closedDate) ? (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-text-muted">
            Closed card history
          </summary>
          <div className="mt-3 space-y-3">
            {cards
              .filter((card) => card.closedDate)
              .map((card) => (
                <div
                  key={card.id}
                  className="rounded-xl border border-border/30 p-3"
                >
                  <p className="text-sm">
                    {card.product?.productName} · {playerLabel(card.player)}
                  </p>
                  <CardHistoryEditor card={card} />
                </div>
              ))}
          </div>
        </details>
      ) : null}
    </SectionCard>
  )
}
