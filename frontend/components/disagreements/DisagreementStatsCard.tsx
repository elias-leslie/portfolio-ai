"use client";

import { AlertTriangle, CheckCircle, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DisagreementStats } from "@/lib/api/disagreements";

interface DisagreementStatsCardProps {
  stats: DisagreementStats;
  className?: string;
}

export function DisagreementStatsCard({ stats, className }: DisagreementStatsCardProps) {
  const agreementPercent = Math.round(stats.agreementRate * 100);
  const minorPercent = Math.round(stats.minorDisagreementRate * 100);
  const majorPercent = Math.round(stats.majorDisagreementRate * 100);
  const avgScore = Math.round(stats.avgAgreementScore * 100);

  // Calculate trend (compare first vs last day of trend data)
  const trend = stats.trend7D;
  const trendDirection = trend.length >= 2
    ? trend[0].avgScore > trend[trend.length - 1].avgScore
      ? "improving"
      : "declining"
    : "stable";

  // Target is 80% agreement rate (20% max disagreement per VISION.md)
  const meetsTarget = agreementPercent >= 80;

  return (
    <div className={cn("rounded-lg border border-border/50 bg-surface/60 p-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text">LLM Consensus Metrics</h3>
        {meetsTarget ? (
          <div className="flex items-center gap-1 text-gain">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm">Target Met</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-warning">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm">Below Target</span>
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {/* Agreement Rate */}
        <div className="text-center">
          <div className="text-2xl font-bold text-gain">{agreementPercent}%</div>
          <div className="text-sm text-text-muted">Agreement</div>
        </div>

        {/* Minor Disagreements */}
        <div className="text-center">
          <div className="text-2xl font-bold text-warning">{minorPercent}%</div>
          <div className="text-sm text-text-muted">Minor</div>
        </div>

        {/* Major Disagreements */}
        <div className="text-center">
          <div className="text-2xl font-bold text-loss">{majorPercent}%</div>
          <div className="text-sm text-text-muted">Major</div>
        </div>

        {/* Avg Agreement Score */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-1">
            <span className="text-2xl font-bold text-text">{avgScore}%</span>
            {trendDirection === "improving" && (
              <TrendingUp className="h-4 w-4 text-gain" />
            )}
            {trendDirection === "declining" && (
              <TrendingDown className="h-4 w-4 text-loss" />
            )}
          </div>
          <div className="text-sm text-text-muted">Avg Score</div>
        </div>
      </div>

      {/* Review Counts */}
      <div className="mt-4 pt-4 border-t border-border/40">
        <div className="flex justify-between text-sm text-text-muted">
          <span>{stats.totalReviews} total reviews</span>
          <span>{stats.totalReviewPairs} review pairs</span>
        </div>
      </div>

      {/* 7-Day Trend Sparkline */}
      {trend.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border/40">
          <div className="text-sm text-text-muted mb-2">7-Day Trend</div>
          <div className="flex items-end gap-1 h-12">
            {trend.slice().reverse().map((day, idx) => {
              const height = Math.max(10, day.avgScore * 100);
              const hasDisagreements = day.disagreements > 0;
              return (
                <div
                  key={idx}
                  className="flex-1 rounded-t"
                  style={{
                    height: `${height}%`,
                    backgroundColor: hasDisagreements
                      ? "var(--color-warning)"
                      : "var(--color-gain)",
                    opacity: 0.5,
                  }}
                  title={`${day.date}: ${day.reviews} reviews, ${day.disagreements} disagreements`}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
