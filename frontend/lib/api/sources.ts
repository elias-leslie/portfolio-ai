/**
 * API Sources Registry Client
 *
 * Endpoints:
 * - GET /api/sources - List all data source providers
 * - GET /api/sources/{provider} - Detailed provider info
 * - GET /api/sources/gap/{gap_id} - Find providers for a gap
 * - GET /api/sources/routing/{data_type} - Data routing recommendations
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ========================================================================
// Types
// ========================================================================

export interface SourceProvider {
  name: string;
  display_name: string;
  tier: "FREE" | "PREMIUM";
  api_key_required: boolean;
  priority: number;
  rate_limits: {
    per_minute: number | null;
    per_day: number | null;
    notes?: string;
  };
  capabilities: string[];
  gap_coverage: string[];
  use_cases: string[];
}

export interface SourcesResponse {
  version: string;
  providers: SourceProvider[];
  data_routing: Record<string, DataRouting>;
  credentials: {
    storage: string;
    table: string;
  };
}

export interface DataRouting {
  primary: string;
  fallback_1?: string;
  fallback_2?: string;
  fallback_3?: string;
  notes?: string;
}

export interface SourceEndpoint {
  path?: string;
  method?: string;
  description: string;
  gap_id?: string;
  params?: Record<string, string>;
  fields_returned: string[];
  example?: string;
  notes?: string;
}

export interface SourceDetail {
  name: string;
  display_name: string;
  tier: "FREE" | "PREMIUM";
  api_key_required: boolean;
  env_var?: string;
  db_key?: string;
  priority: number;
  rate_limits: {
    per_minute: number | null;
    per_day: number | null;
    notes?: string;
  };
  data_delay?: string;
  capabilities: Record<string, boolean>;
  endpoints: Record<string, SourceEndpoint>;
  premium_only: string[];
  use_cases: string[];
  implementation_file: string;
}

export interface GapProviderEndpoint {
  endpoint: string;
  path: string;
  description: string;
  notes?: string;
}

export interface GapProvider {
  provider: string;
  tier: "FREE" | "PREMIUM";
  priority: number;
  endpoints: GapProviderEndpoint[];
}

export interface GapProvidersResponse {
  gap_id: string;
  providers: GapProvider[];
  message?: string;
}

// ========================================================================
// API Functions
// ========================================================================

/**
 * Fetch all API source providers
 */
export async function fetchSources(): Promise<SourcesResponse> {
  const response = await fetch(`${API_BASE}/api/sources/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch sources: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch detailed info for a specific provider
 */
export async function fetchSourceDetail(provider: string): Promise<SourceDetail> {
  const response = await fetch(`${API_BASE}/api/sources/${provider}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch source detail: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Find providers that can address a specific trading gap
 */
export async function fetchGapProviders(gapId: string): Promise<GapProvidersResponse> {
  const response = await fetch(`${API_BASE}/api/sources/gap/${gapId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch gap providers: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get data routing recommendations for a data type
 */
export async function fetchDataRouting(dataType: string): Promise<{ data_type: string; routing: DataRouting }> {
  const response = await fetch(`${API_BASE}/api/sources/routing/${dataType}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch routing: ${response.statusText}`);
  }
  return response.json();
}
