/**
 * Solution Map API client
 * Fetches aggregated system health data for the Solution Map visualization
 */

import { get } from "./client";

export interface LayerSummary {
  name: string;
  count: number;
  healthy: number;
  warning: number;
  critical: number;
  items?: LayerItem[];
}

export interface LayerItem {
  id: string;
  name: string;
  status: "healthy" | "warning" | "critical";
  detail?: string;
}

export interface Blocker {
  layer: string;
  item_id: string;
  item_name: string;
  issue: string;
  severity: "critical" | "warning";
}

export interface SolutionMapResponse {
  vision_goals: LayerSummary;
  features: LayerSummary;
  tasks: LayerSummary;
  tables: LayerSummary;
  endpoints: LayerSummary;
  sources: LayerSummary;
  blockers: Blocker[];
  warnings: Blocker[];
  overall_health: number;
  last_updated: string;
}

/**
 * Fetch the solution map data
 */
export async function fetchSolutionMap(): Promise<SolutionMapResponse> {
  return get<SolutionMapResponse>("/api/solution-map");
}
