import { useQuery } from '@tanstack/react-query'
import { fetchHomeTodayBrief } from '@/lib/api/home'

export function useHomeTodayBrief() {
  return useQuery({
    queryKey: ['home', 'today-brief'],
    queryFn: fetchHomeTodayBrief,
    staleTime: 1000 * 60 * 60,
    refetchOnWindowFocus: false,
  })
}
