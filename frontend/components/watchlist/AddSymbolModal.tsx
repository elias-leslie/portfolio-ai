'use client'

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
import { useAddSymbol } from '@/lib/hooks/useWatchlist'

interface AddSymbolModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentCount?: number
}

const MAX_SYMBOLS = 50
const WARNING_THRESHOLD = 45

export function AddSymbolModal({
  open,
  onOpenChange,
  currentCount = 0,
}: AddSymbolModalProps) {
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const addSymbol = useAddSymbol()

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
  const isAtLimit = currentCount >= MAX_SYMBOLS
  const willExceedLimit = currentCount + valid.length > MAX_SYMBOLS
  const showWarning =
    currentCount >= WARNING_THRESHOLD && currentCount < MAX_SYMBOLS
  const canSubmit =
    valid.length > 0 && !isAtLimit && !willExceedLimit && !isProcessing

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
        await new Promise<void>((resolve, _reject) => {
          addSymbol.mutate(
            {
              symbol,
              note: undefined,
            },
            {
              onSuccess: () => {
                results.success.push(symbol)
                resolve()
              },
              onError: (error) => {
                results.failed.push({
                  symbol,
                  error: error.message || 'Unknown error',
                })
                resolve() // Continue even if one fails
              },
            },
          )
        })
      } catch (error) {
        results.failed.push({
          symbol,
          error: error instanceof Error ? error.message : 'Unknown error',
        })
      }
    }

    // Show summary toast
    if (results.success.length > 0) {
      toast.success(
        `Added ${results.success.length} symbol${results.success.length > 1 ? 's' : ''}: ${results.success.join(', ')}`,
      )
    }

    if (results.failed.length > 0) {
      toast.error(
        `Failed to add ${results.failed.length} symbol${results.failed.length > 1 ? 's' : ''}: ${results.failed.map((f) => f.symbol).join(', ')}`,
      )
    }

    setIsProcessing(false)
    setProgress({ current: 0, total: 0 })
    setInput('')
    onOpenChange(false)
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
                  You have reached the maximum of {MAX_SYMBOLS} symbols. Remove
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
                  {MAX_SYMBOLS}. You currently have {currentCount} symbols.
                  Remove {currentCount + valid.length - MAX_SYMBOLS} or more to
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
                  You have {currentCount} of {MAX_SYMBOLS} symbols. Free tier
                  API quotas are optimized for up to {MAX_SYMBOLS} symbols with
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
            <div className="space-y-1 text-xs">
              {symbols.length > 0 && (
                <>
                  {valid.length > 0 && (
                    <p className="text-gain">
                      ✓ {valid.length} valid symbol{valid.length > 1 ? 's' : ''}
                      : {valid.join(', ')}
                    </p>
                  )}
                  {invalid.length > 0 && (
                    <p className="text-loss">
                      ✗ {invalid.length} invalid symbol
                      {invalid.length > 1 ? 's' : ''}: {invalid.join(', ')}
                      <br />
                      <span className="text-text-muted">
                        (must be 1-10 alphanumeric characters)
                      </span>
                    </p>
                  )}
                </>
              )}
            </div>

            {/* Progress indicator */}
            {isProcessing && (
              <div className="rounded-xl border border-border/50 bg-surface-muted/30 p-3">
                <p className="text-sm font-medium text-text">
                  Adding symbols... {progress.current}/{progress.total}
                </p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full bg-primary transition-all duration-300"
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
