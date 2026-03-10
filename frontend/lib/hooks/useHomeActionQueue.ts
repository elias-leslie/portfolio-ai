import { useQuery } from '@tanstack/react-query'
import { fetchAutomationCenter, fetchHomeActionQueue } from '@/lib/api/home'

export function useHomeActionQueue() {
  return useQuery({
    queryKey: ['home', 'action-queue'],
    queryFn: fetchHomeActionQueue,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 60,
  })
}

export function useAutomationCenter() {
  return useQuery({
    queryKey: ['home', 'automation-center'],
    queryFn: fetchAutomationCenter,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 60,
  })
}
