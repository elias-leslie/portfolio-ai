import { get } from './client'

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
}

export interface HomeActionQueue {
  generatedAt: string
  actions: HomeActionItem[]
  summary: string
}

export async function fetchHomeActionQueue(): Promise<HomeActionQueue> {
  return get<HomeActionQueue>('/api/home/action-queue')
}
