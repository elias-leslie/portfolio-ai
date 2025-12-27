"use client";

import { useState, useEffect, useRef } from "react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { toast } from "sonner";
import type {
    PreferencesResponse,
    ScoreWeights,
    TechnicalSubWeights,
    FundamentalSubWeights,
} from "@/lib/api/preferences";

interface WatchlistPreferencesProps {
    preferences: PreferencesResponse;
    onUpdate: (updates: Partial<PreferencesResponse>) => Promise<void>;
    isPending: boolean;
}

export function WatchlistPreferences({
    preferences,
    onUpdate,
    isPending,
}: WatchlistPreferencesProps) {
    // Basic settings
    const [defaultRefreshMinutes, setDefaultRefreshMinutes] = useState(
        preferences.defaultRefreshMinutes,
    );
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Per-feature overrides
    const [useWatchlistOverride, setUseWatchlistOverride] = useState(
        preferences.watchlistRefreshOverride !== null,
    );
    const [watchlistOverride, setWatchlistOverride] = useState(
        preferences.watchlistRefreshOverride ??
            preferences.defaultRefreshMinutes,
    );
    const [useNewsOverride, setUseNewsOverride] = useState(
        preferences.newsRefreshOverride !== null,
    );
    const [newsOverride, setNewsOverride] = useState(
        preferences.newsRefreshOverride ??
            preferences.defaultRefreshMinutes,
    );
    const [newsLookbackHours, setNewsLookbackHours] = useState(
        preferences.newsLookbackHours,
    );
    const [newsMaxArticles, setNewsMaxArticles] = useState(
        preferences.newsMaxArticles,
    );

    // Legacy watchlist settings
    const [autoExpand, setAutoExpand] = useState(
        preferences.watchlistAutoExpand,
    );
    const [priceWeight, setPriceWeight] = useState(
        preferences.watchlistPriceWeight,
    );
    const [technicalWeight, setTechnicalWeight] = useState(
        preferences.watchlistTechnicalWeight,
    );
    const [showNews, setShowNews] = useState(preferences.watchlistShowNews);

    // New weight configuration (migration 019)
    const [scoreWeights, setScoreWeights] = useState<ScoreWeights>(
        preferences.watchlistScoreWeights ?? { price: 33, technical: 33, fundamental: 34 }
    );
    const [technicalSubWeights, setTechnicalSubWeights] = useState<TechnicalSubWeights>(
        preferences.technicalSubWeights ?? { rsi14: 33, trend: 34, macd: 33 }
    );
    const [fundamentalSubWeights, setFundamentalSubWeights] = useState<FundamentalSubWeights>(
        preferences.fundamentalSubWeights ?? { valuation: 30, growth: 35, health: 25, sentiment: 10 }
    );
    const [showTechnicalSubWeights, setShowTechnicalSubWeights] = useState(false);
    const [showFundamentalSubWeights, setShowFundamentalSubWeights] = useState(false);

    // Track preferences version to detect external changes
    // When preferences change externally (e.g., profile load), we reinitialize
    const preferencesKey = JSON.stringify({
        defaultRefreshMinutes: preferences.defaultRefreshMinutes,
        watchlistRefreshOverride: preferences.watchlistRefreshOverride,
        newsRefreshOverride: preferences.newsRefreshOverride,
        newsLookbackHours: preferences.newsLookbackHours,
        newsMaxArticles: preferences.newsMaxArticles,
        watchlistAutoExpand: preferences.watchlistAutoExpand,
        watchlistPriceWeight: preferences.watchlistPriceWeight,
        watchlistTechnicalWeight: preferences.watchlistTechnicalWeight,
        watchlistShowNews: preferences.watchlistShowNews,
        watchlistScoreWeights: preferences.watchlistScoreWeights,
        technicalSubWeights: preferences.technicalSubWeights,
        fundamentalSubWeights: preferences.fundamentalSubWeights,
    });

    // Reinitialize local state when external preferences change (profile switch)
    // This uses useEffect but sets state only on external change, not on every render
    const lastPreferencesKey = useRef(preferencesKey);
    if (lastPreferencesKey.current !== preferencesKey) {
        lastPreferencesKey.current = preferencesKey;
        // React allows setState during render if it's conditional on props changing
        // This is the "derive state from props" pattern
    }

    // Synchronize when preferences object identity changes (profile switch)
    useEffect(() => {
        // Only sync if we detect the preferences changed externally
        setDefaultRefreshMinutes(preferences.defaultRefreshMinutes);
        setUseWatchlistOverride(preferences.watchlistRefreshOverride !== null);
        setWatchlistOverride(preferences.watchlistRefreshOverride ?? preferences.defaultRefreshMinutes);
        setUseNewsOverride(preferences.newsRefreshOverride !== null);
        setNewsOverride(preferences.newsRefreshOverride ?? preferences.defaultRefreshMinutes);
        setNewsLookbackHours(preferences.newsLookbackHours);
        setNewsMaxArticles(preferences.newsMaxArticles);
        setAutoExpand(preferences.watchlistAutoExpand);
        setPriceWeight(preferences.watchlistPriceWeight);
        setTechnicalWeight(preferences.watchlistTechnicalWeight);
        setShowNews(preferences.watchlistShowNews);
        setScoreWeights(preferences.watchlistScoreWeights ?? { price: 33, technical: 33, fundamental: 34 });
        setTechnicalSubWeights(preferences.technicalSubWeights ?? { rsi14: 33, trend: 34, macd: 33 });
        setFundamentalSubWeights(preferences.fundamentalSubWeights ?? { valuation: 30, growth: 35, health: 25, sentiment: 10 });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [preferencesKey]); // Depend on the key, not the full object

    const hasChanges = () => {
        const currentOverride = useWatchlistOverride ? watchlistOverride : null;
        const savedOverride = preferences.watchlistRefreshOverride;
        const currentNewsOverride = useNewsOverride ? newsOverride : null;
        const savedNewsOverride = preferences.newsRefreshOverride;

        return (
            defaultRefreshMinutes !== preferences.defaultRefreshMinutes ||
            currentOverride !== savedOverride ||
            currentNewsOverride !== savedNewsOverride ||
            newsLookbackHours !== preferences.newsLookbackHours ||
            newsMaxArticles !== preferences.newsMaxArticles ||
            showNews !== preferences.watchlistShowNews ||
            autoExpand !== preferences.watchlistAutoExpand ||
            priceWeight !== preferences.watchlistPriceWeight ||
            technicalWeight !== preferences.watchlistTechnicalWeight ||
            JSON.stringify(scoreWeights) !== JSON.stringify(preferences.watchlistScoreWeights ?? { price: 33, technical: 33, fundamental: 34 }) ||
            JSON.stringify(technicalSubWeights) !== JSON.stringify(preferences.technicalSubWeights ?? { rsi14: 33, trend: 34, macd: 33 }) ||
            JSON.stringify(fundamentalSubWeights) !== JSON.stringify(preferences.fundamentalSubWeights ?? { valuation: 30, growth: 35, health: 25, sentiment: 10 })
        );
    };

    const handleSave = async () => {
        // Validate new main weights sum to 100
        const mainWeightTotal = scoreWeights.price + scoreWeights.technical + scoreWeights.fundamental;
        if (Math.abs(mainWeightTotal - 100) > 0.1) {
            toast.error("Main score weights (Price + Technical + Fundamental) must sum to 100%");
            return;
        }

        // Validate technical sub-weights sum to 100
        const technicalSubTotal = technicalSubWeights.rsi14 + technicalSubWeights.trend + technicalSubWeights.macd;
        if (Math.abs(technicalSubTotal - 100) > 0.1) {
            toast.error("Technical sub-weights (RSI + Trend + MACD) must sum to 100%");
            return;
        }

        // Validate fundamental sub-weights sum to 100
        const fundamentalSubTotal = fundamentalSubWeights.valuation + fundamentalSubWeights.growth + fundamentalSubWeights.health + fundamentalSubWeights.sentiment;
        if (Math.abs(fundamentalSubTotal - 100) > 0.1) {
            toast.error("Fundamental sub-weights (Valuation + Growth + Health + Sentiment) must sum to 100%");
            return;
        }

        try {
            await onUpdate({
                defaultRefreshMinutes: defaultRefreshMinutes,
                watchlistRefreshOverride: useWatchlistOverride
                    ? watchlistOverride
                    : null,
                newsRefreshOverride: useNewsOverride ? newsOverride : null,
                newsLookbackHours: newsLookbackHours,
                newsMaxArticles: newsMaxArticles,
                watchlistAutoExpand: autoExpand,
                watchlistPriceWeight: priceWeight,
                watchlistTechnicalWeight: technicalWeight,
                watchlistShowNews: showNews,
                // New weight configuration
                watchlistScoreWeights: scoreWeights,
                priceSubWeights: { changePct: 100 }, // Price only has one component currently
                technicalSubWeights: technicalSubWeights,
                fundamentalSubWeights: fundamentalSubWeights,
            });
            toast.success("Watchlist preferences updated");
        } catch {
            toast.error("Failed to update preferences");
        }
    };

    const handleReset = () => {
        setDefaultRefreshMinutes(preferences.defaultRefreshMinutes);
        setUseWatchlistOverride(
            preferences.watchlistRefreshOverride !== null,
        );
        setWatchlistOverride(
            preferences.watchlistRefreshOverride ??
                preferences.defaultRefreshMinutes,
        );
        setUseNewsOverride(preferences.newsRefreshOverride !== null);
        setNewsOverride(
            preferences.newsRefreshOverride ??
                preferences.defaultRefreshMinutes,
        );
        setNewsLookbackHours(preferences.newsLookbackHours);
        setNewsMaxArticles(preferences.newsMaxArticles);
        setAutoExpand(preferences.watchlistAutoExpand);
        setPriceWeight(preferences.watchlistPriceWeight);
        setTechnicalWeight(preferences.watchlistTechnicalWeight);
        setShowNews(preferences.watchlistShowNews);
        setScoreWeights(
            preferences.watchlistScoreWeights ?? { price: 33, technical: 33, fundamental: 34 }
        );
        setTechnicalSubWeights(
            preferences.technicalSubWeights ?? { rsi14: 33, trend: 34, macd: 33 }
        );
        setFundamentalSubWeights(
            preferences.fundamentalSubWeights ?? { valuation: 30, growth: 35, health: 25, sentiment: 10 }
        );
    };

    const handleEqualMainWeights = () => {
        setScoreWeights({ price: 33, technical: 33, fundamental: 34 });
    };

    const handleEqualTechnicalSubWeights = () => {
        setTechnicalSubWeights({ rsi14: 33, trend: 34, macd: 33 });
    };

    const handleEqualFundamentalSubWeights = () => {
        setFundamentalSubWeights({ valuation: 25, growth: 25, health: 25, sentiment: 25 });
    };

    // Calculate total weight for validation
    // Weight validation
    const mainWeightTotal = scoreWeights.price + scoreWeights.technical + scoreWeights.fundamental;
    const isMainWeightValid = Math.abs(mainWeightTotal - 100) < 0.1;

    const technicalSubTotal = technicalSubWeights.rsi14 + technicalSubWeights.trend + technicalSubWeights.macd;
    const isTechnicalSubWeightValid = Math.abs(technicalSubTotal - 100) < 0.1;

    const fundamentalSubTotal = fundamentalSubWeights.valuation + fundamentalSubWeights.growth + fundamentalSubWeights.health + fundamentalSubWeights.sentiment;
    const isFundamentalSubWeightValid = Math.abs(fundamentalSubTotal - 100) < 0.1;

    const isAllWeightsValid = isMainWeightValid && isTechnicalSubWeightValid && isFundamentalSubWeightValid;

    return (
        <Card className="border-border">
            <CardHeader>
                <CardTitle>Refresh Control</CardTitle>
                <CardDescription>
                    Configure how often data refreshes across all features
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Basic Settings */}
                <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                    <h4 className="text-sm font-medium text-text">
                        Basic Settings
                    </h4>

                    {/* Default Refresh Interval */}
                    <div className="space-y-3">
                        <Label htmlFor="default-refresh-interval">
                            Default Refresh Interval: {defaultRefreshMinutes}{" "}
                            minutes
                        </Label>
                        <Slider
                            id="default-refresh-interval"
                            min={1}
                            max={60}
                            step={1}
                            value={[defaultRefreshMinutes]}
                            onValueChange={(value) =>
                                setDefaultRefreshMinutes(value[0])
                            }
                            className="w-full"
                            aria-label="Default refresh interval in minutes"
                        />
                        <p className="text-xs text-text-muted">
                            Global default for all features (watchlist,
                            portfolio, news). Each feature can override this in
                            Advanced settings below.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <Label>News Lookback Window</Label>
                        <RadioGroup
                            value={String(newsLookbackHours)}
                            onValueChange={(value) =>
                                setNewsLookbackHours(Number(value))
                            }
                            className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3"
                        >
                            {[6, 12, 24, 48].map((hours) => (
                                <div
                                    key={hours}
                                    className="flex items-center space-x-2 rounded-md border border-border/60 px-3 py-2"
                                >
                                    <RadioGroupItem
                                        id={`news-lookback-${hours}`}
                                        value={String(hours)}
                                    />
                                    <Label
                                        htmlFor={`news-lookback-${hours}`}
                                        className="cursor-pointer"
                                    >
                                        {hours} hours
                                    </Label>
                                </div>
                            ))}
                        </RadioGroup>
                        <p className="text-xs text-text-muted">
                            Controls how far back the News service samples
                            headlines before calculating sentiment scores.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <Label>Max Headlines Per Symbol</Label>
                        <RadioGroup
                            value={String(newsMaxArticles)}
                            onValueChange={(value) =>
                                setNewsMaxArticles(Number(value))
                            }
                            className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3"
                        >
                            {[5, 10, 15, 20].map((count) => (
                                <div
                                    key={count}
                                    className="flex items-center space-x-2 rounded-md border border-border/60 px-3 py-2"
                                >
                                    <RadioGroupItem
                                        id={`news-max-${count}`}
                                        value={String(count)}
                                    />
                                    <Label
                                        htmlFor={`news-max-${count}`}
                                        className="cursor-pointer"
                                    >
                                        {count} headlines
                                    </Label>
                                </div>
                            ))}
                        </RadioGroup>
                        <p className="text-xs text-text-muted">
                            Sets the default number of headlines returned for
                            each symbol and the Market view. API calls can still
                            request fewer or more (up to 20).
                        </p>
                    </div>

                    {/* Frontend Polling (Info Only) */}
                    <div className="space-y-2">
                        <Label className="text-text-muted">
                            Frontend Polling:{" "}
                            {preferences.frontendPollInterval} seconds
                            (automatic)
                        </Label>
                        <p className="text-xs text-text-muted">
                            How often the UI checks for new data. This is
                            separate from backend refresh and optimized for
                            responsiveness.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="toggle-news-visibility"
                                checked={showNews}
                                onCheckedChange={(checked) =>
                                    setShowNews(checked === true)
                                }
                            />
                            <Label
                                htmlFor="toggle-news-visibility"
                                className="cursor-pointer"
                            >
                                Show news sentiment and headlines in watchlist
                            </Label>
                        </div>
                        <p className="text-xs text-text-muted">
                            Disable this to hide the news expansion section for
                            each symbol.
                        </p>
                    </div>
                </div>

                {/* Advanced Settings (Collapsible) */}
                <div className="space-y-4">
                    <Button
                        variant="ghost"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="w-full justify-between"
                    >
                        <span className="text-sm font-medium">
                            Advanced: Per-Feature Overrides
                        </span>
                        <span className="text-xs text-text-muted">
                            {showAdvanced ? "▼" : "▶"}
                        </span>
                    </Button>

                    {showAdvanced && (
                        <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                            {/* Watchlist Override */}
                            <div className="space-y-3">
                                <Label className="text-sm font-medium">
                                    Watchlist Refresh
                                </Label>
                                <RadioGroup
                                    value={
                                        useWatchlistOverride
                                            ? "custom"
                                            : "default"
                                    }
                                    onValueChange={(value) =>
                                        setUseWatchlistOverride(
                                            value === "custom",
                                        )
                                    }
                                >
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem
                                            value="default"
                                            id="watchlist-default"
                                        />
                                        <Label
                                            htmlFor="watchlist-default"
                                            className="cursor-pointer font-normal"
                                        >
                                            Use Default ({defaultRefreshMinutes}{" "}
                                            min)
                                        </Label>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem
                                            value="custom"
                                            id="watchlist-custom"
                                        />
                                        <Label
                                            htmlFor="watchlist-custom"
                                            className="cursor-pointer font-normal"
                                        >
                                            Custom Interval
                                        </Label>
                                    </div>
                                </RadioGroup>

                                {useWatchlistOverride && (
                                    <div className="mt-3 space-y-2">
                                        <Label htmlFor="watchlist-override-slider">
                                            Watchlist Interval:{" "}
                                            {watchlistOverride} minutes
                                        </Label>
                                        <Slider
                                            id="watchlist-override-slider"
                                            min={1}
                                            max={60}
                                            step={1}
                                            value={[watchlistOverride]}
                                            onValueChange={(value) =>
                                                setWatchlistOverride(value[0])
                                            }
                                            className="w-full"
                                            aria-label="Watchlist refresh override interval in minutes"
                                        />
                                    </div>
                                )}
                                <p className="text-xs text-text-muted">
                                    Effective interval:{" "}
                                    {useWatchlistOverride
                                        ? watchlistOverride
                                        : defaultRefreshMinutes}{" "}
                                    minutes
                                </p>
                            </div>

                            {/* Future: Portfolio Override */}
                            <div className="space-y-2 opacity-50">
                                <Label className="text-sm font-medium text-text-muted">
                                    Portfolio Refresh (Future)
                                </Label>
                                <p className="text-xs text-text-muted">
                                    Per-feature override for portfolio analytics
                                    (coming soon)
                                </p>
                            </div>

                            <div className="space-y-3 border-t border-border pt-4">
                                <Label className="text-sm font-medium">
                                    News Refresh
                                </Label>
                                <RadioGroup
                                    value={
                                        useNewsOverride ? "custom" : "default"
                                    }
                                    onValueChange={(value) =>
                                        setUseNewsOverride(value === "custom")
                                    }
                                >
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem
                                            value="default"
                                            id="news-default"
                                        />
                                        <Label
                                            htmlFor="news-default"
                                            className="cursor-pointer font-normal"
                                        >
                                            Use Default ({defaultRefreshMinutes}{" "}
                                            min)
                                        </Label>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem
                                            value="custom"
                                            id="news-custom"
                                        />
                                        <Label
                                            htmlFor="news-custom"
                                            className="cursor-pointer font-normal"
                                        >
                                            Custom Interval
                                        </Label>
                                    </div>
                                </RadioGroup>

                                {useNewsOverride && (
                                    <div className="mt-3 space-y-2">
                                        <Label htmlFor="news-override-slider">
                                            News Interval: {newsOverride}{" "}
                                            minutes
                                        </Label>
                                        <Slider
                                            id="news-override-slider"
                                            min={1}
                                            max={60}
                                            step={1}
                                            value={[newsOverride]}
                                            onValueChange={(value) =>
                                                setNewsOverride(value[0])
                                            }
                                            className="w-full"
                                            aria-label="News refresh override interval in minutes"
                                        />
                                    </div>
                                )}
                                <p className="text-xs text-text-muted">
                                    Effective interval:{" "}
                                    {useNewsOverride
                                        ? newsOverride
                                        : defaultRefreshMinutes}{" "}
                                    minutes
                                </p>
                                <p className="text-xs text-text-muted">
                                    Determines how frequently headline sentiment
                                    is refreshed for market and watchlist views.
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Static Schedules (Info Only) */}
                <div className="space-y-3 rounded-md border border-border bg-surface-muted/30 p-4">
                    <h4 className="text-sm font-medium text-text">
                        Static Schedules (Not Configurable)
                    </h4>
                    <ul className="space-y-2 text-xs text-text-muted">
                        <li>• Paper Trades Update: Daily at 4:30 PM ET</li>
                        <li>
                            • Data Cleanup: Weekly on Sunday 2:00 AM (future)
                        </li>
                    </ul>
                    <p className="text-xs text-text-muted">
                        These tasks run on fixed schedules for business logic
                        reasons and cannot be customized.
                    </p>
                </div>

                {/* Auto-expand Rows */}
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="auto-expand"
                        checked={autoExpand}
                        onCheckedChange={(checked) =>
                            setAutoExpand(checked === true)
                        }
                    />
                    <Label
                        htmlFor="auto-expand"
                        className="cursor-pointer text-sm font-normal"
                    >
                        Auto-expand watchlist rows to show details
                    </Label>
                </div>

                {/* Main Score Weights (3-Pillar System) */}
                <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                    <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium text-text">
                            Main Score Weights
                        </h4>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleEqualMainWeights}
                            className="h-8"
                        >
                            Equal Weights
                        </Button>
                    </div>

                    {/* Price Weight */}
                    <div className="space-y-2">
                        <Label htmlFor="weight-price">
                            Price: {scoreWeights.price.toFixed(1)}%
                        </Label>
                        <Slider
                            id="weight-price"
                            min={0}
                            max={100}
                            step={0.1}
                            value={[scoreWeights.price]}
                            onValueChange={(value) => setScoreWeights({ ...scoreWeights, price: value[0] })}
                            className="w-full"
                            aria-label="Price weight percentage"
                        />
                    </div>

                    {/* Technical Weight */}
                    <div className="space-y-2">
                        <Label htmlFor="weight-technical">
                            Technical: {scoreWeights.technical.toFixed(1)}%
                        </Label>
                        <Slider
                            id="weight-technical"
                            min={0}
                            max={100}
                            step={0.1}
                            value={[scoreWeights.technical]}
                            onValueChange={(value) => setScoreWeights({ ...scoreWeights, technical: value[0] })}
                            className="w-full"
                            aria-label="Technical weight percentage"
                        />
                    </div>

                    {/* Fundamental Weight */}
                    <div className="space-y-2">
                        <Label htmlFor="weight-fundamental">
                            Fundamental: {scoreWeights.fundamental.toFixed(1)}%
                        </Label>
                        <Slider
                            id="weight-fundamental"
                            min={0}
                            max={100}
                            step={0.1}
                            value={[scoreWeights.fundamental]}
                            onValueChange={(value) => setScoreWeights({ ...scoreWeights, fundamental: value[0] })}
                            className="w-full"
                            aria-label="Fundamental weight percentage"
                        />
                    </div>

                    {/* Validation */}
                    <div className="flex items-center justify-between pt-2">
                        <p className={`text-sm ${isMainWeightValid ? "text-text-muted" : "text-loss"}`}>
                            Total: {mainWeightTotal.toFixed(1)}%
                            {!isMainWeightValid && " (must be 100%)"}
                        </p>
                    </div>
                </div>

                {/* Technical Sub-Weights (Collapsible) */}
                <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                    <Button
                        variant="ghost"
                        onClick={() => setShowTechnicalSubWeights(!showTechnicalSubWeights)}
                        className="w-full justify-between p-0 hover:bg-transparent"
                    >
                        <h4 className="text-sm font-medium text-text">
                            Technical Sub-Weights (Advanced)
                        </h4>
                        <span className="text-xs text-text-muted">
                            {showTechnicalSubWeights ? "▼" : "▶"}
                        </span>
                    </Button>

                    {showTechnicalSubWeights && (
                        <div className="space-y-4 pl-4">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleEqualTechnicalSubWeights}
                                className="h-8"
                            >
                                Equal Weights
                            </Button>

                            {/* RSI Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="tech-rsi">
                                    RSI: {technicalSubWeights.rsi14.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="tech-rsi"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[technicalSubWeights.rsi14]}
                                    onValueChange={(value) => setTechnicalSubWeights({ ...technicalSubWeights, rsi14: value[0] })}
                                    className="w-full"
                                />
                            </div>

                            {/* Trend Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="tech-trend">
                                    Trend: {technicalSubWeights.trend.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="tech-trend"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[technicalSubWeights.trend]}
                                    onValueChange={(value) => setTechnicalSubWeights({ ...technicalSubWeights, trend: value[0] })}
                                    className="w-full"
                                />
                            </div>

                            {/* MACD Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="tech-macd">
                                    MACD: {technicalSubWeights.macd.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="tech-macd"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[technicalSubWeights.macd]}
                                    onValueChange={(value) => setTechnicalSubWeights({ ...technicalSubWeights, macd: value[0] })}
                                    className="w-full"
                                />
                            </div>

                            {/* Validation */}
                            <div className="flex items-center justify-between pt-2">
                                <p className={`text-xs ${isTechnicalSubWeightValid ? "text-text-muted" : "text-loss"}`}>
                                    Total: {technicalSubTotal.toFixed(1)}%
                                    {!isTechnicalSubWeightValid && " (must be 100%)"}
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Fundamental Sub-Weights (Collapsible) */}
                <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                    <Button
                        variant="ghost"
                        onClick={() => setShowFundamentalSubWeights(!showFundamentalSubWeights)}
                        className="w-full justify-between p-0 hover:bg-transparent"
                    >
                        <h4 className="text-sm font-medium text-text">
                            Fundamental Sub-Weights (Advanced)
                        </h4>
                        <span className="text-xs text-text-muted">
                            {showFundamentalSubWeights ? "▼" : "▶"}
                        </span>
                    </Button>

                    {showFundamentalSubWeights && (
                        <div className="space-y-4 pl-4">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleEqualFundamentalSubWeights}
                                className="h-8"
                            >
                                Equal Weights
                            </Button>

                            {/* Valuation Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="fund-valuation">
                                    Valuation: {fundamentalSubWeights.valuation.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="fund-valuation"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[fundamentalSubWeights.valuation]}
                                    onValueChange={(value) => setFundamentalSubWeights({ ...fundamentalSubWeights, valuation: value[0] })}
                                    className="w-full"
                                />
                                <p className="text-xs text-text-muted">P/E, PEG, relative multiples</p>
                            </div>

                            {/* Growth Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="fund-growth">
                                    Growth: {fundamentalSubWeights.growth.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="fund-growth"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[fundamentalSubWeights.growth]}
                                    onValueChange={(value) => setFundamentalSubWeights({ ...fundamentalSubWeights, growth: value[0] })}
                                    className="w-full"
                                />
                                <p className="text-xs text-text-muted">Revenue/earnings growth metrics</p>
                            </div>

                            {/* Health Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="fund-health">
                                    Health: {fundamentalSubWeights.health.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="fund-health"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[fundamentalSubWeights.health]}
                                    onValueChange={(value) => setFundamentalSubWeights({ ...fundamentalSubWeights, health: value[0] })}
                                    className="w-full"
                                />
                                <p className="text-xs text-text-muted">Margins, ROIC, cash flow</p>
                            </div>

                            {/* Sentiment Weight */}
                            <div className="space-y-2">
                                <Label htmlFor="fund-sentiment">
                                    Sentiment: {fundamentalSubWeights.sentiment.toFixed(1)}%
                                </Label>
                                <Slider
                                    id="fund-sentiment"
                                    min={0}
                                    max={100}
                                    step={0.1}
                                    value={[fundamentalSubWeights.sentiment]}
                                    onValueChange={(value) => setFundamentalSubWeights({ ...fundamentalSubWeights, sentiment: value[0] })}
                                    className="w-full"
                                />
                                <p className="text-xs text-text-muted">Analyst ratings, institutional activity</p>
                            </div>

                            {/* Validation */}
                            <div className="flex items-center justify-between pt-2">
                                <p className={`text-xs ${isFundamentalSubWeightValid ? "text-text-muted" : "text-loss"}`}>
                                    Total: {fundamentalSubTotal.toFixed(1)}%
                                    {!isFundamentalSubWeightValid && " (must be 100%)"}
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-4">
                    <Button
                        variant="outline"
                        onClick={handleReset}
                        disabled={!hasChanges() || isPending}
                    >
                        Reset
                    </Button>
                    <Button
                        onClick={handleSave}
                        disabled={!hasChanges() || !isAllWeightsValid || isPending}
                    >
                        {isPending ? "Saving..." : "Save Changes"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
