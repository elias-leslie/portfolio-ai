import { useQuery } from '@tanstack/react-query'
import { fetchHomeActionQueue } from '@/lib/api/home'

export function useHomeActionQueue(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['home', 'action-queue'],
    queryFn: fetchHomeActionQueue,
    enabled: options?.enabled ?? true,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })
}
