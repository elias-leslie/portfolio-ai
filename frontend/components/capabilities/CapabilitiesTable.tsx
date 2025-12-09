/**
 * CapabilitiesTable component for displaying system capabilities with expandable rows
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Zap,
  Globe,
  ChevronRight,
  ChevronDown,
  Hash,
  FileText,
  Clock,
  Calendar,
  Loader2,
  Network,
  MessageSquare,
  Save,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "./StatusBadge";
// InsightCard removed - insights migrated to [DEBT] subtasks on features
import type {
  Capability,
  DbCapability,
  CeleryCapability,
  ApiCapability,
  NoteType,
} from "@/lib/api/capabilities";
import {
  fetchCapabilityDetail,
  // reviewInsight removed - insights migrated to [DEBT] subtasks on features
  createNote,
} from "@/lib/api/capabilities";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

interface CapabilitiesTableProps {
  capabilities: Capability[];
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
 * Format age for display (compact)
 */
function formatAge(ageHours: number | null): string {
  if (ageHours === null) return "—";
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m`;
  if (ageHours < 24) return `${Math.round(ageHours)}h`;
  if (ageHours < 168) return `${Math.round(ageHours / 24)}d`;
  if (ageHours < 730) return `${Math.round(ageHours / 168)}w`;
  return `${Math.round(ageHours / 730)}mo`;
}

/**
 * Format number for display (compact with K/M suffixes)
 */
function formatNumber(n: number | null): string {
  if (n === null) return "—";
  if (n < 1000) return n.toString();
  if (n < 1000000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1000000).toFixed(1)}M`;
}

/**
 * Format duration in milliseconds (compact)
 */
function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/**
 * Format Celery schedule (compact)
 */
function formatSchedule(capability: CeleryCapability): string {
  if (capability.schedule_type === "manual") return "Manual";
  if (capability.schedule_interval) return capability.schedule_interval;
  if (capability.schedule_crontab) return capability.schedule_crontab;
  return "—";
}

/**
 * Truncate text with ellipsis
 */
