/**
 * Backup API client
 */

import { get, post } from "./client";

// Types
export interface TreeEntry {
  count: number;
}

export interface BackupVerification {
  verified: boolean;
  verifiedAt: string;
  errors: string[];
  tree: Record<string, TreeEntry>;
  totalFiles: number;
  checksum: string;
}

export interface BackupEntry {
  name: string;
  timestamp: string;
  sizeBytes: number;
  dbSizeBytes: number;
  status: "ok" | "failed" | "in_progress";
  verification?: BackupVerification;
}

export interface BackupStatusResponse {
  status: "healthy" | "stale" | "no_backups" | "error";
  latestBackup: BackupEntry | null;
  backupCount: number;
  destination: string;
  lastUpdated: string | null;
  message: string;
}

export interface BackupIndexResponse {
  version: number;
  retention: number;
  destination: string;
  backups: BackupEntry[];
  lastUpdated: string | null;
}

export interface TriggerBackupResponse {
  jobId: string;
  status: "started" | "already_running";
  message: string;
}

export interface BackupJobStatus {
  jobId: string;
  status: "running" | "completed" | "failed" | "not_found";
  startedAt: string | null;
  completedAt: string | null;
  output: string | null;
  error: string | null;
}

// Query key factory
export const backupKeys = {
  all: ["backup"] as const,
  status: () => [...backupKeys.all, "status"] as const,
  latest: () => [...backupKeys.all, "latest"] as const,
  history: () => [...backupKeys.all, "history"] as const,
  job: (jobId: string) => [...backupKeys.all, "job", jobId] as const,
};

// API functions
export async function getBackupStatus(): Promise<BackupStatusResponse> {
  return get<BackupStatusResponse>("/api/backup/status");
}

export async function getLatestBackup(): Promise<BackupEntry | null> {
  return get<BackupEntry | null>("/api/backup/latest");
}

export async function getBackupHistory(): Promise<BackupIndexResponse> {
  return get<BackupIndexResponse>("/api/backup/history");
}

export async function triggerBackup(quick = false): Promise<TriggerBackupResponse> {
  return post<TriggerBackupResponse>(`/api/backup/trigger?quick=${quick}`);
}

export async function getBackupJobStatus(jobId: string): Promise<BackupJobStatus> {
  return get<BackupJobStatus>(`/api/backup/job/${jobId}`);
}

// Utility functions
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export function formatBackupAge(timestamp: string | null): string {
  if (!timestamp) return "Never";

  const backupTime = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - backupTime.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 1) {
    const mins = Math.floor(diffMs / (1000 * 60));
    return `${mins} min ago`;
  } else if (diffHours < 24) {
    return `${diffHours.toFixed(1)} hours ago`;
  } else {
    const days = Math.floor(diffHours / 24);
    return `${days} day${days > 1 ? "s" : ""} ago`;
  }
}

export function getStatusColor(status: BackupStatusResponse["status"]): string {
  switch (status) {
    case "healthy":
      return "text-gain";
    case "stale":
      return "text-warning";
    case "no_backups":
    case "error":
      return "text-loss";
    default:
      return "text-text-muted";
  }
}
