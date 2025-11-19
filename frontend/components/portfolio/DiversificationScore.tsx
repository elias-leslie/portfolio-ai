"use client";

import { Card } from "@/components/ui/card";
import { Target } from "lucide-react";
import type { DiversificationScore as DiversificationScoreType } from "@/lib/api/portfolio";

interface DiversificationScoreProps {
  diversification: DiversificationScoreType;
}

export function DiversificationScore({ diversification }: DiversificationScoreProps) {
  // Determine color based on level
  const getLevelColor = (level: string) => {
    switch (level) {
      case "Excellent":
        return "text-gain";
      case "Good":
        return "text-accent";
      case "Fair":
        return "text-warning";
      case "Poor":
        return "text-loss";
      default:
        return "text-text-muted";
    }
  };

  const getBgColor = (level: string) => {
    switch (level) {
      case "Excellent":
        return "bg-gain/20";
      case "Good":
        return "bg-accent/20";
      case "Fair":
        return "bg-warning/20";
      case "Poor":
        return "bg-loss/20";
      default:
        return "bg-surface-muted";
    }
  };

  const getProgressColor = (level: string) => {
    switch (level) {
      case "Excellent":
        return "bg-gain";
      case "Good":
        return "bg-accent";
      case "Fair":
        return "bg-warning";
      case "Poor":
        return "bg-loss";
      default:
        return "bg-surface-muted";
    }
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-accent" />
          <h3 className="text-sm font-semibold text-text">Diversification</h3>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${getBgColor(diversification.level)} ${getLevelColor(diversification.level)}`}
        >
          {diversification.level}
        </span>
      </div>

      {/* Score Progress Bar */}
      <div className="mb-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-2xl font-bold text-text">
            {diversification.score.toFixed(0)}
          </span>
          <span className="text-xs text-text-muted">/ 100</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
          <div
            className={`h-full transition-all duration-500 ${getProgressColor(diversification.level)}`}
            style={{ width: `${diversification.score}%` }}
          />
        </div>
      </div>

      {/* Metrics */}
      <div className="space-y-2 border-t border-border pt-4">
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Holdings</span>
          <span className="text-sm font-medium text-text">
            {diversification.num_holdings}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Sectors</span>
          <span className="text-sm font-medium text-text">
            {diversification.num_sectors}
          </span>
        </div>
      </div>
    </Card>
  );
}
