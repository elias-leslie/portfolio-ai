export const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  backend: 'Backend',
  celeryWorker: 'Celery Worker',
  celeryBeat: 'Celery Beat',
  frontend: 'Frontend',
  redis: 'Redis',
  postgresql: 'PostgreSQL',
}

export function getLevelColor(level: string): string {
  switch (level) {
    case 'CRITICAL':
      return 'text-loss font-bold'
    case 'ERROR':
      return 'text-loss'
    case 'WARN':
      return 'text-warning'
    case 'INFO':
      return 'text-accent'
    case 'DEBUG':
      return 'text-text-muted'
    default:
      return 'text-text-muted'
  }
}

export function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return timestamp
  }
}
