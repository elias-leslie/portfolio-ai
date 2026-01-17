'use client'

import { AlertTriangle, Award, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface SourceMetrics {
  vendor: string
  duplicateRate: number
  diversityScore: number
  confidenceAvg: number
  freshnessScore: number
  userUsefulRate: number | null
  qualityScore: number
  articleCount: number
  samplePeriodStart: string
  calculatedAt: string
}

export function SourceQualityCard() {
  const [metrics, setMetrics] = useState<SourceMetrics[]>([])
  const [loading, setLoading] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)
  const [profiling, setProfiling] = useState(false)

  const fetchMetrics = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/news/source-stats')
      if (response.ok) {
        const data = await response.json()
        setMetrics(data)
        setLastUpdate(new Date().toISOString())
      }
    } catch (error) {
      console.error('Failed to fetch source metrics:', error)
    } finally {
      setLoading(false)
    }
  }

  const triggerProfiling = async () => {
    try {
      setProfiling(true)
      const response = await fetch('/api/news/profile-sources', {
        method: 'POST',
      })
      if (response.ok) {
        // Wait 5 seconds then refresh
        setTimeout(() => {
          fetchMetrics()
          setProfiling(false)
        }, 5000)
      }
    } catch (error) {
      console.error('Failed to trigger profiling:', error)
      setProfiling(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  const getQualityBadge = (score: number) => {
    if (score >= 0.8) {
      return <Badge className="bg-gain text-text-inverted">Excellent</Badge>
    } else if (score >= 0.6) {
      return <Badge className="bg-accent text-text-inverted">Good</Badge>
    } else if (score >= 0.4) {
      return <Badge className="bg-warning text-text-inverted">Fair</Badge>
    } else {
      return <Badge variant="destructive">Poor</Badge>
    }
  }

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(0)}%`
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins}m ago`

      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`

      const diffDays = Math.floor(diffHours / 24)
      return `${diffDays}d ago`
    } catch {
      return 'Unknown'
    }
  }

  const summary = lastUpdate
    ? `${metrics.filter((m) => m.articleCount > 0).length} active sources • Updated ${formatTimestamp(lastUpdate)}`
    : 'No profiling data captured yet'

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <Award className="h-5 w-5" />
          <span>News Source Quality</span>
        </div>
      }
      description="Quality, freshness, and diversity metrics for each news vendor."
      summary={summary}
      defaultCollapsed
      actions={
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchMetrics}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={triggerProfiling}
            disabled={profiling}
          >
            {profiling ? 'Profiling...' : 'Run Profiling'}
          </Button>
        </div>
      }
    >
      {loading && metrics.length === 0 ? (
        <div className="flex justify-center py-8">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : metrics.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <AlertTriangle className="h-8 w-8 mx-auto mb-2" />
          <p>No profiling data available</p>
          <p className="text-sm">
            Click &quot;Run Profiling&quot; to generate quality metrics
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {metrics
            .filter((m) => m.articleCount > 0)
            .map((metric) => (
              <div
                key={metric.vendor}
                className="border rounded-lg p-3 hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{metric.vendor}</span>
                    {getQualityBadge(metric.qualityScore)}
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {metric.articleCount} articles
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Quality:</span>{' '}
                    <span className="font-medium">
                      {formatPercent(metric.qualityScore)}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Diversity:</span>{' '}
                    <span className="font-medium">
                      {formatPercent(metric.diversityScore)}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Confidence:</span>{' '}
                    <span className="font-medium">
                      {formatPercent(metric.confidenceAvg)}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Freshness:</span>{' '}
                    <span className="font-medium">
                      {formatPercent(metric.freshnessScore)}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Duplicates:</span>{' '}
                    <span className="font-medium">
                      {formatPercent(metric.duplicateRate)}
                    </span>
                  </div>
                  {metric.userUsefulRate !== null && (
                    <div>
                      <span className="text-muted-foreground">Useful:</span>{' '}
                      <span className="font-medium">
                        {formatPercent(metric.userUsefulRate)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
        </div>
      )}
    </ExpandableCard>
  )
}
