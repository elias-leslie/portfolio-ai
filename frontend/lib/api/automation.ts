/**
 * Automation API client functions for triggering pipeline stages
 */

import { apiRequest } from "./client";

export interface PipelineResponse {
  status: string;
  task_id?: string;
  stage: string;
  message: string;
}

export interface FullPipelineResponse {
  status: string;
  message: string;
  stages: Record<string, { task_id: string; status: string }>;
}

export interface PipelineStatus {
  stages: {
    strategies: { active_count: number };
    signals: { today_count: number };
    paper_trades: { open_count: number };
  };
  last_run: Record<string, string | null>;
}

/**
 * Trigger strategy research
 */
export async function triggerStrategyResearch(
  symbol?: string,
  force?: boolean
): Promise<PipelineResponse> {
  const params = new URLSearchParams();
  if (symbol) params.append("symbol", symbol);
  if (force) params.append("force", "true");

  const query = params.toString() ? `?${params.toString()}` : "";
  return apiRequest<PipelineResponse>(`/api/automation/run/strategy-research${query}`, {
    method: "POST",
  });
}

/**
 * Trigger signal generation
 */
export async function triggerSignalGeneration(): Promise<PipelineResponse> {
  return apiRequest<PipelineResponse>("/api/automation/run/signal-generation", {
    method: "POST",
  });
}

/**
 * Trigger auto paper trading
 */
export async function triggerAutoPaperTrade(
  minStrength: number = 5
): Promise<PipelineResponse> {
  return apiRequest<PipelineResponse>(
    `/api/automation/run/auto-paper-trade?min_strength=${minStrength}`,
    { method: "POST" }
  );
}

/**
 * Trigger full pipeline
 */
export async function triggerFullPipeline(
  skipResearch: boolean = false
): Promise<FullPipelineResponse> {
  return apiRequest<FullPipelineResponse>(
    `/api/automation/run/full-pipeline?skip_research=${skipResearch}`,
    { method: "POST" }
  );
}

/**
 * Get pipeline status
 */
export async function getPipelineStatus(): Promise<PipelineStatus> {
  return apiRequest<PipelineStatus>("/api/automation/status");
}
