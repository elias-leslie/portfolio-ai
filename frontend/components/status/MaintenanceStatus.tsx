"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Database,
  HardDrive,
  Clock,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  PlayCircle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { toast } from "sonner";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import { ServiceActionDialog } from "@/components/status/ServiceActionDialog";
import { getMaintenanceLastRun, type MaintenanceResult, type LastRunSummary } from "@/lib/api/maintenance";
import { formatRelativeTime } from "@/lib/utils";

interface ScheduledTask {
  name: string;
  description: string;
  nextRun: string;
  lastRun: string | null;
  schedule: string;
}

interface DiskSpaceInfo {
  path: string;
  usedGb: number;
  totalGb: number;
  percentUsed: number;
  status: "ok" | "warning" | "critical";
}

interface DatabaseSize {
  databaseName: string;
  sizeMb: number;
  tables: TableInfo[];
}

interface TableInfo {
  name: string;
  sizeMb: number;
  rows: number;
}

interface ScheduleResponse {
  tasks: ScheduledTask[];
}

interface DiskSpaceResponse {
  disks: DiskSpaceInfo[];
}

interface DatabaseSizeResponse {
  database: DatabaseSize;
}

const API_BASE_URL = ""; // Use relative URLs for Next.js proxy

// Helper to format dates
const formatDateTime = (dateStr: string | null) => {
  if (!dateStr) return "Never";
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return "Invalid date";
  }
};

// Status badge component
function StatusBadge({ status, isRunning }: { status: string; isRunning?: boolean }) {
  if (isRunning) {
    return (
      <Badge className="flex items-center gap-1 bg-status-info text-text-inverted animate-pulse">
        <RefreshCw className="h-3 w-3 animate-spin" />
        Running
      </Badge>
    );
  }

  switch (status) {
    case "success":
      return (
        <Badge className="flex items-center gap-1 bg-status-success text-text-inverted">
          <CheckCircle2 className="h-3 w-3" />
          Success
        </Badge>
      );
    case "error":
      return (
        <Badge className="flex items-center gap-1 bg-status-error text-text-inverted">
          <AlertCircle className="h-3 w-3" />
          Error
        </Badge>
      );
    default:
      return <Badge variant="secondary">Unknown</Badge>;
  }
}

