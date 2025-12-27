"use client";

import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { RefreshCw, PlusCircle, Search } from "lucide-react";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";
import { WatchlistDailyReport } from "@/components/watchlist/WatchlistDailyReport";
import { AddSymbolModal } from "@/components/watchlist/AddSymbolModal";
import { useWatchlist, useRefreshWatchlist } from "@/lib/hooks/useWatchlist";
import { useDisagreements } from "@/lib/hooks/useDisagreements";
import { DisagreementAlert, DisagreementCard } from "@/components/disagreements";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageContainer } from "@/components/shared/PageContainer";

type StyleFilter = "all" | "Index" | "Trend" | "Value" | "Swing" | "Event";
type SignalFilter = "all" | "BUY" | "HOLD" | "AVOID";
type RiskFilter = "all" | "Low" | "Medium-Low" | "Medium" | "High";

export default function WatchlistPage() {
  const [addSymbolOpen, setAddSymbolOpen] = useState(false);
  const [styleFilter, setStyleFilter] = useState<StyleFilter>("all");
  const [signalFilter, setSignalFilter] = useState<SignalFilter>("all");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [_isHydrated, _setIsHydrated] = useState(false);

  // Load saved filters from localStorage after hydration
  useEffect(() => {
    const savedStyle = localStorage.getItem("watchlist-style-filter");
    if (savedStyle && ["all", "Index", "Trend", "Value", "Swing", "Event"].includes(savedStyle)) {
      setStyleFilter(savedStyle as StyleFilter);
    }
    const savedSignal = localStorage.getItem("watchlist-signal-filter");
    if (savedSignal && ["all", "BUY", "HOLD", "AVOID"].includes(savedSignal)) {
      setSignalFilter(savedSignal as SignalFilter);
    }
    const savedRisk = localStorage.getItem("watchlist-risk-filter");
    if (savedRisk && ["all", "Low", "Medium-Low", "Medium", "High"].includes(savedRisk)) {
      setRiskFilter(savedRisk as RiskFilter);
    }
    _setIsHydrated(true);
  }, []);

  const { data: watchlistData, isLoading, error } = useWatchlist();
  const refreshMutation = useRefreshWatchlist();
  const { data: disagreementsData } = useDisagreements(7, undefined, 20);

  // Save filters to localStorage when they change
  useEffect(() => {
    localStorage.setItem("watchlist-style-filter", styleFilter);
  }, [styleFilter]);

  useEffect(() => {
    localStorage.setItem("watchlist-signal-filter", signalFilter);
  }, [signalFilter]);

  useEffect(() => {
    localStorage.setItem("watchlist-risk-filter", riskFilter);
  }, [riskFilter]);

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: (data) => {
        // Handle different statuses
        if (data.status === "success") {
          // All success
          toast.success(data.message || `Refreshed ${data.refreshedCount} symbols`);
        } else if (data.status === "partial_success") {
          // Partial success - show warning with failed symbols
          const failedSymbols = data.failed?.slice(0, 3).map((f) => f.symbol).join(", ") || "";
          const moreCount = (data.failedCount || 0) - 3;
          const failedMsg = moreCount > 0 ? `${failedSymbols} and ${moreCount} more` : failedSymbols;

          toast.warning(data.message, {
            description: failedMsg ? `Failed: ${failedMsg}` : undefined,
          });
        }
      },
      onError: (err) => {
        toast.error(`Failed to refresh: ${err.message}`);
      },
    });
  };

  // Filter items by style, signal, risk, and search query
  const filteredItems = useMemo(() => {
    let items = watchlistData?.items || [];

    // Apply style filter
    if (styleFilter !== "all") {
      items = items.filter((item) => item.recommendedStyle === styleFilter);
    }

    // Apply signal filter
    if (signalFilter !== "all") {
      items = items.filter((item) => item.signalType === signalFilter);
    }

    // Apply risk filter
    if (riskFilter !== "all") {
      items = items.filter((item) => item.riskLevel === riskFilter);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      items = items.filter((item) =>
        item.symbol.toLowerCase().includes(query) ||
        item.note?.toLowerCase().includes(query)
      );
    }

    return items;
  }, [watchlistData?.items, styleFilter, signalFilter, riskFilter, searchQuery]);

  // Count by style
  const styleCounts = (watchlistData?.items || []).reduce((acc, item) => {
    if (item.recommendedStyle) {
      acc[item.recommendedStyle] = (acc[item.recommendedStyle] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  // Count by signal
  const signalCounts = (watchlistData?.items || []).reduce((acc, item) => {
    if (item.signalType) {
      acc[item.signalType] = (acc[item.signalType] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  // Count by risk
  const riskCounts = (watchlistData?.items || []).reduce((acc, item) => {
    if (item.riskLevel) {
      acc[item.riskLevel] = (acc[item.riskLevel] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  return (
    <PageContainer className="py-10">
      <PageHeader
        title="Watchlist Intelligence Hub"
        description={
          searchQuery.trim()
            ? `Found ${filteredItems.length} ${filteredItems.length === 1 ? "symbol" : "symbols"} matching "${searchQuery}"`
            : styleFilter === "all"
              ? `Showing all ${watchlistData?.items.length || 0} symbols`
              : `Showing ${filteredItems.length} ${styleFilter} ${filteredItems.length === 1 ? "play" : "plays"}`
        }
        size="md"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${refreshMutation.isPending ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
            <Button onClick={() => setAddSymbolOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Symbol
            </Button>
          </div>
        }
      />

      {/* Major Disagreement Alerts */}
      {disagreementsData?.items
        .filter((d) => d.disagreementSeverity === "major")
        .slice(0, 3)
        .map((disagreement) => (
          <DisagreementAlert
            key={disagreement.reviewPairId}
            symbol={disagreement.symbol}
            severity={disagreement.disagreementSeverity as "minor" | "major"}
            geminiReview={disagreement.geminiReview}
            claudeReview={disagreement.claudeReview}
            agreementScore={disagreement.agreementScore}
            className="mb-4"
          />
        ))}

      <div className="flex flex-wrap gap-2">
        <Select value={signalFilter} onValueChange={(value) => setSignalFilter(value as SignalFilter)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Signal: All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Signals ({watchlistData?.items.length || 0})</SelectItem>
            <SelectItem value="BUY">🟢 BUY ({signalCounts["BUY"] || 0})</SelectItem>
            <SelectItem value="HOLD">🟡 HOLD ({signalCounts["HOLD"] || 0})</SelectItem>
            <SelectItem value="AVOID">🔴 AVOID ({signalCounts["AVOID"] || 0})</SelectItem>
          </SelectContent>
        </Select>
        <Select value={styleFilter} onValueChange={(value) => setStyleFilter(value as StyleFilter)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Style: All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Styles ({watchlistData?.items.length || 0})</SelectItem>
            <SelectItem value="Index">📈 Index ({styleCounts["Index"] || 0})</SelectItem>
            <SelectItem value="Trend">🔥 Trend ({styleCounts["Trend"] || 0})</SelectItem>
            <SelectItem value="Value">💎 Value ({styleCounts["Value"] || 0})</SelectItem>
            <SelectItem value="Swing">⚡ Swing ({styleCounts["Swing"] || 0})</SelectItem>
            <SelectItem value="Event">📅 Event ({styleCounts["Event"] || 0})</SelectItem>
          </SelectContent>
        </Select>
        <Select value={riskFilter} onValueChange={(value) => setRiskFilter(value as RiskFilter)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Risk: All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Risk Levels ({watchlistData?.items.length || 0})</SelectItem>
            <SelectItem value="Low">✓ Low ({riskCounts["Low"] || 0})</SelectItem>
            <SelectItem value="Medium-Low">⚠ Med-Low ({riskCounts["Medium-Low"] || 0})</SelectItem>
            <SelectItem value="Medium">⚠ Medium ({riskCounts["Medium"] || 0})</SelectItem>
            <SelectItem value="High">⚠⚠ High ({riskCounts["High"] || 0})</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <Input
            type="text"
            placeholder="Search by symbol or note..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Daily Watchlist Report */}
      <WatchlistDailyReport />

      {/* Recent LLM Disagreements Section */}
      {disagreementsData && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-text mb-3">
            Recent LLM Review Disagreements
          </h2>
          {disagreementsData.items.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {disagreementsData.items.slice(0, 6).map((disagreement) => (
                <DisagreementCard
                  key={disagreement.reviewPairId}
                  item={disagreement}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-status-success/20 bg-status-success/5 p-4">
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <span className="text-status-success">✓</span>
                <span>No LLM disagreements detected in last 7 days</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-6 rounded-md border border-loss bg-loss/10 p-4 text-sm text-loss">
          Failed to load watchlist: {error.message}
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-md bg-surface-muted"
            />
          ))}
        </div>
      )}

      {/* Watchlist Table */}
      {!isLoading && !error && (
        <WatchlistTable
          items={filteredItems}
        />
      )}

      {/* Add Symbol Modal */}
      <AddSymbolModal
        open={addSymbolOpen}
        onOpenChange={setAddSymbolOpen}
        currentCount={watchlistData?.items.length || 0}
      />
    </PageContainer>
  );
}
