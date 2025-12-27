"use client";

import { useState } from "react";
import { AlertTriangle, X, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface DisagreementAlertProps {
  symbol: string;
  severity: "minor" | "major";
  geminiReview: string | null;
  claudeReview: string | null;
  agreementScore: number;
  onDismiss?: () => void;
  className?: string;
}

export function DisagreementAlert({
  symbol,
  severity,
  geminiReview,
  claudeReview,
  agreementScore,
  onDismiss,
  className,
}: DisagreementAlertProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) return null;

  const isMajor = severity === "major";
  const bgColor = isMajor ? "bg-loss/10" : "bg-warning/10";
  const borderColor = isMajor ? "border-loss/30" : "border-warning/30";
  const textColor = isMajor ? "text-loss" : "text-warning";
  const agreementPercent = Math.round(agreementScore * 100);

  const handleDismiss = () => {
    setIsDismissed(true);
    onDismiss?.();
  };

  return (
    <div
      className={cn(
        "rounded-lg border p-3 transition-all",
        bgColor,
        borderColor,
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn("h-4 w-4", textColor)} />
          <span className={cn("text-sm font-medium", textColor)}>
            {isMajor ? "Major" : "Minor"} LLM Disagreement
          </span>
          <span className="text-sm text-text-muted">
            ({agreementPercent}% agreement)
          </span>
        </div>
        <div className="flex items-center gap-1">
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
          <button
            onClick={handleDismiss}
            className="p-1 hover:bg-surface-hover rounded"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4 text-text-muted" />
          </button>
        </div>
      </div>

      {/* Summary */}
      <p className="mt-1 text-sm text-text-muted">
        {isMajor
          ? `Gemini and Claude significantly disagree on ${symbol} - manual review recommended`
          : `Minor differences in ${symbol} analysis between providers`}
      </p>

      {/* Expanded Reviews */}
      {isExpanded && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {/* Gemini */}
          <div className="rounded bg-surface/50 p-2">
            <div className="flex items-center gap-1.5 mb-1">
              <div className="h-1.5 w-1.5 rounded-full bg-accent" />
              <span className="text-xs font-medium text-text">Gemini</span>
            </div>
            <p className="text-xs text-text-muted line-clamp-3">
              {geminiReview || "No review available"}
            </p>
          </div>

          {/* Claude */}
          <div className="rounded bg-surface/50 p-2">
            <div className="flex items-center gap-1.5 mb-1">
              <div className="h-1.5 w-1.5 rounded-full bg-warning" />
              <span className="text-xs font-medium text-text">Claude</span>
            </div>
            <p className="text-xs text-text-muted line-clamp-3">
              {claudeReview || "No review available"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
