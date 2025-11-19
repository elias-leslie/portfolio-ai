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
        return "bg-red-500";
      case "warning":
        return "bg-yellow-500";
      case "ok":
        return "bg-green-500";
      default:
        return "bg-gray-500";
    }
  };

  // Determine badge color
  const getBadgeColor = () => {
    switch (status) {
      case "critical":
        return "bg-red-100 text-red-800";
      case "warning":
        return "bg-yellow-100 text-yellow-800";
      case "ok":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  // Show warning icon for warning/critical status
  const showWarning = status !== "ok";

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon && <div className="text-gray-600 dark:text-gray-400">{icon}</div>}
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        </div>
        {showWarning && (
          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {percent.toFixed(1)}%
          </span>
          <span
            className={`text-xs px-2 py-1 rounded-full font-medium uppercase ${getBadgeColor()}`}
          >
            {status}
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-300 ${getStatusColor()}`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          ></div>
        </div>
      </div>

      {/* Details */}
      <p className="text-sm text-gray-600 dark:text-gray-400">{details}</p>
    </div>
  );
}
