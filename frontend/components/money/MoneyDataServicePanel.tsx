'use client'

import { KeyRound, Loader2, ShieldCheck } from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type TileColumns = 2 | 3 | 4

const gridColumns: Record<TileColumns, string> = {
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-3',
  4: 'md:grid-cols-4',
}

export interface MoneyDataServiceTile {
  id: string
  label: string
  value: ReactNode
  detail?: ReactNode
  title?: string
  icon?: ReactNode
  badge?: {
    label: string
    variant?: BadgeProps['variant']
  }
}

export interface MoneyDataServiceButton {
  label: string
  icon: ReactNode
  pending?: boolean
  disabled?: boolean
  variant?: 'default' | 'outline'
  onClick: () => void
}

interface MoneyDataServicePanelProps {
  title: string
  summary: ReactNode
  configured: boolean
  canConfigure: boolean
  configOpen: boolean
  onToggleConfig: () => void
  configForm: ReactNode
  statusTiles: MoneyDataServiceTile[]
  metricTiles: MoneyDataServiceTile[]
  syncAction: MoneyDataServiceButton
  connectAction: MoneyDataServiceButton
  alerts?: Array<ReactNode | null | undefined>
  statusColumns?: TileColumns
  metricColumns?: TileColumns
  children?: ReactNode
}

export function formatDataServiceTime(value?: string | null) {
  if (!value) return 'Never synced'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

export function titleCaseDataServiceValue(value?: string | null) {
  if (!value) return 'Not set'
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function formatDataServiceList(values?: string[]) {
  return values?.length ? values.join(', ') : 'Not set'
}

function MoneyDataServiceTileGrid({
  tiles,
  columns,
}: {
  tiles: MoneyDataServiceTile[]
  columns: TileColumns
}) {
  if (!tiles.length) return null
  return (
    <div className={`grid gap-3 ${gridColumns[columns]}`}>
      {tiles.map((tile) => (
        <div
          key={tile.id}
          className="rounded-md border border-border/35 bg-bg/60 p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs uppercase text-text-muted">{tile.label}</p>
            {tile.badge ? (
              <Badge variant={tile.badge.variant ?? 'secondary'}>
                {tile.badge.label}
              </Badge>
            ) : null}
          </div>
          <div className="mt-2 flex min-w-0 items-center gap-2">
            {tile.icon}
            <p
              className="truncate text-sm font-medium text-text"
              title={tile.title}
            >
              {tile.value}
            </p>
          </div>
          {tile.detail ? (
            <p className="text-xs text-text-muted">{tile.detail}</p>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function MoneyDataServiceAction({
  action,
}: {
  action: MoneyDataServiceButton
}) {
  return (
    <Button
      type="button"
      variant={action.variant}
      size="sm"
      onClick={action.onClick}
      disabled={action.disabled}
    >
      {action.pending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        action.icon
      )}
      {action.label}
    </Button>
  )
}

export function MoneyDataServicePanel({
  title,
  summary,
  configured,
  canConfigure,
  configOpen,
  onToggleConfig,
  configForm,
  statusTiles,
  metricTiles,
  syncAction,
  connectAction,
  alerts = [],
  statusColumns = 4,
  metricColumns = 3,
  children,
}: MoneyDataServicePanelProps) {
  return (
    <SectionCard
      variant="surface"
      title={title}
      description={summary}
      actions={
        <>
          <Badge
            variant={configured ? 'success' : 'secondary'}
            className="gap-1"
          >
            {configured ? (
              <ShieldCheck className="h-3.5 w-3.5" />
            ) : (
              <KeyRound className="h-3.5 w-3.5" />
            )}
            {configured ? 'Configured' : 'Not configured'}
          </Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onToggleConfig}
            disabled={!canConfigure}
          >
            <KeyRound className="h-4 w-4" />
            Configure
          </Button>
          <MoneyDataServiceAction action={syncAction} />
          <MoneyDataServiceAction action={connectAction} />
        </>
      }
    >
      <div className="space-y-4">
        {!canConfigure && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            PORTFOLIO_SECRET_KEY is required before encrypted credentials can be
            saved.
          </div>
        )}

        {configOpen ? configForm : null}

        {alerts.filter(Boolean).map((alert, index) => (
          <div
            key={index}
            className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {alert}
          </div>
        ))}

        <MoneyDataServiceTileGrid tiles={statusTiles} columns={statusColumns} />
        <MoneyDataServiceTileGrid tiles={metricTiles} columns={metricColumns} />
        {children}
      </div>
    </SectionCard>
  )
}

export function MoneyDataServiceConfigForm({
  children,
  isPending,
  canConfigure,
  onSubmit,
  onCancel,
}: {
  children: ReactNode
  isPending: boolean
  canConfigure: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onCancel: () => void
}) {
  return (
    <form
      className="grid gap-3 rounded-md border border-border/40 bg-bg/70 p-4 md:grid-cols-2"
      autoComplete="off"
      onSubmit={(event) => onSubmit(event)}
    >
      {children}
      <div className="flex items-center gap-2 md:col-span-2">
        <Button type="submit" disabled={isPending || !canConfigure}>
          {isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Save configuration
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function MoneyDataServiceSecretInput({
  id,
  label,
  value,
  saved,
  onChange,
}: {
  id: string
  label: string
  value: string
  saved: boolean
  onChange: (value: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="password"
        value={value}
        autoComplete="off"
        onChange={(event) => onChange(event.target.value)}
        placeholder={saved ? 'Saved; enter to replace' : undefined}
        required={!saved}
      />
    </div>
  )
}
