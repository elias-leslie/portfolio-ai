/**
 * Resource usage card component (disk, memory, CPU)
 */

import { AlertTriangle } from "lucide-react";

interface ResourceCardProps {
  title: string;
  percent: number;
  status: "ok" | "warning" | "critical";
  details: string;
  icon?: React.ReactNode;
}

export function ResourceCard({
  title,
  percent,
  status,
  details,
  icon,
}: ResourceCardProps) {
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
          {icon && <div className="text-text-muted">{icon}</div>}
          <h3 className="text-lg font-semibold text-text">
            {title}
          </h3>
        </div>
        {showWarning && (
          <AlertTriangle className="h-5 w-5 text-warning" />
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-text-muted">
            {percent.toFixed(1)}%
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

      {/* Details */}
      <p className="text-sm text-text-muted">{details}</p>
    </div>
  );
}
