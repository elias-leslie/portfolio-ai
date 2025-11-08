"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { RefreshCw, PlusCircle, Filter } from "lucide-react";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";
import { AddTickerModal } from "@/components/watchlist/AddTickerModal";
import { useWatchlist, useRefreshWatchlist } from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type StyleFilter = "all" | "Index" | "Trend" | "Value" | "Swing" | "Event";

export default function WatchlistPage() {
  const [addTickerOpen, setAddTickerOpen] = useState(false);
  const [styleFilter, setStyleFilter] = useState<StyleFilter>("all");

  const { data: watchlistData, isLoading, error } = useWatchlist();
  const refreshMutation = useRefreshWatchlist();

  // Load filter from localStorage on mount
  useEffect(() => {
    const savedFilter = localStorage.getItem("watchlist-style-filter");
    if (savedFilter && ["all", "Index", "Trend", "Value", "Swing", "Event"].includes(savedFilter)) {
      setStyleFilter(savedFilter as StyleFilter);
    }
  }, []);

  // Save filter to localStorage when it changes
  useEffect(() => {
    localStorage.setItem("watchlist-style-filter", styleFilter);
  }, [styleFilter]);

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: (data) => {
        // Handle different statuses
        if (data.status === "success") {
          // All success
          toast.success(data.message || `Refreshed ${data.refreshed_count} tickers`);
        } else if (data.status === "partial_success") {
          // Partial success - show warning with failed tickers
          const failedSymbols = data.failed?.slice(0, 3).map((f) => f.symbol).join(", ") || "";
          const moreCount = (data.failed_count || 0) - 3;
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

  // Filter items by style
  const filteredItems = (watchlistData?.items || []).filter((item) => {
    if (styleFilter === "all") return true;
    return item.recommended_style === styleFilter;
  });

  // Count by style
  const styleCounts = (watchlistData?.items || []).reduce((acc, item) => {
    if (item.recommended_style) {
      acc[item.recommended_style] = (acc[item.recommended_style] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="bg-bg min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-text">
              Watchlist Intelligence Hub
            </h1>
            <p className="mt-2 text-sm text-text-muted">
              {styleFilter === "all"
                ? `Showing all ${watchlistData?.items.length || 0} tickers`
                : `Showing ${filteredItems.length} ${styleFilter} ${filteredItems.length === 1 ? "play" : "plays"}`}
            </p>
          </div>
          <div className="flex gap-2">
            <Select value={styleFilter} onValueChange={(value) => setStyleFilter(value as StyleFilter)}>
              <SelectTrigger className="w-[180px]">
                <Filter className="mr-2 h-4 w-4" />
                <SelectValue placeholder="Filter by style" />
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
            <Button onClick={() => setAddTickerOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Ticker
            </Button>
          </div>
        </div>

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

        {/* Add Ticker Modal */}
        <AddTickerModal
          open={addTickerOpen}
          onOpenChange={setAddTickerOpen}
          currentCount={watchlistData?.items.length || 0}
        />
      </div>
    </div>
  );
}
