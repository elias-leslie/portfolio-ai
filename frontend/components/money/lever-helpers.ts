import type {
  HouseholdPriceFinding,
  HouseholdPriceInsight,
  HouseholdSpendingCategory,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import type { MerchantAggregate } from './merchant-aggregation'

export type LeverOpportunity = {
  id: string
  title: string
  playbook: string
  monthlySavings: number
  annualSavings: number
  // Fixed rule-of-thumb rate the savings were modeled at, so the UI can show it.
  trimRate: number
  detail: string
  tone: 'success' | 'warning' | 'outline'
  additive: boolean
  savingsLabel?: string
  evidenceLabel?: string
  footnote?: string
  concrete?: boolean
  // Set when this lever's dollars overlap another lever (e.g. a merchant inside a
  // category) so the card can flag that trimming both is not additive.
  note?: string
}

export const modeledTrimRates: Record<string, number> = {
  Subscriptions: 0.2,
  Dining: 0.15,
  Retail: 0.12,
  Travel: 0.1,
  Fitness: 0.15,
  Home: 0.12,
  Household: 0.06,
}

export function formatLeverDate(value?: string | null) {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function categoryPlaybook(category: string, essentiality: string) {
  if (category === 'Subscriptions') {
    return 'Sweep recurring line items'
  }
  if (category === 'Retail') {
    return 'Batch orders and set cap'
  }
  if (category === 'Travel') {
    return 'Pre-approve trips before booking'
  }
  if (category === 'Dining') {
    return 'Cap convenience spend'
  }
  if (essentiality === 'discretionary') {
    return 'Trim by rule, not memory'
  }
  if (essentiality === 'mixed') {
    return 'Split wants from needs'
  }
  return 'Protect, monitor, renegotiate'
}

export function trimRateForCategory(category: string, essentiality: string) {
  if (category in modeledTrimRates) {
    return modeledTrimRates[category]
  }
  if (essentiality === 'discretionary') {
    return 0.1
  }
  if (essentiality === 'mixed') {
    return 0.05
  }
  return 0.0
}

export function merchantPlaybook(
  category: string,
  essentiality: string,
  transactionCount: number,
) {
  if (category === 'Subscriptions') {
    return 'Cancel, downgrade, or annualize'
  }
  if (transactionCount >= 8 && essentiality === 'discretionary') {
    return 'Add a merchant cap'
  }
  if (essentiality === 'discretionary') {
    return 'Reduce frequency first'
  }
  if (essentiality === 'mixed') {
    return 'Separate staples from drift'
  }
  return 'Keep, then price-check'
}

export interface BuildLeversInput {
  subscriptionCategory: HouseholdSpendingCategory | null
  topDiscretionaryCategory: HouseholdSpendingCategory | null
  topDiscretionaryMerchant: MerchantAggregate | null
  topThreeShare: number
  averageMonthlySpend: number
  coverageMonths: number | undefined
  bestPriceSignal: HouseholdPriceInsight | null
  priceFindings?: HouseholdPriceFinding[]
}

/**
 * Rank up to four trim/watch levers for the window. Pure so it can be unit-tested
 * without rendering the panel.
 */
export function buildLevers({
  subscriptionCategory,
  topDiscretionaryCategory,
  topDiscretionaryMerchant,
  topThreeShare,
  averageMonthlySpend,
  coverageMonths,
  bestPriceSignal,
  priceFindings = [],
}: BuildLeversInput): LeverOpportunity[] {
  const opportunities: LeverOpportunity[] = []

  const push = (value: LeverOpportunity | null) => {
    if (!value || value.monthlySavings <= 0) {
      return
    }
    opportunities.push(value)
  }

  for (const finding of priceFindings
    .filter((row) => row.kind === 'cheaper_elsewhere')
    .sort(
      (left, right) =>
        (right.savingsEstimate ?? 0) - (left.savingsEstimate ?? 0),
    )
    .slice(0, 2)) {
    const savings = finding.savingsEstimate ?? 0
    const vendor = finding.vendorKey
      ? formatEnumLabel(finding.vendorKey)
      : 'Another vendor'
    const productName = finding.productName ?? 'Product'
    const itemName =
      productName.length > 48
        ? `${productName.slice(0, 48).trimEnd()}…`
        : productName
    push({
      id: `cheaper-elsewhere-${finding.id}`,
      title: `${itemName} is cheaper at ${vendor}`,
      playbook: 'Buy at the cheaper vendor',
      monthlySavings: savings,
      annualSavings: 0,
      trimRate: 0,
      detail:
        finding.vendorPrice != null && finding.householdPrice != null
          ? `${vendor} has it for ${formatCurrency(finding.vendorPrice, { decimals: 2 })} vs your ${formatCurrency(finding.householdPrice, { decimals: 2 })}.`
          : `Open price-check finding shows ${vendor} is cheaper before the next rebuy.`,
      tone: 'success',
      additive: false,
      savingsLabel: `Save ${formatCurrency(savings, { decimals: 2 })}/rebuy`,
      evidenceLabel: 'Price check',
      footnote:
        'Concrete cheaper-elsewhere finding from stored vendor quotes — not modeled monthly savings.',
      concrete: true,
    })
  }

  if (subscriptionCategory) {
    const monthlySavings = subscriptionCategory.averageMonthlySpend * 0.2
    push({
      id: 'subscriptions',
      title: 'Subscription sweep first',
      playbook: 'Cancel, downgrade, or annualize',
      monthlySavings,
      annualSavings: monthlySavings * 12,
      trimRate: 0.2,
      detail: `${subscriptionCategory.transactionCount} subscription charges are running about ${formatCurrency(subscriptionCategory.averageMonthlySpend, { decimals: 0 })}/mo. A 20% trim frees real room fast.`,
      tone: 'warning',
      additive: true,
    })
  }

  if (topDiscretionaryCategory) {
    const trimRate = trimRateForCategory(
      topDiscretionaryCategory.category,
      topDiscretionaryCategory.essentiality,
    )
    const monthlySavings =
      topDiscretionaryCategory.averageMonthlySpend * trimRate
    push({
      id: 'category',
      title: `${topDiscretionaryCategory.category} is biggest trim lever`,
      playbook: categoryPlaybook(
        topDiscretionaryCategory.category,
        topDiscretionaryCategory.essentiality,
      ),
      monthlySavings,
      annualSavings: monthlySavings * 12,
      trimRate,
      detail: `${topDiscretionaryCategory.category} is ${formatCurrency(topDiscretionaryCategory.averageMonthlySpend, { decimals: 0 })}/mo and ${formatPercent(topDiscretionaryCategory.shareOfSpend * 100, { decimals: 0 })} of this window.`,
      tone: 'warning',
      additive: topDiscretionaryCategory.category !== 'Subscriptions',
    })
  }

  if (topDiscretionaryMerchant) {
    const monthlyMerchantSpend =
      coverageMonths && coverageMonths > 0
        ? topDiscretionaryMerchant.totalSpend / coverageMonths
        : topDiscretionaryMerchant.totalSpend
    const monthlySavings = monthlyMerchantSpend * 0.15
    const overlapsCategoryLever =
      topDiscretionaryCategory?.category === topDiscretionaryMerchant.category
    push({
      id: 'merchant',
      title: `${topDiscretionaryMerchant.merchant} is merchant drag`,
      playbook: merchantPlaybook(
        topDiscretionaryMerchant.category,
        topDiscretionaryMerchant.essentiality,
        topDiscretionaryMerchant.transactionCount,
      ),
      note: overlapsCategoryLever
        ? `Already inside the ${topDiscretionaryMerchant.category} category lever — trimming both is not additive, so it is excluded from the additive total.`
        : undefined,
      monthlySavings,
      annualSavings: monthlySavings * 12,
      trimRate: 0.15,
      detail: `${topDiscretionaryMerchant.transactionCount} charges in this window. Merchant alone ran ${formatCurrency(topDiscretionaryMerchant.totalSpend, { decimals: 0 })}.`,
      tone: 'outline',
      additive: false,
    })
  }

  if (topThreeShare >= 0.35 && averageMonthlySpend > 0) {
    const monthlySavings = averageMonthlySpend * 0.05
    push({
      id: 'concentration',
      title: 'Top merchants are too concentrated',
      playbook: 'Set merchant caps and pre-approve outliers',
      monthlySavings,
      annualSavings: monthlySavings * 12,
      trimRate: 0.05,
      detail: `Top 3 merchants drive ${formatPercent(topThreeShare * 100, { decimals: 0 })} of spend here. A 5% reset on those names saves more than scattered cuts.`,
      tone: 'outline',
      additive: false,
    })
  }

  if (bestPriceSignal) {
    const signalChange = Math.max(
      Math.abs(bestPriceSignal.unitPriceChangePct ?? 0),
      Math.abs(bestPriceSignal.priceChangePct ?? 0),
    )
    const monthlySavings = averageMonthlySpend * 0.02
    // Marketplace listings can run 100+ chars; keep the headline readable.
    const itemName =
      bestPriceSignal.itemName.length > 48
        ? `${bestPriceSignal.itemName.slice(0, 48).trimEnd()}…`
        : bestPriceSignal.itemName
    push({
      id: 'price-signal',
      title: `${itemName} price drift needs a check`,
      playbook: bestPriceSignal.shrinkflationFlag
        ? 'Swap or size-check before rebuy'
        : 'Price-compare before next order',
      monthlySavings,
      annualSavings: monthlySavings * 12,
      trimRate: 0.02,
      detail: `${bestPriceSignal.merchant} shows ${formatPercent(signalChange, { decimals: 0, sign: true })} drift by ticket or unit math. Use it as a trigger to compare, not autopilot.`,
      tone: 'warning',
      additive: false,
    })
  }

  const ranked = opportunities.sort(
    (left, right) => right.monthlySavings - left.monthlySavings,
  )
  const concrete = ranked.filter((row) => row.concrete)
  const modeled = ranked.filter((row) => !row.concrete)
  return [...concrete, ...modeled].slice(0, 4)
}
