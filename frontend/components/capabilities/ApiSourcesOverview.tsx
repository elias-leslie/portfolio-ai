/**
 * API Sources Overview Component
 *
 * Displays all data source providers with:
 * - Provider cards with tier, rate limits, capabilities
 * - GAP coverage badges
 * - Expandable endpoint details
 */

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Cloud,
  Key,
  Clock,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Zap,
  Database,
  Newspaper,
  BarChart3,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  fetchSources,
  fetchSourceDetail,
  type SourceProvider,
  type SourceDetail,
} from "@/lib/api/sources";

interface ExpandedProviders {
  [key: string]: boolean;
}

export function ApiSourcesOverview() {
  const [expandedProviders, setExpandedProviders] = useState<ExpandedProviders>({});
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  // Fetch all providers
  const {
    data: sourcesData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["api-sources"],
    queryFn: fetchSources,
  });

  // Fetch detail for selected provider
  const { data: providerDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["api-source-detail", selectedProvider],
    queryFn: () => (selectedProvider ? fetchSourceDetail(selectedProvider) : null),
    enabled: !!selectedProvider,
  });

  const toggleProvider = (name: string) => {
    setExpandedProviders((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
    if (!expandedProviders[name]) {
      setSelectedProvider(name);
    }
  };

  // Get capability icon
  const getCapabilityIcon = (cap: string) => {
    switch (cap) {
      case "ohlcv":
        return <BarChart3 className="h-3 w-3" />;
      case "fundamentals":
        return <Database className="h-3 w-3" />;
      case "news":
        return <Newspaper className="h-3 w-3" />;
      case "reference":
        return <Cloud className="h-3 w-3" />;
      case "economic_indicators":
        return <Zap className="h-3 w-3" />;
      default:
        return <CheckCircle2 className="h-3 w-3" />;
    }
  };

  // Get tier badge color
  const getTierColor = (tier: string) => {
    return tier === "FREE"
      ? "bg-green-500/10 text-green-500 border-green-500/20"
      : "bg-purple-500/10 text-purple-500 border-purple-500/20";
  };

  // Get priority badge
  const getPriorityBadge = (priority: number) => {
    if (priority === 1) return { label: "Primary", color: "bg-blue-500/10 text-blue-500" };
    if (priority <= 10) return { label: "High", color: "bg-green-500/10 text-green-500" };
    if (priority <= 20) return { label: "Medium", color: "bg-yellow-500/10 text-yellow-500" };
    return { label: "Backup", color: "bg-gray-500/10 text-gray-500" };
  };

  // Format rate limit
  const formatRateLimit = (limit: number | null, unit: string) => {
    if (limit === null) return "Unlimited";
    return `${limit}/${unit}`;
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
        <XCircle className="mx-auto h-10 w-10 text-destructive" />
        <p className="mt-2 text-sm text-destructive">Failed to load API sources</p>
      </div>
    );
  }

  if (!sourcesData) return null;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-foreground">
            {sourcesData.providers.length}
          </div>
          <div className="text-sm text-muted-foreground">Total Providers</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-green-500">
            {sourcesData.providers.filter((p) => p.tier === "FREE").length}
          </div>
          <div className="text-sm text-muted-foreground">FREE Tier</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-blue-500">
            {new Set(sourcesData.providers.flatMap((p) => p.gapCoverage)).size}
          </div>
          <div className="text-sm text-muted-foreground">GAPs Covered</div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="text-2xl font-bold text-foreground">
            {sourcesData.providers.filter((p) => !p.apiKeyRequired).length}
          </div>
          <div className="text-sm text-muted-foreground">No Key Required</div>
        </div>
      </div>

      {/* Provider Cards */}
      <div className="space-y-3">
        {sourcesData.providers.map((provider) => {
          const isExpanded = expandedProviders[provider.name];
          const priorityBadge = getPriorityBadge(provider.priority);
          const detail = selectedProvider === provider.name ? providerDetail : null;

          return (
            <div
              key={provider.name}
              className="rounded-lg border border-border bg-surface overflow-hidden"
            >
              {/* Header */}
              <button
                onClick={() => toggleProvider(provider.name)}
                className="w-full flex items-center justify-between p-4 hover:bg-surface-hover transition-colors text-left"
              >
                <div className="flex items-center gap-4">
                  {/* Expand Icon */}
                  {isExpanded ? (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  )}

                  {/* Provider Name */}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">
                        {provider.displayName}
                      </span>
                      <Badge variant="outline" className={getTierColor(provider.tier)}>
                        {provider.tier}
                      </Badge>
                      <Badge variant="outline" className={priorityBadge.color}>
                        {priorityBadge.label}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {provider.apiKeyRequired ? (
                        <span className="flex items-center gap-1">
                          <Key className="h-3 w-3" /> API Key Required
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-green-500">
                          <CheckCircle2 className="h-3 w-3" /> No API Key Needed
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Side Info */}
                <div className="flex items-center gap-6">
                  {/* Rate Limits */}
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {formatRateLimit(provider.rateLimits.perMinute, "min")}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatRateLimit(provider.rateLimits.perDay, "day")}
                    </div>
                  </div>

                  {/* Capabilities */}
                  <div className="flex gap-1">
                    {provider.capabilities.map((cap) => (
                      <div
                        key={cap}
                        className="flex items-center justify-center w-6 h-6 rounded bg-surface-muted"
                        title={cap}
                      >
                        {getCapabilityIcon(cap)}
                      </div>
                    ))}
                  </div>

                  {/* GAP Coverage */}
                  {provider.gapCoverage.length > 0 && (
                    <div className="flex gap-1 flex-wrap max-w-[200px]">
                      {provider.gapCoverage.slice(0, 3).map((gap) => (
                        <Badge
                          key={gap}
                          variant="outline"
                          className="text-xs bg-accent/10 text-accent border-accent/20"
                        >
                          {gap}
                        </Badge>
                      ))}
                      {provider.gapCoverage.length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{provider.gapCoverage.length - 3}
                        </Badge>
                      )}
                    </div>
                  )}
                </div>
              </button>

              {/* Expanded Content */}
              {isExpanded && (
                <div className="border-t border-border p-4 bg-surface-muted/30">
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : detail ? (
                    <div className="space-y-4">
                      {/* Use Cases */}
                      <div>
                        <h4 className="text-sm font-medium text-foreground mb-2">
                          Best For
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {detail.useCases.map((useCase, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {useCase}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      {/* GAP Coverage Details */}
                      {provider.gapCoverage.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-foreground mb-2">
                            GAP Coverage
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {provider.gapCoverage.map((gap) => (
                              <Badge
                                key={gap}
                                variant="outline"
                                className="bg-accent/10 text-accent border-accent/20"
                              >
                                {gap}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Endpoints */}
                      <div>
                        <h4 className="text-sm font-medium text-foreground mb-2">
                          Endpoints ({Object.keys(detail.endpoints).length})
                        </h4>
                        <div className="grid gap-2">
                          {Object.entries(detail.endpoints).map(([name, endpoint]) => (
                            <div
                              key={name}
                              className="rounded border border-border bg-surface p-3"
                            >
                              <div className="flex items-start justify-between">
                                <div>
                                  <code className="text-sm font-mono text-foreground">
                                    {endpoint.path || endpoint.method || name}
                                  </code>
                                  {endpoint.gapId && (
                                    <Badge
                                      variant="outline"
                                      className="ml-2 text-xs bg-accent/10 text-accent"
                                    >
                                      {endpoint.gapId}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">
                                {endpoint.description}
                              </p>
                              {endpoint.notes && (
                                <p className="text-xs text-muted-foreground mt-1 italic">
                                  {endpoint.notes}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Premium Only */}
                      {detail.premiumOnly.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-muted-foreground mb-2">
                            Premium Only (Not Available)
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {detail.premiumOnly.map((endpoint, i) => (
                              <Badge
                                key={i}
                                variant="outline"
                                className="text-xs text-muted-foreground"
                              >
                                {endpoint}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Implementation File */}
                      {detail.implementationFile && (
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <ExternalLink className="h-3 w-3" />
                          {detail.implementationFile}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      Click to load details...
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Data Routing Section */}
      {sourcesData.dataRouting && Object.keys(sourcesData.dataRouting).length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <h3 className="font-semibold text-foreground mb-3">Data Routing Recommendations</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(sourcesData.dataRouting).map(([dataType, routing]) => (
              <div
                key={dataType}
                className="rounded border border-border bg-surface-muted/30 p-3"
              >
                <div className="font-medium text-sm text-foreground">{dataType}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Primary: <span className="text-foreground">{routing.primary}</span>
                  {routing.fallback1 && (
                    <> → {routing.fallback1}</>
                  )}
                  {routing.fallback2 && (
                    <> → {routing.fallback2}</>
                  )}
                </div>
                {routing.notes && (
                  <div className="text-xs text-muted-foreground mt-1 italic">
                    {routing.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
