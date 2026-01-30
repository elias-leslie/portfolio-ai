import { Loader2, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { BackupRequirementCheck } from '@/lib/api/maintenance'

interface BackupStatusBadgeProps {
  isCheckingBackup: boolean
  backupCheck: BackupRequirementCheck | null
}

export function BackupStatusBadge({
  isCheckingBackup,
  backupCheck,
}: BackupStatusBadgeProps) {
  if (isCheckingBackup) {
    return (
      <Badge variant="secondary" className="flex items-center gap-1">
        <Loader2 className="h-3 w-3 animate-spin" />
        Checking backup...
      </Badge>
    )
  }

  if (backupCheck?.canProceed) {
    return (
      <Badge variant="default" className="flex items-center gap-1 bg-gain">
        <ShieldCheck className="h-3 w-3" />
        Backup OK
      </Badge>
    )
  }

  return (
    <Badge variant="destructive" className="flex items-center gap-1">
      <ShieldAlert className="h-3 w-3" />
      {backupCheck?.blockingReason?.split('.')[0] || 'No backup'}
    </Badge>
  )
}
