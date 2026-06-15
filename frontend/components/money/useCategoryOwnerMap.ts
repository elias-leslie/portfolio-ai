import { useMemo } from 'react'
import { useHouseholdFacts } from '@/lib/hooks/useHousehold'
import { categoryBudgetMetaMap } from './household-fact-metadata'

export function useCategoryOwnerMap() {
  const { data: facts = [] } = useHouseholdFacts()

  return useMemo(() => {
    const owners = new Map<string, string>()
    for (const [category, meta] of categoryBudgetMetaMap(facts)) {
      const ownerName = meta.ownerName?.trim()
      if (ownerName) {
        owners.set(category, ownerName)
      }
    }
    return owners
  }, [facts])
}
