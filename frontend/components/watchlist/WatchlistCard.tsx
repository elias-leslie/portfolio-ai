"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sparkline } from "@/components/ui/sparkline";
import { ExpandedRow } from "@/components/watchlist/ExpandedRow";
import { ChevronDown, ChevronRight, AlertCircle, Trash2 } from "lucide-react";
import type { WatchlistItem } from "@/lib/api/watchlist";

interface WatchlistCardProps {
  item: WatchlistItem;
  onDelete: (itemId: string, symbol: string) => void;
  isDeleting: boolean;
}

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

export function WatchlistCard({
  item,
  onDelete,
  isDeleting,
}: WatchlistCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasScore = !!item.current_score;
  const overall = item.current_score?.overall ?? 0;
  const priceScore = item.current_score?.price.score ?? 0;
  const techScore = item.current_score?.technical.score ?? 0;
  const priceStale = item.current_score?.price.stale ?? false;
  const techStale = item.current_score?.technical.stale ?? false;

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
      {/* Card Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-text">{item.symbol}</h3>
          {item.score_alert && (
            <AlertCircle
              className="h-4 w-4 text-accent"
              aria-label="Score changed >10 points in last 7 days"
            />
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 w-8 p-0"
            aria-label={isExpanded ? "Collapse details" : "Expand details"}
            aria-expanded={isExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(item.id, item.symbol)}
            disabled={isDeleting}
            className="h-8 w-8 p-0 text-loss hover:bg-loss/10"
            aria-label={`Delete ${item.symbol}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Score Grid */}
      <div className="mb-3 grid grid-cols-3 gap-3">
        <div>
          <p className="mb-1 text-xs text-text-muted">Overall</p>
          {hasScore ? (
            <Badge variant={getScoreBadgeVariant(overall)} className="text-sm">
              {overall.toFixed(1)}
            </Badge>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
        <div>
          <p className="mb-1 text-xs text-text-muted">Price</p>
          {hasScore ? (
            <div className="flex flex-col gap-0.5">
              <Badge variant={getScoreBadgeVariant(priceScore)} className="text-sm">
                {priceScore.toFixed(1)}
              </Badge>
              {priceStale && (
                <span className="text-xs text-text-muted">(stale)</span>
              )}
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
        <div>
          <p className="mb-1 text-xs text-text-muted">Technical</p>
          {hasScore ? (
            <div className="flex flex-col gap-0.5">
              <Badge variant={getScoreBadgeVariant(techScore)} className="text-sm">
                {techScore.toFixed(1)}
              </Badge>
              {techStale && (
                <span className="text-xs text-text-muted">(stale)</span>
              )}
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
      </div>

      {/* 7-Day Trend */}
      {hasScore && (
        <div className="mb-2">
          <p className="mb-1 text-xs text-text-muted">7-Day Trend</p>
          <Sparkline
            data={[65, 68, 72, 70, 73, 71, overall]}
            width={120}
            height={32}
          />
        </div>
      )}

      {/* Updated Timestamp */}
      <p className="text-xs text-text-muted">
        Updated {formatDate(item.updated_at)}
      </p>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mt-4 border-t border-border pt-4">
          <ExpandedRow item={item} />
        </div>
      )}
    </div>
  );
}
