import { useQuery } from '@tanstack/react-query'
import { fetchMarketEvents } from '@/lib/api/market-events'
import type { MarketEventsResponse } from '@/lib/api/market-types'

const ONE_MINUTE = 1000 * 60

function isoDateWithOffset(offsetDays: number): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Calendar events around today: `pastDays` back through `futureDays` ahead. */
export function useMarketEventsWindow(pastDays = 14, futureDays = 30) {
  const startDate = isoDateWithOffset(-pastDays)
  const endDate = isoDateWithOffset(futureDays)
  return useQuery<MarketEventsResponse>({
    queryKey: ['market', 'events', startDate, endDate],
    queryFn: () => fetchMarketEvents(startDate, endDate),
    staleTime: 30 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}
