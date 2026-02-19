'use client'

import { useSearchParams } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { WatchlistCard } from '@/components/watchlist/WatchlistCard'
import { WatchlistTableRow } from '@/components/watchlist/WatchlistTableRow'
import type { WatchlistItem } from '@/lib/api/watchlist'
import { usePortfolio } from '@/lib/hooks/usePortfolio'
import { usePreferences } from '@/lib/hooks/usePreferences'
import {
  useDeleteWatchlistItem,
  useRefreshStatus,
} from '@/lib/hooks/useWatchlist'
import { useWatchlistChangeDetection } from '@/lib/hooks/useWatchlistChangeDetection'
import {
  type SortDirection,
  type SortField,
  sortWatchlistItems,
} from '@/lib/utils/sortWatchlist'

interface WatchlistTableProps {
  items: WatchlistItem[]
}

export function WatchlistTable({ items }: WatchlistTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [sortField, setSortField] = useState<SortField>('symbol')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [highlightedSymbol, setHighlightedSymbol] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<{
    id: string
    symbol: string
  } | null>(null)

  const deleteMutation = useDeleteWatchlistItem()
  const { data: refreshStatus } = useRefreshStatus()
  const { data: preferences } = usePreferences()
  const { data: portfolio } = usePortfolio()
  const searchParams = useSearchParams()
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map())
  const { changedCells, recentlyUpdatedRows } = useWatchlistChangeDetection(items)

  const userTimezone = preferences?.displayTimezone ?? 'America/New_York'

  const portfolioSymbols = new Set(
    portfolio?.positions?.map((p) => p.symbol.toUpperCase()) ?? [],
  )

  // Scroll to symbol from query parameter
  useEffect(() => {
    const symbol = searchParams?.get('symbol')
    if (symbol && items.length > 0) {
      const targetItem = items.find(
        (item) => item.symbol.toUpperCase() === symbol.toUpperCase(),
      )
      if (targetItem) {
        const rowElement = rowRefs.current.get(targetItem.id)
        if (rowElement) {
          setTimeout(() => {
            rowElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
            setExpandedId(targetItem.id)
            setHighlightedSymbol(targetItem.symbol)
            setTimeout(() => setHighlightedSymbol(null), 3000)
          }, 100)
        }
      }
    }
  }, [searchParams, items])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const renderSortableHeader = (field: SortField, label: string) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      {label}
      {sortField === field && (
        <span className="text-xs">{sortDirection === 'asc' ? '↑' : '↓'}</span>
      )}
    </button>
  )

  const handleDelete = (itemId: string, symbol: string) => {
    setPendingDelete({ id: itemId, symbol })
  }

  const confirmDeleteSymbol = async () => {
    if (!pendingDelete) return
    await deleteMutation.mutateAsync(pendingDelete.id)
    if (expandedId === pendingDelete.id) {
      setExpandedId(null)
    }
  }

  const toggleRow = (itemId: string) => {
    setExpandedId((current) => (current === itemId ? null : itemId))
  }

  const sortedItems = sortWatchlistItems(items, sortField, sortDirection)

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-8 text-center">
        <p className="text-text-muted">
          No symbols in your watchlist yet. Click &quot;Add Symbol&quot; to get
          started.
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-md border border-border bg-surface shadow-sm">
        {/* Desktop Table View (hidden on mobile) */}
        <Table className="hidden md:table">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]" />
              <TableHead>{renderSortableHeader('symbol', 'Symbol')}</TableHead>
              <TableHead>{renderSortableHeader('price', 'Price')}</TableHead>
              <TableHead>{renderSortableHeader('overall', 'Score')}</TableHead>
              <TableHead>{renderSortableHeader('risk', 'Risk')}</TableHead>
              <TableHead>
                <span className="font-medium">DQ</span>
              </TableHead>
              <TableHead>Score Trend</TableHead>
              <TableHead>
                {renderSortableHeader('updated', 'Updated')}
              </TableHead>
              <TableHead className="w-[60px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedItems.map((item) => (
              <WatchlistTableRow
                key={item.id}
                item={item}
                isExpanded={expandedId === item.id}
                highlightedSymbol={highlightedSymbol}
                recentlyUpdatedRows={recentlyUpdatedRows}
                changedCells={changedCells}
                portfolioSymbols={portfolioSymbols}
                refreshStatus={refreshStatus}
                isDeleting={deleteMutation.isPending}
                userTimezone={userTimezone}
                rowRef={(el) => {
                  if (el) {
                    rowRefs.current.set(item.id, el)
                  } else {
                    rowRefs.current.delete(item.id)
                  }
                }}
                onToggle={() => toggleRow(item.id)}
                onDelete={handleDelete}
              />
            ))}
          </TableBody>
        </Table>

        {/* Mobile Card View (shown on mobile only) */}
        <div className="md:hidden space-y-3 p-3">
          {sortedItems.map((item) => (
            <WatchlistCard
              key={item.id}
              item={item}
              onDelete={handleDelete}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      </div>
      <ConfirmActionDialog
        open={!!pendingDelete}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDelete(null)
          }
        }}
        title={pendingDelete ? `Remove ${pendingDelete.symbol}` : 'Remove symbol'}
        description="Removing a symbol clears its saved scores and expansions."
        confirmLabel="Remove"
        isPending={deleteMutation.isPending}
        onConfirm={confirmDeleteSymbol}
      />
    </>
  )
}
