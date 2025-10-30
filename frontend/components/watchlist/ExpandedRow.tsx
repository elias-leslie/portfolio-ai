"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkline } from "@/components/ui/sparkline";
import { Save, Edit2, X, Loader2 } from "lucide-react";
import { useUpdateWatchlistItem, useScoreHistory } from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";
import type { WatchlistItem, RefreshStatus } from "@/lib/api/watchlist";

interface ExpandedRowProps {
  item: WatchlistItem;
  refreshStatus?: RefreshStatus;
}

export function ExpandedRow({ item, refreshStatus }: ExpandedRowProps) {
  const [isEditingNote, setIsEditingNote] = useState(false);
  const [noteValue, setNoteValue] = useState(item.note || "");
  const updateMutation = useUpdateWatchlistItem();
  const { data: historyResponse } = useScoreHistory(item.id);

  const hasScore = !!item.current_score;
  const history = historyResponse?.history || [];
  const priceScore = item.current_score?.price;
  const techScore = item.current_score?.technical;

  // Check if this item is currently being refreshed
  const isRefreshing =
    refreshStatus?.is_refreshing && refreshStatus.current_symbol === item.symbol;

  const handleSaveNote = () => {
    updateMutation.mutate(
      {
        itemId: item.id,
        data: { note: noteValue.trim() || undefined },
      },
      {
        onSuccess: () => {
          toast.success("Note updated");
          setIsEditingNote(false);
        },
        onError: (error) => {
          toast.error(`Failed to update note: ${error.message}`);
        },
      }
    );
  };

  const handleCancelEdit = () => {
    setNoteValue(item.note || "");
    setIsEditingNote(false);
  };

  // Get score badge variant
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

  // Format timestamp
  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <div className="space-y-4">
      {/* Refresh Progress Card */}
      {isRefreshing && refreshStatus && (
        <Card className="border-accent bg-accent/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Refreshing Scores...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm text-text-muted">
              {refreshStatus.elapsed_seconds !== undefined && (
                <p>
                  Elapsed time:{" "}
                  <span className="font-medium text-text">
                    {refreshStatus.elapsed_seconds}s
                  </span>
                </p>
              )}
              {refreshStatus.percent_complete !== undefined && (
                <p>
                  Progress:{" "}
                  <span className="font-medium text-text">
                    {refreshStatus.percent_complete.toFixed(0)}%
                  </span>
                </p>
              )}
              {refreshStatus.processed_items !== undefined &&
                refreshStatus.total_items !== undefined && (
                  <p>
                    Items processed:{" "}
                    <span className="font-medium text-text">
                      {refreshStatus.processed_items} / {refreshStatus.total_items}
                    </span>
                  </p>
                )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score Breakdown */}
      {hasScore && (
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Price Score Card */}
          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center justify-between">
                Price Score
                {priceScore?.stale && (
                  <Badge variant="outline" className="text-xs font-normal">
                    Stale
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Badge variant={getScoreBadgeVariant(priceScore?.score ?? 0)}>
                  {priceScore?.score.toFixed(1) ?? "—"}
                </Badge>
                <p className="mt-2 text-xs text-text-muted">
                  Weight: {((priceScore?.weight ?? 0) * 100).toFixed(0)}%
                </p>
              </div>
              {priceScore?.updated_at && (
                <p className="text-xs text-text-muted">
                  Updated: {formatTimestamp(priceScore.updated_at)}
                </p>
              )}
              {priceScore?.metadata && Object.keys(priceScore.metadata).length > 0 && (
                <div className="space-y-1 text-xs">
                  <p className="font-medium text-text">Metrics:</p>
                  {Object.entries(priceScore.metadata).map(([key, value]) => (
                    <p key={key} className="text-text-muted">
                      {key}:{" "}
                      {typeof value === "number"
                        ? value.toFixed(2)
                        : String(value)}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Technical Score Card */}
          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center justify-between">
                Technical Score
                {techScore?.stale && (
                  <Badge variant="outline" className="text-xs font-normal">
                    Stale
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Badge variant={getScoreBadgeVariant(techScore?.score ?? 0)}>
                  {techScore?.score.toFixed(1) ?? "—"}
                </Badge>
                <p className="mt-2 text-xs text-text-muted">
                  Weight: {((techScore?.weight ?? 0) * 100).toFixed(0)}%
                </p>
              </div>
              {techScore?.updated_at && (
                <p className="text-xs text-text-muted">
                  Updated: {formatTimestamp(techScore.updated_at)}
                </p>
              )}
              {techScore?.metadata && Object.keys(techScore.metadata).length > 0 && (
                <div className="space-y-1 text-xs">
                  <p className="font-medium text-text">Metrics:</p>
                  {Object.entries(techScore.metadata).map(([key, value]) => (
                    <p key={key} className="text-text-muted">
                      {key}:{" "}
                      {typeof value === "number"
                        ? value.toFixed(2)
                        : String(value)}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* 7-Day Score Timeline */}
      {history && history.length > 0 && (
        <Card className="border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">7-Day Score History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-medium text-text-muted">
                  Overall Score
                </p>
                <Sparkline
                  data={history.map((h) => h.overall_score)}
                  width={200}
                  height={40}
                  showDots
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-2 text-xs font-medium text-text-muted">
                    Price Score
                  </p>
                  <Sparkline
                    data={history.map((h) => h.price_score)}
                    width={150}
                    height={32}
                  />
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-text-muted">
                    Technical Score
                  </p>
                  <Sparkline
                    data={history.map((h) => h.technical_score)}
                    width={150}
                    height={32}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Notes Section */}
      <Card className="border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            Notes
            {!isEditingNote && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditingNote(true)}
                className="h-8"
              >
                <Edit2 className="mr-1 h-3 w-3" />
                Edit
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isEditingNote ? (
            <div className="space-y-3">
              <Input
                value={noteValue}
                onChange={(e) => setNoteValue(e.target.value)}
                placeholder="Add a note about this ticker..."
                maxLength={200}
                className="w-full"
                autoFocus
              />
              <div className="flex items-center justify-between">
                <p className="text-xs text-text-muted">
                  {noteValue.length}/200 characters
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancelEdit}
                    disabled={updateMutation.isPending}
                  >
                    <X className="mr-1 h-3 w-3" />
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveNote}
                    disabled={updateMutation.isPending}
                  >
                    <Save className="mr-1 h-3 w-3" />
                    Save
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-text-muted">
              {item.note || "No notes yet. Click Edit to add one."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
