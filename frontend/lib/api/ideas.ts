/**
 * Ideas API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
export interface Idea {
  id: string;
  agent_run_id: string;
  idea_type: string;
  title: string;
  thesis: string;
  action: string;
  confidence_score: number;
  risk_level: string;
  reward_estimate: string | null;
  portfolio_impact: string | null;
  data_needed: string | null;
  risks: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface IdeasListResponse {
  ideas: Idea[];
  count: number;
}

export interface GenerateIdeasRequest {
  agent_type: "discovery" | "portfolio_analyzer";
}

export interface GenerateIdeasResponse {
  status: string;
  agent_run_id: string;
  num_ideas: number;
  agent_type: string;
}

export interface UpdateIdeaStatusRequest {
  status: "pending" | "validated" | "executed" | "rejected";
}

/**
 * Fetch investment ideas with optional filtering
 */
export async function fetchIdeas(params?: {
  idea_type?: string;
  status?: string;
  limit?: number;
}): Promise<IdeasListResponse> {
  const queryParams = new URLSearchParams();

  if (params?.idea_type) {
    queryParams.append("idea_type", params.idea_type);
  }
  if (params?.status) {
    queryParams.append("status", params.status);
  }
  if (params?.limit !== undefined) {
    queryParams.append("limit", params.limit.toString());
  }

  const url = `/api/ideas/${queryParams.toString() ? `?${queryParams.toString()}` : ""}`;

  return apiRequest<IdeasListResponse>(url);
}

/**
 * Generate new investment ideas by running an agent
 */
export async function generateIdeas(
  data: GenerateIdeasRequest
): Promise<GenerateIdeasResponse> {
  return apiRequest<GenerateIdeasResponse>("/api/ideas/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Fetch detailed information about a specific idea
 */
export async function fetchIdeaDetails(ideaId: string): Promise<Idea> {
  return apiRequest<Idea>(`/api/ideas/${ideaId}`);
}

/**
 * Update the status of an investment idea
 */
export async function updateIdeaStatus(
  ideaId: string,
  data: UpdateIdeaStatusRequest
): Promise<Idea> {
  return apiRequest<Idea>(`/api/ideas/${ideaId}/status`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
