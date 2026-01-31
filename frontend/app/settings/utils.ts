import {
  DEFAULT_FUND_WEIGHTS,
  DEFAULT_SCORE_WEIGHTS,
  DEFAULT_TECH_WEIGHTS,
} from '@/components/settings/DEFAULTS'
import { TIMEZONE_OPTIONS } from '@/components/settings/sections/DisplaySettings'
import type {
  FundamentalSubWeights,
  PreferencesResponse,
  ScoreWeights,
  TechnicalSubWeights,
} from '@/lib/api/preferences'
import type { EditablePreferences } from './types'
import { OBJECT_FIELDS, PRIMITIVE_FIELDS } from './types'

export const PRICE_SUB_WEIGHTS = { changePct: 100 } as const

export const ensureScoreWeights = (
  weights?: ScoreWeights | null,
): ScoreWeights => ({
  price: weights?.price ?? DEFAULT_SCORE_WEIGHTS.price,
  technical: weights?.technical ?? DEFAULT_SCORE_WEIGHTS.technical,
  fundamental: weights?.fundamental ?? DEFAULT_SCORE_WEIGHTS.fundamental,
})

export const ensureTechnicalWeights = (
  weights?: TechnicalSubWeights | null,
): TechnicalSubWeights => ({
  rsi14: weights?.rsi14 ?? DEFAULT_TECH_WEIGHTS.rsi14,
  trend: weights?.trend ?? DEFAULT_TECH_WEIGHTS.trend,
  macd: weights?.macd ?? DEFAULT_TECH_WEIGHTS.macd,
})

export const ensureFundamentalWeights = (
  weights?: FundamentalSubWeights | null,
): FundamentalSubWeights => ({
  valuation: weights?.valuation ?? DEFAULT_FUND_WEIGHTS.valuation,
  growth: weights?.growth ?? DEFAULT_FUND_WEIGHTS.growth,
  health: weights?.health ?? DEFAULT_FUND_WEIGHTS.health,
  sentiment: weights?.sentiment ?? DEFAULT_FUND_WEIGHTS.sentiment,
})

export const parsePositionSize = (value: string) => {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export const describeRiskTolerance = (value: number) => {
  if (value <= 3) return 'Conservative'
  if (value >= 8) return 'Aggressive'
  return 'Moderate'
}

export const formatTimezoneLabel = (timezone: string) =>
  TIMEZONE_OPTIONS[timezone as keyof typeof TIMEZONE_OPTIONS] ?? timezone

export const buildEditableFromResponse = (
  prefs: PreferencesResponse,
): EditablePreferences => ({
  riskTolerance: prefs.riskTolerance,
  allowLong: prefs.allowLong,
  allowShort: prefs.allowShort,
  allowOptions: prefs.allowOptions,
  allowCrypto: prefs.allowCrypto,
  allowFutures: prefs.allowFutures,
  maxPositionSizePct: prefs.maxPositionSizePct,
  displayTimezone: prefs.displayTimezone,
  defaultRefreshMinutes: prefs.defaultRefreshMinutes,
  watchlistOverride: prefs.watchlistRefreshOverride,
  newsOverride: prefs.newsRefreshOverride,
  newsLookbackHours: prefs.newsLookbackHours,
  newsMaxArticles: prefs.newsMaxArticles,
  showNews: prefs.watchlistShowNews,
  autoExpand: prefs.watchlistAutoExpand,
  scoreWeights: ensureScoreWeights(prefs.watchlistScoreWeights),
  technicalSubWeights: ensureTechnicalWeights(prefs.technicalSubWeights),
  fundamentalSubWeights: ensureFundamentalWeights(prefs.fundamentalSubWeights),
})

export const editableToApiPayload = (editable: EditablePreferences) => ({
  riskTolerance: editable.riskTolerance,
  allowLong: editable.allowLong,
  allowShort: editable.allowShort,
  allowOptions: editable.allowOptions,
  allowCrypto: editable.allowCrypto,
  allowFutures: editable.allowFutures,
  maxPositionSizePct: editable.maxPositionSizePct,
  displayTimezone: editable.displayTimezone,
  defaultRefreshMinutes: editable.defaultRefreshMinutes,
  watchlistRefreshOverride: editable.watchlistOverride,
  newsRefreshOverride: editable.newsOverride,
  newsLookbackHours: editable.newsLookbackHours,
  newsMaxArticles: editable.newsMaxArticles,
  watchlistShowNews: editable.showNews,
  watchlistAutoExpand: editable.autoExpand,
  watchlistScoreWeights: editable.scoreWeights,
  priceSubWeights: PRICE_SUB_WEIGHTS,
  technicalSubWeights: editable.technicalSubWeights,
  fundamentalSubWeights: editable.fundamentalSubWeights,
})

export const mergeEditableIntoResponse = (
  base: PreferencesResponse,
  editable: EditablePreferences,
): PreferencesResponse => ({
  ...base,
  ...editableToApiPayload(editable),
})

export const deepEqual = <T>(a: T, b: T) =>
  JSON.stringify(a) === JSON.stringify(b)

export const countEditableDifferences = (
  current: EditablePreferences,
  baseline: EditablePreferences,
) => {
  let count = 0
  for (const key of PRIMITIVE_FIELDS) {
    if (current[key] !== baseline[key]) {
      count += 1
    }
  }
  for (const key of OBJECT_FIELDS) {
    if (!deepEqual(current[key], baseline[key])) {
      count += 1
    }
  }
  return count
}
