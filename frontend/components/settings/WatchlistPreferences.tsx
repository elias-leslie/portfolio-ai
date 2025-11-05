"use client";

import { useState, useEffect } from "react";
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
import type { PreferencesResponse } from "@/lib/api/preferences";

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
        preferences.default_refresh_minutes,
    );
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Per-feature overrides
    const [useWatchlistOverride, setUseWatchlistOverride] = useState(
        preferences.watchlist_refresh_override !== null,
    );
    const [watchlistOverride, setWatchlistOverride] = useState(
        preferences.watchlist_refresh_override ??
            preferences.default_refresh_minutes,
    );
    const [useNewsOverride, setUseNewsOverride] = useState(
        preferences.news_refresh_override !== null,
    );
    const [newsOverride, setNewsOverride] = useState(
        preferences.news_refresh_override ??
            preferences.default_refresh_minutes,
    );
    const [newsLookbackHours, setNewsLookbackHours] = useState(
        preferences.news_lookback_hours,
    );

    // Legacy watchlist settings
    const [autoExpand, setAutoExpand] = useState(
        preferences.watchlist_auto_expand,
    );
    const [priceWeight, setPriceWeight] = useState(
        preferences.watchlist_price_weight,
    );
    const [technicalWeight, setTechnicalWeight] = useState(
        preferences.watchlist_technical_weight,
    );
    const [showNews, setShowNews] = useState(preferences.watchlist_show_news);

    // Update local state when preferences change
    useEffect(() => {
        setDefaultRefreshMinutes(preferences.default_refresh_minutes);
        setUseWatchlistOverride(
            preferences.watchlist_refresh_override !== null,
        );
        setWatchlistOverride(
            preferences.watchlist_refresh_override ??
                preferences.default_refresh_minutes,
        );
        setUseNewsOverride(preferences.news_refresh_override !== null);
        setNewsOverride(
            preferences.news_refresh_override ??
                preferences.default_refresh_minutes,
        );
        setNewsLookbackHours(preferences.news_lookback_hours);
        setAutoExpand(preferences.watchlist_auto_expand);
        setPriceWeight(preferences.watchlist_price_weight);
        setTechnicalWeight(preferences.watchlist_technical_weight);
        setShowNews(preferences.watchlist_show_news);
    }, [preferences]);

    const hasChanges = () => {
        const currentOverride = useWatchlistOverride ? watchlistOverride : null;
        const savedOverride = preferences.watchlist_refresh_override;
        const currentNewsOverride = useNewsOverride ? newsOverride : null;
        const savedNewsOverride = preferences.news_refresh_override;

        return (
            defaultRefreshMinutes !== preferences.default_refresh_minutes ||
            currentOverride !== savedOverride ||
            currentNewsOverride !== savedNewsOverride ||
            newsLookbackHours !== preferences.news_lookback_hours ||
            showNews !== preferences.watchlist_show_news ||
            autoExpand !== preferences.watchlist_auto_expand ||
            priceWeight !== preferences.watchlist_price_weight ||
            technicalWeight !== preferences.watchlist_technical_weight
        );
    };

    const handleSave = async () => {
        // Validate weights sum to 100
        const totalWeight = priceWeight + technicalWeight;
        if (Math.abs(totalWeight - 100) > 0.1) {
            toast.error("Weights must sum to 100%");
            return;
        }

        try {
            await onUpdate({
                default_refresh_minutes: defaultRefreshMinutes,
                watchlist_refresh_override: useWatchlistOverride
                    ? watchlistOverride
                    : null,
                news_refresh_override: useNewsOverride ? newsOverride : null,
                news_lookback_hours: newsLookbackHours,
                watchlist_auto_expand: autoExpand,
                watchlist_price_weight: priceWeight,
                watchlist_technical_weight: technicalWeight,
                watchlist_show_news: showNews,
            });
            toast.success("Watchlist preferences updated");
        } catch {
            toast.error("Failed to update preferences");
        }
    };

    const handleReset = () => {
        setDefaultRefreshMinutes(preferences.default_refresh_minutes);
        setUseWatchlistOverride(
            preferences.watchlist_refresh_override !== null,
        );
        setWatchlistOverride(
            preferences.watchlist_refresh_override ??
                preferences.default_refresh_minutes,
        );
        setUseNewsOverride(preferences.news_refresh_override !== null);
        setNewsOverride(
            preferences.news_refresh_override ??
                preferences.default_refresh_minutes,
        );
        setNewsLookbackHours(preferences.news_lookback_hours);
        setAutoExpand(preferences.watchlist_auto_expand);
        setPriceWeight(preferences.watchlist_price_weight);
        setTechnicalWeight(preferences.watchlist_technical_weight);
        setShowNews(preferences.watchlist_show_news);
    };

    const handleEqualWeights = () => {
        setPriceWeight(50);
        setTechnicalWeight(50);
    };

    // Calculate total weight for validation
    const totalWeight = priceWeight + technicalWeight;
    const isWeightValid = Math.abs(totalWeight - 100) < 0.1;

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

                    {/* Frontend Polling (Info Only) */}
                    <div className="space-y-2">
                        <Label className="text-text-muted">
                            Frontend Polling:{" "}
                            {preferences.frontend_poll_interval} seconds
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
                            each ticker.
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

                {/* Score Weights */}
                <div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
                    <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium text-text">
                            Score Weights
                        </h4>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleEqualWeights}
                            className="h-8"
                        >
                            Equal Weights
                        </Button>
                    </div>

                    {/* Price Weight */}
                    <div className="space-y-3">
                        <Label htmlFor="price-weight">
                            Price Score: {priceWeight.toFixed(1)}%
                        </Label>
                        <Slider
                            id="price-weight"
                            min={0}
                            max={100}
                            step={0.1}
                            value={[priceWeight]}
                            onValueChange={(value) => setPriceWeight(value[0])}
                            className="w-full"
                            aria-label="Price score weight percentage"
                        />
                    </div>

                    {/* Technical Weight */}
                    <div className="space-y-3">
                        <Label htmlFor="technical-weight">
                            Technical Score: {technicalWeight.toFixed(1)}%
                        </Label>
                        <Slider
                            id="technical-weight"
                            min={0}
                            max={100}
                            step={0.1}
                            value={[technicalWeight]}
                            onValueChange={(value) =>
                                setTechnicalWeight(value[0])
                            }
                            className="w-full"
                            aria-label="Technical score weight percentage"
                        />
                    </div>

                    {/* Weight Validation */}
                    <div className="flex items-center justify-between pt-2">
                        <p
                            className={`text-sm ${isWeightValid ? "text-text-muted" : "text-loss"}`}
                        >
                            Total: {totalWeight.toFixed(1)}%{" "}
                            {!isWeightValid && "(must be 100%)"}
                        </p>
                    </div>
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
                        disabled={!hasChanges() || !isWeightValid || isPending}
                    >
                        {isPending ? "Saving..." : "Save Changes"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
