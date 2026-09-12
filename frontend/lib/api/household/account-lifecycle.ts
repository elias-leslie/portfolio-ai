import { post } from '../client'

export type AccountResolutionTarget = {
  kind: 'registered' | 'discovered'
  id: string
  label: string
  accountType?: string
}

export function recordAccountClosed(
  target: AccountResolutionTarget,
  closedDate: string | null,
) {
  return post<{ accountId: string; label: string; status: string }>(
    '/api/household/accounts/record-closed',
    { kind: target.kind, id: target.id, closedDate },
  )
}
