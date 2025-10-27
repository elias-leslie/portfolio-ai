"use client";

import { useState, useEffect } from "react";
import { usePreferences, useUpdatePreferences } from "@/lib/hooks/usePreferences";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  const { data: preferences, isLoading } = usePreferences();
  const updatePreferences = useUpdatePreferences();

  // Form state
  const [riskTolerance, setRiskTolerance] = useState<number>(5);
  const [allowLong, setAllowLong] = useState(true);
  const [allowShort, setAllowShort] = useState(false);
  const [allowOptions, setAllowOptions] = useState(false);
  const [allowCrypto, setAllowCrypto] = useState(false);
  const [allowFutures, setAllowFutures] = useState(false);
  const [maxPositionSizePct, setMaxPositionSizePct] = useState<string>("20");

  // Update form state when preferences load
  useEffect(() => {
    if (preferences) {
      setRiskTolerance(preferences.risk_tolerance);
      setAllowLong(preferences.allow_long);
      setAllowShort(preferences.allow_short);
      setAllowOptions(preferences.allow_options);
      setAllowCrypto(preferences.allow_crypto);
      setAllowFutures(preferences.allow_futures);
      setMaxPositionSizePct(preferences.max_position_size_pct.toString());
    }
  }, [preferences]);

  // Handle form submit
  const handleSave = () => {
    updatePreferences.mutate({
      risk_tolerance: riskTolerance,
      allow_long: allowLong,
      allow_short: allowShort,
      allow_options: allowOptions,
      allow_crypto: allowCrypto,
      allow_futures: allowFutures,
      max_position_size_pct: parseFloat(maxPositionSizePct),
    });
  };

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
      parseFloat(maxPositionSizePct) !== preferences.max_position_size_pct
    );
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="animate-pulse">
            <div className="h-8 w-48 bg-gray-200 rounded mb-2" />
            <div className="h-4 w-96 bg-gray-200 rounded mb-8" />
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-64 bg-gray-200 rounded" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="mt-2 text-sm text-gray-600">
            Configure your risk tolerance and trading preferences for AI-generated ideas
          </p>
        </div>

        <div className="space-y-6">
          {/* Risk Tolerance */}
          <Card>
            <CardHeader>
              <CardTitle>Risk Tolerance</CardTitle>
              <CardDescription>
                Set your risk tolerance level from 1 (very conservative) to 10 (very aggressive)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Risk Level</Label>
                  <span className="text-2xl font-bold text-primary">
                    {riskTolerance}
                  </span>
                </div>
                <Slider
                  value={[riskTolerance]}
                  onValueChange={(value) => setRiskTolerance(value[0])}
                  min={1}
                  max={10}
                  step={1}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>1 - Very Conservative</span>
                  <span>5 - Moderate</span>
                  <span>10 - Very Aggressive</span>
                </div>
              </div>

              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm text-muted-foreground">
                  {riskTolerance <= 3 && (
                    <>
                      <strong>Conservative:</strong> You prefer stable, low-risk investments with predictable returns. AI agents will focus on blue-chip stocks and conservative strategies.
                    </>
                  )}
                  {riskTolerance >= 4 && riskTolerance <= 7 && (
                    <>
                      <strong>Moderate:</strong> You're willing to accept some risk for potential growth. AI agents will suggest a balanced mix of growth and value opportunities.
                    </>
                  )}
                  {riskTolerance >= 8 && (
                    <>
                      <strong>Aggressive:</strong> You're comfortable with high-risk, high-reward investments. AI agents will explore growth stocks, emerging sectors, and speculative plays.
                    </>
                  )}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Position Size Limit */}
          <Card>
            <CardHeader>
              <CardTitle>Position Size Limit</CardTitle>
              <CardDescription>
                Maximum percentage of portfolio that can be allocated to a single position
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Label htmlFor="max-position">Max Position Size (%)</Label>
                <Input
                  id="max-position"
                  type="number"
                  value={maxPositionSizePct}
                  onChange={(e) => setMaxPositionSizePct(e.target.value)}
                  min="1"
                  max="100"
                  step="1"
                />
                <p className="text-xs text-muted-foreground">
                  Recommended: 10-25% to maintain diversification
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Trading Preferences */}
          <Card>
            <CardHeader>
              <CardTitle>Trading Preferences</CardTitle>
              <CardDescription>
                Select which types of trades you're willing to consider
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="allow-long"
                    checked={allowLong}
                    onCheckedChange={(checked) =>
                      setAllowLong(checked as boolean)
                    }
                  />
                  <Label
                    htmlFor="allow-long"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Long Positions (Buy stocks expecting price to rise)
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="allow-short"
                    checked={allowShort}
                    onCheckedChange={(checked) =>
                      setAllowShort(checked as boolean)
                    }
                  />
                  <Label
                    htmlFor="allow-short"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Short Positions (Sell stocks expecting price to fall)
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="allow-options"
                    checked={allowOptions}
                    onCheckedChange={(checked) =>
                      setAllowOptions(checked as boolean)
                    }
                  />
                  <Label
                    htmlFor="allow-options"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Options Trading (Calls, puts, spreads)
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="allow-crypto"
                    checked={allowCrypto}
                    onCheckedChange={(checked) =>
                      setAllowCrypto(checked as boolean)
                    }
                  />
                  <Label
                    htmlFor="allow-crypto"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Cryptocurrency (Bitcoin, Ethereum, etc.)
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="allow-futures"
                    checked={allowFutures}
                    onCheckedChange={(checked) =>
                      setAllowFutures(checked as boolean)
                    }
                  />
                  <Label
                    htmlFor="allow-futures"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Futures & Commodities
                  </Label>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end gap-4">
            <Button
              variant="outline"
              onClick={() => {
                if (preferences) {
                  setRiskTolerance(preferences.risk_tolerance);
                  setAllowLong(preferences.allow_long);
                  setAllowShort(preferences.allow_short);
                  setAllowOptions(preferences.allow_options);
                  setAllowCrypto(preferences.allow_crypto);
                  setAllowFutures(preferences.allow_futures);
                  setMaxPositionSizePct(
                    preferences.max_position_size_pct.toString()
                  );
                }
              }}
              disabled={!hasChanges()}
            >
              Reset
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges() || updatePreferences.isPending}
            >
              {updatePreferences.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>

          {/* Success Message */}
          {updatePreferences.isSuccess && (
            <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-sm text-green-800">
              Settings saved successfully!
            </div>
          )}

          {/* Error Message */}
          {updatePreferences.isError && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800">
              Error saving settings. Please try again.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
