/**
 * Dashboard tab for System Capabilities - Solution Architecture Map
 * Shows hierarchical view of all system components and their health
 */

"use client";

import { SolutionMap } from "./SolutionMap";

// Tab value type matching the parent capabilities page
type TabValue = "dashboard" | "database" | "celery" | "api" | "sources" | "rules" | "features" | "vision";

interface CapabilitiesDashboardProps {
  onTabChange?: (tab: TabValue) => void;
}

/**
 * CapabilitiesDashboard component - now renders the Solution Map
 */
export function CapabilitiesDashboard({ onTabChange }: CapabilitiesDashboardProps) {
  return <SolutionMap onTabChange={onTabChange} />;
}
