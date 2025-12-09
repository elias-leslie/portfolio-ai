/**
 * Solution Map - Interactive visualization of system architecture and health
 * Shows hierarchical view: Vision Goals → Features → Tasks/Tables/APIs → Sources
 */

"use client";

import { useSolutionMap } from "@/lib/hooks/useSolutionMap";
import { LayerSummary, Blocker } from "@/lib/api/solutionMap";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Target,
  CheckSquare,
  Zap,
  Database,
  Globe,
  Cloud,
  AlertTriangle,
  AlertCircle,
  ChevronDown,
  Loader2,
  ArrowDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Tab value type matching the parent capabilities page
type TabValue = "dashboard" | "database" | "celery" | "api" | "sources" | "rules" | "features" | "vision";

interface SolutionMapProps {
  onTabChange?: (tab: TabValue) => void;
}

/**
 * Get color class based on health percentage
 */
function getHealthColor(healthy: number, total: number): string {
  if (total === 0) return "text-muted-foreground";
  const pct = (healthy / total) * 100;
  if (pct >= 80) return "text-gain";
  if (pct >= 50) return "text-accent";
  return "text-loss";
}

/**
 * Get progress bar color based on percentage
 */
function getProgressColor(pct: number): string {
  if (pct >= 80) return "bg-gain";
  if (pct >= 50) return "bg-accent";
  return "bg-loss";
}

/**
 * Layer Card - clickable card representing a layer in the architecture
 */
interface LayerCardProps {
  layer: LayerSummary;
  icon: React.ReactNode;
  onClick?: () => void;
  className?: string;
  showProgress?: boolean;
}

