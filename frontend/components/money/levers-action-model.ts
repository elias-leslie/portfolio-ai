import type {
  HouseholdCategoryMonthlyTrendPoint,
  HouseholdPriceFinding,
  HouseholdPriceInsight,
  HouseholdProductSummary,
  HouseholdSpendingTransaction,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import type { LeverOpportunity } from './lever-helpers'
import type { MerchantAggregate } from './merchant-aggregation'

export type SavingsActionKind =
  | 'verified'
  | 'recurring_item'
  | 'cut_candidate'
  | 'deviation'
  | 'modeled'

export interface TrendPoint {
  date: string
  value: number
}

export interface TrendSeries {
  id: string
  label: string
  points: TrendPoint[]
  tone?: 'good' | 'bad' | 'neutral'
}

export interface SavingsAction {
  id: string
  kind: SavingsActionKind
  priority: number
  title: string
  playbook: string
  detail: string
  amountLabel: string
  evidenceLabel: string
  tone: 'success' | 'warning' | 'outline'
  score: number
  footnote?: string
  trend?: TrendSeries[]
}

interface BuildSavingsActionsInput {
  priceFindings: HouseholdPriceFinding[]
  products: HouseholdProductSummary[]
  transactions: HouseholdSpendingTransaction[]
  merchantRows: MerchantAggregate[]
  categoryMonthlyTrend: HouseholdCategoryMonthlyTrendPoint[]
  modeledLevers: LeverOpportunity[]
  priceInsights: HouseholdPriceInsight[]
  coverageMonths: number
}

function money(value: number, decimals = 0) {
  return formatCurrency(value, { decimals })
}

function pointValue(point: { unitPrice?: number | null; totalPrice: number }) {
  return point.unitPrice ?? point.totalPrice
}

function productTrend(product: HouseholdProductSummary): TrendSeries[] {
  return [
    {
      id: product.id,
      label: product.canonicalName,
      tone: 'bad',
      points: product.pricePoints.map((point) => ({
        date: point.observedDate,
        value: pointValue(point),
      })),
    },
  ]
}

function categoryTrend(
  category: string,
  rows: HouseholdCategoryMonthlyTrendPoint[],
): TrendSeries[] {
  const points = rows
    .filter((row) => row.category === category)
    .sort((left, right) => left.month.localeCompare(right.month))
    .map((row) => ({ date: row.month, value: row.totalSpend }))
  return points.length > 0
    ? [{ id: category, label: category, tone: 'bad', points }]
    : []
}

export function buildSavingsActions({
  priceFindings,
  products,
  transactions,
  merchantRows,
  categoryMonthlyTrend,
  modeledLevers,
  priceInsights,
  coverageMonths,
}: BuildSavingsActionsInput): SavingsAction[] {
  const actions: SavingsAction[] = []

  for (const finding of priceFindings
    .filter((row) => row.kind === 'cheaper_elsewhere')
    .sort(
      (left, right) =>
        (right.savingsEstimate ?? 0) - (left.savingsEstimate ?? 0),
    )
    .slice(0, 4)) {
    const savings = finding.savingsEstimate ?? 0
    const vendor = finding.vendorKey
      ? formatEnumLabel(finding.vendorKey)
      : 'cheaper vendor'
    const quotedItem = finding.vendorTitle ?? finding.productName ?? 'this item'
    const packageText = finding.vendorPackageLabel
      ? ` (${finding.vendorPackageLabel})`
      : ''
    const promoText = finding.vendorPromoText
      ? ` Promo: ${finding.vendorPromoText}.`
      : ''
    actions.push({
      id: `verified-${finding.id}`,
      kind: 'verified',
      priority: 1,
      title: `Buy ${quotedItem} at ${vendor}`,
      playbook: 'Use cheaper comparable item before rebuy',
      detail:
        finding.vendorPrice != null && finding.householdPrice != null
          ? `${vendor} quoted ${quotedItem}${packageText} at ${money(finding.vendorPrice, 2)} vs your ${money(finding.householdPrice, 2)} for ${finding.productName ?? 'this product'}.${promoText}`
          : `${vendor} is cheaper in the latest price-check finding.${promoText}`,
      amountLabel: `Save ${money(savings, 2)}/rebuy`,
      evidenceLabel: 'Verified',
      tone: 'success',
      score: savings,
      footnote: 'Stored vendor quote; this is a concrete per-rebuy saving.',
    })
  }

  for (const product of products) {
    if (product.purchaseCount < 2 || product.pricePoints.length < 2) continue
    const values = product.pricePoints
      .map(pointValue)
      .filter((value) => value > 0)
    if (values.length < 2) continue
    const latest = values[values.length - 1]
    const priorLow = Math.min(...values.slice(0, -1))
    const delta = latest - priorLow
    if (delta < Math.max(0.5, priorLow * 0.15)) continue
    actions.push({
      id: `recurring-${product.id}`,
      kind: 'recurring_item',
      priority: 2,
      title: `Find lower unit-price substitute for ${product.canonicalName}`,
      playbook: 'Compare same size/oz or alternate brand',
      detail: `${product.purchaseCount} buys. Latest unit basis is ${money(latest, 2)} vs prior low ${money(priorLow, 2)}.`,
      amountLabel: `${money(delta, 2)} higher/unit`,
      evidenceLabel: 'Recurring item',
      tone: 'warning',
      score: delta * product.purchaseCount,
      footnote:
        'This flags a recurring item to price-check; it is not verified cheaper elsewhere until a vendor quote exists.',
      trend: productTrend(product),
    })
  }

  for (const merchant of merchantRows) {
    if (
      merchant.transactionCount < 3 ||
      !['discretionary', 'mixed'].includes(merchant.essentiality)
    ) {
      continue
    }
    const monthlySpend =
      coverageMonths > 0
        ? merchant.totalSpend / coverageMonths
        : merchant.totalSpend
    const cutShare = merchant.essentiality === 'discretionary' ? 0.5 : 0.25
    actions.push({
      id: `cut-${merchant.merchant}`,
      kind: 'cut_candidate',
      priority: 3,
      title: `Cut or cap ${merchant.merchant}`,
      playbook:
        merchant.essentiality === 'discretionary'
          ? 'Do-without candidate'
          : 'Separate wants from needs',
      detail: `${merchant.transactionCount} ${merchant.category} charges ran ${money(monthlySpend)}/mo.`,
      amountLabel: `Review ${money(monthlySpend * cutShare)}/mo`,
      evidenceLabel: formatEnumLabel(merchant.essentiality),
      tone: 'warning',
      score: monthlySpend * cutShare,
      footnote:
        'Priority is based on non-essential frequency and monthly run-rate; exact savings depends on what you cut.',
    })
  }

  const trendByCategory = new Map<
    string,
    HouseholdCategoryMonthlyTrendPoint[]
  >()
  for (const row of categoryMonthlyTrend) {
    const bucket = trendByCategory.get(row.category) ?? []
    bucket.push(row)
    trendByCategory.set(row.category, bucket)
  }
  for (const [category, rows] of trendByCategory) {
    const sorted = [...rows].sort((left, right) =>
      left.month.localeCompare(right.month),
    )
    if (sorted.length < 2) continue
    const latest = sorted[sorted.length - 1]
    const prior = sorted.slice(0, -1)
    const priorAverage =
      prior.reduce((sum, row) => sum + row.totalSpend, 0) / prior.length
    const delta = latest.totalSpend - priorAverage
    if (delta < Math.max(100, priorAverage * 0.25)) continue
    actions.push({
      id: `deviation-category-${category}`,
      kind: 'deviation',
      priority: 4,
      title: `${category} jumped above normal`,
      playbook: 'Inspect unusual purchases',
      detail: `${latest.month} ran ${money(latest.totalSpend)} vs ${money(priorAverage)} recent norm.`,
      amountLabel: `+${money(delta)}`,
      evidenceLabel: 'Deviation',
      tone: 'outline',
      score: delta,
      trend: categoryTrend(category, categoryMonthlyTrend),
    })
  }

  const transactionsByMerchant = new Map<
    string,
    HouseholdSpendingTransaction[]
  >()
  for (const transaction of transactions) {
    const bucket = transactionsByMerchant.get(transaction.merchant) ?? []
    bucket.push(transaction)
    transactionsByMerchant.set(transaction.merchant, bucket)
  }
  for (const [merchant, rows] of transactionsByMerchant) {
    if (rows.length < 3) continue
    const average = rows.reduce((sum, row) => sum + row.amount, 0) / rows.length
    const latest = [...rows].sort((left, right) =>
      right.date.localeCompare(left.date),
    )[0]
    const delta = latest.amount - average
    if (delta < Math.max(50, average)) continue
    actions.push({
      id: `deviation-transaction-${latest.id}`,
      kind: 'deviation',
      priority: 4,
      title: `${merchant} charge is above normal`,
      playbook: 'Review outlier purchase',
      detail: `${latest.description} was ${money(latest.amount, 2)} vs ${money(average, 2)} merchant norm.`,
      amountLabel: `+${money(delta, 2)}`,
      evidenceLabel: 'Outlier',
      tone: 'outline',
      score: delta,
    })
  }

  for (const signal of priceInsights.slice(0, 2)) {
    const change = Math.max(
      Math.abs(signal.unitPriceChangePct ?? 0),
      Math.abs(signal.priceChangePct ?? 0),
    )
    if (change < 15) continue
    actions.push({
      id: `deviation-price-${signal.merchant}-${signal.itemName}`,
      kind: 'deviation',
      priority: 4,
      title: `${signal.itemName} price is outside normal`,
      playbook: 'Run price check before rebuy',
      detail: `${signal.merchant} shows ${change.toFixed(0)}% ticket/unit drift.`,
      amountLabel: 'Price drift',
      evidenceLabel: 'Deviation',
      tone: 'outline',
      score: change,
    })
  }

  for (const lever of modeledLevers) {
    if (lever.id === 'price-signal') continue
    const modeledFootnote =
      lever.id === 'concentration'
        ? `Modeled at ${formatPercent(lever.trimRate * 100, { decimals: 0 })} of monthly spend — rule of thumb, not a guaranteed saving.`
        : `Modeled at ${formatPercent(lever.trimRate * 100, { decimals: 0 })} trim — rule of thumb, not a guaranteed saving.`
    actions.push({
      id: `modeled-${lever.id}`,
      kind: 'modeled',
      priority: 5,
      title: lever.title,
      playbook: lever.playbook,
      detail: lever.detail,
      amountLabel: lever.savingsLabel ?? `${money(lever.monthlySavings)}/mo`,
      evidenceLabel: lever.evidenceLabel ?? 'Modeled',
      tone: lever.tone,
      score: lever.monthlySavings,
      footnote:
        lever.note != null
          ? `${lever.note} ${modeledFootnote}`
          : (lever.footnote ?? modeledFootnote),
    })
  }

  return actions.sort(
    (left, right) => left.priority - right.priority || right.score - left.score,
  )
}

export function topTrendSeries(actions: SavingsAction[]): TrendSeries[] {
  const series: TrendSeries[] = []
  for (const action of actions) {
    for (const trend of action.trend ?? []) {
      if (trend.points.length < 2) continue
      if (series.some((existing) => existing.id === trend.id)) continue
      series.push(trend)
      if (series.length >= 4) return series
    }
  }
  return series
}
