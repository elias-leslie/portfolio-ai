'use client'

import { useQueryClient } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { createWatchlistItem } from '@/lib/api/watchlist'
import { useTradingRules } from '@/lib/hooks/useRules'
import { watchlistKeys } from '@/lib/hooks/useWatchlist'

interface AddSymbolModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentCount?: number
}

const DEFAULT_MAX_SYMBOLS = 50
const WARNING_THRESHOLD_RATIO = 0.9

export function AddSymbolModal({
  open,
  onOpenChange,
  currentCount = 0,
}: AddSymbolModalProps) {
  const queryClient = useQueryClient()
  const { data: tradingRules } = useTradingRules({ enabled: open })
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })

  /**
   * Parse input into array of symbols
   * Accepts comma-separated or newline-separated symbols
   */
  const parseSymbols = (text: string): string[] => {
    return text
      .split(/[,\n]/) // Split by comma or newline
      .map((t) => t.trim().toUpperCase()) // Trim and uppercase
      .filter((t) => t.length > 0) // Remove empty strings
      .filter((t, index, arr) => arr.indexOf(t) === index) // Remove duplicates
  }

  /**
   * Validate a single symbol
   */
  const isValidSymbol = (symbol: string): boolean => {
    return (
      symbol.length >= 1 && symbol.length <= 10 && /^[A-Z0-9.-]+$/.test(symbol)
    )
  }

  /**
   * Get list of parsed symbols and validation state
   */
  const getParsedSymbols = () => {
    const symbols = parseSymbols(input)
    const valid = symbols.filter(isValidSymbol)
    const invalid = symbols.filter((t) => !isValidSymbol(t))
    return { symbols, valid, invalid }
  }

  const { symbols, valid, invalid } = getParsedSymbols()
  const maxSymbols =
    tradingRules?.watchlistManagement.maxWatchlistSize ?? DEFAULT_MAX_SYMBOLS
  const warningThreshold = Math.max(
    1,
    Math.floor(maxSymbols * WARNING_THRESHOLD_RATIO),
  )
  const isAtLimit = currentCount >= maxSymbols
  const willExceedLimit = currentCount + valid.length > maxSymbols
  const showWarning =
    currentCount >= warningThreshold && currentCount < maxSymbols
  const canSubmit =
    valid.length > 0 && !isAtLimit && !willExceedLimit && !isProcessing

  const summarizeSymbols = (items: string[]) => {
    const preview = items.slice(0, 3).join(', ')
    const remaining = items.length - 3
    return remaining > 0 ? `${preview} and ${remaining} more` : preview
  }

  /**
   * Handle bulk add submission
   * Adds symbols sequentially and tracks progress
   */
  const handleSubmit = async () => {
    if (!canSubmit) return

    setIsProcessing(true)
    setProgress({ current: 0, total: valid.length })

    const results = {
      success: [] as string[],
      failed: [] as { symbol: string; error: string }[],
    }

    // Add symbols sequentially to avoid overwhelming the API
    for (let i = 0; i < valid.length; i++) {
      const symbol = valid[i]
      setProgress({ current: i + 1, total: valid.length })

      try {
        await createWatchlistItem({
          symbol,
          note: undefined,
        })
        results.success.push(symbol)
      } catch (error) {
        results.failed.push({
          symbol,
          error: error instanceof Error ? error.message : 'Unknown error',
        })
      }
    }

    if (results.success.length > 0) {
      await queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(),
        refetchType: 'active',
      })
    }

    setIsProcessing(false)
    setProgress({ current: 0, total: 0 })

    if (results.failed.length === 0) {
      toast.success(
        `Added ${results.success.length} symbol${results.success.length === 1 ? '' : 's'}: ${summarizeSymbols(results.success)}`,
      )
      setInput('')
      onOpenChange(false)
      return
    }

    const failedSymbols = results.failed.map((result) => result.symbol)
    const failedSummary = summarizeSymbols(failedSymbols)

    if (results.success.length > 0) {
      toast.warning(
        `Added ${results.success.length} symbol${results.success.length === 1 ? '' : 's'}. Failed to add ${results.failed.length} symbol${results.failed.length === 1 ? '' : 's'}: ${failedSummary}`,
      )
    } else {
      toast.error(
        `Failed to add ${results.failed.length} symbol${results.failed.length === 1 ? '' : 's'}: ${failedSummary}`,
      )
    }

    const failedSet = new Set(failedSymbols)
    const invalidSet = new Set(invalid)
    const remainingSymbols = symbols.filter(
      (symbol) => failedSet.has(symbol) || invalidSet.has(symbol),
    )
    setInput(remainingSymbols.join('\n'))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="add-symbol-modal"
        className="sm:max-w-[500px]"
      >
        <DialogHeader>
          <DialogTitle>Add Symbols to Watchlist</DialogTitle>
          <DialogDescription>
            Enter one or more symbols (one per line or comma-separated)
          </DialogDescription>
        </DialogHeader>

        {/* Quota warning banner */}
        {isAtLimit && (
          <div className="rounded-md border border-loss bg-loss/10 p-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 text-loss" />
              <div className="flex-1">
                <p className="text-sm font-medium text-loss">
                  Watchlist limit reached
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  You have reached the maximum of {maxSymbols} symbols. Remove
                  some symbols to add more, or contact support to increase your
                  limit.
                </p>
              </div>
            </div>
          </div>
        )}

        {willExceedLimit && !isAtLimit && (
          <div className="rounded-md border border-loss bg-loss/10 p-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 text-loss" />
              <div className="flex-1">
                <p className="text-sm font-medium text-loss">
                  Would exceed watchlist limit
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Adding {valid.length} symbols would exceed the limit of{' '}
                  {maxSymbols}. You currently have {currentCount} symbols.
                  Remove {currentCount + valid.length - maxSymbols} or more to
                  proceed.
                </p>
              </div>
            </div>
          </div>
        )}

        {showWarning && !isAtLimit && !willExceedLimit && (
          <div className="rounded-md border border-accent bg-accent/10 p-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 text-accent" />
              <div className="flex-1">
                <p className="text-sm font-medium text-accent">
                  Approaching watchlist limit
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  You have {currentCount} of {maxSymbols} symbols. Free tier
                  API quotas are optimized for up to {maxSymbols} symbols with
                  15-minute refresh intervals.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="symbols">Symbols</Label>
            <Textarea
              id="symbols"
              placeholder={`Enter symbols (one per line or comma-separated):
AAPL
MSFT, TSLA
NVDA`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={6}
              className="font-mono uppercase"
              autoFocus
              disabled={isProcessing}
            />

            {/* Validation feedback */}
            {symbols.length > 0 && (
              <div className="space-y-1.5 text-xs">
                {valid.length > 0 && (
                  <p className="flex items-start gap-1.5 text-gain">
                    <span className="mt-px shrink-0">&#10003;</span>
                    <span>
                      {valid.length} valid symbol{valid.length > 1 ? 's' : ''}:{' '}
                      {valid.join(', ')}
                    </span>
                  </p>
                )}
                {invalid.length > 0 && (
                  <p className="flex items-start gap-1.5 text-loss">
                    <span className="mt-px shrink-0">&#10007;</span>
                    <span>
                      {invalid.length} invalid symbol
                      {invalid.length > 1 ? 's' : ''}: {invalid.join(', ')}
                      <br />
                      <span className="text-text-muted">
                        Must be 1-10 alphanumeric characters
                      </span>
                    </span>
                  </p>
                )}
              </div>
            )}

            {/* Progress indicator */}
            {isProcessing && (
              <div className="rounded-xl border border-border/50 bg-surface-muted/30 p-3">
                <p className="text-sm font-medium text-text">
                  Adding symbols... {progress.current}/{progress.total}
                </p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted/60">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{
                      width: `${(progress.current / progress.total) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isProcessing}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {isProcessing
              ? `Adding ${progress.current}/${progress.total}...`
              : `Add ${valid.length} Symbol${valid.length !== 1 ? 's' : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
