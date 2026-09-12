import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type BillDecision,
  type BillPaymentPreference,
  decideBillMove,
  decideStrategy,
  fetchStrategy,
  proposeStrategy,
  type StrategyDecision,
  type StrategySettings,
  saveBillPaymentPreference,
  saveStrategySettings,
} from '@/lib/api/cards/strategy'

export function useCardStrategy() {
  return useQuery({
    queryKey: ['cards', 'strategy'],
    queryFn: ({ signal }) => fetchStrategy(signal),
    staleTime: 30_000,
  })
}

export function useStrategyActions() {
  const client = useQueryClient()
  const refresh = async () => {
    await Promise.all(
      ['cards', 'home', 'household'].map((key) =>
        client.invalidateQueries({ queryKey: [key] }),
      ),
    )
  }
  const proposal = useMutation({
    mutationFn: ({ key, wait }: { key?: string; wait?: boolean }) =>
      proposeStrategy(key, wait),
    onSuccess: refresh,
  })
  const decision = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StrategyDecision }) =>
      decideStrategy(id, payload),
    onSuccess: refresh,
  })
  const settings = useMutation({
    mutationFn: (value: StrategySettings) => saveStrategySettings(value),
    onSuccess: refresh,
  })
  const bill = useMutation({
    mutationFn: ({
      id,
      key,
      payload,
    }: {
      id: string
      key: string
      payload: BillDecision
    }) => decideBillMove(id, key, payload),
    onSuccess: refresh,
  })
  const billPreference = useMutation({
    mutationFn: ({
      key,
      preference,
    }: {
      key: string
      preference: BillPaymentPreference
    }) => saveBillPaymentPreference(key, preference),
    onSuccess: refresh,
  })
  return { proposal, decision, settings, bill, billPreference }
}
