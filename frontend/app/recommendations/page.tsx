"use client";

import { useState } from "react";
import { Target, TrendingUp, TrendingDown, AlertCircle, DollarSign, Briefcase, LineChart, Sparkles, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRecommendations, usePaperTrade, useTrackInPortfolio } from "@/lib/hooks/useRecommendations";
import { useAccounts } from "@/lib/hooks/usePortfolio";
import type { TradeRecommendation } from "@/lib/api/recommendations";

function SignalBadge({ type, strength }: { type: string; strength: number }) {
  if (type === "BUY") {
    return (
      <Badge className="bg-green-500/90 text-white">
        <TrendingUp className="mr-1 h-3 w-3" />
        BUY {strength}/10
      </Badge>
    );
  }
  if (type === "SELL") {
    return (
      <Badge className="bg-red-500/90 text-white">
        <TrendingDown className="mr-1 h-3 w-3" />
        SELL {strength}/10
      </Badge>
    );
  }
  return (
    <Badge variant="outline">
      HOLD {strength}/10
    </Badge>
  );
}

function SignalStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "better_entry":
      return (
        <Badge className="bg-emerald-500/90 text-white">
          <Sparkles className="mr-1 h-3 w-3" />
          Better Entry
        </Badge>
      );
    case "caution":
      return (
        <Badge className="bg-amber-500/90 text-white">
          <AlertTriangle className="mr-1 h-3 w-3" />
          Caution
        </Badge>
      );
    default:
      return null; // Don't show badge for "valid" status
  }
}

