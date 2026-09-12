'use client'

import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { put } from '@/lib/api/client'
import { formatCurrencyWhole } from '@/lib/formatters'

type BasisAccount = {
  accountId: string
  label: string
  marketValue: number
  coveredValue: number
  costBasis: number
  source: string
  fingerprint: string
  confirmationStale: boolean
}
type BasisSensitivity = {
  label: string
  endingBalance: number
  totalTax: number
}
type BasisCoverage = {
  coverage: number
  accounts: BasisAccount[]
  sensitivity?: BasisSensitivity[]
}
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null
const numeric = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)
function parseCoverage(value: unknown): BasisCoverage | null {
  if (
    !record(value) ||
    !numeric(value.coverage) ||
    !Array.isArray(value.accounts)
  )
    return null
  const accounts = value.accounts.filter(
    (item: unknown): item is BasisAccount =>
      record(item) &&
      ['accountId', 'label', 'source', 'fingerprint'].every(
        (key) => typeof item[key] === 'string',
      ) &&
      ['marketValue', 'coveredValue', 'costBasis'].every((key) =>
        numeric(item[key]),
      ) &&
      typeof item.confirmationStale === 'boolean',
  )
  const sensitivity = Array.isArray(value.sensitivity)
    ? value.sensitivity.filter(
        (item: unknown): item is BasisSensitivity =>
          record(item) &&
          typeof item.label === 'string' &&
          numeric(item.endingBalance) &&
          numeric(item.totalTax),
      )
    : []
  return { coverage: value.coverage, accounts, sensitivity }
}

export function RetirementBasisCoverage({ value }: { value: unknown }) {
  const coverage = parseCoverage(value)
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  if (!coverage || coverage.accounts.length === 0) return null
  return (
    <details
      id="retirement-basis-coverage"
      className="mt-4 rounded-xl border border-border/40 p-3"
    >
      <summary className="cursor-pointer text-sm font-medium">
        Taxable cost basis · {(coverage.coverage * 100).toFixed(1)}% covered
      </summary>
      <p className="my-3 text-xs text-text-muted">
        Only matched tax lots, explicit broker purchase costs, or your confirmed
        basis count. Enter the total acquisition cost of investments in an
        account, excluding its cash balance. Confirmations expire when holdings
        or cash change.
      </p>
      {coverage.accounts.map((account) => (
        <div
          key={account.accountId || account.label}
          className="my-3 border-t border-border/30 pt-3"
        >
          <p className="text-sm">
            {account.label}: {formatCurrencyWhole(account.coveredValue)} of{' '}
            {formatCurrencyWhole(account.marketValue)} has basis evidence.
          </p>
          {account.confirmationStale && (
            <p className="text-xs text-warning">
              Holdings changed since your basis confirmation.
            </p>
          )}
          {account.accountId && (
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <label className="text-xs">
                Total investment cost basis ($)
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={draft[account.accountId] ?? ''}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      [account.accountId]: event.target.value,
                    })
                  }
                />
              </label>
              <Button
                size="sm"
                variant="outline"
                disabled={
                  busy !== null ||
                  !draft[account.accountId]?.trim() ||
                  !Number.isFinite(Number(draft[account.accountId])) ||
                  Number(draft[account.accountId]) < 0
                }
                onClick={async () => {
                  setBusy(account.accountId)
                  setError(null)
                  try {
                    await put(
                      `/api/retirement/basis/${encodeURIComponent(account.accountId)}`,
                      {
                        fingerprint: account.fingerprint,
                        costBasis: Number(draft[account.accountId]),
                      },
                    )
                    setDraft({ ...draft, [account.accountId]: '' })
                    await queryClient.invalidateQueries({
                      queryKey: ['retirement', 'preview'],
                    })
                  } catch (err) {
                    setError(
                      err instanceof Error
                        ? err.message
                        : 'Could not confirm basis.',
                    )
                  } finally {
                    setBusy(null)
                  }
                }}
              >
                {busy === account.accountId ? 'Saving…' : 'Confirm basis'}
              </Button>
            </div>
          )}
        </div>
      ))}
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      {!!coverage.sensitivity?.length && (
        <div className="mt-4 text-xs">
          <p className="font-medium">
            Uncovered basis bounds, using the same expected-return forecast
          </p>
          <p className="text-text-muted">
            These are assumption bounds, not probabilities. Ending balances and
            cumulative taxes are nominal dollars.
          </p>
          {coverage.sensitivity.map((row) => (
            <p className="mt-2" key={row.label}>
              {row.label}: {formatCurrencyWhole(row.endingBalance)} ending
              balance; {formatCurrencyWhole(row.totalTax)} cumulative federal
              tax.
            </p>
          ))}
        </div>
      )}
    </details>
  )
}
