'use client'

import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiRequest } from '@/lib/api/client'

// ============================================================================
// Types (matching backend TransactionDict)
// ============================================================================

interface Transaction {
  id: string
  tradeId: string
  transactionType: 'ENTRY' | 'EXIT'
  symbol: string
  shares: number
  price: number
  amount: number
  cashBefore: number
  cashAfter: number
  timestamp: string
  notes?: string | null
  // Slippage fields (FEAT-210)
  expectedPrice?: number | null
  slippageAmount?: number | null
  slippageBps?: number | null
  adv?: number | null
  slippageModel?: string | null
}

interface TransactionsListProps {
  limit?: number
}

// ============================================================================
// Component
// ============================================================================

export function TransactionsList({ limit = 50 }: TransactionsListProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        setIsLoading(true)
        const data = await apiRequest<Transaction[]>(
          `/api/paper-trading/transactions?limit=${limit}`,
        )
        setTransactions(data)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch transactions:', err)
        setError(
          err instanceof Error ? err.message : 'Failed to load transactions',
        )
      } finally {
        setIsLoading(false)
      }
    }

    fetchTransactions()
  }, [limit])

  // Format helpers
  const formatCurrency = (value: number) => {
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatDateTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getTypeBadgeVariant = (type: string) => {
    return type === 'ENTRY' ? 'default' : 'secondary'
  }

  // Render states
  if (isLoading) {
    return (
      <div className="p-8 text-center text-text-muted">
        Loading transaction history...
      </div>
    )
  }

  if (error) {
    return <div className="p-8 text-center text-loss">Error: {error}</div>
  }

  if (transactions.length === 0) {
    return (
      <div className="p-8 text-center text-text-muted">
        No transactions yet. Transactions will appear here when trades are
        executed.
      </div>
    )
  }

  // Format slippage for display
  const formatSlippage = (tx: Transaction) => {
    if (tx.slippageBps === null || tx.slippageBps === undefined) {
      return <span className="text-text-muted">—</span>
    }
    const bps = tx.slippageBps
    const cost = tx.slippageAmount ?? 0
    const colorClass =
      bps > 0 ? 'text-loss' : bps < 0 ? 'text-gain' : 'text-text-muted'
    return (
      <span
        className={colorClass}
        title={`Model: ${tx.slippageModel ?? 'N/A'}`}
      >
        {bps > 0 ? '+' : ''}
        {bps.toFixed(1)}bps (${Math.abs(cost).toFixed(2)})
      </span>
    )
  }

  // Main render
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date/Time</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Symbol</TableHead>
            <TableHead className="text-right">Shares</TableHead>
            <TableHead className="text-right">Price</TableHead>
            <TableHead className="text-right">Slippage</TableHead>
            <TableHead className="text-right">Amount</TableHead>
            <TableHead className="text-right">Cash After</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {transactions.map((tx) => (
            <TableRow key={tx.id}>
              <TableCell className="text-text-muted">
                {formatDateTime(tx.timestamp)}
              </TableCell>
              <TableCell>
                <Badge variant={getTypeBadgeVariant(tx.transactionType)}>
                  {tx.transactionType}
                </Badge>
              </TableCell>
              <TableCell className="font-semibold">{tx.symbol}</TableCell>
              <TableCell className="text-right">{tx.shares}</TableCell>
              <TableCell className="text-right">
                {formatCurrency(tx.price)}
              </TableCell>
              <TableCell className="text-right">{formatSlippage(tx)}</TableCell>
              <TableCell className="text-right">
                {formatCurrency(tx.amount)}
              </TableCell>
              <TableCell className="text-right">
                {formatCurrency(tx.cashAfter)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
