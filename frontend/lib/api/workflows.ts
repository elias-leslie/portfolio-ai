/**
 * Workflow Graph API client
 */

import { get } from "./client";

// Type definitions
export interface NodeData {
  label: string;
  schedule: string;
  category: string;
  status: "idle" | "running" | "completed" | "failed" | "pending";
  lastRun: string | null;
  nextRun: string | null;
  successRate: number;
  avgDuration: number; // milliseconds
  populatesTables: string[];
  [key: string]: unknown; // Index signature for reactflow compatibility
}

export interface WorkflowNode {
  id: string;
  type: "task" | "workflow" | "agent";
  data: NodeData;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type: "dependency" | "data-flow";
  animated?: boolean;
}

export interface WorkflowGraphResponse {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  categories: string[];
  lastUpdated: string;
}

/**
 * Fetch workflow graph data for visualization
 * @param category - Comma-separated categories to filter
 * @param includeInactive - Include tasks with 0% success rate
 */
export async function fetchWorkflowGraph(
  category?: string,
  includeInactive?: boolean
): Promise<WorkflowGraphResponse> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (includeInactive) params.set("include_inactive", "true");

  const queryString = params.toString();
  const url = `/api/workflows/graph${queryString ? `?${queryString}` : ""}`;

  return get<WorkflowGraphResponse>(url);
}
