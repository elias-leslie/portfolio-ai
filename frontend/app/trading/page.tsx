"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { TrendingUp, DollarSign, Target, Plus, Sparkles, ExternalLink, Wallet, PieChart, RotateCcw } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageContainer } from "@/components/shared/PageContainer";
import { SectionCard } from "@/components/shared/SectionCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { usePaperTrades, usePaperTradeSummary, useResetPaperAccount } from "@/lib/hooks/usePaperTrades";
import { useGenerateStrategiesBatch } from "@/lib/hooks/useStrategies";
import { PaperTradesTable } from "@/components/trading/PaperTradesTable";
import { NewOrderDialog } from "@/components/trading/NewOrderDialog";
import { PipelineControls } from "@/components/trading/PipelineControls";
import { ConfirmActionDialog } from "@/components/shared/ConfirmActionDialog";

export default function TradingPage() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<"open" | "closed">("open");
  const [isNewOrderOpen, setIsNewOrderOpen] = useState(false);
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);

  // Auto-select tab from query parameter (?tab=open or ?tab=closed)
  useEffect(() => {
    const tabParam = searchParams?.get("tab");
    if (tabParam === "open" || tabParam === "closed") {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  // Fetch data with real-time updates
  const { data: openTrades, isLoading: openLoading } = usePaperTrades({
    status: "open",
    limit: 100,
  });

  const { data: closedTrades, isLoading: closedLoading } = usePaperTrades({
    status: "closed",
    limit: 100,
  });

  const { data: summary, isLoading: summaryLoading } = usePaperTradeSummary();
  const generateBatch = useGenerateStrategiesBatch();
  const resetAccount = useResetPaperAccount();

  // Calculate color for P&L display
  const getPnlColor = (value: number | undefined) => {
    if (!value) return "text-text";
    return value >= 0 ? "text-gain" : "text-loss";
  };

  // Format percentage
  const formatPct = (value: number | undefined) => {
    if (value === undefined || value === null) return "0.00%";
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  // Format currency
  const formatCurrency = (value: number | undefined) => {
    if (value === undefined || value === null) return "$0.00";
    const prefix = value >= 0 ? "+$" : "-$";
    return `${prefix}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Calculate unrealized P&L from open trades
  const unrealizedPnl = openTrades?.trades.reduce((sum, trade) => {
    const shares = trade.shares || 0;
    const entry = trade.entry_price || 0;
    const current = trade.current_price || entry;
    return sum + (current - entry) * shares;
  }, 0) || 0;

  // Calculate total realized P&L (from closed trades)
  const realizedPnl = summary ? (summary.total_portfolio_value || 0) - (summary.starting_balance || 100000) - unrealizedPnl : 0;

  // Calculate wins and losses count
  const winsCount = Math.round((summary?.win_rate || 0) / 100 * (summary?.total_closed || 0));
  const lossesCount = (summary?.total_closed || 0) - winsCount;

  return (
    <PageContainer className="space-y-10 py-10">
      {/* Page Header */}
      <PageHeader
        title="Paper Trading"
        description="AI-driven paper trades with real-time performance tracking"
        size="md"
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => generateBatch.mutate({ top_n: 20 })}
              disabled={generateBatch.isPending}
            >
              <Sparkles className="mr-2 h-4 w-4" suppressHydrationWarning />
              {generateBatch.isPending ? "Generating..." : "Generate Strategies"}
            </Button>
            <Link href="/strategies">
              <Button variant="ghost">
                <ExternalLink className="mr-2 h-4 w-4" suppressHydrationWarning />
                View Strategies
              </Button>
            </Link>
            <Button onClick={() => setIsNewOrderOpen(true)}>
              <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
              New Order
            </Button>
          </div>
        }
      />

      {/* New Order Dialog */}
      <NewOrderDialog open={isNewOrderOpen} onOpenChange={setIsNewOrderOpen} />

      {/* Paper Portfolio Balance */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Cash Balance</p>
                <p className="text-2xl font-bold">
                  {summaryLoading ? "-" : `$${(summary?.cash_balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                </p>
              </div>
              <Wallet className="h-8 w-8 text-primary" suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Positions Value</p>
                <p className="text-2xl font-bold">
                  {summaryLoading ? "-" : `$${(summary?.positions_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                </p>
              </div>
              <PieChart className="h-8 w-8 text-accent" suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Total Portfolio</p>
                <p className="text-2xl font-bold">
                  {summaryLoading ? "-" : `$${(summary?.total_portfolio_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                </p>
                {summary?.starting_balance && (
                  <p className={`text-sm ${(summary?.total_portfolio_value || 0) >= summary.starting_balance ? "text-gain" : "text-loss"}`}>
                    {(summary?.total_portfolio_value || 0) >= summary.starting_balance ? "+" : ""}
                    {(((summary?.total_portfolio_value || 0) - summary.starting_balance) / summary.starting_balance * 100).toFixed(2)}% from start
                  </p>
                )}
              </div>
              <div className="flex flex-col items-end gap-2">
                <DollarSign className="h-8 w-8 text-gain" suppressHydrationWarning />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsResetDialogOpen(true)}
                  disabled={resetAccount.isPending}
                >
                  <RotateCcw className="mr-1 h-3 w-3" suppressHydrationWarning />
                  Reset
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline Controls */}
      <PipelineControls />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {/* Open Positions with Unrealized P&L */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Open Positions</p>
                <p className="text-3xl font-bold">
                  {summaryLoading ? "-" : summary?.total_open || 0}
                </p>
                {!summaryLoading && !openLoading && (
                  <p className={`text-sm ${getPnlColor(unrealizedPnl)}`}>
                    {formatCurrency(unrealizedPnl)} unrealized
                  </p>
                )}
              </div>
              <TrendingUp className="h-8 w-8 text-primary" suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>

        {/* Win Rate with Wins/Losses */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Win Rate</p>
                <p className="text-3xl font-bold">
                  {summaryLoading ? "-" : `${(summary?.win_rate || 0).toFixed(1)}%`}
                </p>
                {!summaryLoading && (summary?.total_closed || 0) > 0 && (
                  <p className="text-sm text-text-muted">
                    <span className="text-gain">{winsCount}W</span>
                    {" / "}
                    <span className="text-loss">{lossesCount}L</span>
                    {" of "}{summary?.total_closed} trades
                  </p>
                )}
              </div>
              <Target className="h-8 w-8 text-gain" suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>

        {/* Total P&L with Dollar Amount */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Total P&L</p>
                <p className={`text-3xl font-bold ${getPnlColor(summary?.total_pnl_pct)}`}>
                  {summaryLoading ? "-" : formatPct(summary?.total_pnl_pct)}
                </p>
                {!summaryLoading && summary && (
                  <p className={`text-sm ${getPnlColor((summary.total_portfolio_value || 0) - (summary.starting_balance || 100000))}`}>
                    {formatCurrency((summary.total_portfolio_value || 0) - (summary.starting_balance || 100000))}
                  </p>
                )}
              </div>
              <DollarSign className={`h-8 w-8 ${getPnlColor(summary?.total_pnl_pct)}`} suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>

        {/* Best/Worst Trade */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-muted">Best / Worst Trade</p>
                <p className="text-3xl font-bold text-gain">
                  {summaryLoading ? "-" : formatPct(summary?.best_trade_pct)}
                </p>
                {!summaryLoading && summary?.worst_trade_pct !== undefined && (
                  <p className="text-sm text-loss">
                    Worst: {formatPct(summary.worst_trade_pct)}
                  </p>
                )}
              </div>
              <TrendingUp className="h-8 w-8 text-gain" suppressHydrationWarning />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Trades Table with Tabs */}
      <SectionCard variant="surface" padding="none">
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as "open" | "closed")}>
          <div className="border-b border-border px-6 pt-6">
            <TabsList className="grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="open">
                Open Positions ({openTrades?.total_count || 0})
              </TabsTrigger>
              <TabsTrigger value="closed">
                Closed Trades ({closedTrades?.total_count || 0})
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="open" className="mt-0">
            {openLoading ? (
              <div className="p-8 text-center text-text-muted">Loading open positions...</div>
            ) : openTrades && openTrades.trades.length > 0 ? (
              <PaperTradesTable trades={openTrades.trades} type="open" />
            ) : (
              <div className="p-8 text-center text-text-muted">
                No open positions. AI agents will create trades when opportunities are identified.
              </div>
            )}
          </TabsContent>

          <TabsContent value="closed" className="mt-0">
            {closedLoading ? (
              <div className="p-8 text-center text-text-muted">Loading closed trades...</div>
            ) : closedTrades && closedTrades.trades.length > 0 ? (
              <PaperTradesTable trades={closedTrades.trades} type="closed" />
            ) : (
              <div className="p-8 text-center text-text-muted">
                No closed trades yet. Trades will appear here once positions are exited.
              </div>
            )}
          </TabsContent>
        </Tabs>
      </SectionCard>

      {/* Reset Account Confirmation Dialog */}
      <ConfirmActionDialog
        open={isResetDialogOpen}
        onOpenChange={setIsResetDialogOpen}
        onConfirm={() => {
          resetAccount.mutate(
            { close_open_trades: true },
            { onSuccess: () => setIsResetDialogOpen(false) }
          );
        }}
        title="Reset Paper Trading Account?"
        description={`This will close all ${summary?.total_open || 0} open positions at current prices and reset your cash balance to $${(summary?.starting_balance || 100000).toLocaleString()}. This action cannot be undone.`}
        confirmLabel="Reset Account"
        tone="destructive"
      />
    </PageContainer>
  );
}
