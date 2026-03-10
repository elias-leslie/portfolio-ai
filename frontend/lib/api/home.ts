import { get } from './client'

export interface HomeActionExecution {
  kind: string
  symbol: string | null
  notificationId: string | null
  stage: string | null
}

export interface HomeActionItem {
  id: string
  source: string
  category: string
  priority: string
  title: string
  detail: string
  actionLabel: string
  href: string
  symbol: string | null
  badge: string | null
  execution?: HomeActionExecution | null
}

export interface HomeActionQueue {
  generatedAt: string
  actions: HomeActionItem[]
  summary: string
}

export interface AutomationGuardrail {
  key: string
  label: string
  value: string
  detail: string
}

export interface AutomationRecentRun {
  id: string
  label: string
  status: string
  triggeredBy: string
  startedAt: string
  completedAt: string | null
  detail: string
}

export interface AutomationCenter {
  generatedAt: string
  guardrails: AutomationGuardrail[]
  recentRuns: AutomationRecentRun[]
  warnings: string[]
}

export async function fetchHomeActionQueue(): Promise<HomeActionQueue> {
  return get<HomeActionQueue>('/api/home/action-queue')
}

export async function fetchAutomationCenter(): Promise<AutomationCenter> {
  return get<AutomationCenter>('/api/home/automation-center')
}
