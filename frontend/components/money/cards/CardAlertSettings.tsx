'use client'

import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { HouseholdConfirmedFact } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useRefreshCatalogResearch } from '@/lib/hooks/useCards'
import { useConfirmFact } from '@/lib/hooks/useHousehold'
import { resolveMonthlyCardCap } from './cards-helpers'

export function CardAlertSettings({
  facts,
  primaryCardId,
}: {
  facts: HouseholdConfirmedFact[]
  primaryCardId: string | null | undefined
}) {
  const refreshResearch = useRefreshCatalogResearch()
  const confirmFact = useConfirmFact()
  const [capDraft, setCapDraft] = useState('')

  const currentCap = resolveMonthlyCardCap(facts, primaryCardId)
  const parsedCap = Number(capDraft)
  const canSaveCap =
    Number.isFinite(parsedCap) && parsedCap > 0 && !confirmFact.isPending

  const researchResult = refreshResearch.data

  return (
    <SectionCard
      variant="surface"
      title="Alerts & research"
      description="Spend-pace, welcome-deadline, rotation-due, and annual-fee alerts push to Telegram via Jenny — nothing to configure here."
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="card-monthly-cap">
              Monthly card-spend cap (currently{' '}
              {formatCurrencyWhole(currentCap)})
            </Label>
            <Input
              id="card-monthly-cap"
              type="number"
              inputMode="decimal"
              min="0"
              step="100"
              placeholder={String(currentCap)}
              className="w-40"
              value={capDraft}
              onChange={(event) => setCapDraft(event.target.value)}
            />
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={!canSaveCap}
            onClick={() => {
              confirmFact.mutate(
                {
                  factKey: 'card_monthly_cap_default',
                  factValue: String(parsedCap),
                },
                { onSuccess: () => setCapDraft('') },
              )
            }}
          >
            Save cap
          </Button>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => refreshResearch.mutate()}
              disabled={refreshResearch.isPending}
            >
              {refreshResearch.isPending
                ? 'Researching…'
                : 'Refresh catalog research'}
            </Button>
            <span className="text-xs text-text-muted">
              Verifies fees, bonuses, and point valuations against current
              public sources (also runs monthly).
            </span>
          </div>
          {researchResult ? (
            <div className="space-y-2 rounded-2xl border border-border/40 bg-surface-muted/10 px-4 py-3 text-sm">
              <p className="text-text">
                {researchResult.updatesApplied} update
                {researchResult.updatesApplied === 1 ? '' : 's'} applied ·{' '}
                {researchResult.candidatesAdded} candidate
                {researchResult.candidatesAdded === 1 ? '' : 's'} added
              </p>
              {researchResult.materialChanges.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-warning">
                  {researchResult.materialChanges.map((change) => (
                    <li key={`${change.headline ?? ''}:${change.detail ?? ''}`}>
                      {change.headline}
                      {change.detail ? ` — ${change.detail}` : ''}
                    </li>
                  ))}
                </ul>
              ) : null}
              {researchResult.researchNotes ? (
                <p className="text-xs text-text-muted">
                  {researchResult.researchNotes}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </SectionCard>
  )
}
