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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  const [symbol, setSymbol] = useState("");
  const [note, setNote] = useState("");
  const addTicker = useAddTicker();

  const isValid = () => {
    return symbol.trim().length > 0 && symbol.trim().length <= 10;
  };

  const isAtLimit = currentCount >= MAX_TICKERS;
  const showWarning = currentCount >= WARNING_THRESHOLD && currentCount < MAX_TICKERS;

  const handleSubmit = () => {
    if (!isValid() || isAtLimit) return;

    const symbolUpper = symbol.trim().toUpperCase();

    addTicker.mutate(
      {
        account_id: accountId,
        symbol: symbolUpper,
        note: note.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success(`${symbolUpper} added to watchlist`);
          setSymbol("");
          setNote("");
          onOpenChange(false);
        },
        onError: (error) => {
          toast.error(error.message || "Failed to add ticker");
        },
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isValid() && !addTicker.isPending) {
      handleSubmit();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Add Ticker to Watchlist</DialogTitle>
          <DialogDescription>
            Enter a stock ticker symbol to start tracking price and technical
            indicators
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

        {showWarning && !isAtLimit && (
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
            <Label htmlFor="symbol">Ticker Symbol</Label>
            <Input
              id="symbol"
              placeholder="e.g., AAPL, MSFT, TSLA"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={10}
              className="uppercase"
              autoFocus
              aria-required="true"
              aria-invalid={symbol.length > 0 && !isValid()}
            />
            {symbol.length > 0 && !isValid() && (
              <p className="text-xs text-loss">
                Symbol must be 1-10 characters
              </p>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="note">Notes (optional)</Label>
            <Input
              id="note"
              placeholder="Add a note about this ticker"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={200}
            />
            <p className="text-xs text-text-muted">
              {note.length}/200 characters
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={addTicker.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isValid() || addTicker.isPending || isAtLimit}
          >
            {addTicker.isPending ? "Adding..." : "Add Ticker"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
