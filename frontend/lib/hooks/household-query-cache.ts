import type { QueryClient } from '@tanstack/react-query'

/** Shared stale time for household workspace reads. */
export const HOUSEHOLD_WORKSPACE_STALE_MS = 1000 * 60 * 5

/**
 * Invalidate every `['household', ...]` query. Pass `retirement: true` when the
 * change feeds retirement inputs (ledger edits, holdings, account syncs) so the
 * `['retirement', ...]` actuals and preview refetch too.
 */
export async function invalidateHouseholdQueries(
  queryClient: QueryClient,
  { retirement = false }: { retirement?: boolean } = {},
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['household'], exact: false }),
    retirement
      ? queryClient.invalidateQueries({
          queryKey: ['retirement'],
          exact: false,
        })
      : undefined,
  ])
}
