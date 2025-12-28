"use client";

import { useState, Fragment, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";
import { ExpandedRow } from "@/components/watchlist/ExpandedRow";
import { WatchlistCard } from "@/components/watchlist/WatchlistCard";
import { SourceBadge } from "@/components/watchlist/SourceBadge";
import {
  getScoreBadgeVariant,
  getDataQualityColor,
  getDataQualityBgColor,
} from "@/components/watchlist/ExpandedRowUtils";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Trash2,
  Loader2,
  Briefcase,
} from "lucide-react";
import {
  useDeleteWatchlistItem,
  useRefreshStatus,
} from "@/lib/hooks/useWatchlist";
import { usePreferences } from "@/lib/hooks/usePreferences";
import { usePortfolio } from "@/lib/hooks/usePortfolio";
import type { WatchlistItem } from "@/lib/api/watchlist";
import { cn } from "@/lib/utils";
import { ConfirmActionDialog } from "@/components/shared/ConfirmActionDialog";

interface WatchlistTableProps {
  items: WatchlistItem[];
}

type SortField = "symbol" | "overall" | "price" | "technical" | "news" | "updated" | "risk";
type SortDirection = "asc" | "desc";

type WatchlistSnapshot = {
  price: number | null;
  score: number | null;
  risk: WatchlistItem["riskLevel"];
  updatedAt: string | null;
};