function LayerCard({ layer, icon, onClick, className, showProgress = false }: LayerCardProps) {
  const healthPct = layer.count > 0 ? Math.round((layer.healthy / layer.count) * 100) : 0;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Card
            className={cn(
              "cursor-pointer transition-all hover:border-accent hover:shadow-md",
              className
            )}
            onClick={onClick}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {icon}
                  <CardTitle className="text-sm font-medium">{layer.name}</CardTitle>
                </div>
                <span className="text-lg font-bold">{layer.count}</span>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-gain" />
                  {layer.healthy}
                </span>
                {layer.warning > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-accent" />
                    {layer.warning}
                  </span>
                )}
                {layer.critical > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-loss" />
                    {layer.critical}
                  </span>
                )}
              </div>
              {showProgress && (
                <div className="mt-2">
                  <Progress
                    value={healthPct}
                    className="h-1.5"
                  />
                  <span className={cn("text-xs mt-1", getHealthColor(layer.healthy, layer.count))}>
                    {healthPct}% healthy
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-medium">{layer.name}</p>
            <p className="text-xs text-muted-foreground">
              {layer.healthy} healthy, {layer.warning} warnings, {layer.critical} critical
            </p>
            <p className="text-xs text-muted-foreground">Click to view details</p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * Blocker Item - displays a single blocker or warning
 */
interface BlockerItemProps {
  blocker: Blocker;
  onClick?: () => void;
}

function BlockerItem({ blocker, onClick }: BlockerItemProps) {
  const isCritical = blocker.severity === "critical";

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md p-2 text-sm cursor-pointer transition-colors",
        isCritical
          ? "bg-loss/10 hover:bg-loss/20"
          : "bg-accent/10 hover:bg-accent/20"
      )}
      onClick={onClick}
    >
      {isCritical ? (
        <AlertCircle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
      ) : (
        <AlertTriangle className="h-4 w-4 text-accent shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <span className="font-medium">{blocker.item_name}</span>
        <span className="text-muted-foreground"> ({blocker.layer})</span>
        <p className="text-xs text-muted-foreground truncate">{blocker.issue}</p>
      </div>
    </div>
  );
}

/**
 * Connection Arrow - visual connection between layers
 */
function ConnectionArrow() {
  return (
    <div className="flex justify-center py-1">
      <ArrowDown className="h-4 w-4 text-muted-foreground" />
    </div>
  );
}

/**
 * Main Solution Map Component
 */
export function SolutionMap({ onTabChange }: SolutionMapProps) {
  const { data, isLoading, error } = useSolutionMap();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-loss mb-4" />
        <p className="text-sm font-medium">Failed to load Solution Map</p>
        <p className="text-xs text-muted-foreground mt-1">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  const handleLayerClick = (tab: TabValue) => {
    if (onTabChange) {
      onTabChange(tab);
    }
  };

  // Calculate overall health color
  const overallHealthColor = data.overall_health >= 80
    ? "text-gain"
    : data.overall_health >= 50
      ? "text-accent"
      : "text-loss";

  return (
    <div className="space-y-6">
      {/* Header with Overall Health */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Solution Architecture Map</h2>
          <p className="text-sm text-muted-foreground">
            How all system components interconnect
          </p>
        </div>
        <div className="text-right">
          <div className={cn("text-2xl font-bold", overallHealthColor)}>
            {Math.round(data.overall_health)}%
          </div>
          <div className="text-xs text-muted-foreground">Overall Health</div>
        </div>
      </div>

      {/* Layer Hierarchy */}
      <div className="space-y-2">
        {/* Vision Goals Layer */}
        <LayerCard
          layer={data.vision_goals}
          icon={<Target className="h-5 w-5 text-purple-500" />}
          onClick={() => handleLayerClick("vision")}
          showProgress
        />

        <ConnectionArrow />

        {/* Features Layer */}
        <LayerCard
          layer={data.features}
          icon={<CheckSquare className="h-5 w-5 text-blue-500" />}
          onClick={() => handleLayerClick("features")}
          showProgress
        />

        <ConnectionArrow />

        {/* Infrastructure Layer - Tasks, Tables, APIs side by side */}
        <div className="grid gap-4 md:grid-cols-3">
          <LayerCard
            layer={data.tasks}
            icon={<Zap className="h-5 w-5 text-yellow-500" />}
            onClick={() => handleLayerClick("celery")}
          />
          <LayerCard
            layer={data.tables}
            icon={<Database className="h-5 w-5 text-green-500" />}
            onClick={() => handleLayerClick("database")}
          />
          <LayerCard
            layer={data.endpoints}
            icon={<Globe className="h-5 w-5 text-cyan-500" />}
            onClick={() => handleLayerClick("api")}
          />
        </div>

        <ConnectionArrow />

        {/* Data Sources Layer */}
        <LayerCard
          layer={data.sources}
          icon={<Cloud className="h-5 w-5 text-orange-500" />}
          onClick={() => handleLayerClick("sources")}
        />
      </div>

      {/* Blockers & Warnings Section */}
      {(data.blockers.length > 0 || data.warnings.length > 0) && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-accent" />
              <CardTitle className="text-sm">Issues to Address</CardTitle>
              <span className="text-xs text-muted-foreground">
                ({data.blockers.length} critical, {data.warnings.length} warnings)
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 max-h-64 overflow-y-auto">
            {/* Critical blockers first */}
            {data.blockers.slice(0, 5).map((blocker, idx) => (
              <BlockerItem
                key={`blocker-${idx}`}
                blocker={blocker}
                onClick={() => {
                  // Navigate to appropriate tab based on layer
                  const tabMap: Record<string, TabValue> = {
                    tasks: "celery",
                    features: "features",
                    tables: "database",
                    endpoints: "api",
                    vision_goals: "vision",
                    sources: "sources",
                  };
                  const tab = tabMap[blocker.layer] || "dashboard";
                  handleLayerClick(tab);
                }}
              />
            ))}
            {/* Then warnings */}
            {data.warnings.slice(0, 5).map((warning, idx) => (
              <BlockerItem
                key={`warning-${idx}`}
                blocker={warning}
                onClick={() => {
                  const tabMap: Record<string, TabValue> = {
                    tasks: "celery",
                    features: "features",
                    tables: "database",
                    endpoints: "api",
                    vision_goals: "vision",
                    sources: "sources",
                  };
                  const tab = tabMap[warning.layer] || "dashboard";
                  handleLayerClick(tab);
                }}
              />
            ))}
            {/* Show more indicator if there are more issues */}
            {(data.blockers.length > 5 || data.warnings.length > 5) && (
              <p className="text-xs text-muted-foreground text-center pt-2">
                +{Math.max(0, data.blockers.length - 5) + Math.max(0, data.warnings.length - 5)} more issues
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* No Issues State */}
      {data.blockers.length === 0 && data.warnings.length === 0 && (
        <Card>
          <CardContent className="py-6 text-center">
            <CheckSquare className="h-12 w-12 text-gain mx-auto mb-2 opacity-50" />
            <p className="text-sm font-medium">All Systems Healthy</p>
            <p className="text-xs text-muted-foreground">No critical issues or warnings detected</p>
          </CardContent>
        </Card>
      )}

      {/* Last Updated */}
      <p className="text-xs text-muted-foreground text-right">
        Last updated: {new Date(data.last_updated).toLocaleString()}
      </p>
    </div>
  );
}
