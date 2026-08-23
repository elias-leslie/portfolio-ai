import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdLedgerEntry } from '@/lib/api/household'
import { LedgerRow } from '../LedgerRow'

function entry(
  overrides: Partial<HouseholdLedgerEntry> = {},
): HouseholdLedgerEntry {
  return {
    id: 'txn-1',
    kind: 'transaction',
    itemCount: 0,
    itemCategories: [],
    direction: 'debit',
    description: 'ZELLE TO MARIA TUTORING',
    merchant: 'Zelle',
    amount: 200,
    date: '2026-07-14',
    rowHash: 'hash-1',
    category: 'Household',
    essentiality: 'mixed',
    includedInSpend: false,
    exclusionReason: 'cash_movement:description:zelle to',
    exclusionRule: 'description:zelle to',
    exclusionLabel: 'Zelle sent',
    exclusionIsAppealable: true,
    spendOverride: null,
    ...overrides,
  } as HouseholdLedgerEntry
}

function renderRow(
  ledgerEntry: HouseholdLedgerEntry,
  onSetSpendOverride = vi.fn(),
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <table>
        <tbody>
          <LedgerRow
            entry={ledgerEntry}
            auditOpen={false}
            onToggleAudit={vi.fn()}
            categoryOptions={['Household']}
            categorizePending={false}
            onSetSpendOverride={onSetSpendOverride}
          />
        </tbody>
      </table>
    </QueryClientProvider>,
  )
  return onSetSpendOverride
}

describe('LedgerRow spend appeal', () => {
  it('says which rule dropped the row, in words rather than an enum', () => {
    renderRow(entry())

    expect(screen.getByText('Zelle sent')).toBeInTheDocument()
    expect(screen.queryByText(/cash_movement/i)).not.toBeInTheDocument()
  })

  it('offers to count a dropped row as spend', () => {
    const onSetSpendOverride = renderRow(entry())

    fireEvent.click(screen.getByRole('button', { name: 'Count this as spend' }))

    expect(onSetSpendOverride).toHaveBeenCalledWith(true)
  })

  it('offers to drop a counted row', () => {
    const onSetSpendOverride = renderRow(
      entry({
        description: 'TARGET',
        merchant: 'Target',
        includedInSpend: true,
        exclusionReason: null,
        exclusionRule: null,
        exclusionLabel: null,
        exclusionIsAppealable: false,
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: "Don't count this" }))

    expect(onSetSpendOverride).toHaveBeenCalledWith(false)
  })

  it('lets an appeal be withdrawn, so a wrong appeal is not permanent', () => {
    const onSetSpendOverride = renderRow(
      entry({ includedInSpend: true, spendOverride: 'include' }),
    )

    expect(
      screen.getByText('You said this counts as spend'),
    ).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole('button', { name: 'Undo — let the rules decide' }),
    )

    expect(onSetSpendOverride).toHaveBeenCalledWith(null)
  })

  it('does not invite an appeal against a rule that is not about wording', () => {
    // A row excluded because it is income is not a filter's guess about a
    // string, and offering to overrule it would be offering the wrong argument.
    renderRow(
      entry({
        description: 'PAYROLL',
        includedInSpend: false,
        exclusionReason: 'non_expense_flow',
        exclusionRule: null,
        exclusionLabel: null,
        exclusionIsAppealable: false,
      }),
    )

    expect(
      screen.queryByRole('button', { name: /count this/i }),
    ).not.toBeInTheDocument()
  })
})
