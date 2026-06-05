import type { HouseholdSpendingTransaction } from '@/lib/api/household'

export interface MerchantAggregate {
  merchant: string
  totalSpend: number
  transactionCount: number
  category: string
  essentiality: string
}

/**
 * Group spending transactions by case-insensitive merchant name.
 *
 * Single source of truth for merchant rollups shared by the Budget and Levers
 * panels so the two can never drift on how merchants are bucketed.
 */
export function aggregateMerchants(
  transactions: readonly HouseholdSpendingTransaction[] | undefined,
): Map<string, MerchantAggregate> {
  const buckets = new Map<string, MerchantAggregate>()
  for (const row of transactions ?? []) {
    const key = row.merchant.trim().toLowerCase()
    if (!key) {
      continue
    }
    const current = buckets.get(key)
    if (current) {
      current.totalSpend += row.amount
      current.transactionCount += 1
      continue
    }
    buckets.set(key, {
      merchant: row.merchant,
      totalSpend: row.amount,
      transactionCount: 1,
      category: row.category,
      essentiality: row.essentiality,
    })
  }
  return buckets
}
