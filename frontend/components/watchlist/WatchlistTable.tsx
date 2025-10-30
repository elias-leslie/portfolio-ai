"use client";

import { useState, Fragment } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Sparkline } from "@/components/ui/sparkline";
import { ExpandedRow } from "@/components/watchlist/ExpandedRow";
import { WatchlistCard } from "@/components/watchlist/WatchlistCard";
import { SourceBadge } from "@/components/watchlist/SourceBadge";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Trash2,
  Loader2,
} from "lucide-react";
import {
  useDeleteWatchlistItem,
  useRefreshStatus,
} from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";
import type { WatchlistItem } from "@/lib/api/watchlist";
import { cn } from "@/lib/utils";

interface WatchlistTableProps {
  items: WatchlistItem[];
  accountId: string;
}

type SortField = "symbol" | "overall" | "price" | "technical" | "updated";
type SortDirection = "asc" | "desc";

export function WatchlistTable({ items, accountId }: WatchlistTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("symbol");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const deleteMutation = useDeleteWatchlistItem();
  const { data: refreshStatus } = useRefreshStatus(accountId);

  // Handle sort
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  // Sort items
  const sortedItems = [...items].sort((a, b) => {
    let aVal: string | number = "";
    let bVal: string | number = "";

    switch (sortField) {
      case "symbol":
        aVal = a.symbol;
        bVal = b.symbol;
        break;
      case "overall":
        aVal = a.current_score?.overall ?? -1;
        bVal = b.current_score?.overall ?? -1;
        break;
      case "price":
        aVal = a.current_score?.price.score ?? -1;
        bVal = b.current_score?.price.score ?? -1;
        break;
      case "technical":
        aVal = a.current_score?.technical.score ?? -1;
        bVal = b.current_score?.technical.score ?? -1;
        break;
      case "updated":
        aVal = a.updated_at;
        bVal = b.updated_at;
        break;
    }

    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortDirection === "asc"
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }

    return sortDirection === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  // Handle delete
  const handleDelete = (itemId: string, symbol: string) => {
    if (!confirm(`Remove ${symbol} from watchlist?`)) return;

    deleteMutation.mutate(
      { itemId, accountId },
      {
        onSuccess: () => {
          toast.success(`${symbol} removed from watchlist`);
          if (expandedId === itemId) {
            setExpandedId(null);
          }
        },
        onError: (error) => {
          toast.error(`Failed to remove ticker: ${error.message}`);
        },
      }
    );
  };

  // Get score badge variant based on score value
  const getScoreBadgeVariant = (
    score: number
  ): "viz-0" | "viz-1" | "viz-2" | "viz-3" | "viz-4" | "viz-5" => {
    if (score >= 80) return "viz-5";
    if (score >= 60) return "viz-4";
    if (score >= 40) return "viz-3";
    if (score >= 20) return "viz-2";
    if (score >= 10) return "viz-1";
    return "viz-0";
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-8 text-center">
        <p className="text-text-muted">
          No tickers in your watchlist yet. Click &quot;Add Ticker&quot; to get
          started.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface shadow-sm">
      {/* Desktop Table View (hidden on mobile) */}
      <Table className="hidden md:table">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]" />
            <TableHead>
              <button
                onClick={() => handleSort("symbol")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Symbol
                {sortField === "symbol" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => handleSort("overall")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Overall Score
                {sortField === "overall" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => handleSort("price")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Price
                {sortField === "price" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => handleSort("technical")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Technical
                {sortField === "technical" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>7-Day Trend</TableHead>
            <TableHead>
              <button
                onClick={() => handleSort("updated")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Updated
                {sortField === "updated" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead className="w-[60px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedItems.map((item) => {
            const isExpanded = expandedId === item.id;
            const hasScore = !!item.current_score;
            const overall = item.current_score?.overall ?? 0;
            const priceScore = item.current_score?.price.score ?? 0;
            const techScore = item.current_score?.technical.score ?? 0;
            const priceStale = item.current_score?.price.stale ?? false;
            const techStale = item.current_score?.technical.stale ?? false;

            return (
              <Fragment key={item.id}>
                <TableRow
                  className={cn(
                    "cursor-pointer",
                    isExpanded && "bg-surface-muted/40"
                  )}
                  onClick={() => setExpandedId(isExpanded ? null : item.id)}
                >
                  <TableCell>
                    <button
                      className="rounded p-1 hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      aria-label={isExpanded ? "Collapse row" : "Expand row"}
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                  </TableCell>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <span>{item.symbol}</span>
                      {item.current_score?.price.metadata?.source &&
                      typeof item.current_score.price.metadata.source ===
                        "string" ? (
                        <SourceBadge
                          source={item.current_score.price.metadata.source}
                          stale={item.current_score.price.stale}
                          priority={
                            typeof item.current_score.price.metadata.priority ===
                            "number"
                              ? item.current_score.price.metadata.priority
                              : undefined
                          }
                        />
                      ) : null}
                      {refreshStatus?.is_refreshing &&
                        refreshStatus.current_symbol === item.symbol && (
                          <Loader2
                            className="h-4 w-4 animate-spin text-accent"
                            aria-label="Refreshing..."
                          />
                        )}
                      {item.score_alert && (
                        <AlertCircle
                          className="h-4 w-4 text-accent"
                          aria-label="Score changed >10 points in last 7 days"
                        />
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {hasScore ? (
                      <Badge variant={getScoreBadgeVariant(overall)}>
                        {overall.toFixed(1)}
                      </Badge>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {hasScore ? (
                      <div className="flex items-center gap-1">
                        <Badge variant={getScoreBadgeVariant(priceScore)}>
                          {priceScore.toFixed(1)}
                        </Badge>
                        {priceStale && (
                          <span className="text-xs text-text-muted">
                            (stale)
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {hasScore ? (
                      <div className="flex items-center gap-1">
                        <Badge variant={getScoreBadgeVariant(techScore)}>
                          {techScore.toFixed(1)}
                        </Badge>
                        {techStale && (
                          <span className="text-xs text-text-muted">
                            (stale)
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {hasScore ? (
                      <Sparkline
                        data={[65, 68, 72, 70, 73, 71, overall]}
                        width={80}
                        height={24}
                      />
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-text-muted">
                    {formatDate(item.updated_at)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(item.id, item.symbol);
                      }}
                      disabled={deleteMutation.isPending}
                      className="h-8 w-8 p-0"
                      aria-label={`Delete ${item.symbol}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={8} className="bg-surface-muted/20 p-4">
                      <ExpandedRow item={item} refreshStatus={refreshStatus} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>

      {/* Mobile Card View (shown on mobile only) */}
      <div className="md:hidden space-y-3 p-3">
        {sortedItems.map((item) => (
          <WatchlistCard
            key={item.id}
            item={item}
            onDelete={handleDelete}
            isDeleting={deleteMutation.isPending}
          />
        ))}
      </div>
    </div>
  );
}
