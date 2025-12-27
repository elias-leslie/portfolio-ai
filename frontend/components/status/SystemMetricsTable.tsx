"use client";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  HardDrive,
  MemoryStick,
  Cpu,
  Database,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import type { SystemResources } from "@/lib/api/resources";

interface SystemMetricsTableProps {
  resources: SystemResources;
}

export function SystemMetricsTable({ resources }: SystemMetricsTableProps) {
  const getStatusIcon = (status: "ok" | "warning" | "critical") => {
    switch (status) {
      case "ok":
        return <CheckCircle2 className="h-3.5 w-3.5 text-status-success" />;
      case "warning":
        return <AlertTriangle className="h-3.5 w-3.5 text-status-warning" />;
      case "critical":
        return <XCircle className="h-3.5 w-3.5 text-status-error" />;
    }
  };

  const getStatusBadge = (status: "ok" | "warning" | "critical") => {
    const variants: Record<string, "default" | "secondary" | "destructive"> = {
      ok: "default",
      warning: "secondary",
      critical: "destructive",
    };
    const colors: Record<string, string> = {
      ok: "bg-status-success",
      warning: "bg-status-warning",
      critical: "bg-status-error",
    };
    return (
      <Badge
        variant={variants[status] || "secondary"}
        className={`text-xs ${colors[status] || ""}`}
      >
        {status}
      </Badge>
    );
  };

  const formatPercent = (value: number) => `${value.toFixed(1)}%`;

  // Progress bar component
  const ProgressBar = ({
    percent,
    status,
  }: {
    percent: number;
    status: "ok" | "warning" | "critical";
  }) => {
    const colors: Record<string, string> = {
      ok: "bg-status-success",
      warning: "bg-status-warning",
      critical: "bg-status-error",
    };
    return (
      <div className="w-20 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${colors[status]} transition-all`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    );
  };

  const metrics = [
    {
      id: "disk",
      name: "Disk",
      icon: <HardDrive className="h-4 w-4 text-status-info" />,
      percent: resources.disk?.percentUsed ?? 0,
      status: resources.disk?.status ?? "ok",
      usage: `${(resources.disk?.usedGb ?? 0).toFixed(1)} GB`,
      total: `${(resources.disk?.totalGb ?? 0).toFixed(1)} GB`,
    },
    {
      id: "memory",
      name: "Memory",
      icon: <MemoryStick className="h-4 w-4 text-accent" />,
      percent: resources.memory?.percentUsed ?? 0,
      status: resources.memory?.status ?? "ok",
      usage: `${(resources.memory?.usedGb ?? 0).toFixed(1)} GB`,
      total: `${(resources.memory?.totalGb ?? 0).toFixed(1)} GB`,
    },
    {
      id: "cpu",
      name: "CPU",
      icon: <Cpu className="h-4 w-4 text-status-warning" />,
      percent: resources.cpu?.percentUsed ?? 0,
      status: resources.cpu?.status ?? "ok",
      usage: `${resources.cpu?.cores ?? 0} cores`,
      total: null,
    },
    {
      id: "db_pool",
      name: "DB Pool",
      icon: <Database className="h-4 w-4 text-status-info" />,
      percent: resources.databasePool?.percentUsed ?? 0,
      status: resources.databasePool?.status ?? "ok",
      usage: `${resources.databasePool?.checkedOut ?? 0} active`,
      total: `${resources.databasePool?.poolSize ?? 0} pool`,
      overflow: resources.databasePool?.overflow ?? 0,
    },
  ];

  // Count statuses for summary
  const okCount = metrics.filter((m) => m.status === "ok").length;
  const warningCount = metrics.filter((m) => m.status === "warning").length;
  const criticalCount = metrics.filter((m) => m.status === "critical").length;

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-muted-foreground">Resources:</span>
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-status-success" />
          {okCount} ok
        </span>
        {warningCount > 0 && (
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-status-warning" />
            {warningCount} warning
          </span>
        )}
        {criticalCount > 0 && (
          <span className="flex items-center gap-1.5">
            <XCircle className="h-3.5 w-3.5 text-status-error" />
            {criticalCount} critical
          </span>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[140px]">Resource</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Usage</TableHead>
            <TableHead className="text-right">Percent</TableHead>
            <TableHead>Details</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {metrics.map((metric) => (
            <TableRow key={metric.id}>
              <TableCell>
                <div className="flex items-center gap-2">
                  {metric.icon}
                  <span className="font-medium">{metric.name}</span>
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {getStatusIcon(metric.status)}
                  {getStatusBadge(metric.status)}
                </div>
              </TableCell>
              <TableCell>
                <ProgressBar percent={metric.percent} status={metric.status} />
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {formatPercent(metric.percent)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {metric.usage}
                {metric.total && ` / ${metric.total}`}
                {metric.overflow !== undefined && metric.overflow > 0 && (
                  <span className="text-status-warning ml-1">
                    (+{metric.overflow} overflow)
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