function RecommendationCard({
  rec,
  onPaperTrade,
  onTrackInPortfolio,
  isPaperTrading,
}: {
  rec: TradeRecommendation;
  onPaperTrade: () => void;
  onTrackInPortfolio: () => void;
  isPaperTrading: boolean;
}) {
  const riskReward = rec.risk_reward_ratio;
  const potentialGain = rec.target_price - rec.current_price;
  const potentialLoss = rec.current_price - rec.stop_loss;
  const potentialGainPct = (potentialGain / rec.current_price) * 100;
  const potentialLossPct = (potentialLoss / rec.current_price) * 100;
  const priceChange = rec.current_price - rec.entry_price;
  const priceChangePct = (priceChange / rec.entry_price) * 100;

  return (
    <Card className={`transition-shadow hover:shadow-lg ${rec.signal_status === "caution" ? "border-amber-300 dark:border-amber-700" : ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex flex-wrap items-center gap-2 text-xl">
              {rec.symbol}
              <SignalBadge type={rec.signal_type} strength={rec.signal_strength} />
              <SignalStatusBadge status={rec.signal_status} />
            </CardTitle>
            <p className="mt-1 text-sm text-text-muted">
              {rec.strategy_name} ({rec.strategy_type})
            </p>
          </div>
          {rec.expected_sharpe && (
            <Badge variant="outline" className="text-xs">
              Sharpe: {rec.expected_sharpe.toFixed(2)}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current Price Banner */}
        <div className="flex items-center justify-between rounded-lg bg-surface-muted p-3">
          <div>
            <p className="text-xs font-medium text-text-muted">Current Price</p>
            <p className="text-2xl font-bold">${rec.current_price.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Since Signal</p>
            <p className={`text-lg font-bold ${priceChange >= 0 ? "text-green-600" : "text-red-600"}`}>
              {priceChange >= 0 ? "+" : ""}{priceChangePct.toFixed(2)}%
            </p>
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="rounded-lg bg-red-50 p-3 dark:bg-red-950/30">
            <p className="text-xs font-medium text-red-600 dark:text-red-400">Stop Loss</p>
            <p className="text-lg font-bold text-red-700 dark:text-red-300">
              ${rec.stop_loss.toFixed(2)}
            </p>
            <p className="text-xs text-red-500">-{potentialLossPct.toFixed(1)}%</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-950/30">
            <p className="text-xs font-medium text-blue-600 dark:text-blue-400">Signal Price</p>
            <p className="text-lg font-bold text-blue-700 dark:text-blue-300">
              ${rec.entry_price.toFixed(2)}
            </p>
            <p className="text-xs text-blue-500">{rec.signal_date}</p>
          </div>
          <div className="rounded-lg bg-green-50 p-3 dark:bg-green-950/30">
            <p className="text-xs font-medium text-green-600 dark:text-green-400">Target</p>
            <p className="text-lg font-bold text-green-700 dark:text-green-300">
              ${rec.target_price.toFixed(2)}
            </p>
            <p className="text-xs text-green-500">+{potentialGainPct.toFixed(1)}%</p>
          </div>
        </div>

        {/* Position Sizing */}
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-muted/50 p-3">
          <div>
            <p className="text-sm font-medium">Position Size</p>
            <p className="text-xs text-text-muted">
              {rec.position_size_shares} shares @ ${rec.current_price.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-lg font-bold">${rec.position_size_dollars.toLocaleString()}</p>
            <p className="text-xs text-text-muted">
              R/R: {riskReward > 0 ? `1:${riskReward.toFixed(1)}` : "N/A"}
            </p>
          </div>
        </div>

        {/* Signal Reasons */}
        <div>
          <p className="mb-2 text-xs font-medium text-text-muted">Signal Reasons:</p>
          <div className="flex flex-wrap gap-1">
            {rec.signal_reasons.slice(0, 4).map((reason, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {reason}
              </Badge>
            ))}
            {rec.signal_reasons.length > 4 && (
              <Badge variant="outline" className="text-xs">
                +{rec.signal_reasons.length - 4} more
              </Badge>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Button
            onClick={onPaperTrade}
            disabled={isPaperTrading}
            className="flex-1"
            variant={rec.signal_type === "BUY" ? "default" : "outline"}
          >
            <LineChart className="mr-2 h-4 w-4" />
            {isPaperTrading ? "Trading..." : "Paper Trade"}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={onTrackInPortfolio}
          >
            <Briefcase className="mr-2 h-4 w-4" />
            Track in Portfolio
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

interface TrackModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recommendation: TradeRecommendation | null;
  onConfirm: (accountId: string, shares: number) => void;
  isLoading: boolean;
}

function TrackInPortfolioModal({ open, onOpenChange, recommendation, onConfirm, isLoading }: TrackModalProps) {
  const { data: accounts } = useAccounts();
  const [selectedAccount, setSelectedAccount] = useState<string>("");
  const [shares, setShares] = useState<number>(0);

  // Filter out paper accounts
  const realAccounts = accounts?.filter(a => a.account_type !== "paper") || [];

  // Reset form when modal opens with new recommendation
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && recommendation) {
      setShares(recommendation.position_size_shares);
      setSelectedAccount("");
    }
    onOpenChange(newOpen);
  };

  const handleConfirm = () => {
    if (selectedAccount && shares > 0) {
      onConfirm(selectedAccount, shares);
    }
  };

  if (!recommendation) return null;

  const totalCost = shares * recommendation.current_price;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5" />
            Track {recommendation.symbol} in Portfolio
          </DialogTitle>
          <DialogDescription>
            Add this position to your real portfolio. This is for tracking purposes only -
            you must execute the actual trade with your broker.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Account Selection */}
          <div className="grid gap-2">
            <Label htmlFor="account">Select Account</Label>
            {realAccounts.length === 0 ? (
              <p className="text-sm text-text-muted">
                No real accounts found. Create an account on the Portfolio page first.
              </p>
            ) : (
              <Select value={selectedAccount} onValueChange={setSelectedAccount}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose an account..." />
                </SelectTrigger>
                <SelectContent>
                  {realAccounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name} ({account.account_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Shares Input */}
          <div className="grid gap-2">
            <Label htmlFor="shares">Number of Shares</Label>
            <Input
              id="shares"
              type="number"
              min={1}
              value={shares}
              onChange={(e) => setShares(parseInt(e.target.value) || 0)}
            />
            <p className="text-xs text-text-muted">
              Suggested: {recommendation.position_size_shares} shares (${recommendation.position_size_dollars.toLocaleString()})
            </p>
          </div>

          {/* Summary */}
          <div className="rounded-lg border border-border bg-surface-muted/50 p-3">
            <div className="flex justify-between text-sm">
              <span>Current Price:</span>
              <span className="font-medium">${recommendation.current_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Shares:</span>
              <span className="font-medium">{shares}</span>
            </div>
            <div className="mt-2 flex justify-between border-t border-border pt-2 text-sm font-medium">
              <span>Total Cost:</span>
              <span>${totalCost.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!selectedAccount || shares <= 0 || isLoading || realAccounts.length === 0}
          >
            {isLoading ? "Adding..." : "Add to Portfolio"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function RecommendationsPage() {
  const [minStrength, setMinStrength] = useState(5);
  const [portfolioSize, setPortfolioSize] = useState(100000);
  const [trackModalOpen, setTrackModalOpen] = useState(false);
  const [selectedRec, setSelectedRec] = useState<TradeRecommendation | null>(null);

  const { data, isLoading, error } = useRecommendations({
    min_strength: minStrength,
    limit: 20,
    signal_type: "BUY",
    portfolio_size: portfolioSize,
    position_pct: 0.05,
  });

  const paperTradeMutation = usePaperTrade();
  const trackMutation = useTrackInPortfolio();

  const recommendations = data?.recommendations || [];
  const summary = data?.summary;

  const handleTrackClick = (rec: TradeRecommendation) => {
    setSelectedRec(rec);
    setTrackModalOpen(true);
  };

  const handleTrackConfirm = (accountId: string, shares: number) => {
    if (!selectedRec) return;
    trackMutation.mutate(
      {
        symbol: selectedRec.symbol,
        strategyId: selectedRec.strategy_id,
        accountId,
        shares,
      },
      {
        onSuccess: () => {
          setTrackModalOpen(false);
          setSelectedRec(null);
        },
      }
    );
  };

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">
        {/* Page Header */}
        <PageHeader
          title="Trade Recommendations"
          description="Top trades from active strategies with position sizing"
          size="md"
        />

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Active Signals</p>
                  <p className="text-3xl font-bold text-green-600">
                    {summary?.buy_signals || 0}
                  </p>
                </div>
                <Target className="h-8 w-8 text-primary" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Avg Strength</p>
                  <p className="text-3xl font-bold">{summary?.avg_signal_strength?.toFixed(1) || 0}</p>
                </div>
                <Badge variant="outline" className="text-lg">
                  /10
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Total Position</p>
                  <p className="text-3xl font-bold">
                    ${(summary?.total_position_size || 0).toLocaleString()}
                  </p>
                </div>
                <DollarSign className="h-8 w-8 text-green-600" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Portfolio Size</p>
                  <p className="text-3xl font-bold">${portfolioSize.toLocaleString()}</p>
                </div>
                <Badge variant="outline">{((summary?.position_pct || 0.05) * 100).toFixed(0)}% each</Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Min Signal Strength: {minStrength}</Label>
                <Slider
                  value={[minStrength]}
                  onValueChange={(v) => setMinStrength(v[0])}
                  min={1}
                  max={10}
                  step={1}
                />
              </div>
              <div className="space-y-2">
                <Label>Portfolio Size: ${portfolioSize.toLocaleString()}</Label>
                <Slider
                  value={[portfolioSize]}
                  onValueChange={(v) => setPortfolioSize(v[0])}
                  min={10000}
                  max={1000000}
                  step={10000}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recommendations Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="h-80" />
              </Card>
            ))}
          </div>
        ) : error ? (
          <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/20">
            <CardContent className="flex items-center gap-3 py-6">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <p className="text-red-600">
                Failed to load recommendations: {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </CardContent>
          </Card>
        ) : recommendations.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Target className="mx-auto h-12 w-12 text-text-muted" />
              <h3 className="mt-4 text-lg font-medium">No Recommendations</h3>
              <p className="mt-2 text-text-muted">
                No active BUY signals with strength {">"}= {minStrength}. Try lowering the threshold or
                wait for new signals (generated daily at 21:30 UTC).
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {recommendations.map((rec) => (
              <RecommendationCard
                key={`${rec.strategy_id}-${rec.symbol}`}
                rec={rec}
                onPaperTrade={() =>
                  paperTradeMutation.mutate({
                    symbol: rec.symbol,
                    strategyId: rec.strategy_id,
                  })
                }
                onTrackInPortfolio={() => handleTrackClick(rec)}
                isPaperTrading={paperTradeMutation.isPending}
              />
            ))}
          </div>
        )}

        {/* Track in Portfolio Modal */}
        <TrackInPortfolioModal
          open={trackModalOpen}
          onOpenChange={setTrackModalOpen}
          recommendation={selectedRec}
          onConfirm={handleTrackConfirm}
          isLoading={trackMutation.isPending}
        />
      </div>
    </div>
  );
}
