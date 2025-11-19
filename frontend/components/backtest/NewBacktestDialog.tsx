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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useStartBacktest } from "@/lib/hooks/useBacktest";
import { toast } from "sonner";
import { Calendar } from "lucide-react";

interface NewBacktestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewBacktestDialog({
  open,
  onOpenChange,
}: NewBacktestDialogProps) {
  const [ticker, setTicker] = useState("");
  const [strategy, setStrategy] = useState("signal_classifier");
  const [isProcessing, setIsProcessing] = useState(false);
  const startBacktest = useStartBacktest();

  // Calculate default dates (1 year lookback)
  const getDefaultDates = () => {
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setFullYear(startDate.getFullYear() - 1);

    return {
      start: startDate.toISOString().split("T")[0],
      end: endDate.toISOString().split("T")[0],
    };
  };

  const defaultDates = getDefaultDates();
  const [startDate, setStartDate] = useState(defaultDates.start);
  const [endDate, setEndDate] = useState(defaultDates.end);

  /**
   * Validate form inputs
   */
  const getValidationError = (): string | null => {
    if (!ticker.trim()) {
      return "Please enter a ticker symbol";
    }
    if (ticker.length > 10) {
      return "Ticker must be 10 characters or less";
    }
    if (!/^[A-Z0-9.-]+$/.test(ticker.toUpperCase())) {
      return "Ticker must contain only letters, numbers, dots, and dashes";
    }
    if (!startDate) {
      return "Please select a start date";
    }
    if (!endDate) {
      return "Please select an end date";
    }
    if (new Date(startDate) >= new Date(endDate)) {
      return "Start date must be before end date";
    }
    return null;
  };

  const validationError = getValidationError();
  const canSubmit = !validationError && !isProcessing;

  /**
   * Handle form submission
   */
  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIsProcessing(true);
    try {
      await startBacktest.mutateAsync({
        symbol: ticker.toUpperCase(),
        strategy,
        start_date: startDate,
        end_date: endDate,
      });

      // Reset form and close dialog on success
      setTicker("");
      setStrategy("signal_classifier");
      setStartDate(defaultDates.start);
      setEndDate(defaultDates.end);
      onOpenChange(false);
    } catch (error) {
      // Error is already handled by the mutation hook
      console.error("Backtest submission error:", error);
    } finally {
      setIsProcessing(false);
    }
  };

  /**
   * Handle dialog close
   */
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isProcessing) {
      // Reset form on close
      setTicker("");
      setStrategy("signal_classifier");
      setStartDate(defaultDates.start);
      setEndDate(defaultDates.end);
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Start New Backtest</DialogTitle>
          <DialogDescription>
            Test a trading strategy against historical data
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Ticker Input */}
          <div className="grid gap-2">
            <Label htmlFor="ticker">Ticker Symbol</Label>
            <Input
              id="ticker"
              placeholder="e.g., AAPL, TSLA"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              disabled={isProcessing}
              autoFocus
              className="font-mono uppercase"
            />
            <p className="text-xs text-text-muted">
              Enter the stock symbol to backtest
            </p>
          </div>

          {/* Strategy Select */}
          <div className="grid gap-2">
            <Label htmlFor="strategy">Strategy</Label>
            <Select
              value={strategy}
              onValueChange={setStrategy}
              disabled={isProcessing}
            >
              <SelectTrigger id="strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="signal_classifier">
                  Signal Classifier
                </SelectItem>
                <SelectItem value="momentum">Momentum</SelectItem>
                <SelectItem value="mean_reversion">Mean Reversion</SelectItem>
                <SelectItem value="trend_following">Trend Following</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-muted">
              Choose the trading strategy to test
            </p>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-4">
            {/* Start Date */}
            <div className="grid gap-2">
              <Label htmlFor="start-date">Start Date</Label>
              <div className="relative">
                <Input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={isProcessing}
                  className="pr-10"
                />
                <Calendar className="absolute right-3 top-2.5 h-4 w-4 text-text-muted pointer-events-none" />
              </div>
            </div>

            {/* End Date */}
            <div className="grid gap-2">
              <Label htmlFor="end-date">End Date</Label>
              <div className="relative">
                <Input
                  id="end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={isProcessing}
                  className="pr-10"
                />
                <Calendar className="absolute right-3 top-2.5 h-4 w-4 text-text-muted pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Validation Error */}
          {validationError && (
            <div className="rounded-md border border-loss/50 bg-loss/10 p-3">
              <p className="text-sm text-loss">{validationError}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isProcessing}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {isProcessing ? "Starting..." : "Start Backtest"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
