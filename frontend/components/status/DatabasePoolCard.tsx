/**
 * Database connection pool visualization card
 */

import { AlertTriangle, Database } from "lucide-react";

interface DatabasePoolCardProps {
  poolSize: number;
  checkedOut: number;
  overflow: number;
  percent: number;
  status: "ok" | "warning" | "critical";
}

export function DatabasePoolCard({
  poolSize,
  checkedOut,
  overflow,
  percent,
  status,
}: DatabasePoolCardProps) {
  // Determine progress bar color based on status
  const getStatusColor = () => {
    switch (status) {
      case "critical":
        return "bg-loss";
      case "warning":
        return "bg-warning";
      case "ok":
        return "bg-gain";
      default:
        return "bg-surface-muted";
    }
  };

  // Determine badge color
  const getBadgeColor = () => {
    switch (status) {
      case "critical":
        return "bg-loss/10 text-loss";
      case "warning":
        return "bg-warning/10 text-warning";
      case "ok":
        return "bg-gain/10 text-gain";
      default:
        return "bg-surface text-text";
    }
  };

  // Show warning icon for warning/critical status
  const showWarning = status !== "ok";

  return (
    <div className="bg-surface rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-text-muted" />
          <h3 className="text-lg font-semibold text-text">
            Database Pool
          </h3>
        </div>
        {showWarning && (
          <AlertTriangle className="h-5 w-5 text-warning" />
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-text-muted">
            {checkedOut} / {poolSize} connections
          </span>
          <span
            className={`text-xs px-2 py-1 rounded-full font-medium uppercase ${getBadgeColor()}`}
          >
            {status}
          </span>
        </div>
        <div className="w-full bg-surface-muted rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-300 ${getStatusColor()}`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          ></div>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-text-muted">Active</p>
          <p className="font-semibold text-text">
            {checkedOut}
          </p>
        </div>
        <div>
          <p className="text-text-muted">Available</p>
          <p className="font-semibold text-text">
            {poolSize - checkedOut}
          </p>
        </div>
        <div>
          <p className="text-text-muted">Overflow</p>
          <p className="font-semibold text-text">
            {overflow}
          </p>
        </div>
      </div>

      {/* Usage percentage */}
      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-text-muted">
          Pool utilization: <span className="font-semibold">{percent.toFixed(1)}%</span>
        </p>
      </div>
    </div>
  );
}
