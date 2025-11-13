"use client";

import { useState, useEffect } from "react";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Calendar,
  Database,
  Play,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ExpandableCard } from "@/components/status/ExpandableCard";

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
  status: string;
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
  const [trainingProgress, setTrainingProgress] =
    useState<TrainingProgress | null>(null);

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
    const interval = setInterval(fetchStatus, 300000); // 5 min
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!training || !trainingProgress) return;

    const poll = setInterval(async () => {
      try {
        const response = await fetch(
          `/api/ml/training-progress/${trainingProgress.session_id}`,
        );
        if (response.ok) {
          const progress: TrainingProgress = await response.json();
          setTrainingProgress(progress);
          if (progress.status === "complete" || progress.status === "failed") {
            setTraining(false);
            if (progress.status === "complete") {
              setTimeout(fetchStatus, 2000);
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch training progress:", error);
      }
    }, 2000);

    return () => clearInterval(poll);
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

  const summary = (() => {
    if (!status?.current_model) {
      if (!status) return "No trained model yet";
      return `${status.models_trained} models trained • ${status.total_training_samples.toLocaleString()} samples`;
    }
    return [
      `v${status.current_model.model_version}`,
      `${formatPercent(status.current_model.accuracy)} accuracy`,
      status.next_training
        ? `Next ${new Date(status.next_training).toLocaleDateString()}`
        : "Next training TBD",
    ].join(" • ");
  })();

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5" />
          <span>Article Quality ML Model</span>
        </div>
      }
      description="Monitor classifier health and trigger retraining."
      summary={summary}
      defaultCollapsed
      actions={
        <Button
          variant="default"
          size="sm"
          onClick={triggerTraining}
          disabled={training}
          className="gap-2"
        >
          {training ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Training...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Train Now
            </>
          )}
        </Button>
      }
      contentClassName="space-y-6"
    >
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStatus}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            "Refresh"
          )}
        </Button>
        <Badge variant="outline">
          {status?.models_trained ?? 0} models trained
        </Badge>
      </div>

      {training && trainingProgress && (
        <div className="space-y-2 pb-4 border-b">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Training in Progress</span>
            <Badge
              variant={
                trainingProgress.status === "complete"
                  ? "default"
                  : trainingProgress.status === "failed"
                  ? "destructive"
                  : "secondary"
              }
            >
              {trainingProgress.status.replace(/_/g, " ")}
            </Badge>
          </div>
          <Progress value={trainingProgress.progress_percent} className="h-2" />
          <p className="text-xs text-muted-foreground">
            {trainingProgress.current_step}
          </p>
          {trainingProgress.error_message && (
            <p className="text-xs text-red-500">
              Error: {trainingProgress.error_message}
            </p>
          )}
        </div>
      )}

      {status?.current_model ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Model</span>
            <Badge variant="outline">
              {status.current_model.model_version}
            </Badge>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Trained
            </span>
            <span>{formatDate(status.current_model.trained_at)}</span>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Database className="h-3 w-3" /> Training Samples
            </span>
            <span>
              {status.current_model.training_samples +
                status.current_model.test_samples}
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t">
            <div className="text-sm font-medium">Performance Metrics</div>
            {renderMetricRow(
              "Accuracy",
              status.current_model.accuracy,
              status.previous_model?.accuracy,
              getAccuracyBadge,
            )}
            {renderMetricRow(
              "Precision",
              status.current_model.precision_score,
              status.previous_model?.precision_score,
            )}
            {renderMetricRow(
              "Recall",
              status.current_model.recall_score,
              status.previous_model?.recall_score,
            )}
            {renderMetricRow(
              "F1 Score",
              status.current_model.f1_score,
              status.previous_model?.f1_score,
            )}
          </div>

          <div className="space-y-2 pt-2 border-t">
            <div className="text-sm font-medium">Training Data Balance</div>
            <div className="flex items-center justify-between text-xs">
              <span>Useful Articles</span>
              <span className="font-mono">
                {status.current_model.useful_count} (
                {formatPercent(
                  status.current_model.useful_count /
                    (status.current_model.useful_count +
                      status.current_model.not_useful_count),
                )}
                )
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>Not Useful Articles</span>
              <span className="font-mono">
                {status.current_model.not_useful_count} (
                {formatPercent(
                  status.current_model.not_useful_count /
                    (status.current_model.useful_count +
                      status.current_model.not_useful_count),
                )}
                )
              </span>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No trained model available. Trigger a training session to generate a
          production classifier.
        </p>
      )}

      {status && (
        <div className="grid gap-2 pt-2 border-t text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>Total Models Trained</span>
            <span className="font-mono">{status.models_trained}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Next Scheduled Training</span>
            <span>{formatDate(status.next_training)}</span>
          </div>
        </div>
      )}
    </ExpandableCard>
  );
}

function renderMetricRow(
  label: string,
  current: number,
  previous?: number,
  badgeRenderer?: (value: number) => JSX.Element,
) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      <div className="flex items-center gap-2">
        {badgeRenderer ? badgeRenderer(current) : null}
        <span className="font-mono">{formatPercent(current)}</span>
        {previous !== undefined && getMetricTrend(current, previous)}
      </div>
    </div>
  );
}

function getAccuracyBadge(accuracy: number) {
  if (accuracy >= 0.8) return <Badge className="bg-green-500 text-white">Excellent</Badge>;
  if (accuracy >= 0.7) return <Badge className="bg-blue-500 text-white">Good</Badge>;
  if (accuracy >= 0.6) return <Badge className="bg-yellow-500 text-white">Fair</Badge>;
  return <Badge variant="destructive">Poor</Badge>;
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return "Unknown";
  }
}

function getMetricTrend(current: number, previous?: number) {
  if (previous === undefined) return null;
  if (Math.abs(current - previous) < 0.001) return null;

  const rising = current > previous;
  const Icon = rising ? TrendingUp : TrendingDown;
  const tone = rising ? "text-green-500" : "text-red-500";

  return (
    <span className={`flex items-center text-xs ${tone}`}>
      <Icon className="h-3 w-3 mr-0.5" />
      {( Math.abs(current - previous) * 100).toFixed(1)}%
    </span>
  );
}
