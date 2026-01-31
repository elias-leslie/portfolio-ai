import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { toast } from 'sonner'
import {
  DEFAULT_FUND_WEIGHTS,
  DEFAULT_SCORE_WEIGHTS,
  DEFAULT_TECH_WEIGHTS,
} from '@/components/settings/DEFAULTS'
import type {
  FundamentalSubWeights,
  PreferencesResponse,
  ScoreWeights,
  TechnicalSubWeights,
} from '@/lib/api/preferences'
import {
  usePreferences,
  useUpdatePreferences,
} from '@/lib/hooks/usePreferences'
import type { EditablePreferences } from './types'
import {
  buildEditableFromResponse,
  countEditableDifferences,
  deepEqual,
  describeRiskTolerance,
  editableToApiPayload,
  formatTimezoneLabel,
  mergeEditableIntoResponse,
  parsePositionSize,
} from './utils'

export const useSettingsState = () => {
  const { data: preferences, isLoading } = usePreferences()
  const updatePreferences = useUpdatePreferences()

  // Trading & Risk state
  const [riskTolerance, setRiskTolerance] = useState<number>(5)
  const [allowLong, setAllowLong] = useState(true)
  const [allowShort, setAllowShort] = useState(false)
  const [allowOptions, setAllowOptions] = useState(false)
  const [allowCrypto, setAllowCrypto] = useState(false)
  const [allowFutures, setAllowFutures] = useState(false)
  const [maxPositionSizePct, setMaxPositionSizePct] = useState<string>('20')

  // Display state
  const [displayTimezone, setDisplayTimezone] =
    useState<string>('America/New_York')

  // Watchlist state
  const [defaultRefreshMinutes, setDefaultRefreshMinutes] = useState(15)
  const [watchlistOverride, setWatchlistOverride] = useState<number | null>(
    null,
  )
  const [newsOverride, setNewsOverride] = useState<number | null>(null)
  const [newsLookbackHours, setNewsLookbackHours] = useState(24)
  const [newsMaxArticles, setNewsMaxArticles] = useState(10)
  const [showNews, setShowNews] = useState(true)
  const [autoExpand, setAutoExpand] = useState(false)
  const [scoreWeights, setScoreWeights] = useState<ScoreWeights>({
    ...DEFAULT_SCORE_WEIGHTS,
  })
  const [technicalSubWeights, setTechnicalSubWeights] =
    useState<TechnicalSubWeights>({
      ...DEFAULT_TECH_WEIGHTS,
    })
  const [fundamentalSubWeights, setFundamentalSubWeights] =
    useState<FundamentalSubWeights>({
      ...DEFAULT_FUND_WEIGHTS,
    })

  const applyEditable = useCallback((editable: EditablePreferences) => {
    setRiskTolerance(editable.riskTolerance)
    setAllowLong(editable.allowLong)
    setAllowShort(editable.allowShort)
    setAllowOptions(editable.allowOptions)
    setAllowCrypto(editable.allowCrypto)
    setAllowFutures(editable.allowFutures)
    setMaxPositionSizePct(editable.maxPositionSizePct.toString())
    setDisplayTimezone(editable.displayTimezone)
    setDefaultRefreshMinutes(editable.defaultRefreshMinutes)
    setWatchlistOverride(editable.watchlistOverride)
    setNewsOverride(editable.newsOverride)
    setNewsLookbackHours(editable.newsLookbackHours)
    setNewsMaxArticles(editable.newsMaxArticles)
    setShowNews(editable.showNews)
    setAutoExpand(editable.autoExpand)
    setScoreWeights({ ...editable.scoreWeights })
    setTechnicalSubWeights({ ...editable.technicalSubWeights })
    setFundamentalSubWeights({ ...editable.fundamentalSubWeights })
  }, [])

  // Update form state when preferences load
  useEffect(() => {
    if (!preferences) {
      return
    }

    startTransition(() => {
      applyEditable(buildEditableFromResponse(preferences))
    })
  }, [preferences, applyEditable])

  const currentEditable = useMemo<EditablePreferences>(
    () => ({
      riskTolerance,
      allowLong,
      allowShort,
      allowOptions,
      allowCrypto,
      allowFutures,
      maxPositionSizePct: parsePositionSize(maxPositionSizePct),
      displayTimezone,
      defaultRefreshMinutes,
      watchlistOverride,
      newsOverride,
      newsLookbackHours,
      newsMaxArticles,
      showNews,
      autoExpand,
      scoreWeights,
      technicalSubWeights,
      fundamentalSubWeights,
    }),
    [
      riskTolerance,
      allowLong,
      allowShort,
      allowOptions,
      allowCrypto,
      allowFutures,
      maxPositionSizePct,
      displayTimezone,
      defaultRefreshMinutes,
      watchlistOverride,
      newsOverride,
      newsLookbackHours,
      newsMaxArticles,
      showNews,
      autoExpand,
      scoreWeights,
      technicalSubWeights,
      fundamentalSubWeights,
    ],
  )

  const persistedEditable = useMemo(
    () => (preferences ? buildEditableFromResponse(preferences) : null),
    [preferences],
  )

  const hasChanges = persistedEditable
    ? !deepEqual(currentEditable, persistedEditable)
    : false
  const changeCount = persistedEditable
    ? countEditableDifferences(currentEditable, persistedEditable)
    : 0

  const enabledInstrumentCount = [
    currentEditable.allowLong,
    currentEditable.allowShort,
    currentEditable.allowOptions,
    currentEditable.allowCrypto,
    currentEditable.allowFutures,
  ].filter(Boolean).length

  const tradingSummary = [
    `Risk ${currentEditable.riskTolerance}/10 ${describeRiskTolerance(currentEditable.riskTolerance)}`,
    `Max ${currentEditable.maxPositionSizePct}%`,
    `${enabledInstrumentCount}/5 instruments`,
  ].join(' • ')

  const displaySummary = `TZ: ${formatTimezoneLabel(currentEditable.displayTimezone)}`

  const watchlistSummary = [
    `Refresh ${currentEditable.defaultRefreshMinutes}m`,
    `Lookback ${currentEditable.newsLookbackHours}h`,
    `${currentEditable.newsMaxArticles} headlines`,
    currentEditable.showNews ? 'News visible' : 'News hidden',
    currentEditable.autoExpand ? 'Auto-expand on' : 'Auto-expand off',
  ].join(' • ')

  // Validate weight totals
  const validateWeights = () => {
    const mainTotal =
      currentEditable.scoreWeights.price +
      currentEditable.scoreWeights.technical +
      currentEditable.scoreWeights.fundamental
    const techTotal =
      currentEditable.technicalSubWeights.rsi14 +
      currentEditable.technicalSubWeights.trend +
      currentEditable.technicalSubWeights.macd
    const fundTotal =
      currentEditable.fundamentalSubWeights.valuation +
      currentEditable.fundamentalSubWeights.growth +
      currentEditable.fundamentalSubWeights.health +
      currentEditable.fundamentalSubWeights.sentiment

    if (Math.abs(mainTotal - 100) > 0.1) {
      toast.error(
        'Main score weights (Price + Technical + Fundamental) must sum to 100%',
      )
      return false
    }
    if (Math.abs(techTotal - 100) > 0.1) {
      toast.error('Technical sub-weights (RSI + Trend + MACD) must sum to 100%')
      return false
    }
    if (Math.abs(fundTotal - 100) > 0.1) {
      toast.error(
        'Fundamental sub-weights (Valuation + Growth + Health + Sentiment) must sum to 100%',
      )
      return false
    }
    return true
  }

  // Handle save all
  const handleSaveAll = () => {
    if (!validateWeights()) {
      return
    }

    updatePreferences.mutate(editableToApiPayload(currentEditable), {
      onSuccess: () => {
        toast.success('Settings saved successfully!')
      },
      onError: (error) => {
        toast.error(`Failed to save settings: ${error.message}`)
      },
    })
  }

  // Handle reset all
  const handleResetAll = () => {
    if (preferences) {
      startTransition(() => {
        applyEditable(buildEditableFromResponse(preferences))
      })
    }
  }

  // Helper function to load profile data into form state
  const handleProfileLoad = (profileData: PreferencesResponse) => {
    startTransition(() => {
      applyEditable(buildEditableFromResponse(profileData))
    })
  }

  // Helper to get current preferences as object for profile saving
  const getCurrentPreferences = (): PreferencesResponse => {
    if (!preferences) {
      throw new Error('Preferences not loaded')
    }
    return mergeEditableIntoResponse(preferences, currentEditable)
  }

  return {
    // State
    riskTolerance,
    allowLong,
    allowShort,
    allowOptions,
    allowCrypto,
    allowFutures,
    maxPositionSizePct,
    displayTimezone,
    defaultRefreshMinutes,
    watchlistOverride,
    newsOverride,
    newsLookbackHours,
    newsMaxArticles,
    showNews,
    autoExpand,
    scoreWeights,
    technicalSubWeights,
    fundamentalSubWeights,

    // Setters
    setRiskTolerance,
    setAllowLong,
    setAllowShort,
    setAllowOptions,
    setAllowCrypto,
    setAllowFutures,
    setMaxPositionSizePct,
    setDisplayTimezone,
    setDefaultRefreshMinutes,
    setWatchlistOverride,
    setNewsOverride,
    setNewsLookbackHours,
    setNewsMaxArticles,
    setShowNews,
    setAutoExpand,
    setScoreWeights,
    setTechnicalSubWeights,
    setFundamentalSubWeights,

    // Computed values
    hasChanges,
    changeCount,
    tradingSummary,
    displaySummary,
    watchlistSummary,

    // Handlers
    handleSaveAll,
    handleResetAll,
    handleProfileLoad,
    getCurrentPreferences,

    // Meta
    preferences,
    isLoading,
    isPending: updatePreferences.isPending,
  }
}
