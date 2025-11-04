/**
 * System resources API client
 */

import { API_BASE_URL } from "./client";

export interface DiskUsage {
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface MemoryUsage {
  total_gb: number;
  used_gb: number;
  available_gb: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface CpuUsage {
  percent_used: number;
  cores: number;
  status: "ok" | "warning" | "critical";
}

export interface DatabasePool {
  pool_size: number;
  checked_out: number;
  overflow: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface SystemResources {
  disk: DiskUsage;
  memory: MemoryUsage;
  cpu: CpuUsage;
  database_pool: DatabasePool;
  timestamp: string;
}

export async function getSystemResources(): Promise<SystemResources> {
  const response = await fetch(`${API_BASE_URL}/api/status/resources`);

  if (!response.ok) {
    throw new Error(`Failed to fetch system resources: ${response.statusText}`);
  }

  return response.json();
}
