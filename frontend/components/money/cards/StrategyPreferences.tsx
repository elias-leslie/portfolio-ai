'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { StrategySettings } from '@/lib/api/cards/strategy'
import { useStrategyActions } from '@/lib/hooks/useCardStrategy'

export function StrategyPreferences({ value }: { value: StrategySettings }) {
  const [settings, setSettings] = useState(value)
  const save = useStrategyActions().settings
  const toggles = [
    ['reserveAmazon', 'Keep Amazon spending on its keeper card'],
    ['reserveCostco', 'Reserve Costco shopping for its own card'],
    ['reserveGas', 'Reserve gas spending for its own card'],
    ['remindersEnabled', 'Show card-plan reminders in top-bar Actions'],
    [
      'automaticResearch',
      'Allow automatic offer research near an application decision',
    ],
  ] as const
  return (
    <details className="rounded-xl border border-border/40 p-4">
      <summary className="cursor-pointer font-medium">
        Strategy preferences & usage
      </summary>
      <form
        className="mt-4 space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(settings)
        }}
      >
        <p className="text-sm text-text-muted">
          Routine progress calculations use no AI tokens. Automatic research
          uses Agent Hub, only near an approved application decision, at most
          monthly. Failed attempts also start the cooldown. Manual research
          remains available below.
        </p>
        {toggles.map(([key, label]) => (
          <label key={key} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={settings[key]}
              onChange={(event) =>
                setSettings({ ...settings, [key]: event.target.checked })
              }
            />
            {label}
          </label>
        ))}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm">
            Maximum monthly bonus spending (optional)
            <Input
              type="number"
              min="0"
              step="0.01"
              value={settings.monthlyCap ?? ''}
              placeholder="Use actual spending"
              onChange={(e) =>
                setSettings({
                  ...settings,
                  monthlyCap:
                    e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
          </label>
          <label className="space-y-1 text-sm">
            Expected monthly Costco shopping
            <Input
              type="number"
              min="0"
              step="0.01"
              value={settings.costcoMonthly ?? ''}
              placeholder="Use recorded history"
              onChange={(e) =>
                setSettings({
                  ...settings,
                  costcoMonthly:
                    e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        <p className="text-xs text-text-muted">
          A spending cap can lower the estimate. It cannot create extra
          spending. Changes suggest a revision; they do not rewrite an approved
          plan.
        </p>
        {save.error ? (
          <p role="alert" className="text-sm text-loss">
            {save.error.message}
          </p>
        ) : null}
        <Button size="sm" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save preferences'}
        </Button>
        {save.isSuccess ? (
          <span role="status" className="ml-3 text-sm">
            Preferences saved.
          </span>
        ) : null}
      </form>
    </details>
  )
}
