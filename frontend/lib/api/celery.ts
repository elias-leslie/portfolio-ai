/**
 * Celery task monitoring API client
 */

import { get } from './client'

// Type definitions
export interface TaskInfo {
  id: string
  name: string
  status: string
  startedAt: string | null
  duration: number | null
  worker: string | null
  args: string | null
  kwargs: string | null
  result: string | null
  traceback: string | null
  dateDone: string | null
}

export interface TaskListResponse {
  tasks: TaskInfo[]
  total: number
  activeCount: number
  pendingCount: number
  completedCount: number
  failedCount: number
}

export interface QueueInfo {
  depth: number
  consumers: number
}

export interface ScheduleInfo {
  name: string
  task: string
  schedule: string
  lastRun: string | null
  nextRun: string | null
}

/**
 * Fetch Celery tasks with optional filtering
 */
export async function fetchCeleryTasks(
  status: 'all' | 'active' | 'pending' | 'completed' | 'failed' = 'all',
  limit: number = 50,
  sort: 'time' | 'duration' | 'name' = 'time',
): Promise<TaskListResponse> {
  const params = new URLSearchParams({
    status,
    limit: limit.toString(),
    sort,
  })

  return get<TaskListResponse>(`/api/status/celery/tasks?${params}`)
}

/**
 * Fetch Celery queue depth and consumer count
 */
export async function fetchQueueDepth(): Promise<QueueInfo> {
  return get<QueueInfo>('/api/status/celery/queue')
}

/**
 * Fetch Celery Beat schedule information
 */
export async function fetchBeatSchedule(): Promise<ScheduleInfo[]> {
  return get<ScheduleInfo[]>('/api/status/celery/schedule')
}
