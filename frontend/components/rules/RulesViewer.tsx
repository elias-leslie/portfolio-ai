/**
 * Trading Rules Viewer Component
 *
 * Displays all trading rules from rules.yaml in expandable sections
 */

"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Download, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useRules } from "@/lib/hooks/useRules";
import { toast } from "sonner";

interface ExpandedSections {
  [key: string]: boolean;
}

export function RulesViewer() {
  const { data: rules, isLoading, error } = useRules();
  const [expandedSections, setExpandedSections] = useState<ExpandedSections>({});
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async (format: "yaml" | "json") => {
    setIsExporting(true);
    try {
      const response = await fetch(`/api/rules/export?format=${format}`);
      if (!response.ok) {
        throw new Error("Export failed");
      }

      // Get the blob and trigger download
      const blob = await response.blob();
      const filename = response.headers.get("Content-Disposition")
        ?.match(/filename="(.+)"/)?.[1] || `trading_rules.${format}`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success(`Rules exported as ${format.toUpperCase()}`);
    } catch {
      toast.error("Failed to export rules");
    } finally {
      setIsExporting(false);
    }
  };

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
  const renderCatalystImpacts = (data: Record<string, { impact: number; durationDays: number }>) => {
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
                              ? "text-gain"
                              : catalyst.impact < 0
                              ? "text-loss"
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
                          {catalyst.durationDays}d
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
            Version {rules.version} - Updated {rules.updated} by {rules.updatedBy}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={isExporting}>
              {isExporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Export
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleExport("yaml")}>
              Export as YAML
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("json")}>
              Export as JSON
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-gain">
            {(rules.positionSizing.defaultRiskPercent * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-muted-foreground">Default Risk/Trade</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-loss">
            {rules.riskManagement.portfolioDrawdownHaltPct.toFixed(0)}%
          </div>
          <div className="text-sm text-muted-foreground">Drawdown Halt</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-accent">
            {rules.watchlistManagement.maxWatchlistSize}
          </div>
          <div className="text-sm text-muted-foreground">Max Watchlist</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-accent">
            {Object.keys(rules.catalystImpacts).length}
          </div>
          <div className="text-sm text-muted-foreground">Catalyst Events</div>
        </div>
      </div>

      {/* Rule Sections */}
      <div className="space-y-3">
        {renderRuleSection("position_sizing", rules.positionSizing as Record<string, unknown>)}
        {renderRuleSection("risk_management", rules.riskManagement as Record<string, unknown>)}
        {renderRuleSection("technical_thresholds", rules.technicalThresholds as Record<string, unknown>)}
        {renderRuleSection("scoring", rules.scoring as Record<string, unknown>)}
        {renderRuleSection("fundamentals", rules.fundamentals as Record<string, unknown>)}
        {renderRuleSection("signals", rules.signals as Record<string, unknown>)}
        {renderRuleSection("fees", rules.fees as Record<string, unknown>)}
        {renderRuleSection("compliance", rules.compliance as Record<string, unknown>)}
        {renderRuleSection("market", rules.market as Record<string, unknown>)}
        {renderRuleSection("paper_trading", rules.paperTrading as Record<string, unknown>)}
        {renderCatalystImpacts(rules.catalystImpacts)}
        {renderRuleSection("watchlist_management", rules.watchlistManagement as Record<string, unknown>)}
      </div>
    </div>
  );
}
