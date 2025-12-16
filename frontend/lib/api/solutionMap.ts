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
  itemId: string;
  itemName: string;
  issue: string;
  severity: "critical" | "warning";
}

export interface SolutionMapResponse {
  visionGoals: LayerSummary;
  features: LayerSummary;
  tasks: LayerSummary;
  tables: LayerSummary;
  endpoints: LayerSummary;
  sources: LayerSummary;
  blockers: Blocker[];
  warnings: Blocker[];
  overallHealth: number;
  lastUpdated: string;
}

/**
 * Fetch the solution map data
 */
export async function fetchSolutionMap(): Promise<SolutionMapResponse> {
  return get<SolutionMapResponse>("/api/solution-map");
}
