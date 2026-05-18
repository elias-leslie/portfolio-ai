import { useQuery } from '@tanstack/react-query'
import { fetchTodayNext } from '@/lib/api/today-next'

export function useTodayNext() {
  return useQuery({
    queryKey: ['today-next'],
    queryFn: fetchTodayNext,
    staleTime: 1000 * 60,
    refetchOnWindowFocus: true,
  })
}
