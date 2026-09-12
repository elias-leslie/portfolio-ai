'use client'

import { useQuery } from '@tanstack/react-query'
import { PlusCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { CreditStance, ValuationStance } from '@/lib/api/cards'
import { get } from '@/lib/api/client'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  useCardCatalog,
  useOwnedCards,
  useRotationPlan,
  useSoftCharges,
} from '@/lib/hooks/useCards'
import { useHouseholdFacts } from '@/lib/hooks/useHousehold'
import { ActiveCardPanel } from './ActiveCardPanel'
import { AddCardDialog, type LinkableAccount } from './AddCardDialog'
import { AddSoftChargeDialog, SoftChargesSection } from './AddSoftChargeDialog'
import { CardAlertSettings } from './CardAlertSettings'
import { CardRankingTable } from './CardRankingTable'
import { CardTermsReview } from './CardTermsReview'
import { PLAYER_PRESETS, RotationTimeline } from './RotationTimeline'
import { RotationValueChart } from './RotationValueChart'
import { WelcomeProgressChart } from './WelcomeProgressChart'

// Mirrors CARD_ADVICE_DISCLAIMER in backend/app/models/credit_cards.py — keep in sync.
const FALLBACK_DISCLAIMER =
  'Informational estimates, not financial advice. Values model publicly known ' +
  'reward structures under the stated assumptions and may differ from your ' +
  'results. Card churning carries credit-score and approval risk; pay balances ' +
  'in full to avoid interest, which erases reward value. Verify current terms ' +
  'with the issuer before acting — approval is never guaranteed.'

export function MoneyCardsPanel({
  dashboard,
}: {
  dashboard?: HouseholdFinanceDashboard
}) {
  const [addCardOpen, setAddCardOpen] = useState(false)
  const [comparisonOpen, setComparisonOpen] = useState(false)
  const [addSoftChargeOpen, setAddSoftChargeOpen] = useState(false)
  const [horizonQuarters, setHorizonQuarters] = useState(8)
  const [playerPreset, setPlayerPreset] = useState('both')
  const [ordinarySpend, setOrdinarySpend] = useState('')
  const [closeAfterYear, setCloseAfterYear] = useState(false)

  const ownedCardsQuery = useOwnedCards()
  const ownedCards = ownedCardsQuery.data ?? []
  const { data: catalog = [] } = useCardCatalog()
  const { data: allSoftCharges = [] } = useSoftCharges()
  const softCharges = allSoftCharges.filter(
    (charge) => charge.status !== 'voided',
  )
  const factsQuery = useHouseholdFacts()
  const facts = factsQuery.data ?? []
  const [valuationStance, setValuationStance] =
    useState<ValuationStance>('balanced')
  const [creditStance, setCreditStance] = useState<CreditStance>('easy_only')
  const monthlyTotal =
    ordinarySpend.trim() && Number.isFinite(Number(ordinarySpend))
      ? Math.max(0, Number(ordinarySpend))
      : null
  const cardSpend = useQuery({
    queryKey: ['cards', 'spend-summary'],
    queryFn: ({ signal }) =>
      get<{ total: number; provisional: number; posted: number }>(
        '/api/household/cards/spend-summary',
        { signal },
      ),
  })

  const players = useMemo(
    () =>
      PLAYER_PRESETS.find((preset) => preset.value === playerPreset)
        ?.players ?? ['p1', 'p2'],
    [playerPreset],
  )
  const rotationQuery = useRotationPlan(
    {
      horizonQuarters,
      players,
      monthlyTotal,
      valuationStance,
      creditStance,
      closeAfterMonths: closeAfterYear ? 13 : null,
    },
    comparisonOpen,
  )

  const accounts = useMemo<LinkableAccount[]>(
    () =>
      (dashboard?.accounts ?? [])
        .filter((account) => account.householdAccountId)
        .map((account) => ({
          householdAccountId: account.householdAccountId as string,
          label: account.label,
        })),
    [dashboard],
  )

  const primaryCard =
    ownedCards.find((card) => card.isPrimaryActive && !card.closedDate) ?? null
  const disclaimer = rotationQuery.data?.disclaimer ?? FALLBACK_DISCLAIMER

  return (
    <div className="space-y-6">
      {ownedCardsQuery.isError ? (
        <LoadErrorState
          title="Failed to load the household wallet."
          onRetry={() => {
            void ownedCardsQuery.refetch()
          }}
          isRetrying={ownedCardsQuery.isFetching}
        />
      ) : (
        <ActiveCardPanel
          cards={ownedCards}
          softCharges={softCharges}
          facts={facts}
          monthToDateSpend={cardSpend.data?.total}
          provisionalSpend={cardSpend.data?.provisional}
          actions={
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setAddCardOpen(true)}
            >
              <PlusCircle className="mr-2 h-4 w-4" />
              Add card
            </Button>
          }
        />
      )}

      <WelcomeProgressChart cards={ownedCards} />

      <SoftChargesSection
        softCharges={softCharges}
        onAdd={() => setAddSoftChargeOpen(true)}
      />

      <CardTermsReview />

      <details
        className="rounded-2xl border border-border/40 p-4"
        onToggle={(event) => setComparisonOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer font-medium">
          Compare cards and plan future rotations
        </summary>
        {comparisonOpen ? (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-end gap-4">
              <label className="space-y-1 text-sm">
                Ordinary eligible card spending per month
                <Input
                  aria-label="Ordinary card spending per month"
                  type="number"
                  min="0"
                  value={ordinarySpend}
                  placeholder="Use confirmed category plan"
                  onChange={(event) => setOrdinarySpend(event.target.value)}
                />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={closeAfterYear}
                  onChange={(event) => setCloseAfterYear(event.target.checked)}
                />
                Model closing new cards after 13 months
              </label>
            </div>

            <CardRankingTable
              monthlyTotal={monthlyTotal}
              valuationStance={valuationStance}
              creditStance={creditStance}
              setValuationStance={setValuationStance}
              setCreditStance={setCreditStance}
            />
            <RotationTimeline
              plan={rotationQuery.data}
              isLoading={rotationQuery.isLoading}
              isFetching={rotationQuery.isFetching}
              error={rotationQuery.error}
              onRetry={() => {
                void rotationQuery.refetch()
              }}
              horizonQuarters={horizonQuarters}
              onHorizonChange={setHorizonQuarters}
              playerPreset={playerPreset}
              onPlayerPresetChange={setPlayerPreset}
              catalog={catalog}
            />

            <RotationValueChart plan={rotationQuery.data} />
            <p className="text-xs text-text-muted">{disclaimer}</p>
          </div>
        ) : null}
      </details>

      {factsQuery.isError ? (
        <LoadErrorState
          title="Failed to load alert settings."
          detail="The saved monthly cap could not be loaded."
          onRetry={() => {
            void factsQuery.refetch()
          }}
          isRetrying={factsQuery.isFetching}
        />
      ) : (
        <CardAlertSettings facts={facts} primaryCardId={primaryCard?.id} />
      )}

      <AddCardDialog
        open={addCardOpen}
        onOpenChange={setAddCardOpen}
        catalog={catalog}
        accounts={accounts}
      />
      <AddSoftChargeDialog
        open={addSoftChargeOpen}
        onOpenChange={setAddSoftChargeOpen}
      />
    </div>
  )
}
