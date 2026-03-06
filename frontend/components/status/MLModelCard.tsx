'use client'

import {
  Brain,
  Calendar,
  Database,
  Loader2,
  Play,
  TriangleAlert,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { apiRequest, post } from '@/lib/api/client'

interface MLModelMetrics {
  modelName: string
  modelVersion: string
  trainedAt: string
  trainingSamples: number
  testSamples: number
  accuracy: number
  precisionScore: number
  recallScore: number
  f1Score: number
  usefulCount: number
  notUsefulCount: number
}

interface MLModelStatus {
  currentModel: MLModelMetrics | null
  previousModel: MLModelMetrics | null
  totalTrainingSamples: number
  modelsTrained: number
  nextTraining: string
}

interface TrainingProgress {
  sessionId: string
  status: string
  currentStep: string
  progressPercent: number
  articlesFound: number
  articlesLabeled: number
  articlesTotal: number
  modelVersion: string | null
  accuracy: number | null
  errorMessage: string | null
  startedAt: string
  completedAt: string | null
}

export function MLModelCard({ readOnly = false }: { readOnly?: boolean }) {
  const [status, setStatus] = useState<MLModelStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState(false)
  const [trainingProgress, setTrainingProgress] =
    useState<TrainingProgress | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true)
      const data = await apiRequest<MLModelStatus>(
        '/api/status/ml-model-metrics',
      )
      setStatus(data)
    } catch (error) {
      console.error('Failed to fetch ML model status:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 300000) // 5 min
    return () => clearInterval(interval)
  }, [fetchStatus])

  useEffect(() => {
    if (!training || !trainingProgress) return

    const poll = setInterval(async () => {
      try {
        const progress = await apiRequest<TrainingProgress>(
          `/api/ml/training-progress/${trainingProgress.sessionId}`,
        )
        setTrainingProgress(progress)
        if (progress.status === 'complete' || progress.status === 'failed') {
          setTraining(false)
          if (progress.status === 'complete') {
            setTimeout(fetchStatus, 2000)
          }
        }
      } catch (error) {
        console.error('Failed to fetch training progress:', error)
      }
    }, 2000)

    return () => clearInterval(poll)
  }, [training, trainingProgress, fetchStatus])

  const currentModel = status?.currentModel ?? null
  const previousModel = status?.previousModel ?? null
  const nextTraining = status?.nextTraining ?? null
  const trainingAgeHours = currentModel
    ? getAgeHours(currentModel.trainedAt)
    : null
  const freshness = getModelFreshness(trainingAgeHours)

  const triggerTraining = async () => {
    try {
      setTraining(true)
      const data = await post<{ sessionId: string }>('/api/ml/trigger-training')
      setTrainingProgress({
        sessionId: data.sessionId,
        status: 'queued',
        currentStep: 'Starting training...',
        progressPercent: 0,
        articlesFound: 0,
        articlesLabeled: 0,
        articlesTotal: 0,
        modelVersion: null,
        accuracy: null,
        errorMessage: null,
        startedAt: new Date().toISOString(),
        completedAt: null,
      })
    } catch (error) {
      console.error('Failed to trigger training:', error)
      setTraining(false)
    }
  }

  const summary = (() => {
    if (!currentModel) {
      if (!status) return 'No trained model yet'
      return `${status.modelsTrained ?? 0} models trained • ${(status.totalTrainingSamples ?? 0).toLocaleString()} samples`
    }

    const parts = [
      `v${currentModel.modelVersion}`,
      `${formatPercent(currentModel.accuracy)} accuracy`,
    ]

    if (freshness.label === 'Critical') {
      parts.push(`Last trained ${formatRelativeAge(trainingAgeHours)}`)
    } else if (nextTraining) {
      parts.push(`Next ${new Date(nextTraining).toLocaleDateString()}`)
    }

    return parts.join(' • ')
  })()

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
      actions={!readOnly ? (
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
      ) : undefined}
      contentClassName="space-y-6"
    >
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStatus}
          disabled={loading}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Refresh'}
        </Button>
        <Badge variant="outline">
          {status?.modelsTrained ?? 0} models trained
        </Badge>
        {currentModel && (
          <Badge className={freshness.className}>{freshness.label}</Badge>
        )}
      </div>

      {training && trainingProgress && (
        <div className="space-y-2 pb-4 border-b">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Training in Progress</span>
            <Badge
              variant={
                trainingProgress.status === 'complete'
                  ? 'default'
                  : trainingProgress.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
              }
            >
              {trainingProgress.status.replace(/_/g, ' ')}
            </Badge>
          </div>
          <Progress value={trainingProgress.progressPercent} className="h-2" />
          <p className="text-xs text-muted-foreground">
            {trainingProgress.currentStep}
          </p>
          {trainingProgress.errorMessage && (
            <p className="text-xs text-status-error">
              Error: {trainingProgress.errorMessage}
            </p>
          )}
        </div>
      )}

      {currentModel ? (
        <div className="space-y-4">
          {freshness.label !== 'Fresh' && (
            <div className="flex items-start gap-2 rounded-lg border border-status-warning/40 bg-status-warning/10 p-3 text-sm text-text">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-status-warning" />
              <div>
                Model telemetry is stale. Last successful training was{' '}
                {formatDate(currentModel.trainedAt)}.
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Model</span>
            <Badge variant="outline">{currentModel.modelVersion}</Badge>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Trained
            </span>
            <span>{formatDate(currentModel.trainedAt)}</span>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Database className="h-3 w-3" /> Training Samples
            </span>
            <span>
              {currentModel.trainingSamples + currentModel.testSamples}
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t">
            <div className="text-sm font-medium">Performance Metrics</div>
            {renderMetricRow(
              'Accuracy',
              currentModel.accuracy,
              previousModel?.accuracy,
              getAccuracyBadge,
            )}
            {renderMetricRow(
              'Precision',
              currentModel.precisionScore,
              previousModel?.precisionScore,
            )}
            {renderMetricRow(
              'Recall',
              currentModel.recallScore,
              previousModel?.recallScore,
            )}
            {renderMetricRow(
              'F1 Score',
              currentModel.f1Score,
              previousModel?.f1Score,
            )}
          </div>

          <div className="space-y-2 pt-2 border-t">
            <div className="text-sm font-medium">Training Data Balance</div>
            <div className="flex items-center justify-between text-xs">
              <span>Useful Articles</span>
              <span className="font-mono">
                {currentModel.usefulCount} (
                {formatPercent(safeRatio(
                  currentModel.usefulCount,
                  currentModel.usefulCount + currentModel.notUsefulCount,
                ))}
                )
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>Not Useful Articles</span>
              <span className="font-mono">
                {currentModel.notUsefulCount} (
                {formatPercent(safeRatio(
                  currentModel.notUsefulCount,
                  currentModel.usefulCount + currentModel.notUsefulCount,
                ))}
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
            <span className="font-mono">{status.modelsTrained}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Next Scheduled Training</span>
            <span>
              {freshness.label === 'Critical'
                ? `Expected ${formatDate(status.nextTraining)}`
                : formatDate(status.nextTraining)}
            </span>
          </div>
        </div>
      )}
    </ExpandableCard>
  )
}

function renderMetricRow(
  label: string,
  current: number,
  previous?: number,
  badgeRenderer?: (value: number) => React.ReactElement,
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
  )
}

