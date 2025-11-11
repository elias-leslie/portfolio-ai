"use client";

import { useState, useEffect } from "react";
import { Award, TrendingUp, AlertTriangle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SourceMetrics {
  vendor: string;
  duplicate_rate: number;
  diversity_score: number;
  confidence_avg: number;
  freshness_score: number;
  user_useful_rate: number | null;
  quality_score: number;
  article_count: number;
  sample_period_start: string;
  calculated_at: string;
}

export function SourceQualityCard() {
  const [metrics, setMetrics] = useState<SourceMetrics[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [profiling, setProfiling] = useState(false);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/news/source-stats");
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
        setLastUpdate(new Date().toISOString());
      }
    } catch (error) {
      console.error("Failed to fetch source metrics:", error);
    } finally {
      setLoading(false);
    }
  };

  const triggerProfiling = async () => {
    try {
      setProfiling(true);
      const response = await fetch("/api/news/profile-sources", {
        method: "POST",
      });
      if (response.ok) {
        // Wait 5 seconds then refresh
        setTimeout(() => {
          fetchMetrics();
          setProfiling(false);
        }, 5000);
      }
    } catch (error) {
      console.error("Failed to trigger profiling:", error);
      setProfiling(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const getQualityBadge = (score: number) => {
    if (score >= 0.8) {
      return <Badge className="bg-green-500 text-white">Excellent</Badge>;
    } else if (score >= 0.6) {
      return <Badge className="bg-blue-500 text-white">Good</Badge>;
    } else if (score >= 0.4) {
      return <Badge className="bg-yellow-500 text-white">Fair</Badge>;
    } else {
      return <Badge variant="destructive">Poor</Badge>;
    }
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(0)}%`;
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;

      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;

      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch {
      return "Unknown";
    }
  };

  return (
    <Card className="border-border">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Award className="h-5 w-5" />
            <span>News Source Quality</span>
          </CardTitle>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchMetrics}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={triggerProfiling}
              disabled={profiling}
            >
              {profiling ? "Profiling..." : "Run Profiling"}
            </Button>
          </div>
        </div>
        {lastUpdate && (
          <p className="text-sm text-muted-foreground mt-1">
            Last updated: {formatTimestamp(lastUpdate)}
          </p>
        )}
      </CardHeader>
      <CardContent>
        {loading && metrics.length === 0 ? (
          <div className="flex justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : metrics.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2" />
            <p>No profiling data available</p>
            <p className="text-sm">Click "Run Profiling" to generate quality metrics</p>
          </div>
        ) : (
          <div className="space-y-3">
            {metrics.map((metric) => (
              <div
                key={metric.vendor}
                className="border rounded-lg p-3 hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{metric.vendor}</span>
                    {getQualityBadge(metric.quality_score)}
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {metric.article_count} articles
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Quality:</span>{" "}
                    <span className="font-medium">{formatPercent(metric.quality_score)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Diversity:</span>{" "}
                    <span className="font-medium">{formatPercent(metric.diversity_score)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Confidence:</span>{" "}
                    <span className="font-medium">{formatPercent(metric.confidence_avg)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Freshness:</span>{" "}
                    <span className="font-medium">{formatPercent(metric.freshness_score)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Duplicates:</span>{" "}
                    <span className="font-medium">{formatPercent(metric.duplicate_rate)}</span>
                  </div>
                  {metric.user_useful_rate !== null && (
                    <div>
                      <span className="text-muted-foreground">Useful:</span>{" "}
                      <span className="font-medium">{formatPercent(metric.user_useful_rate)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
