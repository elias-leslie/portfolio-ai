'use client'

import { Database, HardDrive, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  type DatabaseSizeResponse,
  type DiskSpaceResponse,
  getMaintenanceDatabaseSize,
  getMaintenanceDiskSpace,
  getMaintenanceSchedule,
  type MaintenanceScheduleResponse,
} from '@/lib/api/maintenance'
import { ExpandableCard } from './ExpandableCard'

export function MaintenanceStatusCard() {
  const [diskSpace, setDiskSpace] = useState<DiskSpaceResponse | null>(null)
  const [dbSize, setDbSize] = useState<DatabaseSizeResponse | null>(null)
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = async () => {
    try {
      const [diskData, dbData, scheduleData] = await Promise.all([
        getMaintenanceDiskSpace(),
        getMaintenanceDatabaseSize(),
        getMaintenanceSchedule(),
      ])
      setDiskSpace(diskData)
      setDbSize(dbData)
      setSchedule(scheduleData)
    } catch (error) {
      console.error('Failed to fetch maintenance data:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [fetchData])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchData()
  }

  const getDiskStatusVariant = (percentage: number) => {
    if (percentage > 85) return 'destructive'
    if (percentage > 70) return 'secondary'
    return 'default'
  }

  return (
    <ExpandableCard
      title="System Maintenance"
      description="Automated cleanup, disk monitoring, and database optimization"
      summary={
        loading
          ? 'Loading...'
          : `DB: ${dbSize?.databaseSizeMb.toFixed(1)} MB | ${diskSpace?.partitions.length || 0} disks monitored`
      }
      defaultCollapsed={true}
      actions={
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
          />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Disk Space Section */}
        <Card className="p-4">
          <div className="mb-4 flex items-center">
            <HardDrive className="mr-2 h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">Disk Space Usage</h3>
          </div>
          <div className="space-y-3">
            {diskSpace?.partitions.map((partition) => (
              <div key={partition.path} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{partition.path}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={getDiskStatusVariant(partition.usedPercentage)}
                    >
                      {partition.usedPercentage.toFixed(1)}%
                    </Badge>
                    <span className="text-muted-foreground">
                      {(partition.usedBytes / 1024 ** 3).toFixed(1)} GB /{' '}
                      {(partition.totalBytes / 1024 ** 3).toFixed(1)} GB
                    </span>
                  </div>
                </div>
                <Progress value={partition.usedPercentage} />
              </div>
            ))}
          </div>
          {diskSpace && diskSpace.alerts.length > 0 && (
            <div className="mt-4 rounded-md bg-destructive/10 p-3">
              <p className="text-sm font-medium text-destructive">
                ⚠️ {diskSpace.alerts.length} disk space alert(s)
              </p>
              {diskSpace.alerts.map((alert) => (
                <p
                  key={alert.partition}
                  className="text-xs text-muted-foreground"
                >
                  {alert.partition}: {alert.usedPercentage.toFixed(1)}% used (
                  {alert.freeMb.toFixed(0)} MB free)
                </p>
              ))}
            </div>
          )}
        </Card>

        {/* Database Size Section */}
        <Card className="p-4">
          <div className="mb-4 flex items-center">
            <Database className="mr-2 h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">Database Size</h3>
          </div>
          <div className="mb-3">
            <div className="text-2xl font-bold">
              {dbSize?.databaseSizeMb.toFixed(1)} MB
            </div>
            <p className="text-sm text-muted-foreground">Total database size</p>
          </div>
          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
              Top {dbSize?.topTables.length || 0} Tables
            </summary>
            <div className="mt-2 space-y-2">
              {dbSize?.topTables.map((table) => (
                <div
                  key={table.table}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="font-medium">{table.table}</span>
                  <span className="text-muted-foreground">
                    {table.sizePretty}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </Card>

        {/* Scheduled Tasks Section */}
        <Card className="p-4">
          <div className="mb-4 flex items-center">
            <RefreshCw className="mr-2 h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">
              Scheduled Maintenance Tasks
            </h3>
          </div>
          <div className="text-sm text-muted-foreground">
            <p className="mb-2">{schedule?.totalCount || 0} tasks scheduled</p>
            <details>
              <summary className="cursor-pointer font-medium text-foreground hover:underline">
                View All Tasks
              </summary>
              <div className="mt-3 space-y-2">
                {schedule &&
                  Object.entries(schedule.scheduledTasks).map(
                    ([name, task]) => (
                      <div key={name} className="rounded border p-2">
                        <div className="font-medium">{name}</div>
                        <div className="text-xs text-muted-foreground">
                          {task.schedule}
                        </div>
                      </div>
                    ),
                  )}
              </div>
            </details>
          </div>
        </Card>
      </div>
    </ExpandableCard>
  )
}
