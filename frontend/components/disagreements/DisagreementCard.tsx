"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle, MinusCircle, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DisagreementItem } from "@/lib/api/disagreements";

interface DisagreementCardProps {
  item: DisagreementItem;
  className?: string;
}

const severityConfig = {
  none: {
    icon: CheckCircle,
    color: "text-green-500",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/20",
    label: "Agreement",
  },
  minor: {
    icon: MinusCircle,
    color: "text-yellow-500",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/20",
    label: "Minor Disagreement",
  },
  major: {
    icon: AlertTriangle,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/20",
    label: "Major Disagreement",
  },
};

export function DisagreementCard({ item, className }: DisagreementCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const config = severityConfig[item.disagreementSeverity] || severityConfig.none;
  const Icon = config.icon;

  const agreementPercent = Math.round(item.agreementScore * 100);

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-colors",
        config.bgColor,
        config.borderColor,
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Icon className={cn("h-5 w-5", config.color)} />
          <div>
            <span className="font-semibold text-text">{item.symbol}</span>
            <span className={cn("ml-2 text-sm", config.color)}>
              {config.label}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted">
            {agreementPercent}% agreement
          </span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:bg-surface-hover rounded"
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4 text-text-muted" />
            ) : (
              <ChevronDown className="h-4 w-4 text-text-muted" />
            )}
          </button>
        </div>
      </div>

      {/* Summary */}
      <p className="mt-2 text-sm text-text-muted">{item.consensusSummary}</p>

      {/* Expanded Reviews */}
      {isExpanded && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {/* Gemini Review */}
          <div className="rounded-lg bg-surface/50 p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-2 w-2 rounded-full bg-blue-500" />
              <span className="text-sm font-medium text-text">Gemini</span>
            </div>
            <p className="text-sm text-text-muted">
              {item.geminiReview || "Review unavailable"}
            </p>
          </div>

          {/* Claude Review */}
          <div className="rounded-lg bg-surface/50 p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-2 w-2 rounded-full bg-orange-500" />
              <span className="text-sm font-medium text-text">Claude</span>
            </div>
            <p className="text-sm text-text-muted">
              {item.claudeReview || "Review unavailable"}
            </p>
          </div>
        </div>
      )}

      {/* Timestamp */}
      <div className="mt-3 text-xs text-text-muted">
        {new Date(item.createdAt).toLocaleString()}
      </div>
    </div>
  );
}
