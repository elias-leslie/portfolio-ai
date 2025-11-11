"use client";

import { useState, useEffect, startTransition } from "react";
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
    price: 33,
    technical: 33,
    fundamental: 34,
  });
  const [technicalSubWeights, setTechnicalSubWeights] =
    useState<TechnicalSubWeights>({
      rsi_14: 33,
      trend: 34,
      macd: 33,
    });
  const [fundamentalSubWeights, setFundamentalSubWeights] =
    useState<FundamentalSubWeights>({
      valuation: 30,
      growth: 35,
      health: 25,
      sentiment: 10,
    });

  // Update form state when preferences load
  useEffect(() => {
    if (!preferences) {
      return;
    }

    startTransition(() => {
      // Trading & Risk
      setRiskTolerance(preferences.risk_tolerance);
      setAllowLong(preferences.allow_long);
      setAllowShort(preferences.allow_short);
      setAllowOptions(preferences.allow_options);
      setAllowCrypto(preferences.allow_crypto);
      setAllowFutures(preferences.allow_futures);
      setMaxPositionSizePct(preferences.max_position_size_pct.toString());

      // Display
      setDisplayTimezone(preferences.display_timezone);

      // Watchlist
      setDefaultRefreshMinutes(preferences.default_refresh_minutes);
      setWatchlistOverride(preferences.watchlist_refresh_override);
      setNewsOverride(preferences.news_refresh_override);
      setNewsLookbackHours(preferences.news_lookback_hours);
      setNewsMaxArticles(preferences.news_max_articles);
      setShowNews(preferences.watchlist_show_news);
      setAutoExpand(preferences.watchlist_auto_expand);
      setScoreWeights(
        preferences.watchlist_score_weights ?? {
          price: 33,
          technical: 33,
          fundamental: 34,
        }
      );
      setTechnicalSubWeights(
        preferences.technical_sub_weights ?? {
          rsi_14: 33,
          trend: 34,
          macd: 33,
        }
      );
      setFundamentalSubWeights(
        preferences.fundamental_sub_weights ?? {
          valuation: 30,
          growth: 35,
          health: 25,
          sentiment: 10,
        }
      );
    });
  }, [preferences]);

  // Check if form has changed from saved preferences
  const hasChanges = () => {
    if (!preferences) return false;
    return (
      riskTolerance !== preferences.risk_tolerance ||
      allowLong !== preferences.allow_long ||
      allowShort !== preferences.allow_short ||
      allowOptions !== preferences.allow_options ||
      allowCrypto !== preferences.allow_crypto ||
      allowFutures !== preferences.allow_futures ||
      parseFloat(maxPositionSizePct) !== preferences.max_position_size_pct ||
      displayTimezone !== preferences.display_timezone ||
      defaultRefreshMinutes !== preferences.default_refresh_minutes ||
      watchlistOverride !== preferences.watchlist_refresh_override ||
      newsOverride !== preferences.news_refresh_override ||
      newsLookbackHours !== preferences.news_lookback_hours ||
      newsMaxArticles !== preferences.news_max_articles ||
      showNews !== preferences.watchlist_show_news ||
      autoExpand !== preferences.watchlist_auto_expand ||
      JSON.stringify(scoreWeights) !==
        JSON.stringify(
          preferences.watchlist_score_weights ?? {
            price: 33,
            technical: 33,
            fundamental: 34,
          }
        ) ||
      JSON.stringify(technicalSubWeights) !==
        JSON.stringify(
          preferences.technical_sub_weights ?? {
            rsi_14: 33,
            trend: 34,
            macd: 33,
          }
        ) ||
      JSON.stringify(fundamentalSubWeights) !==
        JSON.stringify(
          preferences.fundamental_sub_weights ?? {
            valuation: 30,
            growth: 35,
            health: 25,
            sentiment: 10,
          }
        )
    );
  };

  // Count number of changes
  const countChanges = () => {
    if (!preferences) return 0;
    let count = 0;
    if (riskTolerance !== preferences.risk_tolerance) count++;
    if (allowLong !== preferences.allow_long) count++;
    if (allowShort !== preferences.allow_short) count++;
    if (allowOptions !== preferences.allow_options) count++;
    if (allowCrypto !== preferences.allow_crypto) count++;
    if (allowFutures !== preferences.allow_futures) count++;
    if (parseFloat(maxPositionSizePct) !== preferences.max_position_size_pct)
      count++;
    if (displayTimezone !== preferences.display_timezone) count++;
    if (defaultRefreshMinutes !== preferences.default_refresh_minutes) count++;
    if (watchlistOverride !== preferences.watchlist_refresh_override) count++;
    if (newsOverride !== preferences.news_refresh_override) count++;
    if (newsLookbackHours !== preferences.news_lookback_hours) count++;
    if (newsMaxArticles !== preferences.news_max_articles) count++;
    if (showNews !== preferences.watchlist_show_news) count++;
    if (autoExpand !== preferences.watchlist_auto_expand) count++;
    if (
      JSON.stringify(scoreWeights) !==
      JSON.stringify(
        preferences.watchlist_score_weights ?? {
          price: 33,
          technical: 33,
          fundamental: 34,
        }
      )
    )
      count++;
    if (
      JSON.stringify(technicalSubWeights) !==
      JSON.stringify(
        preferences.technical_sub_weights ?? {
          rsi_14: 33,
          trend: 34,
          macd: 33,
        }
      )
    )
      count++;
    if (
      JSON.stringify(fundamentalSubWeights) !==
      JSON.stringify(
        preferences.fundamental_sub_weights ?? {
          valuation: 30,
          growth: 35,
          health: 25,
          sentiment: 10,
        }
      )
    )
      count++;
    return count;
  };

  // Validate weight totals
  const validateWeights = () => {
    const mainTotal = scoreWeights.price + scoreWeights.technical + scoreWeights.fundamental;
    const techTotal = technicalSubWeights.rsi_14 + technicalSubWeights.trend + technicalSubWeights.macd;
    const fundTotal =
      fundamentalSubWeights.valuation +
      fundamentalSubWeights.growth +
      fundamentalSubWeights.health +
      fundamentalSubWeights.sentiment;

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
      {
        // Trading & Risk
        risk_tolerance: riskTolerance,
        allow_long: allowLong,
        allow_short: allowShort,
        allow_options: allowOptions,
        allow_crypto: allowCrypto,
        allow_futures: allowFutures,
        max_position_size_pct: parseFloat(maxPositionSizePct),
        // Display
        display_timezone: displayTimezone,
        // Watchlist
        default_refresh_minutes: defaultRefreshMinutes,
        watchlist_refresh_override: watchlistOverride,
        news_refresh_override: newsOverride,
        news_lookback_hours: newsLookbackHours,
        news_max_articles: newsMaxArticles,
        watchlist_show_news: showNews,
        watchlist_auto_expand: autoExpand,
        watchlist_score_weights: scoreWeights,
        price_sub_weights: { change_pct: 100 },
        technical_sub_weights: technicalSubWeights,
        fundamental_sub_weights: fundamentalSubWeights,
      },
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
        // Trading & Risk
        setRiskTolerance(preferences.risk_tolerance);
        setAllowLong(preferences.allow_long);
        setAllowShort(preferences.allow_short);
        setAllowOptions(preferences.allow_options);
        setAllowCrypto(preferences.allow_crypto);
        setAllowFutures(preferences.allow_futures);
        setMaxPositionSizePct(preferences.max_position_size_pct.toString());
        // Display
        setDisplayTimezone(preferences.display_timezone);
        // Watchlist
        setDefaultRefreshMinutes(preferences.default_refresh_minutes);
        setWatchlistOverride(preferences.watchlist_refresh_override);
        setNewsOverride(preferences.news_refresh_override);
        setNewsLookbackHours(preferences.news_lookback_hours);
        setNewsMaxArticles(preferences.news_max_articles);
        setShowNews(preferences.watchlist_show_news);
        setAutoExpand(preferences.watchlist_auto_expand);
        setScoreWeights(
          preferences.watchlist_score_weights ?? {
            price: 33,
            technical: 33,
            fundamental: 34,
          }
        );
        setTechnicalSubWeights(
          preferences.technical_sub_weights ?? {
            rsi_14: 33,
            trend: 34,
            macd: 33,
          }
        );
        setFundamentalSubWeights(
          preferences.fundamental_sub_weights ?? {
            valuation: 30,
            growth: 35,
            health: 25,
            sentiment: 10,
          }
        );
      });
    }
  };

  if (isLoading) {
    return (
      <div className="bg-bg">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="animate-pulse space-y-6">
            <div className="h-9 w-48 rounded-md bg-surface-muted/60" />
            <div className="h-4 w-80 rounded-md bg-surface-muted/60" />
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-64 rounded-lg bg-surface-muted/60" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Helper function to load profile data into form state
  const handleProfileLoad = (profileData: PreferencesResponse) => {
    startTransition(() => {
      // Trading & Risk
      setRiskTolerance(profileData.risk_tolerance);
      setAllowLong(profileData.allow_long);
      setAllowShort(profileData.allow_short);
      setAllowOptions(profileData.allow_options);
      setAllowCrypto(profileData.allow_crypto);
      setAllowFutures(profileData.allow_futures);
      setMaxPositionSizePct(profileData.max_position_size_pct.toString());
      // Display
      setDisplayTimezone(profileData.display_timezone);
      // Watchlist
      setDefaultRefreshMinutes(profileData.default_refresh_minutes);
      setWatchlistOverride(profileData.watchlist_refresh_override);
      setNewsOverride(profileData.news_refresh_override);
      setNewsLookbackHours(profileData.news_lookback_hours);
      setNewsMaxArticles(profileData.news_max_articles);
      setShowNews(profileData.watchlist_show_news);
      setAutoExpand(profileData.watchlist_auto_expand);
      setScoreWeights(
        profileData.watchlist_score_weights ?? {
          price: 33,
          technical: 33,
          fundamental: 34,
        }
      );
      setTechnicalSubWeights(
        profileData.technical_sub_weights ?? {
          rsi_14: 33,
          trend: 34,
          macd: 33,
        }
      );
      setFundamentalSubWeights(
        profileData.fundamental_sub_weights ?? {
          valuation: 30,
          growth: 35,
          health: 25,
          sentiment: 10,
        }
      );
    });
  };

  // Helper to get current preferences as object for profile saving
  const getCurrentPreferences = (): PreferencesResponse => ({
    ...preferences!,
    risk_tolerance: riskTolerance,
    allow_long: allowLong,
    allow_short: allowShort,
    allow_options: allowOptions,
    allow_crypto: allowCrypto,
    allow_futures: allowFutures,
    max_position_size_pct: parseFloat(maxPositionSizePct),
    display_timezone: displayTimezone,
    default_refresh_minutes: defaultRefreshMinutes,
    watchlist_refresh_override: watchlistOverride,
    news_refresh_override: newsOverride,
    news_lookback_hours: newsLookbackHours,
    news_max_articles: newsMaxArticles,
    watchlist_show_news: showNews,
    watchlist_auto_expand: autoExpand,
    watchlist_score_weights: scoreWeights,
    technical_sub_weights: technicalSubWeights,
    fundamental_sub_weights: fundamentalSubWeights,
  });

  return (
    <div className="bg-bg pb-24">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-semibold text-text">Settings</h1>
          <p className="mt-2 text-sm text-text-muted">
            Configure your preferences, risk tolerance, and system behavior
          </p>
        </div>

        <div className="space-y-12">
          {/* Profile Selector */}
          {preferences && (
            <ProfileSelector
              currentPreferences={getCurrentPreferences()}
              onProfileLoad={handleProfileLoad}
            />
          )}

          {/* Trading & Risk Settings */}
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

          {/* Display Settings */}
          <DisplaySettings
            displayTimezone={displayTimezone}
            onDisplayTimezoneChange={setDisplayTimezone}
          />

          {/* Watchlist Settings */}
          <WatchlistSettingsSection
            defaultRefreshMinutes={defaultRefreshMinutes}
            watchlistOverride={watchlistOverride}
            newsOverride={newsOverride}
            newsLookbackHours={newsLookbackHours}
            newsMaxArticles={newsMaxArticles}
            frontendPollInterval={preferences?.frontend_poll_interval ?? 30}
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
        </div>
      </div>

      {/* Unified Save Bar */}
      <SaveBar
        hasChanges={hasChanges()}
        onSave={handleSaveAll}
        onReset={handleResetAll}
        isPending={updatePreferences.isPending}
        changeCount={countChanges()}
      />
    </div>
  );
}
