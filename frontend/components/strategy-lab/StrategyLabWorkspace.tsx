'use client'

import { AlertCircle, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type {
  StrategyLabAction,
  StrategyLabReviewError,
  StrategyLabReviewSuccess,
} from '@/lib/api/strategy-lab'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import {
  useStrategyLabDetail,
  useStrategyLabList,
  useStrategyLabReview,
} from '@/lib/hooks/useStrategyLab'

function actionLabel(action: StrategyLabAction) {
  switch (action) {
    case 'buy_now':
      return 'Buy now'
    case 'buy_in_stages':
      return 'Buy in stages'
    case 'hold':
      return 'Hold'
    case 'wait':
      return 'Wait'
  }
}

function strategyLabel(template: string) {
  return template === 'pullback_accumulator'
    ? 'Pullback Accumulator'
    : 'Breakout Confirmation'
}

function unavailableDetail(item: {
  requestedStartDate: string | null
  requestedEndDate: string | null
  availableStartDate: string | null
  availableEndDate: string | null
  lookbackDays: number | null
}) {
  const requested =
    item.requestedStartDate && item.requestedEndDate
      ? `Requested ${item.requestedStartDate} to ${item.requestedEndDate}.`
      : null
  const available =
    item.availableStartDate && item.availableEndDate
      ? `Available ${item.availableStartDate} to ${item.availableEndDate}.`
      : null
  const lookback =
    item.lookbackDays != null ? `${item.lookbackDays} daily bars found.` : null
  return [requested, available, lookback].filter(Boolean).join(' ')
}

function isReviewError(
  value: StrategyLabReviewSuccess | StrategyLabReviewError,
): value is StrategyLabReviewError {
  return 'status' in value
}

export function StrategyLabWorkspace({
  initialSymbol,
}: {
  initialSymbol: string | null
}) {
  const normalizedInitialSymbol = initialSymbol?.toUpperCase() ?? null
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(
    normalizedInitialSymbol,
  )
  const [reviewResult, setReviewResult] = useState<
    StrategyLabReviewSuccess | StrategyLabReviewError | null
  >(null)
  const lastAppliedInitialSymbol = useRef<string | null>(
    normalizedInitialSymbol,
  )

  const listQuery = useStrategyLabList()
  const listItems = listQuery.data?.items ?? []
  const unavailableItems = listQuery.data?.unavailableItems ?? []
  const detailQuery = useStrategyLabDetail(selectedSymbol)
  const reviewMutation = useStrategyLabReview(selectedSymbol)

  useEffect(() => {
    if (normalizedInitialSymbol !== lastAppliedInitialSymbol.current) {
      lastAppliedInitialSymbol.current = normalizedInitialSymbol
      setSelectedSymbol(normalizedInitialSymbol)
      setReviewResult(null)
    }
  }, [normalizedInitialSymbol])

  useEffect(() => {
    if (!normalizedInitialSymbol && !selectedSymbol && listItems.length > 0) {
      setSelectedSymbol(listItems[0]?.symbol ?? null)
    }
  }, [normalizedInitialSymbol, selectedSymbol, listItems])

  const refreshAll = async () => {
    setReviewResult(null)
    await listQuery.refetch()
    if (selectedSymbol) {
      await detailQuery.refetch()
    }
  }

  const selectedDetail = detailQuery.data
  const staleDetached =
    selectedDetail &&
    !listItems.some((item) => item.symbol === selectedDetail.symbol)

  const listErrorMessage = listQuery.error?.message ?? null
  const detailErrorMessage = detailQuery.error?.message ?? null

  const backtestSummary = useMemo(() => {
    const snapshot = selectedDetail?.backtestSnapshot
    if (!snapshot) return null
    if (snapshot.status !== 'ready') return snapshot.helperText
    return [
      snapshot.totalReturnPct != null
        ? `Strategy ${formatPercent(snapshot.totalReturnPct, { sign: true })}`
        : null,
      snapshot.buyHoldReturnPct != null
        ? `Buy & hold ${formatPercent(snapshot.buyHoldReturnPct, { sign: true })}`
        : null,
      snapshot.maxDrawdownPct != null
        ? `Max drawdown ${formatPercent(snapshot.maxDrawdownPct)}`
        : null,
      `Trades ${snapshot.tradeCount}`,
    ]
      .filter(Boolean)
      .join(' · ')
  }, [selectedDetail])

  return (
    <PageContainer className="space-y-6 py-8">
      <PageHeader
        eyebrow="Investing"
        title="Strategy Lab"
        description="One best current action per symbol, in plain English."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void refreshAll()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button asChild>
              <Link href="/portfolio?tab=symbols">Add Symbol</Link>
            </Button>
          </div>
        }
      />

      {listQuery.isLoading ? (
        <SectionCard variant="surface" title="Strategy Lab">
          <div className="space-y-3">
            <div className="skeleton h-8 rounded-xl" />
            <div className="skeleton h-8 rounded-xl" />
            <div className="skeleton h-8 rounded-xl" />
          </div>
        </SectionCard>
      ) : null}

      {listErrorMessage ? (
        <SectionCard variant="surface" title="Strategy Lab">
          <div className="flex items-start gap-3 text-sm text-text-muted">
            <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
            <p>{listErrorMessage}</p>
          </div>
        </SectionCard>
      ) : null}

      {!listQuery.isLoading &&
      !listErrorMessage &&
      listItems.length === 0 &&
      unavailableItems.length === 0 &&
      !selectedDetail ? (
        <SectionCard variant="surface" title="Strategy Lab">
          <div className="space-y-3 text-sm text-text-muted">
            <p>No symbols are ready for Strategy Lab yet.</p>
            <Button asChild>
              <Link href="/portfolio?tab=symbols">Add Symbol</Link>
            </Button>
          </div>
        </SectionCard>
      ) : null}

      {!listQuery.isLoading &&
      !listErrorMessage &&
      unavailableItems.length > 0 ? (
        <SectionCard variant="surface" title="Partial Data">
          <div className="space-y-3">
            <div className="flex items-start gap-3 text-sm text-text-muted">
              <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
              <div>
                <p className="text-text">
                  {listItems.length > 0
                    ? `${unavailableItems.length} symbol${unavailableItems.length === 1 ? '' : 's'} ${unavailableItems.length === 1 ? 'needs' : 'need'} more data before Strategy Lab can score the backtest cleanly.`
                    : 'No symbols have enough clean data for Strategy Lab yet.'}
                </p>
              </div>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {unavailableItems.map((item) => (
                <div
                  key={`${item.symbol}-${item.reason}`}
                  className="rounded-2xl border border-warning/20 bg-warning/10 p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-text">{item.symbol}</p>
                    <p className="text-xs uppercase tracking-[0.16em] text-warning">
                      {item.reason === 'insufficient_history'
                        ? 'History'
                        : 'Unavailable'}
                    </p>
                  </div>
                  <p className="mt-1 text-sm text-text-muted">{item.message}</p>
                  {unavailableDetail(item) ? (
                    <p className="mt-1 text-xs text-text-muted">
                      {unavailableDetail(item)}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <SectionCard variant="surface" title="Symbols">
          <div className="space-y-2">
            {listItems.map((item) => {
              const active = item.symbol === selectedSymbol
              return (
                <button
                  key={item.symbol}
                  type="button"
                  onClick={() => {
                    setSelectedSymbol(item.symbol)
                    setReviewResult(null)
                  }}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? 'border-primary bg-primary/10'
                      : 'border-border/40 bg-surface-muted/20 hover:border-primary/40'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-text">{item.symbol}</span>
                    <span className="text-xs text-text-muted">
                      {actionLabel(item.action)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-text-muted">
                    {strategyLabel(item.strategyTemplate)}
                  </div>
                  {item.primaryAccountTarget ? (
                    <div className="mt-1 text-xs text-text-muted">
                      {item.primaryAccountTarget.accountName}
                    </div>
                  ) : null}
                  {item.helperText ? (
                    <div className="mt-1 text-xs text-warning">
                      {item.helperText}
                    </div>
                  ) : null}
                </button>
              )
            })}
          </div>
        </SectionCard>

        <div className="space-y-4">
          {staleDetached ? (
            <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
              This symbol is no longer in the fresh list, but its stale detail
              is still shown below.
            </div>
          ) : null}

          {detailErrorMessage ? (
            <SectionCard variant="surface" title="Strategy Lab detail">
              <div className="flex items-start gap-3 text-sm text-text-muted">
                <AlertCircle className="mt-0.5 h-4 w-4 text-warning" />
                <p>{detailErrorMessage}</p>
              </div>
            </SectionCard>
          ) : null}

          {selectedDetail ? (
            <>
              <SectionCard variant="surface" title="Best Signal">
                <p className="font-display italic text-2xl text-text">
                  {actionLabel(selectedDetail.action)}
                </p>
                <p className="mt-2 text-sm text-text-muted">
                  {strategyLabel(selectedDetail.strategyTemplate)} · Updated{' '}
                  {new Date(selectedDetail.updatedAt).toLocaleString()}
                </p>
                {selectedDetail.helperText ? (
                  <p className="mt-3 text-sm text-warning">
                    {selectedDetail.helperText}
                  </p>
                ) : null}
              </SectionCard>

              <SectionCard variant="surface" title="What To Do">
                {selectedDetail.ticket ? (
                  <div className="space-y-2 text-sm text-text-muted">
                    <p>{selectedDetail.ticket.accountName}</p>
                    <p>
                      {formatCurrency(
                        selectedDetail.ticket.firstTrancheDollars,
                      )}{' '}
                      now
                    </p>
                    <p>
                      {selectedDetail.ticket.estimatedShares.toFixed(2)}{' '}
                      estimated shares
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-text-muted">
                    {selectedDetail.helperText ?? 'No trade ticket right now.'}
                  </p>
                )}
              </SectionCard>

              <SectionCard variant="surface" title="Why">
                <ul className="space-y-2 text-sm text-text-muted">
                  {selectedDetail.whyBullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
                <p className="mt-3 text-sm text-text">
                  {selectedDetail.watchItem}
                </p>
              </SectionCard>

              <SectionCard variant="surface" title="Backtest Snapshot">
                <p className="text-sm text-text-muted">{backtestSummary}</p>
                {selectedDetail.backtestSnapshot.equityCurve.length > 0 ? (
                  <div className="mt-3 text-xs text-text-muted">
                    {selectedDetail.backtestSnapshot.equityCurve.length} daily
                    points
                  </div>
                ) : null}
              </SectionCard>

              <SectionCard variant="surface" title="Review">
                {!selectedDetail.review.available ? (
                  <p className="text-sm text-text-muted">
                    {selectedDetail.review.message}
                  </p>
                ) : (
                  <div className="space-y-3">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setReviewResult(null)
                        reviewMutation.mutate(undefined, {
                          onSuccess: (result) => setReviewResult(result),
                          onError: (error) =>
                            setReviewResult({
                              status: 'unavailable',
                              message: error.message,
                            }),
                        })
                      }}
                    >
                      Review
                    </Button>
                    {reviewResult ? (
                      isReviewError(reviewResult) ? (
                        <p className="text-sm text-text-muted">
                          {reviewResult.message}
                        </p>
                      ) : (
                        <div className="space-y-2 text-sm text-text-muted">
                          <p className="font-medium text-text">
                            {reviewResult.verdict}
                          </p>
                          <p>{reviewResult.summary}</p>
                        </div>
                      )
                    ) : (
                      <p className="text-sm text-text-muted">
                        Optional one-shot AI memo.
                      </p>
                    )}
                  </div>
                )}
              </SectionCard>
            </>
          ) : null}
        </div>
      </div>
    </PageContainer>
  )
}
