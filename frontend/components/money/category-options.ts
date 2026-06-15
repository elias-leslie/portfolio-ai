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
