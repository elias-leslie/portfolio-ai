/**
 * Celery task monitoring API client
 */

// Type definitions
export interface TaskInfo {
  id: string;
  name: string;
  status: string;
  started_at: string | null;
  duration: number | null;
  worker: string | null;
  args: string | null;
  kwargs: string | null;
  result: string | null;
  traceback: string | null;
  date_done: string | null;
}

export interface TaskListResponse {
  tasks: TaskInfo[];
  total: number;
  active_count: number;
  pending_count: number;
  completed_count: number;
  failed_count: number;
}

export interface QueueInfo {
  depth: number;
  consumers: number;
}

export interface ScheduleInfo {
  name: string;
  task: string;
  schedule: string;
  last_run: string | null;
  next_run: string | null;
}

/**
 * Fetch Celery tasks with optional filtering
 */
export async function fetchCeleryTasks(
  status: "all" | "active" | "pending" | "completed" | "failed" = "all",
  limit: number = 50,
  sort: "time" | "duration" | "name" = "time"
): Promise<TaskListResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const params = new URLSearchParams({
    status,
    limit: limit.toString(),
    sort,
  });

  const response = await fetch(`${apiUrl}/api/status/celery/tasks?${params}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Celery tasks: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch Celery queue depth and consumer count
 */
export async function fetchQueueDepth(): Promise<QueueInfo> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const response = await fetch(`${apiUrl}/api/status/celery/queue`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch queue depth: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch Celery Beat schedule information
 */
export async function fetchBeatSchedule(): Promise<ScheduleInfo[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const response = await fetch(`${apiUrl}/api/status/celery/schedule`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch beat schedule: ${response.statusText}`);
  }

  return response.json();
}
