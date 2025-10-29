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

interface AddTickerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accountId: string;
}

export function AddTickerModal({
  open,
  onOpenChange,
  accountId,
}: AddTickerModalProps) {
  const [symbol, setSymbol] = useState("");
  const [note, setNote] = useState("");
  const addTicker = useAddTicker();

  const isValid = () => {
    return symbol.trim().length > 0 && symbol.trim().length <= 10;
  };

  const handleSubmit = () => {
    if (!isValid()) return;

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
            disabled={!isValid() || addTicker.isPending}
          >
            {addTicker.isPending ? "Adding..." : "Add Ticker"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
