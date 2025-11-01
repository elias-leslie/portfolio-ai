"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAddTicker } from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";

interface AddTickerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accountId: string;
  currentCount?: number;
}

const MAX_TICKERS = 50;
const WARNING_THRESHOLD = 45;

export function AddTickerModal({
  open,
  onOpenChange,
  accountId,
  currentCount = 0,
}: AddTickerModalProps) {
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const addTicker = useAddTicker();

  /**
   * Parse input into array of ticker symbols
   * Accepts comma-separated or newline-separated tickers
   */
  const parseTickers = (text: string): string[] => {
    return text
      .split(/[,\n]/) // Split by comma or newline
      .map((t) => t.trim().toUpperCase()) // Trim and uppercase
      .filter((t) => t.length > 0) // Remove empty strings
      .filter((t, index, arr) => arr.indexOf(t) === index); // Remove duplicates
  };

  /**
   * Validate a single ticker symbol
   */
  const isValidTicker = (symbol: string): boolean => {
    return symbol.length >= 1 && symbol.length <= 10 && /^[A-Z0-9.-]+$/.test(symbol);
  };

  /**
   * Get list of parsed tickers and validation state
   */
  const getParsedTickers = () => {
    const tickers = parseTickers(input);
    const valid = tickers.filter(isValidTicker);
    const invalid = tickers.filter((t) => !isValidTicker(t));
    return { tickers, valid, invalid };
  };

  const { tickers, valid, invalid } = getParsedTickers();
  const isAtLimit = currentCount >= MAX_TICKERS;
  const willExceedLimit = currentCount + valid.length > MAX_TICKERS;
  const showWarning = currentCount >= WARNING_THRESHOLD && currentCount < MAX_TICKERS;
  const canSubmit = valid.length > 0 && !isAtLimit && !willExceedLimit && !isProcessing;

  /**
   * Handle bulk add submission
   * Adds tickers sequentially and tracks progress
   */
  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIsProcessing(true);
    setProgress({ current: 0, total: valid.length });

    const results = {
      success: [] as string[],
      failed: [] as { symbol: string; error: string }[],
    };

    // Add tickers sequentially to avoid overwhelming the API
    for (let i = 0; i < valid.length; i++) {
      const symbol = valid[i];
      setProgress({ current: i + 1, total: valid.length });

      try {
        await new Promise<void>((resolve, reject) => {
          addTicker.mutate(
            {
              account_id: accountId,
              symbol,
              note: undefined,
            },
            {
              onSuccess: () => {
                results.success.push(symbol);
                resolve();
              },
              onError: (error) => {
                results.failed.push({
                  symbol,
                  error: error.message || "Unknown error",
                });
                resolve(); // Continue even if one fails
              },
            }
          );
        });
      } catch (error) {
        results.failed.push({
          symbol,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    // Show summary toast
    if (results.success.length > 0) {
      toast.success(
        `Added ${results.success.length} ticker${results.success.length > 1 ? "s" : ""}: ${results.success.join(", ")}`
      );
    }

    if (results.failed.length > 0) {
      toast.error(
        `Failed to add ${results.failed.length} ticker${results.failed.length > 1 ? "s" : ""}: ${results.failed.map((f) => f.symbol).join(", ")}`
      );
    }

    setIsProcessing(false);
    setProgress({ current: 0, total: 0 });
    setInput("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Tickers to Watchlist</DialogTitle>
          <DialogDescription>
            Enter one or more ticker symbols (one per line or comma-separated)
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
                  You have reached the maximum of {MAX_TICKERS} tickers. Remove
                  some tickers to add more, or contact support to increase your
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
                  Adding {valid.length} tickers would exceed the limit of {MAX_TICKERS}.
                  You currently have {currentCount} tickers. Remove{" "}
                  {currentCount + valid.length - MAX_TICKERS} or more to proceed.
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
                  You have {currentCount} of {MAX_TICKERS} tickers. Free tier
                  API quotas are optimized for up to {MAX_TICKERS} tickers with
                  15-minute refresh intervals.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="tickers">Ticker Symbols</Label>
            <Textarea
              id="tickers"
              placeholder={`Enter tickers (one per line or comma-separated):
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
              {tickers.length > 0 && (
                <>
                  {valid.length > 0 && (
                    <p className="text-profit">
                      ✓ {valid.length} valid ticker{valid.length > 1 ? "s" : ""}: {valid.join(", ")}
                    </p>
                  )}
                  {invalid.length > 0 && (
                    <p className="text-loss">
                      ✗ {invalid.length} invalid ticker{invalid.length > 1 ? "s" : ""}: {invalid.join(", ")}
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
              <div className="rounded-md border bg-background-secondary p-3">
                <p className="text-sm font-medium">
                  Adding tickers... {progress.current}/{progress.total}
                </p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-background-tertiary">
                  <div
                    className="h-full bg-profit transition-all duration-300"
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
              : `Add ${valid.length} Ticker${valid.length !== 1 ? "s" : ""}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
