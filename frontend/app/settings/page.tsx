"use client";

import { useState, useEffect, startTransition, useMemo, useCallback } from "react";
import {
  usePreferences,
  useUpdatePreferences,
} from "@/lib/hooks/usePreferences";
import { toast } from "sonner";
import { SaveBar } from "@/components/settings/SaveBar";
import { ProfileSelector } from "@/components/settings/ProfileSelector";
import { TradingRiskSettings } from "@/components/settings/sections/TradingRiskSettings";
import { DisplaySettings } from "@/components/settings/sections/DisplaySettings";
import { WatchlistSettingsSection } from "@/components/settings/sections/WatchlistSettingsSection";
import type {
  PreferencesResponse,
  ScoreWeights,
  TechnicalSubWeights,
  FundamentalSubWeights,
} from "@/lib/api/preferences";
import { PageHeader } from "@/components/shared/PageHeader";
import {
  DEFAULT_SCORE_WEIGHTS,
  DEFAULT_TECH_WEIGHTS,
  DEFAULT_FUND_WEIGHTS,
} from "@/components/settings/DEFAULTS";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { TIMEZONE_OPTIONS } from "@/components/settings/sections/DisplaySettings";

const PRICE_SUB_WEIGHTS = { change_pct: 100 } as const;

type EditablePreferences = {
  riskTolerance: number;
  allowLong: boolean;
  allowShort: boolean;
  allowOptions: boolean;
  allowCrypto: boolean;
  allowFutures: boolean;
  maxPositionSizePct: number;
  displayTimezone: string;
  defaultRefreshMinutes: number;
  watchlistOverride: number | null;
  newsOverride: number | null;
  newsLookbackHours: number;
  newsMaxArticles: number;
  showNews: boolean;
  autoExpand: boolean;
  scoreWeights: ScoreWeights;
  technicalSubWeights: TechnicalSubWeights;
  fundamentalSubWeights: FundamentalSubWeights;
};

const PRIMITIVE_FIELDS: Array<keyof EditablePreferences> = [
  "riskTolerance",
  "allowLong",
  "allowShort",
  "allowOptions",
  "allowCrypto",
  "allowFutures",
  "maxPositionSizePct",
  "displayTimezone",
  "defaultRefreshMinutes",
  "watchlistOverride",
  "newsOverride",
  "newsLookbackHours",
  "newsMaxArticles",
  "showNews",
  "autoExpand",
];

const OBJECT_FIELDS: Array<keyof EditablePreferences> = [
  "scoreWeights",
  "technicalSubWeights",
  "fundamentalSubWeights",
];

const ensureScoreWeights = (weights?: ScoreWeights | null): ScoreWeights => ({
  price: weights?.price ?? DEFAULT_SCORE_WEIGHTS.price,
  technical: weights?.technical ?? DEFAULT_SCORE_WEIGHTS.technical,
  fundamental: weights?.fundamental ?? DEFAULT_SCORE_WEIGHTS.fundamental,
});

const ensureTechnicalWeights = (
  weights?: TechnicalSubWeights | null,
): TechnicalSubWeights => ({
  rsi_14: weights?.rsi_14 ?? DEFAULT_TECH_WEIGHTS.rsi_14,
  trend: weights?.trend ?? DEFAULT_TECH_WEIGHTS.trend,
  macd: weights?.macd ?? DEFAULT_TECH_WEIGHTS.macd,
});

const ensureFundamentalWeights = (
  weights?: FundamentalSubWeights | null,
): FundamentalSubWeights => ({
  valuation: weights?.valuation ?? DEFAULT_FUND_WEIGHTS.valuation,
  growth: weights?.growth ?? DEFAULT_FUND_WEIGHTS.growth,
  health: weights?.health ?? DEFAULT_FUND_WEIGHTS.health,
  sentiment: weights?.sentiment ?? DEFAULT_FUND_WEIGHTS.sentiment,
});