function getAccuracyBadge(accuracy: number) {
  if (accuracy >= 0.8)
    return (
      <Badge className="bg-status-success text-text-inverted">Excellent</Badge>
    )
  if (accuracy >= 0.7)
    return <Badge className="bg-status-info text-text-inverted">Good</Badge>
  if (accuracy >= 0.6)
    return <Badge className="bg-status-warning text-text-inverted">Fair</Badge>
  return <Badge variant="destructive">Poor</Badge>
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return 'Unknown'
  }
}

function getAgeHours(iso: string) {
  const timestamp = Date.parse(iso)
  if (!Number.isFinite(timestamp)) return null
  return (Date.now() - timestamp) / 3600000
}

function formatRelativeAge(ageHours: number | null) {
  if (ageHours === null) return 'at an unknown time'
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m ago`
  if (ageHours < 24) return `${Math.round(ageHours)}h ago`
  return `${Math.round(ageHours / 24)}d ago`
}

function getModelFreshness(ageHours: number | null) {
  if (ageHours === null) {
    return {
      label: 'Unknown',
      className: 'bg-surface-muted text-text',
    }
  }

  if (ageHours > 48) {
    return {
      label: 'Critical',
      className: 'bg-status-error text-text-inverted',
    }
  }

  if (ageHours > 24) {
    return {
      label: 'Stale',
      className: 'bg-status-warning text-text-inverted',
    }
  }

  return {
    label: 'Fresh',
    className: 'bg-status-success text-text-inverted',
  }
}

function safeRatio(numerator: number, denominator: number) {
  if (denominator <= 0) return 0
  return numerator / denominator
}

function getMetricTrend(current: number, previous?: number) {
  if (previous === undefined) return null
  if (Math.abs(current - previous) < 0.001) return null

  const rising = current > previous
  const Icon = rising ? TrendingUp : TrendingDown
  const tone = rising ? 'text-status-success' : 'text-status-error'

  return (
    <span className={`flex items-center text-xs ${tone}`}>
      <Icon className="h-3 w-3 mr-0.5" />
      {(Math.abs(current - previous) * 100).toFixed(1)}%
    </span>
  )
}
