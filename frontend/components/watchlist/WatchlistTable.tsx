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
// TEMPORARILY DISABLED: Re-enable after 90 days of snapshot data accumulated (see sparkline removal decision)
// import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";
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
import { usePreferences } from "@/lib/hooks/usePreferences";
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
  const { data: preferences } = usePreferences();

  // Get user's timezone preference
  const userTimezone = preferences?.display_timezone ?? "America/New_York";

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
        aVal = a.current_score?.price?.updated_at ?? a.updated_at;
        bVal = b.current_score?.price?.updated_at ?? b.updated_at;
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
      },
    );
  };

  // Get score badge variant based on score value
  const getScoreBadgeVariant = (
    score: number,
  ): "viz-0" | "viz-1" | "viz-2" | "viz-3" | "viz-4" | "viz-5" => {
    if (score >= 80) return "viz-5";
    if (score >= 60) return "viz-4";
    if (score >= 40) return "viz-3";
    if (score >= 20) return "viz-2";
    if (score >= 10) return "viz-1";
    return "viz-0";
  };

  // Get signal badge variant and icon
  const getSignalDisplay = (signalType?: "BUY" | "HOLD" | "AVOID" | null) => {
    switch (signalType) {
      case "BUY":
        return {
          icon: "🟢",
          color: "bg-green-500/10 text-green-600 border-green-500/20",
          label: "BUY",
        };
      case "HOLD":
        return {
          icon: "🟡",
          color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
          label: "HOLD",
        };
      case "AVOID":
        return {
          icon: "🔴",
          color: "bg-red-500/10 text-red-600 border-red-500/20",
          label: "AVOID",
        };
      default:
        return null;
    }
  };

  // Get trading style display
  const getStyleDisplay = (style?: "Index" | "Trend" | "Value" | "Swing" | "Event" | null) => {
    switch (style) {
      case "Index":
        return { icon: "📈", color: "bg-blue-500/10 text-blue-600 border-blue-500/20" };
      case "Trend":
        return { icon: "🔥", color: "bg-orange-500/10 text-orange-600 border-orange-500/20" };
      case "Value":
        return { icon: "💎", color: "bg-purple-500/10 text-purple-600 border-purple-500/20" };
      case "Swing":
        return { icon: "⚡", color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20" };
      case "Event":
        return { icon: "📅", color: "bg-red-500/10 text-red-600 border-red-500/20" };
      default:
        return null;
    }
  };

  // Get timezone abbreviation (EST, PST, etc.)
  const getTimezoneAbbreviation = (timezone: string): string => {
    const date = new Date();
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      timeZoneName: "short",
    });
    const parts = formatter.formatToParts(date);
    const timeZonePart = parts.find((part) => part.type === "timeZoneName");
    return timeZonePart?.value ?? "";
  };

  // Format date with timezone
  const formatDate = (dateStr: string, timezone: string) => {
    const date = new Date(dateStr);
    const formatted = date.toLocaleString("en-US", {
      timeZone: timezone,
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
    const tzAbbr = getTimezoneAbbreviation(timezone);
    return `${formatted} ${tzAbbr}`;
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
                Signal
                {sortField === "overall" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>Style</TableHead>
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
            {/* TEMPORARILY DISABLED: Sparkline column - re-enable after 90 days of data */}
            {/* <TableHead>7-Day Trend</TableHead> */}
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
                    isExpanded && "bg-surface-muted/40",
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
                            typeof item.current_score.price.metadata
                              .priority === "number"
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
                    {item.signal_type ? (
                      (() => {
                        const signalDisplay = getSignalDisplay(item.signal_type);
                        return signalDisplay ? (
                          <div className="flex items-center gap-2">
                            <div
                              className={cn(
                                "inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold",
                                signalDisplay.color
                              )}
                            >
                              <span>{signalDisplay.icon}</span>
                              <span>{signalDisplay.label}</span>
                              {item.signal_strength !== null && item.signal_strength !== undefined && (
                                <span className="ml-1 text-xs opacity-75">
                                  {item.signal_strength}/10
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-text-muted">—</span>
                        );
                      })()
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {item.recommended_style ? (
                      (() => {
                        const styleDisplay = getStyleDisplay(item.recommended_style);
                        return styleDisplay ? (
                          <div
                            className={cn(
                              "inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold",
                              styleDisplay.color
                            )}
                            title={item.optimal_holding_period ?? undefined}
                          >
                            <span>{styleDisplay.icon}</span>
                            <span>{item.recommended_style}</span>
                          </div>
                        ) : (
                          <span className="text-text-muted">—</span>
                        );
                      })()
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
                  {/* TEMPORARILY DISABLED: Sparkline column - re-enable after 90 days of data */}
                  {/* <TableCell>
                    {hasScore ? (
                      <SparklineWithHistory
                        itemId={item.id}
                        width={80}
                        height={24}
                        recommendedStyle={item.recommended_style}
                      />
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell> */}
                  <TableCell className="text-xs text-text-muted">
                    {item.current_score?.price?.updated_at
                      ? formatDate(item.current_score.price.updated_at, userTimezone)
                      : formatDate(item.updated_at, userTimezone)}
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
                    <TableCell colSpan={9} className="bg-surface-muted/20 p-4">
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
