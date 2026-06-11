'use client'

import { useEffect, useState } from 'react'
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
import type { ManualHoldingEntryInput } from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'
import {
  useHouseholdAccountHoldings,
  useReplaceHouseholdAccountHoldings,
} from '@/lib/hooks/useHousehold'

type EntryMode = 'percent' | 'shares'

interface EntryRow {
  symbol: string
  amount: string
}

interface HouseholdHoldingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  householdAccountId: string | null
  accountLabel: string
  accountValue: number
}

const EMPTY_ROW: EntryRow = { symbol: '', amount: '' }

export function HouseholdHoldingsDialog({
  open,
  onOpenChange,
  householdAccountId,
  accountLabel,
  accountValue,
}: HouseholdHoldingsDialogProps) {
  const { data: holdings, isLoading } = useHouseholdAccountHoldings(
    open ? householdAccountId : null,
  )
  const replaceHoldings = useReplaceHouseholdAccountHoldings()

  const [mode, setMode] = useState<EntryMode>('percent')
  const [rows, setRows] = useState<EntryRow[]>([EMPTY_ROW])
  const [seededFor, setSeededFor] = useState<string | null>(null)

  // Seed editable rows from saved positions once per dialog open/account.
  useEffect(() => {
    if (!open) {
      setSeededFor(null)
      return
    }
    if (!holdings || seededFor === holdings.householdAccountId) return
    if (holdings.positions.length > 0) {
      setMode('shares')
      setRows(
        holdings.positions.map((position) => ({
          symbol: position.symbol,
          amount: String(position.shares),
        })),
      )
    } else {
      setMode('percent')
      setRows([EMPTY_ROW])
    }
    setSeededFor(holdings.householdAccountId)
  }, [open, holdings, seededFor])

  const parsedRows = rows
    .map((row) => ({
      symbol: row.symbol.trim().toUpperCase(),
      amount: parseFloat(row.amount),
    }))
    .filter((row) => row.symbol.length > 0 || !Number.isNaN(row.amount))
  const completeRows = parsedRows.filter(
    (row) =>
      row.symbol.length > 0 && Number.isFinite(row.amount) && row.amount > 0,
  )
  const percentTotal =
    mode === 'percent'
      ? completeRows.reduce((sum, row) => sum + row.amount, 0)
      : null
  const percentOver = percentTotal !== null && percentTotal > 100.0001
  const canSubmit =
    completeRows.length > 0 &&
    completeRows.length === parsedRows.length &&
    !percentOver &&
    !replaceHoldings.isPending

  const handleSubmit = () => {
    if (!householdAccountId || !canSubmit) return
    const entries: ManualHoldingEntryInput[] = completeRows.map((row) =>
      mode === 'percent'
        ? { symbol: row.symbol, percent: row.amount }
        : { symbol: row.symbol, shares: row.amount },
    )
    replaceHoldings.mutate(
      {
        householdAccountId,
        payload: {
          entries,
          accountValue: mode === 'percent' ? accountValue : undefined,
        },
      },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  const updateRow = (index: number, patch: Partial<EntryRow>) => {
    setRows((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, ...patch } : row,
      ),
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Holdings — {accountLabel}</DialogTitle>
          <DialogDescription>
            Enter what this account holds so projections use its real
            allocation. The account value (
            {formatCurrency(accountValue, { decimals: 0 })}) stays
            authoritative; holdings set the mix. For institutional funds without
            a ticker, use the closest public proxy (e.g. VTI for a US
            total-market index fund, BND for core bonds).
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === 'percent' ? 'default' : 'outline'}
            onClick={() => setMode('percent')}
          >
            By percent
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === 'shares' ? 'default' : 'outline'}
            onClick={() => setMode('shares')}
          >
            By shares
          </Button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            handleSubmit()
          }}
        >
          {isLoading ? (
            <p className="py-4 text-sm text-text-muted">Loading holdings…</p>
          ) : (
            <div className="space-y-2">
              {rows.map((row, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    aria-label={`Symbol ${index + 1}`}
                    placeholder="Symbol (e.g. VTI)"
                    value={row.symbol}
                    onChange={(event) =>
                      updateRow(index, {
                        symbol: event.target.value.toUpperCase(),
                      })
                    }
                  />
                  <Input
                    aria-label={
                      mode === 'percent'
                        ? `Percent ${index + 1}`
                        : `Shares ${index + 1}`
                    }
                    placeholder={mode === 'percent' ? '% of account' : 'Shares'}
                    type="number"
                    min="0"
                    step="any"
                    value={row.amount}
                    onChange={(event) =>
                      updateRow(index, { amount: event.target.value })
                    }
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`Remove row ${index + 1}`}
                    disabled={rows.length === 1}
                    onClick={() =>
                      setRows((current) =>
                        current.filter((_, rowIndex) => rowIndex !== index),
                      )
                    }
                  >
                    ✕
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setRows((current) => [...current, EMPTY_ROW])}
              >
                Add row
              </Button>
              {percentTotal !== null && completeRows.length > 0 ? (
                <p
                  className={`text-xs ${percentOver ? 'text-danger' : 'text-text-muted'}`}
                >
                  Total: {percentTotal.toFixed(1)}%
                  {percentOver
                    ? ' — cannot exceed 100%'
                    : percentTotal < 99.5
                      ? ' — remainder is treated as unclassified account value'
                      : ''}
                </p>
              ) : null}
            </div>
          )}
          <DialogFooter className="mt-4">
            <Button
              type="submit"
              disabled={!canSubmit}
              aria-busy={replaceHoldings.isPending}
            >
              {replaceHoldings.isPending ? 'Saving…' : 'Save holdings'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
