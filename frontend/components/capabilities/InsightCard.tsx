/**
 * InsightCard component for displaying individual capability insights
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./StatusBadge";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2,
  MessageSquarePlus,
  Plus,
} from "lucide-react";
import type { CapabilityInsight } from "@/lib/api/capabilities";
import { formatDistanceToNow } from "date-fns";

interface InsightCardProps {
  insight: CapabilityInsight;
  onReview: (
    insightId: number,
    status: "confirmed" | "dismissed" | "in_progress" | "fixed",
    reason: string
  ) => Promise<void>;
  onAddNote?: (insightId: number) => void;
  onCreateFeature?: (insight: CapabilityInsight) => void;
  isLoading?: boolean;
}

/**
 * InsightCard component
 */
export function InsightCard({ insight, onReview, onAddNote, onCreateFeature, isLoading = false }: InsightCardProps) {
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewReason, setReviewReason] = useState("");

  const handleReview = async (status: "confirmed" | "dismissed" | "in_progress" | "fixed") => {
    setIsReviewing(true);
    try {
      await onReview(insight.id, status, reviewReason);
      setReviewReason("");
    } finally {
      setIsReviewing(false);
    }
  };

  // Determine icon based on severity
  const getIcon = () => {
    switch (insight.severity) {
      case "critical":
      case "high":
        return <AlertCircle className="h-5 w-5 text-loss" />;
      case "medium":
        return <AlertCircle className="h-5 w-5 text-accent" />;
      case "low":
        return <AlertCircle className="h-5 w-5 text-muted-foreground" />;
      default:
        return <AlertCircle className="h-5 w-5" />;
    }
  };

  // Determine if actions should be shown (only for pending insights)
  const showActions = insight.status === "pending";

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {getIcon()}
          <div className="flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <StatusBadge type="severity" value={insight.severity} />
              <StatusBadge type="status" value={insight.status} />
              <span className="text-xs text-muted-foreground">
                {insight.insight_type.replace(/_/g, " ")}
              </span>
            </div>
            <p className="text-sm font-medium text-text">{insight.finding}</p>
          </div>
        </div>
      </div>

      {/* Impact */}
      {insight.impact && (
        <div className="mb-3 rounded-md bg-surface-muted p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Impact</p>
          <p className="text-sm text-text">{insight.impact}</p>
        </div>
      )}

      {/* Suggested Fix */}
      {insight.suggested_fix && (
        <div className="mb-3 rounded-md bg-surface-muted p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Suggested Fix</p>
          <p className="text-sm text-text">{insight.suggested_fix}</p>
        </div>
      )}

      {/* Confidence & Metadata */}
      <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>
          Confidence: <span className="font-medium">{Math.round(insight.confidence * 100)}%</span>
        </span>
        <span>•</span>
        <span>
          Generated {formatDistanceToNow(new Date(insight.generated_at), { addSuffix: true })}
        </span>
        {insight.reviewed_at && (
          <>
            <span>•</span>
            <span>
              Reviewed by {insight.reviewed_by}{" "}
              {formatDistanceToNow(new Date(insight.reviewed_at), { addSuffix: true })}
            </span>
          </>
        )}
      </div>

      {/* Review Reason (if reviewed) */}
      {insight.status_reason && (
        <div className="mb-3 rounded-md border border-border bg-bg p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Review Note</p>
          <p className="text-sm text-text">{insight.status_reason}</p>
        </div>
      )}

      {/* Actions (for pending insights) */}
      {showActions && (
        <div className="space-y-3 border-t border-border pt-3">
          {/* Review Reason Input */}
          <Textarea
            placeholder="Add a note about this insight (optional)..."
            value={reviewReason}
            onChange={(e) => setReviewReason(e.target.value)}
            className="min-h-[60px] text-sm"
            disabled={isReviewing || isLoading}
          />

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => handleReview("confirmed")}
              disabled={isReviewing || isLoading}
            >
              {isReviewing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 h-4 w-4" />
              )}
              Confirm
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleReview("in_progress")}
              disabled={isReviewing || isLoading}
            >
              <Loader2 className="mr-2 h-4 w-4" />
              In Progress
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleReview("dismissed")}
              disabled={isReviewing || isLoading}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Dismiss
            </Button>
            {onAddNote && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onAddNote(insight.id)}
                disabled={isReviewing || isLoading}
              >
                <MessageSquarePlus className="mr-2 h-4 w-4" />
                Add Note
              </Button>
            )}
            {onCreateFeature && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onCreateFeature(insight)}
                disabled={isReviewing || isLoading}
                title="Create a feature task from this tech debt item"
              >
                <Plus className="mr-2 h-4 w-4" />
                Create Feature
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
