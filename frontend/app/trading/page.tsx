"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, DollarSign, Target } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { usePaperTrades, usePaperTradeSummary } from "@/lib/hooks/usePaperTrades";
import { PaperTradesTable } from "@/components/trading/PaperTradesTable";

export default function TradingPage() {
  const [activeTab, setActiveTab] = useState<"open" | "closed">("open");

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

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-6 lg:px-8">
        {/* Page Header */}
        <PageHeader
          title="Paper Trading"
          description="AI-driven paper trades with real-time performance tracking"
          size="md"
        />

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {/* Open Positions */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Open Positions</p>
                  <p className="text-3xl font-bold">
                    {summaryLoading ? "-" : summary?.total_open || 0}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-primary" />
              </div>
            </CardContent>
          </Card>

          {/* Win Rate */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Win Rate</p>
                  <p className="text-3xl font-bold">
                    {summaryLoading ? "-" : `${(summary?.win_rate || 0).toFixed(1)}%`}
                  </p>
                </div>
                <Target className="h-8 w-8 text-gain" />
              </div>
            </CardContent>
          </Card>

          {/* Total P&L */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Total P&L</p>
                  <p className={`text-3xl font-bold ${getPnlColor(summary?.total_pnl_pct)}`}>
                    {summaryLoading ? "-" : formatPct(summary?.total_pnl_pct)}
                  </p>
                </div>
                <DollarSign className={`h-8 w-8 ${getPnlColor(summary?.total_pnl_pct)}`} />
              </div>
            </CardContent>
          </Card>

          {/* Best Trade */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-muted">Best Trade</p>
                  <p className="text-3xl font-bold text-gain">
                    {summaryLoading ? "-" : formatPct(summary?.best_trade_pct)}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-gain" />
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
      </div>
    </div>
  );
}
