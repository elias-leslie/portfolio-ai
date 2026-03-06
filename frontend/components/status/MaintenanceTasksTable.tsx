'use client'

import { ArrowUpDown, Loader2, PlayCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  formatLastRun,
  formatSize,
  getCategoryBadge,
  getStatusIcon,
  type TaskCategory,
} from '@/lib/maintenance/formatters'
import type { MaintenanceTask, SortKey } from './hooks/useMaintenanceTasks'

interface MaintenanceTasksTableProps {
  readOnly?: boolean
  tasks: MaintenanceTask[]
  filteredTasks: MaintenanceTask[]
  categoryFilter: TaskCategory | 'all'
  setCategoryFilter: (value: TaskCategory | 'all') => void
  toggleSort: (key: SortKey) => void
  triggeringTask: string | null
  liveBlocked: boolean
  scheduledTaskCount: number
  onTriggerTask: (task: MaintenanceTask) => void
}

function SortableHeader({
  label,
  sortKey,
  align = 'left',
  onToggle,
}: {
  label: string
  sortKey: SortKey
  align?: 'left' | 'right'
  onToggle: (key: SortKey) => void
}) {
  const alignClass = align === 'right' ? 'text-right' : ''
  const flexClass =
    align === 'right' ? 'flex items-center justify-end gap-1' : 'flex items-center gap-1'
  return (
    <TableHead
      className={`cursor-pointer select-none ${alignClass}`}
      onClick={() => onToggle(sortKey)}
    >
      <div className={flexClass}>
        {label}
        <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
      </div>
    </TableHead>
  )
}

export function MaintenanceTasksTable({
  readOnly = false,
  tasks,
  filteredTasks,
  categoryFilter,
  setCategoryFilter,
  toggleSort,
  triggeringTask,
  liveBlocked,
  scheduledTaskCount,
  onTriggerTask,
}: MaintenanceTasksTableProps) {
  return (
    <div className="space-y-4">
      {/* Category Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Filter:</span>
        <Select
          value={categoryFilter}
          onValueChange={(v) => setCategoryFilter(v as TaskCategory | 'all')}
        >
          <SelectTrigger className="w-32 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All ({tasks.length})</SelectItem>
            <SelectItem value="file">
              File ({tasks.filter((t) => t.category === 'file').length})
            </SelectItem>
            <SelectItem value="cache">
              Cache ({tasks.filter((t) => t.category === 'cache').length})
            </SelectItem>
            <SelectItem value="data">
              Data ({tasks.filter((t) => t.category === 'data').length})
            </SelectItem>
            <SelectItem value="database">
              Database ({tasks.filter((t) => t.category === 'database').length})
            </SelectItem>
            <SelectItem value="system">
              System ({tasks.filter((t) => t.category === 'system').length})
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Task Table */}
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHeader label="Task" sortKey="name" onToggle={toggleSort} />
            <SortableHeader label="Category" sortKey="category" onToggle={toggleSort} />
            <SortableHeader label="Size" sortKey="sizeMb" align="right" onToggle={toggleSort} />
            <SortableHeader label="Files" sortKey="fileCount" align="right" onToggle={toggleSort} />
            <TableHead>Retention</TableHead>
            <SortableHeader label="Schedule" sortKey="schedule" onToggle={toggleSort} />
            <SortableHeader label="Last Run" sortKey="lastRun" onToggle={toggleSort} />
            {!readOnly && <TableHead className="w-12 text-center">Run</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredTasks.map((task) => (
            <TableRow key={task.id} className="group">
              <TableCell>
                <div className="flex items-center gap-2">
                  {task.icon}
                  <span className="font-medium">{task.name}</span>
                </div>
              </TableCell>
              <TableCell>{getCategoryBadge(task.category)}</TableCell>
              <TableCell className="text-right font-mono text-xs">
                {formatSize(task.sizeMb)}
              </TableCell>
              <TableCell className="text-right font-mono text-xs">
                {task.fileCount?.toLocaleString() ?? '—'}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {task.retentionPolicy ?? '—'}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {task.schedule}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1.5">
                  {getStatusIcon(task.lastRun)}
                  <span className="text-xs text-muted-foreground">
                    {formatLastRun(task.lastRun)}
                  </span>
                </div>
              </TableCell>
              {!readOnly && (
                <TableCell className="text-center">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0"
                    onClick={() => onTriggerTask(task)}
                    disabled={
                      triggeringTask === task.taskName ||
                      (liveBlocked && !!task.isDbTask)
                    }
                    title={`Run ${task.name}`}
                  >
                    {triggeringTask === task.taskName ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <PlayCircle className="h-4 w-4" />
                    )}
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Scheduled Tasks Summary */}
      <div className="text-xs text-muted-foreground text-center pt-2 border-t">
        {scheduledTaskCount} scheduled maintenance tasks configured
      </div>
    </div>
  )
}