// Disk space card
function DiskSpaceCard({ disks, isLoading }: { disks: DiskSpaceInfo[] | null; isLoading: boolean }) {
  if (isLoading && !disks) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Disk Space Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!disks || disks.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Disk Space Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No disk information available</p>
        </CardContent>
      </Card>
    );
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "critical":
        return "Critical";
      case "warning":
        return "Warning";
      default:
        return "OK";
    }
  };

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HardDrive className="h-5 w-5" />
          Disk Space Usage
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {disks.map((disk) => (
            <div key={disk.path} className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{disk.path}</p>
                  <p className="text-xs text-muted-foreground">
                    {disk.usedGb.toFixed(1)} GB / {disk.totalGb.toFixed(1)} GB
                  </p>
                </div>
                <Badge variant={disk.status === "ok" ? "default" : "destructive"}>
                  {getStatusText(disk.status)}
                </Badge>
              </div>
              <div className="space-y-1">
                <Progress value={disk.percentUsed} className="h-2" />
                <div className="text-right text-xs text-muted-foreground">
                  {disk.percentUsed.toFixed(1)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// Database size card
function DatabaseSizeCard({ database, isLoading }: { database: DatabaseSize | null; isLoading: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading && !database) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Size
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!database) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Size
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No database information available</p>
        </CardContent>
      </Card>
    );
  }

  const topTables = [...database.tables]
    .sort((a, b) => b.sizeMb - a.sizeMb)
    .slice(0, 5);

  const totalTableSize = database.tables.reduce((sum, t) => sum + t.sizeMb, 0);

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            <span>Database Size</span>
          </div>
          <Badge variant="outline">{database.sizeMb.toFixed(1)} MB</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Database</p>
              <p className="text-lg font-semibold">{database.databaseName}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Total Size</p>
              <p className="text-lg font-semibold">{database.sizeMb.toFixed(1)} MB</p>
            </div>
          </div>

          <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="w-full justify-between">
                <span>Top Tables ({topTables.length})</span>
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-3">
                {topTables.map((table) => (
                  <div key={table.name} className="border rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-sm font-medium">{table.name}</p>
                      <Badge variant="secondary">{table.sizeMb.toFixed(1)} MB</Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{table.rows.toLocaleString()} rows</span>
                      <span>{((table.sizeMb / totalTableSize) * 100).toFixed(1)}% of total</span>
                    </div>
                    <Progress value={(table.sizeMb / totalTableSize) * 100} className="h-1.5" />
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      </CardContent>
    </Card>
  );
}

// Scheduled tasks card
function ScheduledTasksCard({ tasks, isLoading }: { tasks: ScheduledTask[] | null; isLoading: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading && !tasks) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Scheduled Tasks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!tasks || tasks.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Scheduled Tasks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No scheduled tasks available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          <span>Scheduled Tasks</span>
          <Badge variant="secondary" className="ml-auto">
            {tasks.length} tasks
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between">
              <span>View all scheduled tasks</span>
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-4 space-y-3">
              {tasks.map((task) => (
                <div key={task.name} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm">{task.name}</p>
                      <p className="text-xs text-muted-foreground">{task.description}</p>
                    </div>
                    <Badge variant="outline" className="font-mono text-xs">
                      {task.schedule}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <p className="text-muted-foreground">Last run</p>
                      <p className="font-mono">{formatRelativeTime(task.lastRun)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Next run</p>
                      <p className="font-mono">{formatDateTime(task.nextRun)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}

// Task trigger section
interface TaskTriggerSectionProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  lastRun: MaintenanceResult | null;
  onTrigger: () => void;
  isLoading: boolean;
}

function TaskTriggerSection({
  title,
  description,
  icon,
  lastRun,
  onTrigger,
  isLoading,
}: TaskTriggerSectionProps) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3 flex-1">
          {icon}
          <div>
            <h3 className="font-semibold text-sm">{title}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
        <Button size="sm" onClick={onTrigger} disabled={isLoading} variant="outline">
          {isLoading ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
          <span className="ml-1 hidden sm:inline">Trigger</span>
        </Button>
      </div>

      {lastRun ? (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Last run</span>
            <StatusBadge status={lastRun.status} />
          </div>
          <div className="text-xs text-muted-foreground">
            {formatDateTime(lastRun.startedAt)}
          </div>
          {lastRun.dryRun && (
            <Badge variant="outline" className="text-xs">
              Dry Run
            </Badge>
          )}
          {lastRun.status === "error" && lastRun.errorMessage && (
            <div className="text-xs text-loss bg-loss/10 p-2 rounded">
              {lastRun.errorMessage}
            </div>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t">
          <span className="text-xs text-muted-foreground">Never run</span>
        </div>
      )}
    </div>
  );
}

/**
 * MaintenanceStatus Component
 *
 * Displays:
 * - Last run times for each maintenance task
 * - Next scheduled run times
 * - Current disk space usage with progress bars
 * - Current database size and top tables
 * - Manual trigger buttons for each task
 * - Confirmation dialogs before triggering tasks
 */
export function MaintenanceStatus() {
  // State for maintenance tasks
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(null);
  const [isFetching, setIsFetching] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);

  // State for disk space and database info
  const [diskSpace, setDiskSpace] = useState<DiskSpaceInfo[] | null>(null);
  const [diskLoading, setDiskLoading] = useState(false);

  const [database, setDatabase] = useState<DatabaseSize | null>(null);
  const [databaseLoading, setDatabaseLoading] = useState(false);

  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[] | null>(null);
  const [tasksLoading, setTasksLoading] = useState(false);

  // Dialog state
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
  } | null>(null);

  const fetchAllData = useCallback(async () => {
    await Promise.all([
      fetchLastRunData(),
      fetchDiskSpace(),
      fetchDatabaseSize(),
      fetchScheduledTasks(),
    ]);
  }, []);

  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAllData, 30000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  const fetchLastRunData = async () => {
    setIsFetching(true);
    try {
      const data = await getMaintenanceLastRun();
      setLastRunSummary(data);
    } catch (error) {
      console.error("Failed to fetch maintenance data:", error);
    } finally {
      setIsFetching(false);
    }
  };

  const fetchDiskSpace = async () => {
    setDiskLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/disk-space`);
      if (!response.ok) throw new Error("Failed to fetch disk space");
      const data: DiskSpaceResponse = await response.json();
      setDiskSpace(data.disks);
    } catch (error) {
      console.error("Failed to fetch disk space:", error);
    } finally {
      setDiskLoading(false);
    }
  };

  const fetchDatabaseSize = async () => {
    setDatabaseLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/database-size`);
      if (!response.ok) throw new Error("Failed to fetch database size");
      const data: DatabaseSizeResponse = await response.json();
      setDatabase(data.database);
    } catch (error) {
      console.error("Failed to fetch database size:", error);
    } finally {
      setDatabaseLoading(false);
    }
  };

  const fetchScheduledTasks = async () => {
    setTasksLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/schedule`);
      if (!response.ok) throw new Error("Failed to fetch scheduled tasks");
      const data: ScheduleResponse = await response.json();
      setScheduledTasks(data.tasks);
    } catch (error) {
      console.error("Failed to fetch scheduled tasks:", error);
    } finally {
      setTasksLoading(false);
    }
  };

  // Check if user has disabled confirmation dialogs
  const shouldShowDialog = (storageKey: string) => {
    if (typeof window === "undefined") return true;
    return !localStorage.getItem(storageKey);
  };

  // Generic trigger handler
  const triggerTask = (taskName: string, taskLabel: string, handler: () => Promise<void>) => {
    const storageKey = `status.confirm.maintenance.${taskName}`;
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: `Trigger ${taskLabel}`,
        description: `This will manually trigger the ${taskLabel} maintenance task. The task will run in the background.`,
        actionLabel: "Trigger Now",
        onConfirm: handler,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handler();
    }
  };

  // Task handlers
  const handleTriggerTask = async (taskName: string) => {
    setIsTriggering(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/maintenance/trigger/${taskName}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Failed to trigger ${taskName}`);
      }

      await response.json(); // Consume response body
      toast.success(`${taskName} triggered successfully`);
      await fetchLastRunData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to trigger task";
      toast.error(message);
    } finally {
      setIsTriggering(false);
    }
  };

  return (
    <>
      <ExpandableCard
        title="Maintenance Overview"
        description="Scheduled tasks, disk usage, and database size monitoring."
        defaultCollapsed={false}
      >
        <div className="space-y-4">
          {/* Disk Space and Database Size in grid */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <DiskSpaceCard disks={diskSpace} isLoading={diskLoading} />
            <DatabaseSizeCard database={database} isLoading={databaseLoading} />
          </div>

          {/* Scheduled Tasks */}
          <ScheduledTasksCard tasks={scheduledTasks} isLoading={tasksLoading} />

          {/* Refresh button */}
          <div className="flex justify-center pt-2">
            <Button variant="outline" size="sm" onClick={fetchAllData} disabled={isFetching}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </ExpandableCard>

      {/* Task triggers */}
      <ExpandableCard
        title="Manual Task Triggers"
        description="Manually trigger maintenance tasks on demand."
        defaultCollapsed={true}
      >
        <div className="space-y-3">
          <TaskTriggerSection
            title="Cleanup Old News"
            description="Remove news articles older than 90 days"
            icon={<AlertCircle className="h-5 w-5 text-status-warning flex-shrink-0" />}
            lastRun={lastRunSummary?.tasks?.cleanupOldNewsTask || lastRunSummary?.tasks?.cleanupNews || null}
            onTrigger={() =>
              triggerTask("cleanup_news", "Cleanup News", () =>
                handleTriggerTask("cleanup_news")
              )
            }
            isLoading={isTriggering}
          />

          <TaskTriggerSection
            title="Vacuum Database"
            description="Optimize tables and reclaim disk space"
            icon={<Database className="h-5 w-5 text-status-info flex-shrink-0" />}
            lastRun={lastRunSummary?.tasks?.vacuumDatabaseTask || lastRunSummary?.tasks?.vacuumDatabase || null}
            onTrigger={() =>
              triggerTask("vacuum_database", "Vacuum Database", () =>
                handleTriggerTask("vacuum_database")
              )
            }
            isLoading={isTriggering}
          />

          <TaskTriggerSection
            title="Validate Data Integrity"
            description="Check for orphaned records and consistency issues"
            icon={<CheckCircle2 className="h-5 w-5 text-status-success flex-shrink-0" />}
            lastRun={lastRunSummary?.tasks?.validateIntegrityTask || lastRunSummary?.tasks?.validateIntegrity || null}
            onTrigger={() =>
              triggerTask("validate_integrity", "Validate Integrity", () =>
                handleTriggerTask("validate_integrity")
              )
            }
            isLoading={isTriggering}
          />
        </div>
      </ExpandableCard>

      {/* Service Action Dialog */}
      {actionDialogConfig && (
        <ServiceActionDialog
          open={actionDialogOpen}
          onOpenChange={setActionDialogOpen}
          title={actionDialogConfig.title}
          description={actionDialogConfig.description}
          actionLabel={actionDialogConfig.actionLabel}
          onConfirm={actionDialogConfig.onConfirm}
          storageKey={actionDialogConfig.storageKey}
        />
      )}
    </>
  );
}
