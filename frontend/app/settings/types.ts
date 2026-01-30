import type {
  FundamentalSubWeights,
  ScoreWeights,
  TechnicalSubWeights,
} from '@/lib/api/preferences'

export type EditablePreferences = {
  riskTolerance: number
  allowLong: boolean
  allowShort: boolean
  allowOptions: boolean
  allowCrypto: boolean
  allowFutures: boolean
  maxPositionSizePct: number
  displayTimezone: string
  defaultRefreshMinutes: number
  watchlistOverride: number | null
  newsOverride: number | null
  newsLookbackHours: number
  newsMaxArticles: number
  showNews: boolean
  autoExpand: boolean
  scoreWeights: ScoreWeights
  technicalSubWeights: TechnicalSubWeights
  fundamentalSubWeights: FundamentalSubWeights
}

export const PRIMITIVE_FIELDS: Array<keyof EditablePreferences> = [
  'riskTolerance',
  'allowLong',
  'allowShort',
  'allowOptions',
  'allowCrypto',
  'allowFutures',
  'maxPositionSizePct',
  'displayTimezone',
  'defaultRefreshMinutes',
  'watchlistOverride',
  'newsOverride',
  'newsLookbackHours',
  'newsMaxArticles',
  'showNews',
  'autoExpand',
]

export const OBJECT_FIELDS: Array<keyof EditablePreferences> = [
  'scoreWeights',
  'technicalSubWeights',
  'fundamentalSubWeights',
]
