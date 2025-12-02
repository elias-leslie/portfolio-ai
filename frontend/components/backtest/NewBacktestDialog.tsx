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
import { Slider } from "@/components/ui/slider";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useStartBacktest } from "@/lib/hooks/useBacktest";
import { Calendar, ChevronDown, Settings2 } from "lucide-react";

interface NewBacktestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Strategy descriptions for tooltips
const STRATEGY_INFO: Record<string, string> = {
  enhanced: "Multi-confirmation technical strategy with configurable parameters",
  signal_classifier: "Original signal classifier using technical indicators",
  momentum: "Rides intermediate-term momentum with trend confirmation",
  mean_reversion: "Catches oversold bounces in uptrending stocks",
  trend_following: "Follows strong trends with trailing ATR stops",
};

export function NewBacktestDialog({
  open,
  onOpenChange,
}: NewBacktestDialogProps) {
  const [ticker, setTicker] = useState("");
  const [strategy, setStrategy] = useState("enhanced");
  const [isProcessing, setIsProcessing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const startBacktest = useStartBacktest();

  // Strategy parameters with defaults
  const [stopLossAtr, setStopLossAtr] = useState(2.0);
  const [maxHoldingDays, setMaxHoldingDays] = useState(30);
  const [targetProfitPct, setTargetProfitPct] = useState(15);
  const [minConfirmations, setMinConfirmations] = useState(5);

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
   * Reset form to defaults
   */
  const resetForm = () => {
    setTicker("");
    setStrategy("enhanced");
    setStartDate(defaultDates.start);
    setEndDate(defaultDates.end);
    setStopLossAtr(2.0);
    setMaxHoldingDays(30);
    setTargetProfitPct(15);
    setMinConfirmations(5);
    setShowAdvanced(false);
  };

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
        parameters: {
          stop_loss_atr_multiplier: stopLossAtr,
          max_holding_days: maxHoldingDays,
          target_profit_pct: targetProfitPct,
          min_confirmations: minConfirmations,
        },
      });

      // Reset form and close dialog on success
      resetForm();
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
      resetForm();
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
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
                <SelectItem value="enhanced">Enhanced Signal</SelectItem>
                <SelectItem value="signal_classifier">
                  Signal Classifier
                </SelectItem>
                <SelectItem value="momentum">Momentum</SelectItem>
                <SelectItem value="mean_reversion">Mean Reversion</SelectItem>
                <SelectItem value="trend_following">Trend Following</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-muted">
              {STRATEGY_INFO[strategy] || "Select a strategy"}
            </p>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-4">
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

          {/* Advanced Parameters (Collapsible) */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-between text-text-muted hover:text-text"
                disabled={isProcessing}
              >
                <span className="flex items-center gap-2">
                  <Settings2 className="h-4 w-4" />
                  Advanced Parameters
                </span>
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${
                    showAdvanced ? "rotate-180" : ""
                  }`}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4 space-y-4 rounded-lg border border-border bg-card p-4">
              {/* Stop Loss ATR Multiplier */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Stop Loss</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {stopLossAtr.toFixed(1)}x ATR
                  </span>
                </div>
                <Slider
                  value={[stopLossAtr]}
                  onValueChange={([v]) => setStopLossAtr(v)}
                  min={1.0}
                  max={4.0}
                  step={0.5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Exit when price drops this many ATR from entry
                </p>
              </div>

              {/* Max Holding Days */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Max Holding Period</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {maxHoldingDays} days
                  </span>
                </div>
                <Slider
                  value={[maxHoldingDays]}
                  onValueChange={([v]) => setMaxHoldingDays(v)}
                  min={5}
                  max={120}
                  step={5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Force exit after this many days regardless of price
                </p>
              </div>

              {/* Target Profit % */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Target Profit</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {targetProfitPct}%
                  </span>
                </div>
                <Slider
                  value={[targetProfitPct]}
                  onValueChange={([v]) => setTargetProfitPct(v)}
                  min={5}
                  max={50}
                  step={5}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Take profit when gain reaches this percentage
                </p>
              </div>

              {/* Min Confirmations */}
              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Min Confirmations</Label>
                  <span className="text-sm font-mono text-text-muted">
                    {minConfirmations} / 8
                  </span>
                </div>
                <Slider
                  value={[minConfirmations]}
                  onValueChange={([v]) => setMinConfirmations(v)}
                  min={3}
                  max={8}
                  step={1}
                  disabled={isProcessing}
                  className="w-full"
                />
                <p className="text-xs text-text-muted">
                  Minimum technical confirmations required to enter trade
                </p>
              </div>
            </CollapsibleContent>
          </Collapsible>

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