const parsePositionSize = (value: string) => {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const describeRiskTolerance = (value: number) => {
  if (value <= 3) return "Conservative";
  if (value >= 8) return "Aggressive";
  return "Moderate";
};

const formatTimezoneLabel = (timezone: string) =>
  TIMEZONE_OPTIONS[timezone as keyof typeof TIMEZONE_OPTIONS] ?? timezone;

const buildEditableFromResponse = (
  prefs: PreferencesResponse,
): EditablePreferences => ({
  riskTolerance: prefs.risk_tolerance,
  allowLong: prefs.allow_long,
  allowShort: prefs.allow_short,
  allowOptions: prefs.allow_options,
  allowCrypto: prefs.allow_crypto,
  allowFutures: prefs.allow_futures,
  maxPositionSizePct: prefs.max_position_size_pct,
  displayTimezone: prefs.display_timezone,
  defaultRefreshMinutes: prefs.default_refresh_minutes,
  watchlistOverride: prefs.watchlist_refresh_override,
  newsOverride: prefs.news_refresh_override,
  newsLookbackHours: prefs.news_lookback_hours,
  newsMaxArticles: prefs.news_max_articles,
  showNews: prefs.watchlist_show_news,
  autoExpand: prefs.watchlist_auto_expand,
  scoreWeights: ensureScoreWeights(prefs.watchlist_score_weights),
  technicalSubWeights: ensureTechnicalWeights(prefs.technical_sub_weights),
  fundamentalSubWeights: ensureFundamentalWeights(prefs.fundamental_sub_weights),
});

const editableToApiPayload = (editable: EditablePreferences) => ({
  risk_tolerance: editable.riskTolerance,
  allow_long: editable.allowLong,
  allow_short: editable.allowShort,
  allow_options: editable.allowOptions,
  allow_crypto: editable.allowCrypto,
  allow_futures: editable.allowFutures,
  max_position_size_pct: editable.maxPositionSizePct,
  display_timezone: editable.displayTimezone,
  default_refresh_minutes: editable.defaultRefreshMinutes,
  watchlist_refresh_override: editable.watchlistOverride,
  news_refresh_override: editable.newsOverride,
  news_lookback_hours: editable.newsLookbackHours,
  news_max_articles: editable.newsMaxArticles,
  watchlist_show_news: editable.showNews,
  watchlist_auto_expand: editable.autoExpand,
  watchlist_score_weights: editable.scoreWeights,
  price_sub_weights: PRICE_SUB_WEIGHTS,
  technical_sub_weights: editable.technicalSubWeights,
  fundamental_sub_weights: editable.fundamentalSubWeights,
});

const mergeEditableIntoResponse = (
  base: PreferencesResponse,
  editable: EditablePreferences,
): PreferencesResponse => ({
  ...base,
  ...editableToApiPayload(editable),
});

const deepEqual = <T,>(a: T, b: T) => JSON.stringify(a) === JSON.stringify(b);

const countEditableDifferences = (
  current: EditablePreferences,
  baseline: EditablePreferences,
) => {
  let count = 0;
  for (const key of PRIMITIVE_FIELDS) {
    if (current[key] !== baseline[key]) {
      count += 1;
    }
  }
  for (const key of OBJECT_FIELDS) {
    if (!deepEqual(current[key], baseline[key])) {
      count += 1;
    }
  }
  return count;
};

import { PageContainer } from "@/components/shared/PageContainer";

export default function SettingsPage() {
  const { data: preferences, isLoading } = usePreferences();
  const updatePreferences = useUpdatePreferences();

  // Trading & Risk state
  const [riskTolerance, setRiskTolerance] = useState<number>(5);
  const [allowLong, setAllowLong] = useState(true);
  const [allowShort, setAllowShort] = useState(false);
  const [allowOptions, setAllowOptions] = useState(false);
  const [allowCrypto, setAllowCrypto] = useState(false);
  const [allowFutures, setAllowFutures] = useState(false);
  const [maxPositionSizePct, setMaxPositionSizePct] = useState<string>("20");

  // Display state
  const [displayTimezone, setDisplayTimezone] =
    useState<string>("America/New_York");

  // Watchlist state
  const [defaultRefreshMinutes, setDefaultRefreshMinutes] = useState(15);
  const [watchlistOverride, setWatchlistOverride] = useState<number | null>(null);
  const [newsOverride, setNewsOverride] = useState<number | null>(null);
  const [newsLookbackHours, setNewsLookbackHours] = useState(24);
  const [newsMaxArticles, setNewsMaxArticles] = useState(10);
  const [showNews, setShowNews] = useState(true);
  const [autoExpand, setAutoExpand] = useState(false);
  const [scoreWeights, setScoreWeights] = useState<ScoreWeights>({
    ...DEFAULT_SCORE_WEIGHTS,
  });
  const [technicalSubWeights, setTechnicalSubWeights] =
    useState<TechnicalSubWeights>({ ...DEFAULT_TECH_WEIGHTS });
  const [fundamentalSubWeights, setFundamentalSubWeights] =
    useState<FundamentalSubWeights>({ ...DEFAULT_FUND_WEIGHTS });

  const applyEditable = useCallback((editable: EditablePreferences) => {
    setRiskTolerance(editable.riskTolerance);
    setAllowLong(editable.allowLong);
    setAllowShort(editable.allowShort);
    setAllowOptions(editable.allowOptions);
    setAllowCrypto(editable.allowCrypto);
    setAllowFutures(editable.allowFutures);
    setMaxPositionSizePct(editable.maxPositionSizePct.toString());
    setDisplayTimezone(editable.displayTimezone);
    setDefaultRefreshMinutes(editable.defaultRefreshMinutes);
    setWatchlistOverride(editable.watchlistOverride);
    setNewsOverride(editable.newsOverride);
    setNewsLookbackHours(editable.newsLookbackHours);
    setNewsMaxArticles(editable.newsMaxArticles);
    setShowNews(editable.showNews);
    setAutoExpand(editable.autoExpand);
    setScoreWeights({ ...editable.scoreWeights });
    setTechnicalSubWeights({ ...editable.technicalSubWeights });
    setFundamentalSubWeights({ ...editable.fundamentalSubWeights });
  }, []);

  // Update form state when preferences load
  useEffect(() => {
    if (!preferences) {
      return;
    }

    startTransition(() => {
      applyEditable(buildEditableFromResponse(preferences));
    });
  }, [preferences, applyEditable]);

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
  );

  const persistedEditable = useMemo(
    () => (preferences ? buildEditableFromResponse(preferences) : null),
    [preferences],
  );

  const hasChanges = persistedEditable
    ? !deepEqual(currentEditable, persistedEditable)
    : false;
  const changeCount = persistedEditable
    ? countEditableDifferences(currentEditable, persistedEditable)
    : 0;

  const enabledInstrumentCount = [
    currentEditable.allowLong,
    currentEditable.allowShort,
    currentEditable.allowOptions,
    currentEditable.allowCrypto,
    currentEditable.allowFutures,
  ].filter(Boolean).length;

  const tradingSummary = [
    `Risk ${currentEditable.riskTolerance}/10 ${describeRiskTolerance(currentEditable.riskTolerance)}`,
    `Max ${currentEditable.maxPositionSizePct}%`,
    `${enabledInstrumentCount}/5 instruments`,
  ].join(" • ");

  const displaySummary = `TZ: ${formatTimezoneLabel(currentEditable.displayTimezone)}`;

  const watchlistSummary = [
    `Refresh ${currentEditable.defaultRefreshMinutes}m`,
    `Lookback ${currentEditable.newsLookbackHours}h`,
    `${currentEditable.newsMaxArticles} headlines`,
    currentEditable.showNews ? "News visible" : "News hidden",
    currentEditable.autoExpand ? "Auto-expand on" : "Auto-expand off",
  ].join(" • ");

  // Validate weight totals
  const validateWeights = () => {
    const mainTotal =
      currentEditable.scoreWeights.price +
      currentEditable.scoreWeights.technical +
      currentEditable.scoreWeights.fundamental;
    const techTotal =
      currentEditable.technicalSubWeights.rsi_14 +
      currentEditable.technicalSubWeights.trend +
      currentEditable.technicalSubWeights.macd;
    const fundTotal =
      currentEditable.fundamentalSubWeights.valuation +
      currentEditable.fundamentalSubWeights.growth +
      currentEditable.fundamentalSubWeights.health +
      currentEditable.fundamentalSubWeights.sentiment;

    if (Math.abs(mainTotal - 100) > 0.1) {
      toast.error(
        "Main score weights (Price + Technical + Fundamental) must sum to 100%"
      );
      return false;
    }
    if (Math.abs(techTotal - 100) > 0.1) {
      toast.error("Technical sub-weights (RSI + Trend + MACD) must sum to 100%");
      return false;
    }
    if (Math.abs(fundTotal - 100) > 0.1) {
      toast.error(
        "Fundamental sub-weights (Valuation + Growth + Health + Sentiment) must sum to 100%"
      );
      return false;
    }
    return true;
  };

  // Handle save all
  const handleSaveAll = () => {
    if (!validateWeights()) {
      return;
    }

    updatePreferences.mutate(
      editableToApiPayload(currentEditable),
      {
        onSuccess: () => {
          toast.success("Settings saved successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to save settings: ${error.message}`);
        },
      }
    );
  };

  // Handle reset all
  const handleResetAll = () => {
    if (preferences) {
      startTransition(() => {
        applyEditable(buildEditableFromResponse(preferences));
      });
    }
  };

  if (isLoading) {
    return (
      <PageContainer className="max-w-6xl space-y-12 py-10" fullWidth>
        <div className="animate-pulse space-y-6">
          <div className="h-9 w-48 rounded-md bg-surface-muted/60" />
          <div className="h-4 w-80 rounded-md bg-surface-muted/60" />
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-64 rounded-lg bg-surface-muted/60" />
            ))}
          </div>
        </div>
      </PageContainer>
    );
  }

  // Helper function to load profile data into form state
  const handleProfileLoad = (profileData: PreferencesResponse) => {
    startTransition(() => {
      applyEditable(buildEditableFromResponse(profileData));
    });
  };

  // Helper to get current preferences as object for profile saving
  const getCurrentPreferences = (): PreferencesResponse => {
    if (!preferences) {
      throw new Error("Preferences not loaded");
    }
    return mergeEditableIntoResponse(preferences, currentEditable);
  };

  return (
    <PageContainer className="max-w-6xl space-y-12 py-10 pb-24" fullWidth>
      <PageHeader
        title="Settings"
        description="Configure your preferences, risk tolerance, and system behavior."
        size="md"
      />

      <div className="space-y-8">
        {preferences && (
          <SettingsSection
            title="Profiles"
            description="Save and reuse preference sets for different strategies."
            summary="Import, export, and activate saved profiles"
            defaultCollapsed={false}
          >
            <ProfileSelector
              variant="plain"
              currentPreferences={getCurrentPreferences()}
              onProfileLoad={handleProfileLoad}
            />
          </SettingsSection>
        )}

        <SettingsSection
          title="Trading & Risk"
          description="Control the instruments, position sizing, and risk tolerance available to AI agents."
          summary={tradingSummary}
        >
          <TradingRiskSettings
            riskTolerance={riskTolerance}
            maxPositionSizePct={maxPositionSizePct}
            allowLong={allowLong}
            allowShort={allowShort}
            allowOptions={allowOptions}
            allowCrypto={allowCrypto}
            allowFutures={allowFutures}
            onRiskToleranceChange={setRiskTolerance}
            onMaxPositionSizePctChange={setMaxPositionSizePct}
            onAllowLongChange={setAllowLong}
            onAllowShortChange={setAllowShort}
            onAllowOptionsChange={setAllowOptions}
            onAllowCryptoChange={setAllowCrypto}
            onAllowFuturesChange={setAllowFutures}
          />
        </SettingsSection>

        <SettingsSection
          title="Display & Interface"
          description="Choose your preferred timezone."
          summary={displaySummary}
        >
          <DisplaySettings
            displayTimezone={displayTimezone}
            onDisplayTimezoneChange={setDisplayTimezone}
          />
        </SettingsSection>

        <SettingsSection
          title="Watchlist & Scoring"
          description="Tune refresh cadence, news visibility, and scoring weights for watchlist insights."
          summary={watchlistSummary}
        >
          <WatchlistSettingsSection
            defaultRefreshMinutes={defaultRefreshMinutes}
            watchlistOverride={watchlistOverride}
            newsOverride={newsOverride}
            newsLookbackHours={newsLookbackHours}
            newsMaxArticles={newsMaxArticles}
            showNews={showNews}
            autoExpand={autoExpand}
            scoreWeights={scoreWeights}
            technicalSubWeights={technicalSubWeights}
            fundamentalSubWeights={fundamentalSubWeights}
            onDefaultRefreshMinutesChange={setDefaultRefreshMinutes}
            onWatchlistOverrideChange={setWatchlistOverride}
            onNewsOverrideChange={setNewsOverride}
            onNewsLookbackHoursChange={setNewsLookbackHours}
            onNewsMaxArticlesChange={setNewsMaxArticles}
            onShowNewsChange={setShowNews}
            onAutoExpandChange={setAutoExpand}
            onScoreWeightsChange={setScoreWeights}
            onTechnicalSubWeightsChange={setTechnicalSubWeights}
            onFundamentalSubWeightsChange={setFundamentalSubWeights}
          />
        </SettingsSection>
      </div>

      {/* Unified Save Bar */}
      <SaveBar
        hasChanges={hasChanges}
        onSave={handleSaveAll}
        onReset={handleResetAll}
        isPending={updatePreferences.isPending}
        changeCount={changeCount}
      />
    </PageContainer>
  );
}
