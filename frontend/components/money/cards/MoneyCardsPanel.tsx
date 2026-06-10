'use client'

import { PlusCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
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
import { PLAYER_PRESETS, RotationTimeline } from './RotationTimeline'
import { RotationValueChart } from './RotationValueChart'
import { WelcomeProgressChart } from './WelcomeProgressChart'

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
  const [addSoftChargeOpen, setAddSoftChargeOpen] = useState(false)
  const [horizonQuarters, setHorizonQuarters] = useState(8)
  const [playerPreset, setPlayerPreset] = useState('both')

  const { data: ownedCards = [] } = useOwnedCards()
  const { data: catalog = [] } = useCardCatalog()
  const { data: softCharges = [] } = useSoftCharges()
  const { data: facts = [] } = useHouseholdFacts()

  const players = useMemo(
    () =>
      PLAYER_PRESETS.find((preset) => preset.value === playerPreset)
        ?.players ?? ['p1', 'p2'],
    [playerPreset],
  )
  const rotationQuery = useRotationPlan({ horizonQuarters, players })

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
      <p className="rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-xs text-text-muted">
        {disclaimer}
      </p>

      <ActiveCardPanel
        cards={ownedCards}
        softCharges={softCharges}
        facts={facts}
        monthToDateSpend={dashboard?.budgetSnapshot.monthToDateSpend}
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

      <WelcomeProgressChart cards={ownedCards} />

      <SoftChargesSection
        softCharges={softCharges}
        onAdd={() => setAddSoftChargeOpen(true)}
      />

      <CardRankingTable />

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

      <CardAlertSettings facts={facts} primaryCardId={primaryCard?.id} />

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
