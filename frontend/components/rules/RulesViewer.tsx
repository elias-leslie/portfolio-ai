/**
 * Trading Rules Viewer Component
 *
 * Displays all trading rules from rules.yaml in expandable sections
 */

"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useRules } from "@/lib/hooks/useRules";

interface ExpandedSections {
  [key: string]: boolean;
}

export function RulesViewer() {
  const { data: rules, isLoading, error } = useRules();
  const [expandedSections, setExpandedSections] = useState<ExpandedSections>({});

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // Format field names to readable labels
  const formatLabel = (key: string): string => {
    return key
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Format values for display
  const formatValue = (value: unknown): string => {
    if (typeof value === "boolean") {
      return value ? "Yes" : "No";
    }
    if (typeof value === "number") {
      // Check if it's a percentage (< 1 or explicitly named as such)
      if (value < 1 && value > -1 && value !== 0) {
        return `${(value * 100).toFixed(2)}%`;
      }
      return value.toString();
    }
    if (Array.isArray(value)) {
      return value.join(", ");
    }
    if (typeof value === "string") {
      return value;
    }
    return JSON.stringify(value);
  };

  // Render a rule section with key-value pairs
  const renderRuleSection = (title: string, data: Record<string, unknown>) => {
    const isExpanded = expandedSections[title];

    return (
      <div key={title} className="rounded-lg border border-border bg-surface overflow-hidden">
        {/* Header */}
        <button
          onClick={() => toggleSection(title)}
          className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
            <span className="font-semibold text-foreground">{formatLabel(title)}</span>
            <Badge variant="outline" className="text-xs">
              {Object.keys(data).length} rules
            </Badge>
          </div>
        </button>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-border bg-surface-muted/30 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(data).map(([key, value]) => (
                <div
                  key={key}
                  className="rounded border border-border bg-surface p-3"
                >
                  <div className="text-sm font-medium text-muted-foreground mb-1">
                    {formatLabel(key)}
                  </div>
                  <div className="text-base font-semibold text-foreground">
                    {formatValue(value)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render catalyst impacts section (special handling for nested structure)
  const renderCatalystImpacts = (data: Record<string, { impact: number; duration_days: number }>) => {
    const title = "catalyst_impacts";
    const isExpanded = expandedSections[title];

    return (
      <div key={title} className="rounded-lg border border-border bg-surface overflow-hidden">
        {/* Header */}
        <button
          onClick={() => toggleSection(title)}
          className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
            <span className="font-semibold text-foreground">Catalyst Impacts</span>
            <Badge variant="outline" className="text-xs">
              {Object.keys(data).length} events
            </Badge>
          </div>
        </button>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-border bg-surface-muted/30 p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(data)
                .sort((a, b) => b[1].impact - a[1].impact) // Sort by impact (highest first)
                .map(([eventType, catalyst]) => (
                  <div
                    key={eventType}
                    className="rounded border border-border bg-surface p-3"
                  >
                    <div className="text-sm font-medium text-foreground mb-2">
                      {formatLabel(eventType)}
                    </div>
                    <div className="flex items-center gap-3">
                      <div>
                        <div className="text-xs text-muted-foreground">Impact</div>
                        <div
                          className={`text-base font-semibold ${
                            catalyst.impact > 0
                              ? "text-green-500"
                              : catalyst.impact < 0
                              ? "text-red-500"
                              : "text-muted-foreground"
                          }`}
                        >
                          {catalyst.impact > 0 ? "+" : ""}
                          {catalyst.impact.toFixed(1)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Duration</div>
                        <div className="text-base font-semibold text-foreground">
                          {catalyst.duration_days}d
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-sm text-destructive">Failed to load trading rules</p>
      </div>
    );
  }

  if (!rules) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Trading Rules</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Version {rules.version} - Updated {rules.updated} by {rules.updated_by}
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-green-500">
            {(rules.position_sizing.default_risk_percent * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-muted-foreground">Default Risk/Trade</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-red-500">
            {rules.risk_management.portfolio_drawdown_halt_pct.toFixed(0)}%
          </div>
          <div className="text-sm text-muted-foreground">Drawdown Halt</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-blue-500">
            {rules.watchlist_management.max_watchlist_size}
          </div>
          <div className="text-sm text-muted-foreground">Max Watchlist</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-purple-500">
            {Object.keys(rules.catalyst_impacts).length}
          </div>
          <div className="text-sm text-muted-foreground">Catalyst Events</div>
        </div>
      </div>

      {/* Rule Sections */}
      <div className="space-y-3">
        {renderRuleSection("position_sizing", rules.position_sizing as Record<string, unknown>)}
        {renderRuleSection("risk_management", rules.risk_management as Record<string, unknown>)}
        {renderRuleSection("technical_thresholds", rules.technical_thresholds as Record<string, unknown>)}
        {renderRuleSection("scoring", rules.scoring as Record<string, unknown>)}
        {renderRuleSection("fundamentals", rules.fundamentals as Record<string, unknown>)}
        {renderRuleSection("signals", rules.signals as Record<string, unknown>)}
        {renderRuleSection("fees", rules.fees as Record<string, unknown>)}
        {renderRuleSection("compliance", rules.compliance as Record<string, unknown>)}
        {renderRuleSection("market", rules.market as Record<string, unknown>)}
        {renderRuleSection("paper_trading", rules.paper_trading as Record<string, unknown>)}
        {renderCatalystImpacts(rules.catalyst_impacts)}
        {renderRuleSection("watchlist_management", rules.watchlist_management as Record<string, unknown>)}
      </div>
    </div>
  );
}
