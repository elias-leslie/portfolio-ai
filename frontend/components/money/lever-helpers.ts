import type {
  HouseholdPriceInsight,
  HouseholdSpendingCategory,
} from '@/lib/api/household'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import type { MerchantAggregate } from './merchant-aggregation'

export type LeverOpportunity = {
  id: string
  title: string
  playbook: string
  monthlySavings: number
  annualSavings: number
  detail: string
  tone: 'success' | 'warning' | 'outline'
  additive: boolean
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
}: BuildLeversInput): LeverOpportunity[] {
  const opportunities: LeverOpportunity[] = []

  const push = (value: LeverOpportunity | null) => {
    if (!value || value.monthlySavings <= 0) {
      return
    }
    opportunities.push(value)
  }

  if (subscriptionCategory) {
    const monthlySavings = subscriptionCategory.averageMonthlySpend * 0.2
    push({
      id: 'subscriptions',
      title: 'Subscription sweep first',
      playbook: 'Cancel, downgrade, or annualize',
      monthlySavings,
      annualSavings: monthlySavings * 12,
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
    push({
      id: 'price-signal',
      title: `${bestPriceSignal.itemName} price drift needs a check`,
      playbook: bestPriceSignal.shrinkflationFlag
        ? 'Swap or size-check before rebuy'
        : 'Price-compare before next order',
      monthlySavings,
      annualSavings: monthlySavings * 12,
      detail: `${bestPriceSignal.merchant} shows ${formatPercent(signalChange, { decimals: 0, sign: true })} drift by ticket or unit math. Use it as a trigger to compare, not autopilot.`,
      tone: 'warning',
      additive: false,
    })
  }

  return opportunities
    .sort((left, right) => right.monthlySavings - left.monthlySavings)
    .slice(0, 4)
}
