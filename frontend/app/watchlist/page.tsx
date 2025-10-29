"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { RefreshCw, PlusCircle } from "lucide-react";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";
import { AddTickerModal } from "@/components/watchlist/AddTickerModal";
import { useWatchlist, useRefreshWatchlist } from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";

export default function WatchlistPage() {
  const [addTickerOpen, setAddTickerOpen] = useState(false);
  const [accountId] = useState("default"); // TODO: Get from auth context

  const { data: watchlistData, isLoading, error } = useWatchlist(accountId);
  const refreshMutation = useRefreshWatchlist();

  const handleRefresh = () => {
    refreshMutation.mutate(accountId, {
      onSuccess: (data) => {
        toast.success(data.message || "Watchlist refreshed successfully");
      },
      onError: (err) => {
        toast.error(`Failed to refresh: ${err.message}`);
      },
    });
  };

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
              Monitor price and technical scores for your tracked securities
            </p>
          </div>
          <div className="flex gap-2">
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
            items={watchlistData?.items || []}
            accountId={accountId}
          />
        )}

        {/* Add Ticker Modal */}
        <AddTickerModal
          open={addTickerOpen}
          onOpenChange={setAddTickerOpen}
          accountId={accountId}
        />
      </div>
    </div>
  );
}
