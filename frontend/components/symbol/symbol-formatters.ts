import type { JennyNotification } from '@/lib/api/portfolio'
import { formatEnumLabel, formatPercent } from '@/lib/formatters'

export function formatCountLabel(
  count: number,
  singular: string,
  plural = `${singular}s`,
) {
  return `${count} ${count === 1 ? singular : plural}`
}

export function formatEvidenceSummary(
  confirmations?: number | null,
  avoidFlags?: number | null,
) {
  const segments: string[] = []

  if (confirmations != null) {
    segments.push(formatCountLabel(confirmations, 'green light'))
  }
  if (avoidFlags != null && (avoidFlags > 0 || confirmations != null)) {
    segments.push(formatCountLabel(avoidFlags, 'caution flag'))
  }

  return segments.length > 0 ? segments.join(' · ') : null
}

export function formatTenPointConfidence(confidence?: number | null) {
  if (confidence == null) {
    return 'Confidence unavailable'
  }

  const boundedConfidence = Math.max(0, Math.min(10, confidence))
  const displayValue = Number.isInteger(boundedConfidence)
    ? boundedConfidence.toFixed(0)
    : boundedConfidence.toFixed(1)

  return `${displayValue}/10 confidence`
}

export function formatShareCount(shares?: number | null) {
  if (shares == null) {
    return null
  }

  return `${shares.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: Number.isInteger(shares) ? 0 : 2,
  })} share${Math.abs(shares) === 1 ? '' : 's'}`
}

export function formatPortfolioWeight(weightPct?: number | null) {
  if (weightPct == null) {
    return null
  }

  if (weightPct > 0 && weightPct < 0.1) {
    return '<0.1% of invested assets'
  }

  return `${formatPercent(weightPct)} of invested assets`
}

export function formatIfNotHeldReasoning(reasoning?: string | null) {
  if (!reasoning) {
    return 'No extra context yet.'
  }

  return reasoning.replace(
    /Signal:\s*([A-Z_]+),\s*Strength:\s*(\d+(?:\.\d+)?)\/10/gi,
    (_, signalType: string, strength: string) =>
      `Current setup: ${formatEnumLabel(signalType, 'Unavailable')} · Strength ${strength}/10`,
  )
}

export function formatNewsSentimentSummary(
  news?: {
    sentimentLabel?: string | null
    sentimentScore?: number | null
  } | null,
) {
  if (news?.sentimentLabel) {
    return news.sentimentScore != null
      ? `${news.sentimentLabel} · score ${news.sentimentScore.toFixed(1)}`
      : news.sentimentLabel
  }

  if (news?.sentimentScore != null) {
    return `Sentiment score ${news.sentimentScore.toFixed(1)}`
  }

  return 'Sentiment unavailable'
}

export function stripSymbolPrefix(title: string, symbol: string) {
  return title.replace(new RegExp(`^${symbol}:\\s*`, 'i'), '')
}

export function compareNotifications(
  a: JennyNotification,
  b: JennyNotification,
) {
  const severityRank = (severity?: string | null) => {
    if (severity === 'critical') {
      return 0
    }
    if (severity === 'warning') {
      return 1
    }
    return 2
  }

  const severityDelta = severityRank(a.severity) - severityRank(b.severity)
  if (severityDelta !== 0) {
    return severityDelta
  }

  return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
}
