/**
 * React Query hook for workflow graph data
 */

import { useQuery } from "@tanstack/react-query";

import { fetchWorkflowGraph, WorkflowGraphResponse } from "../api/workflows";

export function useWorkflowGraph(category?: string, includeInactive = false) {
  return useQuery<WorkflowGraphResponse>({
    queryKey: ["workflow-graph", category, includeInactive],
    queryFn: () => fetchWorkflowGraph(category, includeInactive),
    staleTime: 30_000, // 30s - matches polling interval
    gcTime: 60_000,
    retry: 1,
  });
}
