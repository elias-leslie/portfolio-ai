import { get } from './client'
import type { SymbolDecisionSection } from './symbols'

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
  decision?: SymbolDecisionSection | null
  execution?: HomeActionExecution | null
}

export interface HomeActionQueue {
  generatedAt: string
  actions: HomeActionItem[]
  summary: string
}

export async function fetchHomeActionQueue(): Promise<HomeActionQueue> {
  return get<HomeActionQueue>('/api/home/action-queue')
}
