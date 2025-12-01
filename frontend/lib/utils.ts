import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a timestamp as relative time ("2m ago", "1h ago") or absolute time for older dates
 * @param timestamp ISO 8601 timestamp string
 * @returns Formatted time string
 */
/**
 * Format a date string consistently across the app (MM/DD/YYYY style)
 * @param dateStr ISO 8601 date string or date-only string (YYYY-MM-DD)
 * @param includeYear Whether to include the year (default: true)
 * @returns Formatted date string like "Nov 18, 2025" or "Nov 18"
 */
export function formatDate(dateStr: string | undefined | null, includeYear: boolean = true): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(includeYear && { year: "numeric" }),
  });
}

/**
 * Format a datetime string with time component
 * @param dateStr ISO 8601 timestamp string
 * @returns Formatted string like "Nov 18, 10:30 AM"
 */
export function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now.getTime() - then.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  // Format as absolute time for > 24h
  return then.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}
