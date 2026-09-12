'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Button } from '@/components/ui/button'
import { get } from '@/lib/api/client'
import { assumptionFields, formatAssumptionValue } from './assumption-fields'

type Change = {
  field: string
  before: string | number | null
  after: string | number | null
}
type Entry = {
  id: string
  source: string
  changedAt: string
  changes: Change[]
}

function showValue(field: string, value: Change['before']) {
  if (value == null) return 'Not set'
  const definition = assumptionFields.find((item) => item.fieldName === field)
  return definition ? formatAssumptionValue(definition, value) : String(value)
}

export function AssumptionChangeHistory() {
  const [open, setOpen] = useState(false)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['household', 'profile', 'history'],
    queryFn: () => get<Entry[]>('/api/household/profile/history'),
    enabled: open,
  })
  return (
    <details
      className="rounded-xl border border-border/40 p-4"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-sm font-medium">
        Saved assumption changes
      </summary>
      <div className="mt-3 space-y-3 text-sm">
        {isLoading ? <p role="status">Loading change history…</p> : null}
        {error ? (
          <p role="alert">
            Change history could not be loaded.{' '}
            <Button variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </p>
        ) : null}
        {data?.length === 0 ? (
          <p>
            No changes recorded since history tracking began. Earlier saved
            values are retained.
          </p>
        ) : null}
        {data?.map((entry) => (
          <div key={entry.id} className="border-t border-border/30 pt-3">
            <p className="text-text-muted">
              {entry.source === 'jenny_chat'
                ? 'From your conversation with Jenny'
                : 'Saved assumptions'}{' '}
              · <RelativeTime value={entry.changedAt} />
            </p>
            {entry.changes.map((change) => (
              <p key={change.field} className="mt-1 break-words">
                {assumptionFields.find(
                  (item) => item.fieldName === change.field,
                )?.label ?? change.field.replaceAll('_', ' ')}
                : {showValue(change.field, change.before)} →{' '}
                {showValue(change.field, change.after)}
              </p>
            ))}
          </div>
        ))}
        {data?.length === 50 ? <p>Showing the latest 50 changes.</p> : null}
      </div>
    </details>
  )
}