function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 1) + "…";
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
          {db.age_hours != null && (
            <span className="text-xs text-muted-foreground">{formatAge(db.age_hours)}</span>
          )}
        </div>
      );
    }
    case "celery": {
      const celery = capability as CeleryCapability;
      const hasRun = celery.last_run_at != null;
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
 * Get row background class based on health status
 */
function getHealthRowClass(health: string): string {
  switch (health) {
    case "orphaned":
      return "bg-loss/5 hover:bg-loss/10 dark:bg-loss/10 dark:hover:bg-loss/20";
    case "legacy":
      return "bg-surface-muted/50 hover:bg-surface-muted opacity-60";
    case "suspect":
      return "bg-accent/5 hover:bg-accent/10 dark:bg-accent/10 dark:hover:bg-accent/20";
    case "active":
    default:
      return "hover:bg-surface-muted";
  }
}

/**
 * Database Overview Component
 */
function DbOverview({ db }: { db: DbCapability }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Table Name</p>
        <p className="text-sm font-medium">{db.table_name}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Freshness Status</p>
        <StatusBadge type="freshness" value={db.freshness_status} />
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Row Count</p>
        <p className="text-sm font-medium">
          <Hash className="inline h-3 w-3" /> {db.row_count?.toLocaleString() || "0"}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Age</p>
        <p className="text-sm font-medium">
          <Clock className="inline h-3 w-3" />{" "}
          {db.age_hours != null ? `${db.age_hours.toFixed(1)} hours` : "—"}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Source</p>
        <p className="text-sm font-medium">{db.source || "—"}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Expected Refresh (hours)</p>
        <p className="text-sm font-medium">{db.expected_refresh_hours}</p>
      </div>
      {db.description && (
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{db.description}</p>
        </div>
      )}
      {db.columns && db.columns.length > 0 && (
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
            Columns ({db.columns.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {db.columns.map((col) => (
              <span
                key={col}
                className="rounded-md bg-surface-muted px-2 py-1 text-xs font-mono text-text"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Celery Overview Component
 */
function CeleryOverview({ celery }: { celery: CeleryCapability }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Task Name</p>
        <p className="text-sm font-medium font-mono">{celery.task_name}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Schedule Type</p>
        <p className="text-sm font-medium">{celery.schedule_type || "—"}</p>
      </div>
      <div className="col-span-2">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Schedule</p>
        <p className="text-sm font-medium">{celery.schedule_interval || "—"}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Run</p>
        <p className="text-sm font-medium">
          <Calendar className="inline h-3 w-3" />{" "}
          {celery.last_run_at
            ? formatDistanceToNow(new Date(celery.last_run_at), { addSuffix: true })
            : "Never"}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Status</p>
        {celery.last_run_status ? (
          <StatusBadge
            type="status"
            value={celery.last_run_status === "SUCCESS" ? "confirmed" : "dismissed"}
          />
        ) : (
          <p className="text-sm font-medium">—</p>
        )}
      </div>
      {celery.description && (
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{celery.description}</p>
        </div>
      )}
    </div>
  );
}

/**
 * API Overview Component
 */
function ApiOverview({ api }: { api: ApiCapability }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="col-span-2">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Endpoint Path</p>
        <p className="text-sm font-medium font-mono">{api.endpoint_path}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">HTTP Method</p>
        <StatusBadge type="category" value={api.http_method} />
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Response Format</p>
        <p className="text-sm font-medium">{api.response_format || "JSON"}</p>
      </div>
      {api.description && (
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{api.description}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Dependencies Section Component
 */
function DependenciesSection({
  dependencies,
}: {
  dependencies: {
    populates_tables?: string[];
    depends_on_tasks?: string[];
    depends_on_tables?: string[];
  };
}) {
  const hasAnyDependencies =
    (dependencies.populates_tables?.length || 0) > 0 ||
    (dependencies.depends_on_tasks?.length || 0) > 0 ||
    (dependencies.depends_on_tables?.length || 0) > 0;

  if (!hasAnyDependencies) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <Network className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
        <p className="mt-4 text-sm text-muted-foreground">No dependencies tracked</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {dependencies.populates_tables && dependencies.populates_tables.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Populates Tables</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.populates_tables.map((table) => (
              <span
                key={table}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Database className="mr-1 inline h-3 w-3" />
                {table}
              </span>
            ))}
          </div>
        </div>
      )}

      {dependencies.depends_on_tasks && dependencies.depends_on_tasks.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Depends On Tasks</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.depends_on_tasks.map((task) => (
              <span
                key={task}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Zap className="mr-1 inline h-3 w-3" />
                {task}
              </span>
            ))}
          </div>
        </div>
      )}

      {dependencies.depends_on_tables && dependencies.depends_on_tables.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Depends On Tables</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.depends_on_tables.map((table) => (
              <span
                key={table}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Database className="mr-1 inline h-3 w-3" />
                {table}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Database Table Row Component (Type-specific dense layout)
 */
function DbTableRow({
  capability,
  isExpanded,
  onClick,
}: {
  capability: DbCapability;
  isExpanded: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className={`grid grid-cols-[auto_200px_120px_100px_100px_80px_80px_70px_70px_120px_60px] gap-3 px-4 py-3 transition-colors duration-150 cursor-pointer ${getHealthRowClass(capability.health_status)}`}
      onClick={onClick}
    >
      {/* Icon + Expand */}
      <div className="flex items-center gap-2">
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <div className="rounded-md bg-surface-muted p-2">
          <Database className="h-4 w-4" />
        </div>
      </div>

      {/* Name */}
      <div className="flex flex-col justify-center">
        <p className="text-sm font-medium text-text truncate" title={capability.table_name}>
          {truncate(capability.table_name, 25)}
        </p>
      </div>

      {/* Category */}
      <div className="flex items-center">
        <StatusBadge type="category" value={capability.category || "unknown"} />
      </div>

      {/* Row Count */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={capability.row_count?.toLocaleString() || "0"}>
          #{formatNumber(capability.row_count)}
        </span>
      </div>

      {/* Health */}
      <div className="flex items-center">
        <StatusBadge type="health" value={capability.health_status} />
      </div>

      {/* Freshness */}
      <div className="flex items-center">
        <StatusBadge type="freshness" value={capability.freshness_status} />
      </div>

      {/* Age */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={`${capability.age_hours?.toFixed(1)} hours`}>
          {formatAge(capability.age_hours)}
        </span>
      </div>

      {/* Insights */}
      <div className="flex items-center justify-center">
        {capability.insights_count > 0 ? (
          <span className="text-xs font-medium text-accent">#{capability.insights_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Notes */}
      <div className="flex items-center justify-center">
        {capability.notes_count > 0 ? (
          <span className="text-xs font-medium text-muted-foreground">#{capability.notes_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Updated */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={capability.last_updated || "Unknown"}>
          {capability.last_updated
            ? formatDistanceToNow(new Date(capability.last_updated), { addSuffix: true })
            : "—"}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-center">
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
          •••
        </Button>
      </div>
    </div>
  );
}

/**
 * Celery Task Row Component (Type-specific dense layout)
 */
function CeleryTaskRow({
  capability,
  isExpanded,
  onClick,
}: {
  capability: CeleryCapability;
  isExpanded: boolean;
  onClick: () => void;
}) {
  const successRate = capability.success_rate_pct;
  const successRateColor =
    successRate != null && successRate >= 95
      ? "text-gain"
      : successRate != null && successRate >= 80
      ? "text-accent"
      : "text-loss";

  return (
    <div
      className={`grid grid-cols-[auto_200px_120px_140px_120px_100px_100px_80px_70px_70px_60px] gap-3 px-4 py-3 transition-colors duration-150 cursor-pointer ${getHealthRowClass(capability.health_status)}`}
      onClick={onClick}
    >
      {/* Icon + Expand */}
      <div className="flex items-center gap-2">
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <div className="rounded-md bg-surface-muted p-2">
          <Zap className="h-4 w-4" />
        </div>
      </div>

      {/* Name */}
      <div className="flex flex-col justify-center">
        <p className="text-sm font-medium text-text truncate" title={capability.task_name}>
          {truncate(capability.task_name, 25)}
        </p>
      </div>

      {/* Category */}
      <div className="flex items-center">
        <StatusBadge type="category" value={capability.category || "unknown"} />
      </div>

      {/* Schedule */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={formatSchedule(capability)}>
          {truncate(formatSchedule(capability), 18)}
        </span>
      </div>

      {/* Last Run */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={capability.last_run_at || "Never"}>
          {capability.last_run_at
            ? formatDistanceToNow(new Date(capability.last_run_at), { addSuffix: true })
            : "Never"}
        </span>
      </div>

      {/* Success Rate */}
      <div className="flex items-center">
        <span className={`text-xs font-medium ${successRateColor}`}>
          {successRate != null ? `${successRate.toFixed(0)}%` : "—"}
        </span>
      </div>

      {/* Health */}
      <div className="flex items-center">
        <StatusBadge type="health" value={capability.health_status} />
      </div>

      {/* Duration */}
      <div className="flex items-center">
        <span
          className="text-xs text-muted-foreground"
          title={`Avg: ${formatDuration(capability.avg_duration_ms)}, Max: ${formatDuration(capability.max_duration_ms)}`}
        >
          {formatDuration(capability.avg_duration_ms)}
        </span>
      </div>

      {/* Insights */}
      <div className="flex items-center justify-center">
        {capability.insights_count > 0 ? (
          <span className="text-xs font-medium text-accent">#{capability.insights_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Notes */}
      <div className="flex items-center justify-center">
        {capability.notes_count > 0 ? (
          <span className="text-xs font-medium text-muted-foreground">#{capability.notes_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-center">
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
          •••
        </Button>
      </div>
    </div>
  );
}

/**
 * API Endpoint Row Component (Type-specific dense layout)
 */
function ApiEndpointRow({
  capability,
  isExpanded,
  onClick,
}: {
  capability: ApiCapability;
  isExpanded: boolean;
  onClick: () => void;
}) {
  const methodColors: Record<string, string> = {
    GET: "bg-blue-500/10 text-blue-500",
    POST: "bg-green-500/10 text-green-500",
    PUT: "bg-yellow-500/10 text-yellow-500",
    PATCH: "bg-yellow-500/10 text-yellow-500",
    DELETE: "bg-red-500/10 text-red-500",
  };

  const methodColor = methodColors[capability.http_method] || "bg-surface-muted text-muted-foreground";

  return (
    <div
      className={`grid grid-cols-[auto_250px_80px_120px_80px_100px_70px_70px_200px_60px] gap-3 px-4 py-3 transition-colors duration-150 cursor-pointer ${getHealthRowClass(capability.health_status)}`}
      onClick={onClick}
    >
      {/* Icon + Expand */}
      <div className="flex items-center gap-2">
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <div className="rounded-md bg-surface-muted p-2">
          <Globe className="h-4 w-4" />
        </div>
      </div>

      {/* Path */}
      <div className="flex flex-col justify-center">
        <p className="text-sm font-medium text-text truncate font-mono" title={capability.endpoint_path}>
          {truncate(capability.endpoint_path, 35)}
        </p>
      </div>

      {/* Method */}
      <div className="flex items-center">
        <span className={`text-xs font-medium px-2 py-1 rounded ${methodColor}`}>
          {capability.http_method}
        </span>
      </div>

      {/* Category */}
      <div className="flex items-center">
        <StatusBadge type="category" value={capability.category || "unknown"} />
      </div>

      {/* Dependencies */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground" title={capability.depends_on_tables.join(", ")}>
          {capability.depends_on_tables.length > 0
            ? `${capability.depends_on_tables.length} tbl`
            : "—"}
        </span>
      </div>

      {/* Health */}
      <div className="flex items-center">
        <StatusBadge type="health" value={capability.health_status} />
      </div>

      {/* Insights */}
      <div className="flex items-center justify-center">
        {capability.insights_count > 0 ? (
          <span className="text-xs font-medium text-accent">#{capability.insights_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Notes */}
      <div className="flex items-center justify-center">
        {capability.notes_count > 0 ? (
          <span className="text-xs font-medium text-muted-foreground">#{capability.notes_count}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* File */}
      <div className="flex items-center">
        <span className="text-xs text-muted-foreground font-mono truncate" title={capability.route_file || "—"}>
          {capability.route_file ? truncate(capability.route_file.split("/").pop() || "—", 25) : "—"}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-center">
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
          •••
        </Button>
      </div>
    </div>
  );
}

/**
 * CapabilitiesTable component
 */
export function CapabilitiesTable({ capabilities }: CapabilitiesTableProps) {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [noteType, setNoteType] = useState<NoteType>("observation");
  const [noteText, setNoteText] = useState("");
  const [showNoteForm, setShowNoteForm] = useState(false);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
    if (expandedId !== id) {
      setShowNoteForm(false);
      setNoteText("");
      setNoteType("observation");
    }
  };

  // Get capability detail when expanded
  const expandedCapability = capabilities.find(
    (c) => `${c.capability_type}-${c.id}` === expandedId
  );

  const { data: detailData, isLoading: detailLoading } = useQuery({
    queryKey: ["capability-detail", expandedCapability?.capability_type, expandedCapability?.id],
    queryFn: () => {
      if (!expandedCapability) throw new Error("No capability selected");
      return fetchCapabilityDetail(expandedCapability.capability_type, expandedCapability.id);
    },
    enabled: !!expandedCapability,
  });

  // Review insight mutation removed - insights migrated to [DEBT] subtasks on features

  // Create note mutation
  const createNoteMutation = useMutation({
    mutationFn: async () => {
      if (!noteText.trim() || !expandedCapability) throw new Error("Missing data");
      return createNote({
        capability_type: expandedCapability.capability_type,
        capability_id: expandedCapability.id,
        note_type: noteType,
        note: noteText,
      });
    },
    onSuccess: () => {
      toast.success("Note added successfully");
      setNoteText("");
      setNoteType("observation");
      setShowNoteForm(false);
      queryClient.invalidateQueries({
        queryKey: ["capability-detail", expandedCapability?.capability_type, expandedCapability?.id],
      });
    },
    onError: (error: Error) => {
      toast.error(`Failed to add note: ${error.message}`);
    },
  });

  if (capabilities.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <FileText className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
        <p className="mt-4 text-sm text-muted-foreground">No capabilities found</p>
      </div>
    );
  }

  // Group capabilities by type for rendering type-specific headers
  const dbCapabilities = capabilities.filter((c) => c.capability_type === "db") as DbCapability[];
  const celeryCapabilities = capabilities.filter(
    (c) => c.capability_type === "celery"
  ) as CeleryCapability[];
  const apiCapabilities = capabilities.filter((c) => c.capability_type === "api") as ApiCapability[];

  return (
    <div className="space-y-6">
      {/* Database Tables */}
      {dbCapabilities.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          {/* Header */}
          <div className="grid grid-cols-[auto_200px_120px_100px_100px_80px_80px_70px_70px_120px_60px] gap-3 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground">
            <div></div>
            <div>Name</div>
            <div>Category</div>
            <div>Rows</div>
            <div>Health</div>
            <div>Freshness</div>
            <div>Age</div>
            <div className="text-center">Insights</div>
            <div className="text-center">Notes</div>
            <div>Updated</div>
            <div></div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-border">
            {dbCapabilities.map((capability) => {
              const capabilityId = `${capability.capability_type}-${capability.id}`;
              const isExpanded = expandedId === capabilityId;

              return (
                <div key={capabilityId}>
                  <DbTableRow
                    capability={capability}
                    isExpanded={isExpanded}
                    onClick={() => toggleExpand(capabilityId)}
                  />

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="p-6 bg-surface-muted border-t border-border" onClick={(e) => e.stopPropagation()}>
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Overview Section */}
                      <div>
                        <h4 className="text-sm font-semibold text-text mb-3">Overview</h4>
                        <div className="rounded-lg border border-border bg-surface p-4">
                          <DbOverview db={capability} />
                        </div>
                      </div>

                      {/* Dependencies Section */}
                      {detailData?.dependencies && (
                        <div>
                          <h4 className="text-sm font-semibold text-text mb-3">Dependencies</h4>
                          <DependenciesSection dependencies={detailData.dependencies} />
                        </div>
                      )}

                      {/* Insights Section removed - migrated to [DEBT] subtasks on features */}

                      {/* Notes Section */}
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-semibold text-text">
                            Notes ({detailData?.notes.length || 0})
                          </h4>
                          {!showNoteForm && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowNoteForm(true)}
                            >
                              <MessageSquare className="mr-2 h-4 w-4" />
                              Add Note
                            </Button>
                          )}
                        </div>

                        {/* Add Note Form */}
                        {showNoteForm && (
                          <div className="rounded-lg border border-border bg-surface p-4 space-y-3 mb-3">
                            <Label htmlFor="note-type">Add a note</Label>
                            <Select value={noteType} onValueChange={(val) => setNoteType(val as NoteType)}>
                              <SelectTrigger id="note-type">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="observation">Observation</SelectItem>
                                <SelectItem value="recommendation">Recommendation</SelectItem>
                                <SelectItem value="question">Question</SelectItem>
                                <SelectItem value="decision">Decision</SelectItem>
                                <SelectItem value="reference">Reference</SelectItem>
                              </SelectContent>
                            </Select>
                            <Textarea
                              placeholder="Enter your note..."
                              value={noteText}
                              onChange={(e) => setNoteText(e.target.value)}
                              className="min-h-[100px]"
                            />
                            <div className="flex gap-2">
                              <Button
                                onClick={() => createNoteMutation.mutate()}
                                disabled={createNoteMutation.isPending || !noteText.trim()}
                                size="sm"
                              >
                                {createNoteMutation.isPending ? (
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                  <Save className="mr-2 h-4 w-4" />
                                )}
                                Save Note
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  setShowNoteForm(false);
                                  setNoteText("");
                                  setNoteType("observation");
                                }}
                              >
                                <X className="mr-2 h-4 w-4" />
                                Cancel
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* Notes List */}
                        {detailData?.notes && detailData.notes.length > 0 ? (
                          <div className="space-y-3">
                            {detailData.notes.map((note) => (
                              <div key={note.id} className="rounded-lg border border-border bg-surface p-4">
                                <div className="mb-2 flex items-center justify-between">
                                  <StatusBadge type="category" value={note.note_type} />
                                  <span className="text-xs text-muted-foreground">
                                    {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })} by{" "}
                                    {note.created_by}
                                  </span>
                                </div>
                                <p className="text-sm text-text">{note.note}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded-lg border border-border bg-surface p-4 text-center">
                            <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground opacity-50" />
                            <p className="mt-2 text-xs text-muted-foreground">No notes yet</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Celery Tasks */}
      {celeryCapabilities.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          {/* Header */}
          <div className="grid grid-cols-[auto_200px_120px_140px_120px_100px_100px_80px_70px_70px_60px] gap-3 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground">
            <div></div>
            <div>Name</div>
            <div>Category</div>
            <div>Schedule</div>
            <div>Last Run</div>
            <div>Success %</div>
            <div>Health</div>
            <div>Duration</div>
            <div className="text-center">Insights</div>
            <div className="text-center">Notes</div>
            <div></div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-border">
            {celeryCapabilities.map((capability) => {
              const capabilityId = `${capability.capability_type}-${capability.id}`;
              const isExpanded = expandedId === capabilityId;

              return (
                <div key={capabilityId}>
                  <CeleryTaskRow
                    capability={capability}
                    isExpanded={isExpanded}
                    onClick={() => toggleExpand(capabilityId)}
                  />

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="p-6 bg-surface-muted border-t border-border" onClick={(e) => e.stopPropagation()}>
                      {detailLoading ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <div className="space-y-6">
                          {/* Overview Section */}
                          <div>
                            <h4 className="text-sm font-semibold text-text mb-3">Overview</h4>
                            <div className="rounded-lg border border-border bg-surface p-4">
                              <CeleryOverview celery={capability} />
                            </div>
                          </div>

                          {/* Dependencies Section */}
                          {detailData?.dependencies && (
                            <div>
                              <h4 className="text-sm font-semibold text-text mb-3">Dependencies</h4>
                              <DependenciesSection dependencies={detailData.dependencies} />
                            </div>
                          )}

                          {/* Insights Section removed - migrated to [DEBT] subtasks on features */}

                          {/* Notes Section */}
                          <div>
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="text-sm font-semibold text-text">
                                Notes ({detailData?.notes.length || 0})
                              </h4>
                              {!showNoteForm && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setShowNoteForm(true)}
                                >
                                  <MessageSquare className="mr-2 h-4 w-4" />
                                  Add Note
                                </Button>
                              )}
                            </div>

                            {/* Add Note Form */}
                            {showNoteForm && (
                              <div className="rounded-lg border border-border bg-surface p-4 space-y-3 mb-3">
                                <Label htmlFor="note-type">Add a note</Label>
                                <Select value={noteType} onValueChange={(val) => setNoteType(val as NoteType)}>
                                  <SelectTrigger id="note-type">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="observation">Observation</SelectItem>
                                    <SelectItem value="recommendation">Recommendation</SelectItem>
                                    <SelectItem value="question">Question</SelectItem>
                                    <SelectItem value="decision">Decision</SelectItem>
                                    <SelectItem value="reference">Reference</SelectItem>
                                  </SelectContent>
                                </Select>
                                <Textarea
                                  placeholder="Enter your note..."
                                  value={noteText}
                                  onChange={(e) => setNoteText(e.target.value)}
                                  className="min-h-[100px]"
                                />
                                <div className="flex gap-2">
                                  <Button
                                    onClick={() => createNoteMutation.mutate()}
                                    disabled={createNoteMutation.isPending || !noteText.trim()}
                                    size="sm"
                                  >
                                    {createNoteMutation.isPending ? (
                                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    ) : (
                                      <Save className="mr-2 h-4 w-4" />
                                    )}
                                    Save Note
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      setShowNoteForm(false);
                                      setNoteText("");
                                      setNoteType("observation");
                                    }}
                                  >
                                    <X className="mr-2 h-4 w-4" />
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            )}

                            {/* Notes List */}
                            {detailData?.notes && detailData.notes.length > 0 ? (
                              <div className="space-y-3">
                                {detailData.notes.map((note) => (
                                  <div key={note.id} className="rounded-lg border border-border bg-surface p-4">
                                    <div className="mb-2 flex items-center justify-between">
                                      <StatusBadge type="category" value={note.note_type} />
                                      <span className="text-xs text-muted-foreground">
                                        {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })} by{" "}
                                        {note.created_by}
                                      </span>
                                    </div>
                                    <p className="text-sm text-text">{note.note}</p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="rounded-lg border border-border bg-surface p-4 text-center">
                                <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground opacity-50" />
                                <p className="mt-2 text-xs text-muted-foreground">No notes yet</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* API Endpoints */}
      {apiCapabilities.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          {/* Header */}
          <div className="grid grid-cols-[auto_250px_80px_120px_80px_100px_70px_70px_200px_60px] gap-3 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground">
            <div></div>
            <div>Path</div>
            <div>Method</div>
            <div>Category</div>
            <div>Deps</div>
            <div>Health</div>
            <div className="text-center">Insights</div>
            <div className="text-center">Notes</div>
            <div>File</div>
            <div></div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-border">
            {apiCapabilities.map((capability) => {
              const capabilityId = `${capability.capability_type}-${capability.id}`;
              const isExpanded = expandedId === capabilityId;

              return (
                <div key={capabilityId}>
                  <ApiEndpointRow
                    capability={capability}
                    isExpanded={isExpanded}
                    onClick={() => toggleExpand(capabilityId)}
                  />

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="p-6 bg-surface-muted border-t border-border" onClick={(e) => e.stopPropagation()}>
                      {detailLoading ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <div className="space-y-6">
                          {/* Overview Section */}
                          <div>
                            <h4 className="text-sm font-semibold text-text mb-3">Overview</h4>
                            <div className="rounded-lg border border-border bg-surface p-4">
                              <ApiOverview api={capability} />
                            </div>
                          </div>

                          {/* Dependencies Section */}
                          {detailData?.dependencies && (
                            <div>
                              <h4 className="text-sm font-semibold text-text mb-3">Dependencies</h4>
                              <DependenciesSection dependencies={detailData.dependencies} />
                            </div>
                          )}

                          {/* Insights Section removed - migrated to [DEBT] subtasks on features */}

                          {/* Notes Section */}
                          <div>
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="text-sm font-semibold text-text">
                                Notes ({detailData?.notes.length || 0})
                              </h4>
                              {!showNoteForm && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setShowNoteForm(true)}
                                >
                                  <MessageSquare className="mr-2 h-4 w-4" />
                                  Add Note
                                </Button>
                              )}
                            </div>

                            {/* Add Note Form */}
                            {showNoteForm && (
                              <div className="rounded-lg border border-border bg-surface p-4 space-y-3 mb-3">
                                <Label htmlFor="note-type">Add a note</Label>
                                <Select value={noteType} onValueChange={(val) => setNoteType(val as NoteType)}>
                                  <SelectTrigger id="note-type">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="observation">Observation</SelectItem>
                                    <SelectItem value="recommendation">Recommendation</SelectItem>
                                    <SelectItem value="question">Question</SelectItem>
                                    <SelectItem value="decision">Decision</SelectItem>
                                    <SelectItem value="reference">Reference</SelectItem>
                                  </SelectContent>
                                </Select>
                                <Textarea
                                  placeholder="Enter your note..."
                                  value={noteText}
                                  onChange={(e) => setNoteText(e.target.value)}
                                  className="min-h-[100px]"
                                />
                                <div className="flex gap-2">
                                  <Button
                                    onClick={() => createNoteMutation.mutate()}
                                    disabled={createNoteMutation.isPending || !noteText.trim()}
                                    size="sm"
                                  >
                                    {createNoteMutation.isPending ? (
                                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    ) : (
                                      <Save className="mr-2 h-4 w-4" />
                                    )}
                                    Save Note
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      setShowNoteForm(false);
                                      setNoteText("");
                                      setNoteType("observation");
                                    }}
                                  >
                                    <X className="mr-2 h-4 w-4" />
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            )}

                            {/* Notes List */}
                            {detailData?.notes && detailData.notes.length > 0 ? (
                              <div className="space-y-3">
                                {detailData.notes.map((note) => (
                                  <div key={note.id} className="rounded-lg border border-border bg-surface p-4">
                                    <div className="mb-2 flex items-center justify-between">
                                      <StatusBadge type="category" value={note.note_type} />
                                      <span className="text-xs text-muted-foreground">
                                        {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })} by{" "}
                                        {note.created_by}
                                      </span>
                                    </div>
                                    <p className="text-sm text-text">{note.note}</p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="rounded-lg border border-border bg-surface p-4 text-center">
                                <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground opacity-50" />
                                <p className="mt-2 text-xs text-muted-foreground">No notes yet</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
