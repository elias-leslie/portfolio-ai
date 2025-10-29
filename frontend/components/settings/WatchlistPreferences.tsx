"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  const [refreshMinutes, setRefreshMinutes] = useState(
    preferences.watchlist_refresh_minutes
  );
  const [autoExpand, setAutoExpand] = useState(
    preferences.watchlist_auto_expand
  );
  const [priceWeight, setPriceWeight] = useState(
    preferences.watchlist_price_weight
  );
  const [technicalWeight, setTechnicalWeight] = useState(
    preferences.watchlist_technical_weight
  );

  // Update local state when preferences change
  useEffect(() => {
    setRefreshMinutes(preferences.watchlist_refresh_minutes);
    setAutoExpand(preferences.watchlist_auto_expand);
    setPriceWeight(preferences.watchlist_price_weight);
    setTechnicalWeight(preferences.watchlist_technical_weight);
  }, [preferences]);

  const hasChanges = () => {
    return (
      refreshMinutes !== preferences.watchlist_refresh_minutes ||
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
        watchlist_refresh_minutes: refreshMinutes,
        watchlist_auto_expand: autoExpand,
        watchlist_price_weight: priceWeight,
        watchlist_technical_weight: technicalWeight,
      });
      toast.success("Watchlist preferences updated");
    } catch {
      toast.error("Failed to update preferences");
    }
  };

  const handleReset = () => {
    setRefreshMinutes(preferences.watchlist_refresh_minutes);
    setAutoExpand(preferences.watchlist_auto_expand);
    setPriceWeight(preferences.watchlist_price_weight);
    setTechnicalWeight(preferences.watchlist_technical_weight);
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
        <CardTitle>Watchlist Preferences</CardTitle>
        <CardDescription>
          Configure refresh interval, display options, and score weights
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Refresh Interval */}
        <div className="space-y-3">
          <Label htmlFor="refresh-interval">
            Refresh Interval: {refreshMinutes} minutes
          </Label>
          <Slider
            id="refresh-interval"
            min={1}
            max={60}
            step={1}
            value={[refreshMinutes]}
            onValueChange={(value) => setRefreshMinutes(value[0])}
            className="w-full"
            aria-label="Watchlist refresh interval in minutes"
          />
          <p className="text-xs text-text-muted">
            How often to automatically refresh watchlist scores (1-60 minutes)
          </p>
        </div>

        {/* Auto-expand Rows */}
        <div className="flex items-center space-x-2">
          <Checkbox
            id="auto-expand"
            checked={autoExpand}
            onCheckedChange={(checked) => setAutoExpand(checked === true)}
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
            <h4 className="text-sm font-medium text-text">Score Weights</h4>
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
              onValueChange={(value) => setTechnicalWeight(value[0])}
              className="w-full"
              aria-label="Technical score weight percentage"
            />
          </div>

          {/* Weight Validation */}
          <div className="flex items-center justify-between pt-2">
            <p
              className={`text-sm ${isWeightValid ? "text-text-muted" : "text-loss"}`}
            >
              Total: {totalWeight.toFixed(1)}% {!isWeightValid && "(must be 100%)"}
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
