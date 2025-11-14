/**
 * CapabilitiesTable component for displaying system capabilities
 */

import {
  Database,
  Zap,
  Globe,
  ChevronRight,
  Hash,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./StatusBadge";
import type {
  Capability,
  DbCapability,
  CeleryCapability,
  ApiCapability,
} from "@/lib/api/capabilities";
import { formatDistanceToNow } from "date-fns";

interface CapabilitiesTableProps {
  capabilities: Capability[];
  onRowClick: (capability: Capability) => void;
}

/**
 * Get icon for capability type
 */
function getCapabilityIcon(type: string) {
  switch (type) {
    case "db":
      return <Database className="h-4 w-4" />;
    case "celery":
      return <Zap className="h-4 w-4" />;
    case "api":
      return <Globe className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
}

/**
 * Format age for display
 */
function formatAge(ageHours: number | null): string {
  if (ageHours === null) return "—";
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m`;
  if (ageHours < 24) return `${Math.round(ageHours)}h`;
  return `${Math.round(ageHours / 24)}d`;
}

/**
 * Get capability name based on type
 */
function getCapabilityName(capability: Capability): string {
  switch (capability.capability_type) {
    case "db":
      return (capability as DbCapability).table_name;
    case "celery":
      return (capability as CeleryCapability).task_name;
    case "api":
      return (capability as ApiCapability).endpoint_path;
    default:
      return "Unknown";
  }
}

/**
 * Get capability source/schedule info
 */
function getCapabilitySource(capability: Capability): string {
  switch (capability.capability_type) {
    case "db":
      return (capability as DbCapability).source || "—";
    case "celery": {
      const celery = capability as CeleryCapability;
      if (celery.schedule_type === "cron") {
        return `Scheduled (${celery.schedule_interval || "—"})`;
      } else if (celery.schedule_type === "interval") {
        return `Every ${celery.schedule_interval || "—"}`;
      } else if (celery.schedule_type === "manual") {
        return "Manual";
      }
      return "—";
    }
    case "api":
      return (capability as ApiCapability).http_method;
    default:
      return "—";
  }
}

/**
 * Get capability status/coverage info
 */
function getCapabilityStatus(capability: Capability): React.ReactNode {
  switch (capability.capability_type) {
    case "db": {
      const db = capability as DbCapability;
      return (
        <div className="flex items-center gap-2">
          <StatusBadge type="freshness" value={db.freshness_status} />
          {db.age_hours !== null && (
            <span className="text-xs text-muted-foreground">{formatAge(db.age_hours)}</span>
          )}
        </div>
      );
    }
    case "celery": {
      const celery = capability as CeleryCapability;
      const hasRun = celery.last_run_at !== null;
      return (
        <div className="flex items-center gap-2">
          {hasRun ? (
            <>
              <span className="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(celery.last_run_at!), { addSuffix: true })}
              </span>
              {celery.last_run_status && (
                <StatusBadge
                  type="status"
                  value={celery.last_run_status === "SUCCESS" ? "confirmed" : "dismissed"}
                />
              )}
            </>
          ) : (
            <span className="text-xs text-muted-foreground">Never run</span>
          )}
        </div>
      );
    }
    case "api": {
      const api = capability as ApiCapability;
      return (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {api.depends_on_tables.length} dependencies
          </span>
        </div>
      );
    }
    default:
      return "—";
  }
}

/**
 * CapabilitiesTable component
 */
export function CapabilitiesTable({ capabilities, onRowClick }: CapabilitiesTableProps) {
  if (capabilities.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <FileText className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
        <p className="mt-4 text-sm text-muted-foreground">No capabilities found</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      {/* Table Header */}
      <div className="grid grid-cols-12 gap-4 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground">
        <div className="col-span-1">Type</div>
        <div className="col-span-3">Name</div>
        <div className="col-span-2">Category</div>
        <div className="col-span-2">Source/Schedule</div>
        <div className="col-span-2">Status</div>
        <div className="col-span-1 text-center">Insights</div>
        <div className="col-span-1 text-right">Actions</div>
      </div>

      {/* Table Body */}
      <div className="divide-y divide-border">
        {capabilities.map((capability) => (
          <div
            key={`${capability.capability_type}-${capability.id}`}
            className="grid grid-cols-12 gap-4 px-4 py-3 hover:bg-surface-muted transition-colors cursor-pointer"
            onClick={() => onRowClick(capability)}
          >
            {/* Type Icon */}
            <div className="col-span-1 flex items-center">
              <div className="flex items-center justify-center rounded-md bg-surface-muted p-2">
                {getCapabilityIcon(capability.capability_type)}
              </div>
            </div>

            {/* Name */}
            <div className="col-span-3 flex flex-col justify-center">
              <p className="text-sm font-medium text-text">
                {getCapabilityName(capability)}
              </p>
              {capability.capability_type === "db" && (
                <p className="text-xs text-muted-foreground">
                  <Hash className="inline h-3 w-3" />{" "}
                  {(capability as DbCapability).row_count?.toLocaleString() || "0"} rows
                </p>
              )}
            </div>

            {/* Category */}
            <div className="col-span-2 flex items-center">
              <StatusBadge type="category" value={capability.category || "unknown"} />
            </div>

            {/* Source/Schedule */}
            <div className="col-span-2 flex items-center">
              <span className="text-xs text-muted-foreground">
                {getCapabilitySource(capability)}
              </span>
            </div>

            {/* Status */}
            <div className="col-span-2 flex items-center">{getCapabilityStatus(capability)}</div>

            {/* Insights Count */}
            <div className="col-span-1 flex items-center justify-center">
              {capability.insights_count > 0 ? (
                <span className="inline-flex items-center justify-center rounded-full bg-accent/10 px-2 py-1 text-xs font-medium text-accent">
                  {capability.insights_count}
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </div>

            {/* Actions */}
            <div className="col-span-1 flex items-center justify-end">
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
