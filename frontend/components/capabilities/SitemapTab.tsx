/**
 * Sitemap Tab - Dynamic endpoint monitoring
 *
 * Features:
 * - Tree view (hierarchical by port -> path)
 * - Table view (flat, filterable, sortable)
 * - Health indicators (green/yellow/red)
 * - Summary cards (Total, Healthy, Warnings, Errors, Unknown)
 * - View toggle: Tree / Table
 * - Filters: Port, Health status
 * - Evidence capture integration
 */

"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  RefreshCw,
  TreePine,
  Table2,
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Compass,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchSitemapEntries,
  fetchHealthSummary,
  triggerDiscovery,
  type SitemapEntry,
  type HealthStatus,
} from "@/lib/api/sitemap";
import { SitemapTreeView } from "./SitemapTreeView";
import { SitemapTableView } from "./SitemapTableView";

type ViewMode = "tree" | "table";

export function SitemapTab() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("tree");
  const [portFilter, setPortFilter] = useState<string>("all");
  const [healthFilter, setHealthFilter] = useState<string>("all");

  // Queries
  const { data: entriesData, isLoading: entriesLoading } = useQuery({
    queryKey: ["sitemap", "entries", portFilter, healthFilter],
    queryFn: () =>
      fetchSitemapEntries({
        port: portFilter !== "all" ? parseInt(portFilter) : undefined,
        health_status: healthFilter !== "all" ? (healthFilter as HealthStatus) : undefined,
        limit: 500,
      }),
    refetchInterval: 60000, // Refresh every 60 seconds
  });

  const { data: healthSummary } = useQuery({
    queryKey: ["sitemap", "health-summary"],
    queryFn: fetchHealthSummary,
    refetchInterval: 60000,
  });

  // Mutations
  const discoverMutation = useMutation({
    mutationFn: triggerDiscovery,
    onSuccess: (result) => {
      toast.success(
        `Discovery complete: ${result.backend_discovered} backend, ${result.frontend_discovered} frontend`
      );
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["sitemap"] }), 2000);
    },
    onError: () => toast.error("Failed to start discovery"),
  });

  // Health indicator component
  const HealthIcon = ({ status, size = "default" }: { status: string; size?: "default" | "sm" }) => {
    const sizeClass = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
    switch (status) {
      case "healthy":
        return <CheckCircle2 className={`${sizeClass} text-gain`} />;
      case "warning":
        return <AlertTriangle className={`${sizeClass} text-warning`} />;
      case "error":
        return <AlertCircle className={`${sizeClass} text-loss`} />;
      default:
        return <HelpCircle className={`${sizeClass} text-neutral`} />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Total</div>
          <div className="text-xl font-semibold">{healthSummary?.total || 0}</div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3 text-gain" />
            <span className="text-xs text-text-secondary">Healthy</span>
          </div>
          <div className="text-xl font-semibold text-gain">{healthSummary?.healthy || 0}</div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-warning" />
            <span className="text-xs text-text-secondary">Warnings</span>
          </div>
          <div className="text-xl font-semibold text-warning">{healthSummary?.warning || 0}</div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="flex items-center gap-1">
            <AlertCircle className="h-3 w-3 text-loss" />
            <span className="text-xs text-text-secondary">Errors</span>
          </div>
          <div className="text-xl font-semibold text-loss">{healthSummary?.error || 0}</div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="flex items-center gap-1">
            <HelpCircle className="h-3 w-3 text-neutral" />
            <span className="text-xs text-text-secondary">Unknown</span>
          </div>
          <div className="text-xl font-semibold text-neutral">{healthSummary?.unknown || 0}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* View toggle */}
        <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
          <TabsList className="h-8">
            <TabsTrigger value="tree" className="h-6 px-2 text-xs">
              <TreePine className="h-3.5 w-3.5 mr-1" />
              Tree
            </TabsTrigger>
            <TabsTrigger value="table" className="h-6 px-2 text-xs">
              <Table2 className="h-3.5 w-3.5 mr-1" />
              Table
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Port filter */}
        <Select value={portFilter} onValueChange={setPortFilter}>
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue placeholder="Port" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Ports</SelectItem>
            <SelectItem value="3000">:3000 (Frontend)</SelectItem>
            <SelectItem value="8000">:8000 (Backend)</SelectItem>
          </SelectContent>
        </Select>

        {/* Health filter */}
        <Select value={healthFilter} onValueChange={setHealthFilter}>
          <SelectTrigger className="w-32 h-8 text-xs">
            <SelectValue placeholder="Health" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="healthy">
              <span className="flex items-center gap-1">
                <HealthIcon status="healthy" size="sm" />
                Healthy
              </span>
            </SelectItem>
            <SelectItem value="warning">
              <span className="flex items-center gap-1">
                <HealthIcon status="warning" size="sm" />
                Warning
              </span>
            </SelectItem>
            <SelectItem value="error">
              <span className="flex items-center gap-1">
                <HealthIcon status="error" size="sm" />
                Error
              </span>
            </SelectItem>
            <SelectItem value="unknown">
              <span className="flex items-center gap-1">
                <HealthIcon status="unknown" size="sm" />
                Unknown
              </span>
            </SelectItem>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {/* Discovery button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => discoverMutation.mutate()}
          disabled={discoverMutation.isPending}
          className="h-8"
        >
          {discoverMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <Compass className="h-3.5 w-3.5 mr-1" />
          )}
          Discover
        </Button>
      </div>

      {/* Content */}
      {entriesLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-text-secondary" />
        </div>
      ) : !entriesData?.entries.length ? (
        <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
          <Compass className="h-12 w-12 mb-4 opacity-50" />
          <p className="text-sm">No sitemap entries found</p>
          <p className="text-xs mt-1">Click &quot;Discover&quot; to scan for endpoints</p>
        </div>
      ) : viewMode === "tree" ? (
        <SitemapTreeView entries={entriesData.entries} />
      ) : (
        <SitemapTableView entries={entriesData.entries} />
      )}
    </div>
  );
}
