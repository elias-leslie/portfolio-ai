/**
 * Canonical category-editing primitives shared by every surface that changes a
 * transaction's category (Budget drill-downs, Ledger rows). The save path is
 * always useCategorizeHouseholdTransaction -> POST /transactions/{id}/categorize.
 */

export const CATEGORY_OPTIONS = [
  'Unknown',
  'Bills',
  'Dining',
  'Donations',
  'Education',
  'Entertainment',
  'Fitness',
  'Gas',
  'Groceries',
  'Healthcare',
  'Home',
  'Household',
  'Insurance',
  'Personal Care',
  'Retail',
  'Subscriptions',
  'Transportation',
  'Travel',
]

export type RecategorizeDraft = {
  transactionId: string
  category: string
  essentiality: string
  applyToMerchant: boolean
}

/**
 * Union the standard taxonomy with categories observed in live data, sorted
 * alphabetically with Unknown pinned first so uncategorized work surfaces.
 */
export function buildCategoryOptions(observed: Iterable<string>): string[] {
  const categories = new Set(CATEGORY_OPTIONS)
  for (const category of observed) {
    if (category.trim()) {
      categories.add(category)
    }
  }
  return Array.from(categories).sort((left, right) =>
    left === 'Unknown'
      ? -1
      : right === 'Unknown'
        ? 1
        : left.localeCompare(right),
  )
}

/** Seed an edit draft from a transaction-shaped row's current classification. */
export function startRecategorizeDraft(row: {
  id: string
  category?: string | null
  essentiality?: string | null
}): RecategorizeDraft {
  const category = row.category || 'Unknown'
  return {
    transactionId: row.id,
    category,
    essentiality: row.essentiality || 'mixed',
    applyToMerchant: category === 'Unknown',
  }
}