export function WatchlistTable({ items }: WatchlistTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("symbol");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [highlightedSymbol, setHighlightedSymbol] = useState<string | null>(null);
  const deleteMutation = useDeleteWatchlistItem();
  const { data: refreshStatus } = useRefreshStatus();
  const { data: preferences } = usePreferences();
  const { data: portfolio } = usePortfolio();
  const searchParams = useSearchParams();
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map());
  const previousSnapshots = useRef<Map<string, WatchlistSnapshot>>(new Map());
  const [changedCells, setChangedCells] = useState<Record<string, Record<string, boolean>>>({});
  const [recentlyUpdatedRows, setRecentlyUpdatedRows] = useState<Set<string>>(new Set());

  // Get user's timezone preference
  const userTimezone = preferences?.displayTimezone ?? "America/New_York";

  // Get current portfolio symbols (for showing portfolio badge)
  const portfolioSymbols = new Set(
    portfolio?.positions?.map((p) => p.symbol.toUpperCase()) ?? []
  );

  const buildSnapshot = (item: WatchlistItem): WatchlistSnapshot => ({
    price:
      typeof item.currentScore?.price.metadata?.price === "number"
        ? item.currentScore.price.metadata.price
        : null,
    score: item.currentScore?.overall ?? null,
    risk: item.riskLevel ?? null,
    updatedAt: item.currentScore?.price?.updatedAt ?? item.updatedAt,
  });

  // Scroll to symbol from query parameter
  useEffect(() => {
    const symbol = searchParams?.get("symbol");
    if (symbol && items.length > 0) {
      const targetItem = items.find(
        (item) => item.symbol.toUpperCase() === symbol.toUpperCase()
      );
      if (targetItem) {
        const rowElement = rowRefs.current.get(targetItem.id);
        if (rowElement) {
          setTimeout(() => {
            rowElement.scrollIntoView({ behavior: "smooth", block: "center" });
            setExpandedId(targetItem.id);
            setHighlightedSymbol(targetItem.symbol);
            setTimeout(() => setHighlightedSymbol(null), 3000);
          }, 100);
        }
      }
    }
  }, [searchParams, items]);

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
        aVal = a.currentScore?.overall ?? -1;
        bVal = b.currentScore?.overall ?? -1;
        break;
      case "price":
        aVal = a.currentScore?.price.score ?? -1;
        bVal = b.currentScore?.price.score ?? -1;
        break;
      case "technical":
        aVal = a.currentScore?.technical.score ?? -1;
        bVal = b.currentScore?.technical.score ?? -1;
        break;
      case "news":
        aVal = a.newsSentimentScore ?? -2;
        bVal = b.newsSentimentScore ?? -2;
        break;
      case "risk":
        aVal = a.riskLevel ?? "";
        bVal = b.riskLevel ?? "";
        break;
      case "updated":
        aVal = a.currentScore?.price?.updatedAt ?? a.updatedAt;
        bVal = b.currentScore?.price?.updatedAt ?? b.updatedAt;
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

  const [pendingDelete, setPendingDelete] = useState<{ id: string; symbol: string } | null>(null);

  // Handle delete (request confirmation)
  const handleDelete = (itemId: string, symbol: string) => {
    setPendingDelete({ id: itemId, symbol });
  };

  const confirmDeleteSymbol = async () => {
    if (!pendingDelete) return;
    try {
      await deleteMutation.mutateAsync(pendingDelete.id);
      if (expandedId === pendingDelete.id) {
        setExpandedId(null);
      }
    } catch (error) {
      throw error;
    }
  };

  const toggleRow = (itemId: string) => {
    setExpandedId((current) => (current === itemId ? null : itemId));
  };

  const deleteDialog = (
    <ConfirmActionDialog
      open={!!pendingDelete}
      onOpenChange={(open) => {
        if (!open) {
          setPendingDelete(null);
        }
      }}
      title={
        pendingDelete ? `Remove ${pendingDelete.symbol}` : "Remove symbol"
      }
      description="Removing a symbol clears its saved scores and expansions."
      confirmLabel="Remove"
      isPending={deleteMutation.isPending}
      onConfirm={confirmDeleteSymbol}
    />
  );

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

  // Get data quality color based on percentage
  const getDataQualityColor = (pct: number): string => {
    if (pct >= 80) return "text-gain";
    if (pct >= 60) return "text-warning";
    if (pct >= 40) return "text-neutral";
    return "text-loss";
  };

  // Get data quality background color
  const getDataQualityBgColor = (pct: number): string => {
    if (pct >= 80) return "bg-gain/10";
    if (pct >= 60) return "bg-warning/10";
    if (pct >= 40) return "bg-neutral/10";
    return "bg-loss/10";
  };

  // Format pillar status
  const formatPillarStatus = (status: string): string => {
    const statusMap: Record<string, string> = {
      complete: "✓ Complete",
      partial: "◐ Partial",
      stale: "⏱ Stale",
      "n/a": "— N/A",
    };
    return statusMap[status] || status;
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

  // Track change detection for cell flash animations
  // Uses refs to avoid synchronous setState in effect body
  useEffect(() => {
    // Handle empty items - clear refs only, no setState needed
    // The render will use current state which may be stale but harmless
    if (!items.length) {
      previousSnapshots.current = new Map();
      // Let the animation timeouts clear themselves naturally
      return;
    }

    const nextSnapshots = new Map<string, WatchlistSnapshot>();
    const nextChanged: Record<string, Record<string, boolean>> = {};
    const updatedRows: string[] = [];

    items.forEach((item) => {
      const snapshot = buildSnapshot(item);
      nextSnapshots.set(item.id, snapshot);
      const previous = previousSnapshots.current.get(item.id);
      if (!previous) {
        updatedRows.push(item.id);
        return;
      }

      const fieldChanges: Record<string, boolean> = {};
      if (snapshot.price !== previous.price) fieldChanges.price = true;
      if (snapshot.score !== previous.score) fieldChanges.score = true;
      if (snapshot.risk !== previous.risk) fieldChanges.risk = true;
      if (snapshot.updatedAt !== previous.updatedAt) fieldChanges.updatedAt = true;

      if (Object.keys(fieldChanges).length > 0) {
        nextChanged[item.id] = fieldChanges;
        updatedRows.push(item.id);
      }
    });

    previousSnapshots.current = nextSnapshots;

    // Use setTimeout(0) to defer state updates outside the synchronous effect body
    // This avoids the "setState in effect" warning while maintaining the same behavior
    const immediateTimeout = window.setTimeout(() => {
      // Set changed cells if there are actual changes
      if (Object.keys(nextChanged).length > 0) {
        setChangedCells(nextChanged);
      }
      // Set updated rows if there are actual updates
      if (updatedRows.length > 0) {
        setRecentlyUpdatedRows(new Set(updatedRows));
      }
    }, 0);

    // Clear animation state after delay
    const cellTimeout = window.setTimeout(() => setChangedCells({}), 2200);
    const rowTimeout = window.setTimeout(() => setRecentlyUpdatedRows(new Set()), 1500);

    return () => {
      window.clearTimeout(immediateTimeout);
      window.clearTimeout(cellTimeout);
      window.clearTimeout(rowTimeout);
    };
  }, [items]);

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-8 text-center">
        <p className="text-text-muted">
          No symbols in your watchlist yet. Click &quot;Add Symbol&quot; to get
          started.
        </p>
      </div>
    );
  }

  return (
    <>
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
                onClick={() => handleSort("overall")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Score
                {sortField === "overall" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => handleSort("risk")}
                className="flex items-center gap-1 font-medium hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Risk
                {sortField === "risk" && (
                  <span className="text-xs">
                    {sortDirection === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            </TableHead>
            <TableHead>
              <span className="font-medium">DQ</span>
            </TableHead>
            <TableHead>Score Trend</TableHead>
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
            const hasScore = !!item.currentScore;
            const overall = item.currentScore?.overall ?? 0;

            return (
              <Fragment key={item.id}>
                <TableRow
                  ref={(el) => {
                    if (el) {
                      rowRefs.current.set(item.id, el);
                    } else {
                      rowRefs.current.delete(item.id);
                    }
                  }}
                  className={cn(
                    "cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    isExpanded && "bg-surface-muted/40",
                    highlightedSymbol === item.symbol && "bg-accent/10 animate-pulse"
                  )}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  aria-controls={`watchlist-row-${item.id}`}
                  data-slot="table-row"
                  data-recently-updated={
                    recentlyUpdatedRows.has(item.id) ? "true" : undefined
                  }
                  onClick={() => toggleRow(item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleRow(item.id);
                    }
                  }}
                >
                  <TableCell data-slot="table-cell">
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
                  <TableCell className="font-medium" data-slot="table-cell">
                    <div className="flex items-center gap-2">
                      <span>{item.symbol}</span>
                      {portfolioSymbols.has(item.symbol.toUpperCase()) && (
                        <Badge
                          variant="outline"
                          className="gap-1 text-xs px-1.5 py-0 h-5 bg-accent/10 border-accent/30 text-accent"
                        >
                          <Briefcase className="h-3 w-3" />
                          <span>Portfolio</span>
                        </Badge>
                      )}
                      {item.currentScore?.price.metadata?.source &&
                      typeof item.currentScore.price.metadata.source ===
                        "string" ? (
                        <SourceBadge
                          source={item.currentScore.price.metadata.source}
                          stale={item.currentScore.price.stale}
                          priority={
                            typeof item.currentScore.price.metadata
                              .priority === "number"
                              ? item.currentScore.price.metadata.priority
                              : undefined
                          }
                        />
                      ) : null}
                      {refreshStatus?.isRefreshing &&
                        refreshStatus.currentSymbol === item.symbol && (
                          <Loader2
                            className="h-4 w-4 animate-spin text-accent"
                            aria-label="Refreshing..."
                          />
                        )}
                      {item.scoreAlert && (
                        <AlertCircle
                          className="h-4 w-4 text-accent"
                          aria-label="Score changed >10 points in last 7 days"
                        />
                      )}
                    </div>
                  </TableCell>
                  <TableCell
                    data-slot="table-cell"
                    data-changed={changedCells[item.id]?.price ? "true" : undefined}
                  >
                    {item.currentScore?.price.metadata?.price ? (
                      <div
                        className="text-sm price-display"
                        data-changed={
                          changedCells[item.id]?.price ? "true" : undefined
                        }
                      >
                        <div className="font-medium">
                          ${typeof item.currentScore.price.metadata.price === 'number'
                            ? item.currentScore.price.metadata.price.toFixed(2)
                            : String(item.currentScore.price.metadata.price)}
                        </div>
                        {item.currentScore.price.metadata.rawChangePct !== undefined && (
                          <div className={cn(
                            "text-xs",
                            typeof item.currentScore.price.metadata.rawChangePct === 'number' && item.currentScore.price.metadata.rawChangePct >= 0
                              ? "text-gain"
                              : "text-loss"
                          )}>
                            {typeof item.currentScore.price.metadata.rawChangePct === 'number'
                              ? `${item.currentScore.price.metadata.rawChangePct >= 0 ? '+' : ''}${item.currentScore.price.metadata.rawChangePct.toFixed(2)}%`
                              : `${String(item.currentScore.price.metadata.rawChangePct)}%`}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell
                    data-slot="table-cell"
                    data-changed={changedCells[item.id]?.score ? "true" : undefined}
                  >
                    {hasScore ? (
                      <div className="flex items-center gap-2">
                        <Badge variant={getScoreBadgeVariant(overall)} className="score-badge">
                          {overall.toFixed(0)}
                        </Badge>
                        <div className="flex-1 h-2 bg-surface-muted rounded-full overflow-hidden min-w-[60px]">
                          <div
                            className={cn(
                              "h-full transition-all",
                              overall >= 80 ? "bg-gain" : overall >= 60 ? "bg-warning" : overall >= 40 ? "bg-neutral" : "bg-loss"
                            )}
                            style={{ width: `${overall}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell
                    data-slot="table-cell"
                    data-changed={changedCells[item.id]?.risk ? "true" : undefined}
                  >
                    {item.riskLevel ? (
                      (() => {
                        const riskConfig: Record<string, { label: string; icon: string; color: string }> = {
                          "Low": { label: "Low", icon: "✓", color: "text-gain" },
                          "Medium-Low": { label: "Med-Low", icon: "⚠", color: "text-warning" },
                          "Medium": { label: "Medium", icon: "⚠", color: "text-neutral" },
                          "High": { label: "High", icon: "⚠⚠", color: "text-loss" }
                        };
                        const config = riskConfig[item.riskLevel] || { label: item.riskLevel, icon: "", color: "text-text-muted" };
                        return (
                          <div className={cn("text-xs font-medium", config.color)}>
                            {config.icon} {config.label}
                          </div>
                        );
                      })()
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell data-slot="table-cell">
                    {item.dataQuality ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div
                              className={cn(
                                "inline-flex items-center justify-center rounded-md px-2 py-1 text-xs font-semibold cursor-help",
                                getDataQualityBgColor(item.dataQuality.overallPct),
                                getDataQualityColor(item.dataQuality.overallPct)
                              )}
                            >
                              {item.dataQuality.overallPct.toFixed(0)}%
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs">
                            <div className="space-y-1.5">
                              <div className="font-semibold text-xs border-b border-border pb-1">
                                Data Quality Breakdown
                              </div>
                              {Object.entries(item.dataQuality.pillars).map(([pillar, data]) => (
                                <div key={pillar} className="text-xs">
                                  <div className="font-medium capitalize">{pillar}:</div>
                                  <div className="text-text-muted ml-2">
                                    {formatPillarStatus(data.status)} - {data.details}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell data-slot="table-cell">
                    {hasScore ? (
                      <SparklineWithHistory
                        itemId={item.id}
                        width={80}
                        height={24}
                        recommendedStyle={item.recommendedStyle}
                      />
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                  <TableCell
                    className="text-xs text-text-muted"
                    data-slot="table-cell"
                    data-changed={changedCells[item.id]?.updatedAt ? "true" : undefined}
                  >
                    {item.currentScore?.price?.updatedAt
                      ? formatDate(item.currentScore.price.updatedAt, userTimezone)
                      : formatDate(item.updatedAt, userTimezone)}
                  </TableCell>
                  <TableCell data-slot="table-cell">
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
                  <TableRow id={`watchlist-row-${item.id}`} data-state="open">
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
      {deleteDialog}
    </>
  );
}
