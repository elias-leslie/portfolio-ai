'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { get } from '@/lib/api/client'
import { formatCurrency } from '@/lib/formatters'

type LotResponse = {
  quotePrice: number | null
  quoteTime: string | null
  quoteSource: string | null
  accounts: {
    accountId: string
    accountName: string
    taxable: boolean
    positionShares: number
    recordedLotShares: number
    coverage: 'complete' | 'partial' | 'missing' | 'mismatch'
    lots: {
      id: string
      acquiredDate: string
      remainingShares: number
      remainingBasis: number
      gainAtQuote: number | null
    }[]
  }[]
}

export function SymbolLotEvidence({ symbol }: { symbol: string }) {
  const [open, setOpen] = useState(false)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['portfolio', 'lots', symbol],
    queryFn: () =>
      get<LotResponse>(`/api/portfolio/tlh/lots/${encodeURIComponent(symbol)}`),
    enabled: open,
    staleTime: 30_000,
  })
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Review tax lots before a sale
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90dvh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{symbol} · recorded tax lots</DialogTitle>
            <DialogDescription>
              Compare recorded basis with the current quote. Missing lots remain
              unknown; this does not estimate tax owed or submit a sale.
            </DialogDescription>
          </DialogHeader>
          {isLoading ? <p role="status">Loading recorded lots…</p> : null}
          {error ? (
            <div role="alert">
              Recorded lots could not be loaded.{' '}
              <Button variant="outline" onClick={() => void refetch()}>
                Retry
              </Button>
            </div>
          ) : null}
          {data ? (
            <>
              <p className="text-sm text-text-muted">
                {data.quotePrice != null ? (
                  <>
                    Quote {formatCurrency(data.quotePrice)} ·{' '}
                    {data.quoteSource ?? 'Source unavailable'} ·{' '}
                    {data.quoteTime ? (
                      <RelativeTime value={data.quoteTime} />
                    ) : (
                      'Quote time unavailable'
                    )}
                  </>
                ) : (
                  'Quote unavailable; gains are not calculated.'
                )}
              </p>
              {data.accounts.length === 0 ? (
                <p>No current long position was found in non-paper accounts.</p>
              ) : null}
              {data.accounts.map((account) => (
                <section
                  key={account.accountId}
                  className="space-y-3 rounded-xl border border-border p-4"
                >
                  <h3 className="font-medium">{account.accountName}</h3>
                  <p className="text-sm text-text-muted">
                    {account.taxable
                      ? 'Taxable account'
                      : 'Tax-advantaged account'}{' '}
                    · {account.recordedLotShares.toLocaleString()} shares in
                    recorded lots / {account.positionShares.toLocaleString()}{' '}
                    held
                  </p>
                  <p className="text-sm">
                    {account.coverage === 'complete'
                      ? 'Recorded lot quantities match this position.'
                      : account.coverage === 'mismatch'
                        ? 'Lot quantities exceed the current position. Reconcile the account before relying on these lots.'
                        : 'Complete acquisition dates and basis are not established. Review an account statement or activity history.'}
                  </p>
                  {account.lots.map((lot) => (
                    <div
                      key={lot.id}
                      className="grid grid-cols-2 gap-2 border-t border-border pt-3 text-sm"
                    >
                      <span>Acquired {lot.acquiredDate}</span>
                      <span>{lot.remainingShares.toLocaleString()} shares</span>
                      <span>
                        Remaining basis {formatCurrency(lot.remainingBasis)}
                      </span>
                      <span>
                        Gain at quote{' '}
                        {lot.gainAtQuote == null
                          ? 'Unavailable'
                          : formatCurrency(lot.gainAtQuote)}
                      </span>
                    </div>
                  ))}
                </section>
              ))}
              <Link
                href="/money?tab=accounts&focus=account-coverage"
                className="text-sm text-primary underline"
              >
                Check account evidence and coverage
              </Link>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}
