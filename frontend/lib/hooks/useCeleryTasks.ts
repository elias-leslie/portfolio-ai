/**
 * React Query hook for Celery task monitoring
 *
 * NOTE: This hook uses enabled=false by default to avoid performance issues.
 * Celery inspection is slow (~4s) so we only fetch when explicitly requested.
 * Call refetch() to load data on-demand.
 */

import { useQuery } from "@tanstack/react-query";
import { fetchCeleryTasks, fetchQueueDepth, fetchBeatSchedule } from "../api/celery";
import type { TaskListResponse, QueueInfo, ScheduleInfo } from "../api/celery";

/**
 * Hook to fetch Celery tasks (manual refresh only, no auto-polling)
 *
 * Usage:
 *   const { data, refetch, isLoading } = useCeleryTasks("all");
 *   // Call refetch() when user clicks refresh button
 */
export function useCeleryTasks(
  status: "all" | "active" | "pending" | "completed" | "failed" = "all",
  limit: number = 50
) {
  return useQuery<TaskListResponse, Error>({
    queryKey: ["celery-tasks", status, limit],
    queryFn: () => fetchCeleryTasks(status, limit),
    enabled: false, // Don't auto-fetch - performance issue
    staleTime: 30000, // Data fresh for 30s
    gcTime: 60000, // Keep in cache for 1 min
    retry: 1,
  });
}

/**
 * Hook to fetch queue depth (manual refresh only)
 */
export function useQueueDepth() {
  return useQuery<QueueInfo, Error>({
    queryKey: ["celery-queue"],
    queryFn: fetchQueueDepth,
    enabled: false, // Don't auto-fetch - performance issue
    staleTime: 30000,
    gcTime: 60000,
    retry: 1,
  });
}

/**
 * Hook to fetch beat schedule (manual refresh only)
 */
export function useBeatSchedule() {
  return useQuery<ScheduleInfo[], Error>({
    queryKey: ["celery-schedule"],
    queryFn: fetchBeatSchedule,
    enabled: false, // Don't auto-fetch - performance issue
    staleTime: 60000, // Schedule changes rarely
    gcTime: 120000,
    retry: 1,
  });
}
