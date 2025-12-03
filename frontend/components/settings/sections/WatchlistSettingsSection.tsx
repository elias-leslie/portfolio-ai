"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { WeightConfigurator } from "../WeightConfigurator";
import type {
  ScoreWeights,
  TechnicalSubWeights,
  FundamentalSubWeights,
} from "@/lib/api/preferences";

interface WatchlistSettingsSectionProps {
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
  onDefaultRefreshMinutesChange: (value: number) => void;
  onWatchlistOverrideChange: (value: number | null) => void;
  onNewsOverrideChange: (value: number | null) => void;
  onNewsLookbackHoursChange: (value: number) => void;
  onNewsMaxArticlesChange: (value: number) => void;
  onShowNewsChange: (value: boolean) => void;
  onAutoExpandChange: (value: boolean) => void;
  onScoreWeightsChange: (value: ScoreWeights) => void;
  onTechnicalSubWeightsChange: (value: TechnicalSubWeights) => void;
  onFundamentalSubWeightsChange: (value: FundamentalSubWeights) => void;
}

export function WatchlistSettingsSection({
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
  onDefaultRefreshMinutesChange,
  onWatchlistOverrideChange,
  onNewsOverrideChange,
  onNewsLookbackHoursChange,
  onNewsMaxArticlesChange,
  onShowNewsChange,
  onAutoExpandChange,
  onScoreWeightsChange,
  onTechnicalSubWeightsChange,
  onFundamentalSubWeightsChange,
}: WatchlistSettingsSectionProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTechnicalSubWeights, setShowTechnicalSubWeights] = useState(false);
  const [showFundamentalSubWeights, setShowFundamentalSubWeights] = useState(false);

  return (
    <div className="space-y-6">
      {/* Basic Settings */}
      <Card>
        <CardContent className="space-y-6 pt-6">
          <h4 className="text-sm font-medium text-text">Basic Settings</h4>

          {/* Default Refresh Interval */}
          <div className="space-y-3">
            <Label htmlFor="default-refresh-interval">
              Default Refresh Interval: {defaultRefreshMinutes} minutes
            </Label>
            <Slider
              id="default-refresh-interval"
              min={1}
              max={60}
              step={1}
              value={[defaultRefreshMinutes]}
              onValueChange={(value) => onDefaultRefreshMinutesChange(value[0])}
              className="w-full"
              aria-label="Default refresh interval in minutes"
            />
            <p className="text-xs text-text-muted">
              Global default for all features (watchlist, portfolio, news). Each
              feature can override this in Advanced settings below.
            </p>
          </div>

          {/* News Lookback Window */}
          <div className="space-y-3">
            <Label>News Lookback Window</Label>
            <RadioGroup
              value={String(newsLookbackHours)}
              onValueChange={(value) => onNewsLookbackHoursChange(Number(value))}
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
              Controls how far back the News service samples headlines before
              calculating sentiment scores.
            </p>
          </div>

          {/* Max Headlines Per Symbol */}
          <div className="space-y-3">
            <Label>Max Headlines Per Symbol</Label>
            <RadioGroup
              value={String(newsMaxArticles)}
              onValueChange={(value) => onNewsMaxArticlesChange(Number(value))}
              className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3"
            >
              {[5, 10, 15, 20].map((count) => (
                <div
                  key={count}
                  className="flex items-center space-x-2 rounded-md border border-border/60 px-3 py-2"
                >
                  <RadioGroupItem id={`news-max-${count}`} value={String(count)} />
                  <Label htmlFor={`news-max-${count}`} className="cursor-pointer">
                    {count} headlines
                  </Label>
                </div>
              ))}
            </RadioGroup>
            <p className="text-xs text-text-muted">
              Sets the default number of headlines returned for each symbol and the
              Market view.
            </p>
          </div>

          {/* Show News Toggle */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Checkbox
                id="toggle-news-visibility"
                checked={showNews}
                onCheckedChange={(checked) => onShowNewsChange(checked === true)}
              />
              <Label htmlFor="toggle-news-visibility" className="cursor-pointer">
                Show news sentiment and headlines in watchlist
              </Label>
            </div>
            <p className="text-xs text-text-muted">
              Disable this to hide the news expansion section for each symbol.
            </p>
          </div>

          {/* Auto-expand Rows */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto-expand"
              checked={autoExpand}
              onCheckedChange={(checked) => onAutoExpandChange(checked === true)}
            />
            <Label htmlFor="auto-expand" className="cursor-pointer text-sm font-normal">
              Auto-expand watchlist rows to show details
            </Label>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Settings - Per-Feature Overrides */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <Card>
          <CardContent className="pt-6">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-0 hover:bg-transparent"
              >
                <span className="text-sm font-medium">
                  Advanced: Per-Feature Overrides
                </span>
                <span className="text-xs text-text-muted">
                  {showAdvanced ? "▼" : "▶"}
                </span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4 space-y-4">
              {/* Watchlist Override */}
              <div className="space-y-3 rounded-md border border-border bg-surface-muted/30 p-4">
                <Label className="text-sm font-medium">Watchlist Refresh</Label>
                <RadioGroup
                  value={watchlistOverride === null ? "default" : "custom"}
                  onValueChange={(value) =>
                    onWatchlistOverrideChange(
                      value === "custom" ? defaultRefreshMinutes : null
                    )
                  }
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="default" id="watchlist-default" />
                    <Label htmlFor="watchlist-default" className="cursor-pointer font-normal">
                      Use Default ({defaultRefreshMinutes} min)
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="custom" id="watchlist-custom" />
                    <Label htmlFor="watchlist-custom" className="cursor-pointer font-normal">
                      Custom Interval
                    </Label>
                  </div>
                </RadioGroup>

                {watchlistOverride !== null && (
                  <div className="mt-3 space-y-2">
                    <Label htmlFor="watchlist-override-slider">
                      Watchlist Interval: {watchlistOverride} minutes
                    </Label>
                    <Slider
                      id="watchlist-override-slider"
                      min={1}
                      max={60}
                      step={1}
                      value={[watchlistOverride]}
                      onValueChange={(value) => onWatchlistOverrideChange(value[0])}
                      className="w-full"
                    />
                  </div>
                )}
                <p className="text-xs text-text-muted">
                  Effective interval:{" "}
                  {watchlistOverride ?? defaultRefreshMinutes} minutes
                </p>
              </div>

              {/* News Override */}
              <div className="space-y-3 rounded-md border border-border bg-surface-muted/30 p-4">
                <Label className="text-sm font-medium">News Refresh</Label>
                <RadioGroup
                  value={newsOverride === null ? "default" : "custom"}
                  onValueChange={(value) =>
                    onNewsOverrideChange(
                      value === "custom" ? defaultRefreshMinutes : null
                    )
                  }
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="default" id="news-default" />
                    <Label htmlFor="news-default" className="cursor-pointer font-normal">
                      Use Default ({defaultRefreshMinutes} min)
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="custom" id="news-custom" />
                    <Label htmlFor="news-custom" className="cursor-pointer font-normal">
                      Custom Interval
                    </Label>
                  </div>
                </RadioGroup>

                {newsOverride !== null && (
                  <div className="mt-3 space-y-2">
                    <Label htmlFor="news-override-slider">
                      News Interval: {newsOverride} minutes
                    </Label>
                    <Slider
                      id="news-override-slider"
                      min={1}
                      max={60}
                      step={1}
                      value={[newsOverride]}
                      onValueChange={(value) => onNewsOverrideChange(value[0])}
                      className="w-full"
                    />
                  </div>
                )}
                <p className="text-xs text-text-muted">
                  Effective interval: {newsOverride ?? defaultRefreshMinutes}{" "}
                  minutes
                </p>
              </div>
            </CollapsibleContent>
          </CardContent>
        </Card>
      </Collapsible>

      {/* Main Score Weights */}
      <Card>
        <CardContent className="pt-6">
          <WeightConfigurator
            title="Main Score Weights"
            weights={[
              { id: "price", label: "Price", value: scoreWeights.price },
              { id: "technical", label: "Technical", value: scoreWeights.technical },
              {
                id: "fundamental",
                label: "Fundamental",
                value: scoreWeights.fundamental,
              },
            ]}
            onChange={(weights) => {
              onScoreWeightsChange({
                price: weights.find((w) => w.id === "price")?.value ?? 33,
                technical: weights.find((w) => w.id === "technical")?.value ?? 33,
                fundamental:
                  weights.find((w) => w.id === "fundamental")?.value ?? 34,
              });
            }}
          />
        </CardContent>
      </Card>

      {/* Technical Sub-Weights */}
      <Collapsible
        open={showTechnicalSubWeights}
        onOpenChange={setShowTechnicalSubWeights}
      >
        <Card>
          <CardContent className="pt-6">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-0 hover:bg-transparent"
              >
                <h4 className="text-sm font-medium text-text">
                  Technical Sub-Weights (Advanced)
                </h4>
                <span className="text-xs text-text-muted">
                  {showTechnicalSubWeights ? "▼" : "▶"}
                </span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4">
              <WeightConfigurator
                title=""
                weights={[
                  {
                    id: "rsi_14",
                    label: "RSI",
                    value: technicalSubWeights.rsi_14,
                  },
                  {
                    id: "trend",
                    label: "Trend",
                    value: technicalSubWeights.trend,
                  },
                  { id: "macd", label: "MACD", value: technicalSubWeights.macd },
                ]}
                onChange={(weights) => {
                  onTechnicalSubWeightsChange({
                    rsi_14: weights.find((w) => w.id === "rsi_14")?.value ?? 33,
                    trend: weights.find((w) => w.id === "trend")?.value ?? 34,
                    macd: weights.find((w) => w.id === "macd")?.value ?? 33,
                  });
                }}
              />
            </CollapsibleContent>
          </CardContent>
        </Card>
      </Collapsible>

      {/* Fundamental Sub-Weights */}
      <Collapsible
        open={showFundamentalSubWeights}
        onOpenChange={setShowFundamentalSubWeights}
      >
        <Card>
          <CardContent className="pt-6">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-0 hover:bg-transparent"
              >
                <h4 className="text-sm font-medium text-text">
                  Fundamental Sub-Weights (Advanced)
                </h4>
                <span className="text-xs text-text-muted">
                  {showFundamentalSubWeights ? "▼" : "▶"}
                </span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4">
              <WeightConfigurator
                title=""
                weights={[
                  {
                    id: "valuation",
                    label: "Valuation",
                    value: fundamentalSubWeights.valuation,
                    description: "P/E, PEG, relative multiples",
                  },
                  {
                    id: "growth",
                    label: "Growth",
                    value: fundamentalSubWeights.growth,
                    description: "Revenue/earnings growth metrics",
                  },
                  {
                    id: "health",
                    label: "Health",
                    value: fundamentalSubWeights.health,
                    description: "Margins, ROIC, cash flow",
                  },
                  {
                    id: "sentiment",
                    label: "Sentiment",
                    value: fundamentalSubWeights.sentiment,
                    description: "Analyst ratings, institutional activity",
                  },
                ]}
                onChange={(weights) => {
                  onFundamentalSubWeightsChange({
                    valuation:
                      weights.find((w) => w.id === "valuation")?.value ?? 30,
                    growth: weights.find((w) => w.id === "growth")?.value ?? 35,
                    health: weights.find((w) => w.id === "health")?.value ?? 25,
                    sentiment:
                      weights.find((w) => w.id === "sentiment")?.value ?? 10,
                  });
                }}
              />
            </CollapsibleContent>
          </CardContent>
        </Card>
      </Collapsible>

      {/* Static Schedules Info */}
      <Card className="border-border/50">
        <CardContent className="pt-6">
          <h4 className="mb-3 text-sm font-medium text-text">
            Static Schedules (Not Configurable)
          </h4>
          <ul className="space-y-2 text-xs text-text-muted">
            <li>• Paper Trades Update: Daily at 4:30 PM ET</li>
            <li>• Data Cleanup: Weekly on Sunday 2:00 AM (future)</li>
          </ul>
          <p className="mt-3 text-xs text-text-muted">
            These tasks run on fixed schedules for business logic reasons and cannot
            be customized.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
