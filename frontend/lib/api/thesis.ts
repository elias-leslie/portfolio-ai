/**
 * Thesis System API client functions
 */

import { apiRequest, post } from "./client";

// Types matching backend Pydantic models
export interface ClaudeValidation {
    provider: string;
    approved: boolean;
    confidence: number;
    review_summary: string;
    issues: string[];
}

export interface CoreReason {
    reason: string;
    confidence: number;
}

export interface KeyCatalyst {
    catalyst: string;
    expected_date: string | null;
    impact: "positive" | "negative" | "neutral";
}

export interface Risk {
    risk: string;
    severity: "high" | "medium" | "low";
    mitigation: string | null;
}

export interface ValueDrivers {
    market_size: string | null;
    company_position: string | null;
    upside_potential: string | null;
    competitive_moat: string | null;
}

export interface Thesis {
    id: string;
    symbol: string;
    version: number;
    status: "active" | "invalidated" | "flagged_for_review";
    action: "BUY" | "HOLD" | "SELL";
    core_reasons: CoreReason[];
    key_catalysts: KeyCatalyst[];
    risks: Risk[];
    value_drivers: ValueDrivers | null;
    expected_return_pct: number | null;
    expected_timeframe_days: number | null;
    claude_validation: ClaudeValidation | null;
    cross_validation_score: number | null;
    created_at: string;
    updated_at: string;
}

export interface ThesisVersion {
    version: number;
    status: string;
    action: string;
    created_at: string;
    updated_at: string;
}

export interface ThesisResponse {
    thesis: Thesis | null;
    versions: ThesisVersion[];
    version_count: number;
}

export interface GenerateThesisRequest {
    force_regenerate?: boolean;
}

export interface InvalidateThesisRequest {
    reason: string;
}

/**
 * Get thesis for a symbol
 */
export async function fetchThesis(symbol: string): Promise<ThesisResponse> {
    return apiRequest<ThesisResponse>(`/api/thesis/${symbol}`);
}

/**
 * Generate thesis for a symbol
 */
export async function generateThesis(
    symbol: string,
    request: GenerateThesisRequest = {}
): Promise<ThesisResponse> {
    return post<ThesisResponse>(`/api/thesis/${symbol}/generate`, request);
}

/**
 * Invalidate a thesis
 */
export async function invalidateThesis(
    symbol: string,
    reason: string
): Promise<ThesisResponse> {
    return post<ThesisResponse>(`/api/thesis/${symbol}/invalidate`, { reason });
}
