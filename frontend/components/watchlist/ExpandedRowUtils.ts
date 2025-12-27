/**
 * Utility functions for ExpandedRow components
 *
 * Extracted from ExpandedRow.tsx to reduce file size and improve modularity.
 */

/**
 * Sanitize HTML/text input to prevent XSS
 */
export function sanitizeText(input?: string | null): string {
    if (!input) return "";
    const value = input.trim();
    if (!value) return "";
    try {
        if (
            typeof window !== "undefined" &&
            typeof window.DOMParser !== "undefined"
        ) {
            const parser = new window.DOMParser();
            const doc = parser.parseFromString(value, "text/html");
            return (doc.body?.textContent ?? "").replace(/\s+/g, " ").trim();
        }
    } catch {
        // fallthrough to regex
    }
    return value
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

/**
 * Format score change with +/- sign
 */
export function formatScoreChange(change?: number | null): string | null {
    if (change === null || change === undefined || Number.isNaN(change)) {
        return null;
    }
    const formatted = change.toFixed(2);
    return change >= 0 ? `+${formatted}` : formatted;
}

/**
 * Get score badge variant based on score value
 */
export function getScoreBadgeVariant(
    score: number,
): "viz-0" | "viz-1" | "viz-2" | "viz-3" | "viz-4" | "viz-5" {
    if (score >= 80) return "viz-5";
    if (score >= 60) return "viz-4";
    if (score >= 40) return "viz-3";
    if (score >= 20) return "viz-2";
    if (score >= 10) return "viz-1";
    return "viz-0";
}

/**
 * Get timezone abbreviation (EST, PST, etc.)
 */
export function getTimezoneAbbreviation(timezone: string): string {
    const date = new Date();
    const formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: timezone,
        timeZoneName: "short",
    });
    const parts = formatter.formatToParts(date);
    const timeZonePart = parts.find((part) => part.type === "timeZoneName");
    return timeZonePart?.value ?? "";
}

/**
 * Format timestamp with user's timezone
 */
export function formatTimestamp(timestamp: string | undefined, userTimezone: string): string {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const formatted = date.toLocaleString("en-US", {
        timeZone: userTimezone,
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
    const tzAbbr = getTimezoneAbbreviation(userTimezone);
    return `${formatted} ${tzAbbr}`;
}

/**
 * Format model coverage display string
 */
export function formatModelCoverage(
    totalModelCoverage: number,
    finbertCoverage: number,
): string {
    if (totalModelCoverage === 0) {
        return "No articles scored";
    }
    if (finbertCoverage === totalModelCoverage) {
        return "FinBERT coverage";
    }
    if (finbertCoverage === 0) {
        return "Fallback sentiment (VADER)";
    }
    return `FinBERT ${finbertCoverage}/${totalModelCoverage}`;
}

/**
 * Get signal display configuration
 */
export function getSignalDisplay(signalType: "BUY" | "HOLD" | "AVOID") {
    switch (signalType) {
        case "BUY":
            return {
                icon: "🟢",
                color: "bg-status-success/10 text-status-success border-status-success/20",
                label: "BUY",
            };
        case "HOLD":
            return {
                icon: "🟡",
                color: "bg-status-warning/10 text-status-warning border-status-warning/20",
                label: "HOLD",
            };
        case "AVOID":
            return {
                icon: "🔴",
                color: "bg-status-error/10 text-status-error border-status-error/20",
                label: "AVOID",
            };
    }
}
