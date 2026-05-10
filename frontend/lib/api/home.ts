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

export interface HomeTodayBriefAsOf {
  household: string | null
  portfolio: string | null
  market: string | null
  news: string | null
}

export interface HomeTodayBriefBlock {
  headline: string
  summary: string
  stance: string
  confidence: string
  whyNow: string
  bullets: string[]
}

export interface HomeTodayBriefCatalyst {
  id: string
  title: string
  direction: string
  marketEffect: string
  portfolioEffect: string
  moneyEffect: string
  sourceIds: string[]
}

export interface HomeTodayBriefImpact {
  label: string
  direction: string
  magnitude: string
  rationale: string
  affectedSymbols: string[]
  sourceIds: string[]
}

export interface HomeTodayBriefMetric {
  key: string
  label: string
  value: string
  changePct: number | null
  detail: string
  tone: string
  horizon?: string | null
  asOf?: string | null
  asOfLabel?: string | null
  /** Layout hint: 'wide' makes the tile span two columns when the grid splits. */
  span?: 'wide' | null
}

export interface HomeTodayBriefSource {
  id: string
  kind: string
  label: string
  publishedAt: string | null
  url: string | null
  sourceSignalTier: string | null
  decisionValueScore: number | null
}

export interface HomeTodayBrief {
  generatedAt: string
  cacheTtlSeconds: number
  asOf: HomeTodayBriefAsOf
  marketStatus: string
  brief: HomeTodayBriefBlock
  catalysts: HomeTodayBriefCatalyst[]
  impacts: HomeTodayBriefImpact[]
  marketMetrics: HomeTodayBriefMetric[]
  sources: HomeTodayBriefSource[]
  stalenessNotes: string[]
}

export async function fetchHomeActionQueue(): Promise<HomeActionQueue> {
  return get<HomeActionQueue>('/api/home/action-queue')
}

export async function fetchHomeTodayBrief(): Promise<HomeTodayBrief> {
  return get<HomeTodayBrief>('/api/home/today-brief')
}
