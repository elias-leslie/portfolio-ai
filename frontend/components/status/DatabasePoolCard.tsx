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
          <Database className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Database Pool
          </h3>
        </div>
        {showWarning && (
          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {checkedOut} / {poolSize} connections
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

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-gray-500 dark:text-gray-400">Active</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {checkedOut}
          </p>
        </div>
        <div>
          <p className="text-gray-500 dark:text-gray-400">Available</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {poolSize - checkedOut}
          </p>
        </div>
        <div>
          <p className="text-gray-500 dark:text-gray-400">Overflow</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {overflow}
          </p>
        </div>
      </div>

      {/* Usage percentage */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-600 dark:text-gray-400">
          Pool utilization: <span className="font-semibold">{percent.toFixed(1)}%</span>
        </p>
      </div>
    </div>
  );
}
