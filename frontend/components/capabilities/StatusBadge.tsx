/**
 * StatusBadge component for displaying severity and freshness status
 */

import { Badge } from "@/components/ui/badge";
import type { InsightSeverity } from "@/lib/api/capabilities";

interface StatusBadgeProps {
  type: "severity" | "freshness" | "status" | "category" | "health";
  value: string | null | undefined;
  className?: string;
}

/**
 * Get badge variant and icon for severity levels
 */
function getSeverityStyle(severity: InsightSeverity) {
  switch (severity) {
    case "critical":
      return {
        variant: "destructive" as const,
        icon: "🔴",
        className: "bg-loss/10 text-loss border-loss/20",
      };
    case "high":
      return {
        variant: "default" as const,
        icon: "⚠️",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    case "medium":
      return {
        variant: "default" as const,
        icon: "📊",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    case "low":
      return {
        variant: "secondary" as const,
        icon: "ℹ️",
        className: "bg-muted text-muted-foreground",
      };
    default:
      return {
        variant: "secondary" as const,
        icon: "",
        className: "",
      };
  }
}

/**
 * Get badge variant and icon for freshness status
 */
function getFreshnessStyle(status: string | null | undefined) {
  if (!status) {
    return {
      variant: "secondary" as const,
      icon: "❓",
      className: "bg-muted text-muted-foreground",
    };
  }

  switch (status) {
    case "fresh":
      return {
        variant: "default" as const,
        icon: "✅",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "stale":
      return {
        variant: "default" as const,
        icon: "⚠️",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    case "critical":
      return {
        variant: "destructive" as const,
        icon: "🔴",
        className: "bg-loss/10 text-loss border-loss/20",
      };
    case "unknown":
      return {
        variant: "secondary" as const,
        icon: "❓",
        className: "bg-muted text-muted-foreground",
      };
    default:
      return {
        variant: "secondary" as const,
        icon: "",
        className: "",
      };
  }
}

/**
 * Get badge variant for insight/note status
 */
function getStatusStyle(status: string | null | undefined) {
  if (!status) {
    return {
      variant: "secondary" as const,
      icon: "❓",
      className: "bg-muted text-muted-foreground",
    };
  }

  switch (status) {
    case "confirmed":
      return {
        variant: "default" as const,
        icon: "✓",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "fixed":
      return {
        variant: "default" as const,
        icon: "✅",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "in_progress":
      return {
        variant: "default" as const,
        icon: "🔄",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    case "dismissed":
      return {
        variant: "secondary" as const,
        icon: "✕",
        className: "bg-muted text-muted-foreground",
      };
    case "pending":
      return {
        variant: "default" as const,
        icon: "⏳",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    default:
      return {
        variant: "secondary" as const,
        icon: "",
        className: "",
      };
  }
}

/**
 * Get badge variant for category
 */
function getCategoryStyle(category: string | null | undefined) {
  if (!category) {
    return {
      variant: "secondary" as const,
      icon: "📦",
      className: "",
    };
  }

  switch (category.toLowerCase()) {
    case "market_data":
      return {
        variant: "default" as const,
        icon: "📈",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    case "portfolio":
      return {
        variant: "default" as const,
        icon: "💼",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "news":
      return {
        variant: "default" as const,
        icon: "📰",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "system":
      return {
        variant: "default" as const,
        icon: "⚙️",
        className: "bg-muted text-muted-foreground",
      };
    case "trading":
      return {
        variant: "default" as const,
        icon: "💹",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    default:
      return {
        variant: "secondary" as const,
        icon: "📦",
        className: "",
      };
  }
}

/**
 * Get badge variant for health status
 */
function getHealthStyle(health: string | null | undefined) {
  if (!health) {
    return {
      variant: "secondary" as const,
      icon: "❓",
      className: "bg-muted text-muted-foreground",
    };
  }

  switch (health.toLowerCase()) {
    case "active":
      return {
        variant: "default" as const,
        icon: "✅",
        className: "bg-gain/10 text-gain border-gain/20",
      };
    case "orphaned":
      return {
        variant: "destructive" as const,
        icon: "🔴",
        className: "bg-loss/10 text-loss border-loss/20",
      };
    case "legacy":
      return {
        variant: "secondary" as const,
        icon: "📦",
        className: "bg-muted text-muted-foreground opacity-70",
      };
    case "suspect":
      return {
        variant: "default" as const,
        icon: "⚠️",
        className: "bg-accent/10 text-accent border-accent/20",
      };
    default:
      return {
        variant: "secondary" as const,
        icon: "❓",
        className: "bg-muted text-muted-foreground",
      };
  }
}

/**
 * StatusBadge component
 */
export function StatusBadge({ type, value, className = "" }: StatusBadgeProps) {
  // Handle null/undefined value
  if (!value) {
    return (
      <Badge variant="secondary" className={`bg-muted text-muted-foreground ${className}`.trim()}>
        <span className="mr-1">❓</span>
        Unknown
      </Badge>
    );
  }

  let style;
  let displayValue = value;

  switch (type) {
    case "severity":
      style = getSeverityStyle(value as InsightSeverity);
      displayValue = value.toUpperCase();
      break;
    case "freshness":
      style = getFreshnessStyle(value);
      displayValue = value.charAt(0).toUpperCase() + value.slice(1);
      break;
    case "status":
      style = getStatusStyle(value);
      displayValue = value
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
      break;
    case "category":
      style = getCategoryStyle(value);
      displayValue = value
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
      break;
    case "health":
      style = getHealthStyle(value);
      displayValue = value.charAt(0).toUpperCase() + value.slice(1);
      break;
    default:
      style = { variant: "secondary" as const, icon: "", className: "" };
  }

  return (
    <Badge variant={style.variant} className={`${style.className} ${className}`.trim()}>
      {style.icon && <span className="mr-1">{style.icon}</span>}
      {displayValue}
    </Badge>
  );
}
