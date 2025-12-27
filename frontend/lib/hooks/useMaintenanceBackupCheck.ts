"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  checkBackupRequirements,
  type BackupRequirementCheck,
} from "@/lib/api/maintenance";

export interface UseMaintenanceBackupCheckReturn {
  backupCheck: BackupRequirementCheck | null;
  isCheckingBackup: boolean;
  checkBackupStatus: () => Promise<void>;
}

/**
 * Hook to check backup status when dry-run mode is toggled off.
 * Shared between MaintenanceTable and UnifiedMaintenanceCard.
 *
 * @param dryRun - Whether dry-run mode is enabled
 * @param maxAgeHours - Maximum backup age in hours (default: 24)
 * @param requireVerified - Whether to require verified backup (default: true)
 */
export function useMaintenanceBackupCheck(
  dryRun: boolean,
  maxAgeHours: number = 24,
  requireVerified: boolean = true
): UseMaintenanceBackupCheckReturn {
  const [backupCheck, setBackupCheck] = useState<BackupRequirementCheck | null>(null);
  const [isCheckingBackup, setIsCheckingBackup] = useState(false);

  const checkBackupStatus = useCallback(async () => {
    setIsCheckingBackup(true);
    try {
      const check = await checkBackupRequirements(maxAgeHours, requireVerified);
      setBackupCheck(check);
      if (!check.canProceed) {
        toast.warning(`Backup check: ${check.blockingReason || "Requirements not met"}`);
      }
    } catch {
      toast.error("Could not verify backup status");
      setBackupCheck({
        backupExists: false,
        backupRecent: false,
        backupVerified: false,
        backupName: null,
        backupAgeHours: null,
        canProceed: false,
        blockingReason: "Could not verify backup status",
        warnings: [],
      });
    } finally {
      setIsCheckingBackup(false);
    }
  }, [maxAgeHours, requireVerified]);

  // Check backup when dry-run is toggled off
  useEffect(() => {
    if (!dryRun) {
      checkBackupStatus();
    } else {
      setBackupCheck(null);
    }
  }, [dryRun, checkBackupStatus]);

  return {
    backupCheck,
    isCheckingBackup,
    checkBackupStatus,
  };
}
