import { AlertCircle, CheckCircle2, Clock, HardDrive } from 'lucide-react'

import type { BackupStatusResponse } from '@/lib/api/backup'

export function StatusIcon({
  status,
}: {
  status: BackupStatusResponse['status']
}) {
  switch (status) {
    case 'healthy':
      return <CheckCircle2 className="size-5 text-gain" />
    case 'stale':
      return <Clock className="size-5 text-warning" />
    case 'no_backups':
    case 'error':
      return <AlertCircle className="size-5 text-loss" />
    default:
      return <HardDrive className="size-5 text-text-muted" />
  }
}
