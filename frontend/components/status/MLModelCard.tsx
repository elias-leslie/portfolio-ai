"use client";

import { useState, useEffect } from "react";
import { Brain, TrendingUp, TrendingDown, Calendar, Database, Play, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface MLModelMetrics {
  model_name: string;
  model_version: string;
  trained_at: string;
  training_samples: number;
  test_samples: number;
  accuracy: number;
  precision_score: number;
  recall_score: number;
  f1_score: number;
  useful_count: number;
  not_useful_count: number;
}

interface MLModelStatus {
  current_model: MLModelMetrics | null;
  previous_model: MLModelMetrics | null;
  total_training_samples: number;
  models_trained: number;
  next_training: string;
}

interface TrainingProgress {
  session_id: string;
  status: string; // querying, labeling, training, complete, failed
  current_step: string;
  progress_percent: number;
  articles_found: number;
  articles_labeled: number;
  articles_total: number;
  model_version: string | null;
  accuracy: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export function MLModelCard() {
  const [status, setStatus] = useState<MLModelStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState<TrainingProgress | null>(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/status/ml-model-metrics");
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error("Failed to fetch ML model status:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();

    // Refresh every 5 minutes
    const interval = setInterval(fetchStatus, 300000);
    return () => clearInterval(interval);
  }, []);

  // Poll for training progress
  useEffect(() => {
    if (!training || !trainingProgress) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/ml/training-progress/${trainingProgress.session_id}`);
        if (response.ok) {
          const progress: TrainingProgress = await response.json();
          setTrainingProgress(progress);

          // Stop polling when complete or failed
          if (progress.status === "complete" || progress.status === "failed") {
            setTraining(false);

            // Refresh model status after successful training
            if (progress.status === "complete") {
              setTimeout(fetchStatus, 2000);
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch training progress:", error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [training, trainingProgress]);

  const triggerTraining = async () => {
    try {
      setTraining(true);
      const response = await fetch("/api/ml/trigger-training", {
        method: "POST",
      });

      if (response.ok) {
        const data = await response.json();
        setTrainingProgress({
          session_id: data.session_id,
          status: "queued",
          current_step: "Starting training...",
          progress_percent: 0,
          articles_found: 0,
          articles_labeled: 0,
          articles_total: 0,
          model_version: null,
          accuracy: null,
          error_message: null,
          started_at: new Date().toISOString(),
          completed_at: null,
        });
      } else {
        console.error("Failed to trigger training");
        setTraining(false);
      }
    } catch (error) {
      console.error("Failed to trigger training:", error);
      setTraining(false);
    }
  };

  const getAccuracyBadge = (accuracy: number) => {
    if (accuracy >= 0.8) {
      return <Badge className="bg-green-500 text-white">Excellent</Badge>;
    } else if (accuracy >= 0.7) {
      return <Badge className="bg-blue-500 text-white">Good</Badge>;
    } else if (accuracy >= 0.6) {
      return <Badge className="bg-yellow-500 text-white">Fair</Badge>;
    } else {
      return <Badge variant="destructive">Poor</Badge>;
    }
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  const getMetricTrend = (current: number, previous: number | undefined) => {
    if (!previous) return null;

    const diff = current - previous;
    const isPositive = diff > 0;

    return (
      <span className={`text-xs ml-2 ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
        {isPositive ? <TrendingUp className="inline h-3 w-3" /> : <TrendingDown className="inline h-3 w-3" />}
        {' '}{formatPercent(Math.abs(diff))}
      </span>
    );
  };

  if (loading && !status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            ML Model Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  if (!status || !status.current_model) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            ML Model Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No model trained yet</p>
        </CardContent>
      </Card>
    );
  }

  const { current_model, previous_model } = status;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Article Quality ML Model
          </CardTitle>
          <Button
            size="sm"
            onClick={triggerTraining}
            disabled={training}
          >
            {training ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Training...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Train Now
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Training Progress */}
        {training && trainingProgress && (
          <div className="space-y-2 pb-4 border-b">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Training in Progress</span>
              <Badge variant={
                trainingProgress.status === "complete" ? "default" :
                trainingProgress.status === "failed" ? "destructive" : "secondary"
              }>
                {trainingProgress.status}
              </Badge>
            </div>

            <Progress value={trainingProgress.progress_percent} className="h-2" />

            <p className="text-xs text-muted-foreground">
              {trainingProgress.current_step}
            </p>

            {trainingProgress.status === "labeling" && trainingProgress.articles_total > 0 && (
              <p className="text-xs text-muted-foreground">
                Labeled: {trainingProgress.articles_labeled} / {trainingProgress.articles_total}
              </p>
            )}

            {trainingProgress.error_message && (
              <p className="text-xs text-red-500">
                Error: {trainingProgress.error_message}
              </p>
            )}

            {trainingProgress.status === "complete" && trainingProgress.accuracy && (
              <p className="text-xs text-green-600 font-medium">
                ✓ Complete! New accuracy: {(trainingProgress.accuracy * 100).toFixed(1)}%
              </p>
            )}
          </div>
        )}

        {/* Current Model Info */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Model</span>
            <Badge variant="outline">{current_model.model_version}</Badge>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              Trained
            </span>
            <span>{formatDate(current_model.trained_at)}</span>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Database className="h-3 w-3" />
              Training Samples
            </span>
            <span>{current_model.training_samples + current_model.test_samples} total</span>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="space-y-2 pt-2 border-t">
          <div className="text-sm font-medium mb-2">Performance Metrics</div>

          <div className="flex items-center justify-between">
            <span className="text-sm">Accuracy</span>
            <div className="flex items-center">
              {getAccuracyBadge(current_model.accuracy)}
              <span className="ml-2 text-sm font-mono">{formatPercent(current_model.accuracy)}</span>
              {previous_model && getMetricTrend(current_model.accuracy, previous_model.accuracy)}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm">Precision</span>
            <div className="flex items-center">
              <span className="text-sm font-mono">{formatPercent(current_model.precision_score)}</span>
              {previous_model && getMetricTrend(current_model.precision_score, previous_model.precision_score)}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm">Recall</span>
            <div className="flex items-center">
              <span className="text-sm font-mono">{formatPercent(current_model.recall_score)}</span>
              {previous_model && getMetricTrend(current_model.recall_score, previous_model.recall_score)}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm">F1 Score</span>
            <div className="flex items-center">
              <span className="text-sm font-mono">{formatPercent(current_model.f1_score)}</span>
              {previous_model && getMetricTrend(current_model.f1_score, previous_model.f1_score)}
            </div>
          </div>
        </div>

        {/* Label Distribution */}
        <div className="space-y-2 pt-2 border-t">
          <div className="text-sm font-medium mb-2">Training Data Balance</div>

          <div className="flex items-center justify-between text-xs">
            <span>Useful Articles</span>
            <span className="font-mono">{current_model.useful_count} ({formatPercent(current_model.useful_count / (current_model.useful_count + current_model.not_useful_count))})</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span>Not Useful Articles</span>
            <span className="font-mono">{current_model.not_useful_count} ({formatPercent(current_model.not_useful_count / (current_model.useful_count + current_model.not_useful_count))})</span>
          </div>
        </div>

        {/* Training History */}
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Total Models Trained</span>
            <span className="font-mono">{status.models_trained}</span>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Next Scheduled Training</span>
            <span>{formatDate(status.next_training)}</span>
          </div>
        </div>

        {/* Info */}
        <div className="pt-2 border-t">
          <p className="text-xs text-muted-foreground">
            Model automatically retrains daily with new Gemini-labeled articles to adapt to evolving news patterns.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
