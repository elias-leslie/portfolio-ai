'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import type {
  HouseholdAccountSummary,
  HouseholdDocument,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { formatRelativeTime } from '@/lib/utils'

const freshnessTone = {
  fresh: 'border-gain/25 bg-gain/5 text-gain',
  aging: 'border-warning/25 bg-warning/5 text-warning',
  stale: 'border-loss/25 bg-loss/5 text-loss',
  needs_evidence: 'border-primary/25 bg-primary/5 text-primary',
}

const matchTone = {
  linked: 'border-gain/20 bg-gain/5 text-gain',
  tracked: 'border-border/40 bg-surface-muted/20 text-text-muted',
  candidate: 'border-warning/25 bg-warning/5 text-warning',
}

export function MoneyAccountsPanel({
  accounts,
  documents,
}: {
  accounts: HouseholdAccountSummary[]
  documents: HouseholdDocument[]
}) {
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(
    accounts[0]?.id ?? null,
  )

  useEffect(() => {
    if (!accounts.some((account) => account.id === selectedAccountId)) {
      setSelectedAccountId(accounts[0]?.id ?? null)
    }
  }, [accounts, selectedAccountId])

  const selectedAccount =
    accounts.find((account) => account.id === selectedAccountId) ??
    accounts[0] ??
    null
  const documentsById = Object.fromEntries(
    documents.map((document) => [document.id, document]),
  )

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <SectionCard
        variant="surface"
        title="Account Cards"
      >
        {accounts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            No account/entity cards yet. Upload financial evidence and Jenny
            will either update an existing account or create an explicit
            candidate.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {accounts.map((account) => (
              <button
                key={account.id}
                type="button"
                onClick={() => setSelectedAccountId(account.id)}
                className={`rounded-2xl border p-4 text-left transition-colors ${
                  account.id === selectedAccountId
                    ? 'border-primary/40 bg-primary/10 shadow-[0_0_20px_-10px] shadow-primary/50'
                    : 'border-border/40 bg-surface-muted/15 hover:border-border/60'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">
                      {account.label}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {account.assetGroup} · {account.accountType}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold tabular-nums text-text">
                    {formatCurrencyWhole(account.currentValue)}
                  </p>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <span
                    className={`rounded-full border px-2.5 py-1 ${
                      freshnessTone[
                        account.freshnessStatus as keyof typeof freshnessTone
                      ] ?? freshnessTone.needs_evidence
                    }`}
                  >
                    {account.freshnessLabel}
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-1 ${
                      matchTone[
                        account.matchStatus as keyof typeof matchTone
                      ] ?? matchTone.tracked
                    }`}
                  >
                    {account.matchStatus}
                  </span>
                  <span className="rounded-full border border-border/40 bg-surface/50 px-2.5 py-1 text-text-muted">
                    {account.evidenceCount} source
                    {account.evidenceCount === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {account.gapFlags.slice(0, 3).map((gap) => (
                    <span
                      key={`${account.id}-${gap.code}`}
                      className="rounded-full border border-border/40 bg-surface/60 px-2.5 py-1 text-[11px] text-text-muted"
                    >
                      {gap.title}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Account Detail"
      >
        {!selectedAccount ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            Select an account to inspect the current evidence and any missing
            data.
          </div>
        ) : (
          <div className="space-y-5">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-text">
                    {selectedAccount.label}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    {selectedAccount.institutionName ??
                      'Institution not confirmed'}
                    {selectedAccount.linkedPortfolioAccountName
                      ? ` · linked to ${selectedAccount.linkedPortfolioAccountName}`
                      : ''}
                  </p>
                </div>
                <p className="text-lg font-semibold tabular-nums text-text">
                  {formatCurrencyWhole(selectedAccount.currentValue)}
                </p>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-border/30 bg-surface/60 px-3 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                    Freshness
                  </p>
                  <p className="mt-2 text-sm font-semibold text-text">
                    {selectedAccount.freshnessLabel}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {selectedAccount.lastEvidenceAt
                      ? `Last evidence ${formatRelativeTime(selectedAccount.lastEvidenceAt)}`
                      : 'No financial evidence linked yet'}
                  </p>
                </div>
                <div className="rounded-xl border border-border/30 bg-surface/60 px-3 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                    Match confidence
                  </p>
                  <p className="mt-2 text-sm font-semibold text-text">
                    {selectedAccount.matchConfidence != null
                      ? `${Math.round(selectedAccount.matchConfidence * 100)}%`
                      : '—'}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Status: {selectedAccount.matchStatus}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                Gaps
              </p>
              {selectedAccount.gapFlags.length === 0 ? (
                <p className="mt-3 text-sm text-text-muted">
                  Jenny does not currently see an explicit freshness or
                  data-completeness gap here.
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {selectedAccount.gapFlags.map((gap) => (
                    <div
                      key={`${selectedAccount.id}-${gap.code}`}
                      className="rounded-xl border border-border/30 bg-surface/60 px-3 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">
                          {gap.title}
                        </p>
                        <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          {gap.severity}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-text-muted">
                        {gap.detail}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                Supporting documents
              </p>
              {selectedAccount.documentIds.length === 0 ? (
                <p className="mt-3 text-sm text-text-muted">
                  No supporting documents are attached to this account yet.
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {selectedAccount.documentIds.map((documentId) => {
                    const document = documentsById[documentId]
                    return (
                      <div
                        key={documentId}
                        className="flex items-center justify-between gap-3 rounded-xl border border-border/30 bg-surface/60 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-text">
                            {document?.filename ?? documentId}
                          </p>
                          <p className="text-xs text-text-muted">
                            {document?.sourceType ?? 'unknown'} ·{' '}
                            {document?.status ?? 'unavailable'}
                          </p>
                        </div>
                        <span className="text-xs text-text-muted">
                          {document?.uploadedAt
                            ? formatRelativeTime(document.uploadedAt)
                            : 'Stored review'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
