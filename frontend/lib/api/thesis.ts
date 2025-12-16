/**
 * Thesis System API client functions
 */

import { apiRequest, post } from "./client";

// Types matching backend Pydantic models
export interface ClaudeValidation {
    provider: string;
    approved: boolean;
    confidence: number;
    reviewSummary: string;
    issues: string[];
}

export interface CoreReason {
    reason: string;
    confidence: number;
}

export interface KeyCatalyst {
    catalyst: string;
    expectedDate: string | null;
    impact: "positive" | "negative" | "neutral";
}

export interface Risk {
    risk: string;
    severity: "high" | "medium" | "low";
    mitigation: string | null;
}

export interface ValueDrivers {
    marketSize: string | null;
    companyPosition: string | null;
    upsidePotential: string | null;
    competitiveMoat: string | null;
}

export interface Thesis {
    id: string;
    symbol: string;
    version: number;
    status: "active" | "invalidated" | "flaggedForReview";
    action: "BUY" | "HOLD" | "SELL";
    coreReasons: CoreReason[];
    keyCatalysts: KeyCatalyst[];
    risks: Risk[];
    valueDrivers: ValueDrivers | null;
    expectedReturnPct: number | null;
    expectedTimeframeDays: number | null;
    claudeValidation: ClaudeValidation | null;
    crossValidationScore: number | null;
    createdAt: string;
    updatedAt: string;
}

export interface ThesisVersion {
    version: number;
    status: string;
    action: string;
    createdAt: string;
    updatedAt: string;
}

export interface ThesisResponse {
    thesis: Thesis | null;
    versions: ThesisVersion[];
    versionCount: number;
}

export interface GenerateThesisRequest {
    forceRegenerate?: boolean;
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
