"use client";

import { useState, useEffect, Suspense } from "react";
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
import { TransactionsList } from "@/components/trading/TransactionsList";
import { ConfirmActionDialog } from "@/components/shared/ConfirmActionDialog";

function TradingPageContent() {
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
    const entry = trade.entryPrice || 0;
    const current = trade.currentPrice || entry;
    return sum + (current - entry) * shares;
  }, 0) || 0;

  // Calculate total realized P&L (from closed trades) - reserved for future use
  const _realizedPnl = summary ? (summary.totalPortfolioValue || 0) - (summary.startingBalance || 100000) - unrealizedPnl : 0;

  // Calculate wins and losses count
  const winsCount = Math.round((summary?.winRate || 0) / 100 * (summary?.totalClosed || 0));
  const lossesCount = (summary?.totalClosed || 0) - winsCount;

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
              onClick={() => generateBatch.mutate({ topN: 20 })}
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
                  {summaryLoading ? "-" : `$${(summary?.cashBalance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
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
                  {summaryLoading ? "-" : `$${(summary?.positionsValue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
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
                  {summaryLoading ? "-" : `$${(summary?.totalPortfolioValue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                </p>
                {summary?.startingBalance && (
                  <p className={`text-sm ${(summary?.totalPortfolioValue || 0) >= summary.startingBalance ? "text-gain" : "text-loss"}`}>
                    {(summary?.totalPortfolioValue || 0) >= summary.startingBalance ? "+" : ""}
                    {(((summary?.totalPortfolioValue || 0) - summary.startingBalance) / summary.startingBalance * 100).toFixed(2)}% from start
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
                  {summaryLoading ? "-" : summary?.totalOpen || 0}
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
                  {summaryLoading ? "-" : `${(summary?.winRate || 0).toFixed(1)}%`}
                </p>
                {!summaryLoading && (summary?.totalClosed || 0) > 0 && (
                  <p className="text-sm text-text-muted">
                    <span className="text-gain">{winsCount}W</span>
                    {" / "}
                    <span className="text-loss">{lossesCount}L</span>
                    {" of "}{summary?.totalClosed} trades
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
                <p className={`text-3xl font-bold ${getPnlColor(summary?.totalPnlPct)}`}>
                  {summaryLoading ? "-" : formatPct(summary?.totalPnlPct)}
                </p>
                {!summaryLoading && summary && (
                  <p className={`text-sm ${getPnlColor((summary.totalPortfolioValue || 0) - (summary.startingBalance || 100000))}`}>
                    {formatCurrency((summary.totalPortfolioValue || 0) - (summary.startingBalance || 100000))}
                  </p>
                )}
              </div>
              <DollarSign className={`h-8 w-8 ${getPnlColor(summary?.totalPnlPct)}`} suppressHydrationWarning />
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
                  {summaryLoading ? "-" : formatPct(summary?.bestTradePct)}
                </p>
                {!summaryLoading && summary?.worstTradePct !== undefined && (
                  <p className="text-sm text-loss">
                    Worst: {formatPct(summary.worstTradePct)}
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
                Open Positions ({openTrades?.totalCount || 0})
              </TabsTrigger>
              <TabsTrigger value="closed">
                Closed Trades ({closedTrades?.totalCount || 0})
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

      {/* Transaction History */}
      <SectionCard variant="surface" padding="none">
        <div className="border-b border-border px-6 py-4">
          <h2 className="text-xl font-semibold">Transaction History</h2>
          <p className="text-sm text-text-muted">Complete log of all entry and exit transactions</p>
        </div>
        <div className="p-6">
          <TransactionsList limit={50} />
        </div>
      </SectionCard>

      {/* Reset Account Confirmation Dialog */}
      <ConfirmActionDialog
        open={isResetDialogOpen}
        onOpenChange={setIsResetDialogOpen}
        onConfirm={() => {
          resetAccount.mutate(
            { closeOpenTrades: true },
            { onSuccess: () => setIsResetDialogOpen(false) }
          );
        }}
        title="Reset Paper Trading Account?"
        description={`This will close all ${summary?.totalOpen || 0} open positions at current prices and reset your cash balance to $${(summary?.startingBalance || 100000).toLocaleString()}. This action cannot be undone.`}
        confirmLabel="Reset Account"
        tone="destructive"
      />
    </PageContainer>
  );
}

export default function TradingPage() {
  return (
    <Suspense fallback={<div className="p-10">Loading...</div>}>
      <TradingPageContent />
    </Suspense>
  );
}
