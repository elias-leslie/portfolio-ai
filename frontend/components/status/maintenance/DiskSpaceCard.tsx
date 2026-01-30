import { HardDrive, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { type DiskSpaceInfo } from './types'
import { getStatusText } from './utils'

export function DiskSpaceCard({
  disks,
  isLoading,
}: {
  disks: DiskSpaceInfo[] | null
  isLoading: boolean
}) {
  if (isLoading && !disks) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Disk Space Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!disks || disks.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Disk Space Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No disk information available
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HardDrive className="h-5 w-5" />
          Disk Space Usage
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {disks.map((disk) => (
            <div key={disk.path} className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{disk.path}</p>
                  <p className="text-xs text-muted-foreground">
                    {disk.usedGb.toFixed(1)} GB / {disk.totalGb.toFixed(1)} GB
                  </p>
                </div>
                <Badge
                  variant={disk.status === 'ok' ? 'default' : 'destructive'}
                >
                  {getStatusText(disk.status)}
                </Badge>
              </div>
              <div className="space-y-1">
                <Progress value={disk.percentUsed} className="h-2" />
                <div className="text-right text-xs text-muted-foreground">
                  {disk.percentUsed.toFixed(1)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
