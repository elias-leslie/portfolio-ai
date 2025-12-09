/**
 * Trading Intelligence Gap Detection API Client
 *
 * Endpoints:
 * - GET /api/gaps/summary - System-wide gap summary
 * - GET /api/gaps/by-analysis - Gaps grouped by analysis type
 * - GET /api/gaps/by-symbol/:symbol - Per-symbol gap analysis
 * - GET /api/gaps/watchlist - Watchlist gaps
 * - POST /api/gaps/generate-task-list - Generate task list for gaps
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ========================================================================
// Types
// ========================================================================

export interface GapInfo {
  gap_id: string;
  capability: string;
  analysis_type: string;
  criticality: "P0" | "P1" | "P2" | "P3";
  current_state: string;
  desired_state: string;
  impact: string;
  data_sources: Array<Record<string, any>>;
  effort: "LOW" | "MEDIUM" | "HIGH";
  blocks_strategies: string[];
  recommendation: string;
  severity: "blocking" | "limiting" | "optional";
}

export interface CoverageResult {
  analysis_type: string;
  description: string;
  total_capabilities: number;
  available_capabilities: number;
  missing_capabilities: number;
  coverage_pct: number;
  maturity_level: number;  // 0-3
  gaps: GapInfo[];
}

export interface GapSummary {
  timestamp: string;
  total_gaps: number;
  resolved_count: number;  // Gaps resolved (tracked via feature passes=true)
  p0_gaps: number;
  p1_gaps: number;
  p2_gaps: number;
  p3_gaps: number;
  analysis_types: Record<string, CoverageResult>;
  avg_coverage_pct: number;
  top_10_priorities: GapInfo[];
  mvp_roadmap: Record<string, any>;
}

export interface GapsByAnalysis {
  analysis_types: Record<string, CoverageResult>;
}

export interface SymbolGaps {
  symbol: string;
  analysis_types: Record<string, any>;
}

export interface WatchlistGaps {
  watchlist_symbols: string[];
  symbol_coverage: Record<string, any>;
  aggregate_gaps: Array<{
    capability: string;
    description: string;
    affected_symbols: number;
    total_symbols: number;
    affected_pct: number;
    symbols: string[];
  }>;
}

export interface TaskListGenerated {
  gap_ids: string[];
  task_file: string;
  message: string;
}

// ========================================================================
// API Functions
// ========================================================================

/**
 * Fetch system-wide gap summary
 */
export async function fetchGapSummary(): Promise<GapSummary> {
  const response = await fetch(`${API_BASE}/api/gaps/summary`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to fetch gap summary");
  }

  return response.json();
}

/**
 * Fetch gaps grouped by analysis type
 */
export async function fetchGapsByAnalysis(): Promise<GapsByAnalysis> {
  const response = await fetch(`${API_BASE}/api/gaps/by-analysis`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to fetch gaps by analysis");
  }

  return response.json();
}

/**
 * Fetch per-symbol gap analysis
 */
export async function fetchSymbolGaps(symbol: string): Promise<SymbolGaps> {
  const response = await fetch(`${API_BASE}/api/gaps/by-symbol/${symbol}`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to fetch symbol gaps");
  }

  return response.json();
}

/**
 * Fetch gaps affecting current watchlist
 */
export async function fetchWatchlistGaps(): Promise<WatchlistGaps> {
  const response = await fetch(`${API_BASE}/api/gaps/watchlist`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to fetch watchlist gaps");
  }

  return response.json();
}

/**
 * Generate task list to fill specific gaps
 */
export async function generateTaskList(gapIds: string[]): Promise<TaskListGenerated> {
  const response = await fetch(`${API_BASE}/api/gaps/generate-task-list`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ gap_ids: gapIds }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate task list");
  }

  return response.json();
}
