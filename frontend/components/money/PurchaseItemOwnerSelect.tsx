'use client'

import { ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSetPurchaseItemOwner } from '@/lib/hooks/useHouseholdPurchases'
import { cn } from '@/lib/utils'
import { buildOwnerOptions } from './owner-options'

interface PurchaseItemOwnerSelectProps {
  itemId: string
  itemLabel: string
  ownerName?: string | null
  ownerSource?: string | null
  inheritedOwnerName?: string | null
  className?: string
}

export function PurchaseItemOwnerSelect({
  itemId,
  itemLabel,
  ownerName,
  ownerSource,
  inheritedOwnerName,
  className,
}: PurchaseItemOwnerSelectProps) {
  const explicitOwner = ownerName?.trim() ?? ''
  const inheritedOwner = inheritedOwnerName?.trim() ?? ''
  const effectiveOwner = explicitOwner || inheritedOwner
  const [draft, setDraft] = useState(effectiveOwner)
  const [open, setOpen] = useState(false)
  const [applyToProduct, setApplyToProduct] = useState(false)
  const setOwner = useSetPurchaseItemOwner()
  const listId = `owner-options-${itemId}`
  const inputId = `owner-${itemId}`
  const sourceLabel = explicitOwner
    ? ownerSource && ownerSource !== 'none'
      ? ownerSource.replace(/_/g, ' ')
      : 'item owner'
    : inheritedOwner
      ? 'inherited from category'
      : 'unassigned'
  const options = buildOwnerOptions([draft, effectiveOwner])

  useEffect(() => {
    setDraft(effectiveOwner)
    setApplyToProduct(false)
  }, [effectiveOwner])

  async function commit(
    nextOwner: string,
    applyRule = applyToProduct,
    force = false,
  ) {
    const trimmed = nextOwner.trim()
    const unchanged =
      trimmed === explicitOwner ||
      (!explicitOwner && trimmed === inheritedOwner)
    if (!force && unchanged) {
      return
    }
    await setOwner.mutateAsync({
      itemId,
      ownerName: trimmed || null,
      applyToProduct: applyRule,
    })
  }

  return (
    <div
      className={cn('relative w-full min-w-[11rem] max-w-[14rem]', className)}
      onBlur={(event) => {
        const nextFocus = event.relatedTarget
        if (
          nextFocus instanceof Node &&
          event.currentTarget.contains(nextFocus)
        ) {
          return
        }
        setOpen(false)
        void commit(draft)
      }}
    >
      <Label htmlFor={inputId} className="sr-only">
        Owner for {itemLabel}
      </Label>
      <div className="relative">
        <Input
          id={inputId}
          value={draft}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          className="h-8 pr-9 text-xs"
          placeholder="Owner"
          disabled={setOwner.isPending}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onChange={(event) => {
            setDraft(event.target.value)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              setOpen(false)
              void commit(draft)
            }
          }}
        />
        <button
          type="button"
          aria-label={`Show owner options for ${itemLabel}`}
          aria-expanded={open}
          aria-controls={listId}
          disabled={setOwner.isPending}
          className="absolute inset-y-0 right-0 flex w-8 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text disabled:opacity-50"
          onClick={() => setOpen(!open)}
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
      <p className="mt-1 text-[10px] capitalize leading-none text-text-muted">
        {sourceLabel}
      </p>
      <label className="mt-1 flex items-center gap-1 text-[10px] leading-none text-text-muted">
        <Checkbox
          checked={applyToProduct}
          disabled={setOwner.isPending}
          className="h-3 w-3"
          onCheckedChange={(checked) => {
            const nextApply = checked === true
            setApplyToProduct(nextApply)
            if (nextApply && draft.trim()) {
              void commit(draft, nextApply, true)
            }
          }}
        />
        <span>Product rule</span>
      </label>
      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label={`Owner options for ${itemLabel}`}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
        >
          {options.map((owner) => (
            <button
              key={owner}
              type="button"
              role="option"
              aria-selected={owner === draft}
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs text-text transition-colors hover:bg-surface-muted/70',
                owner === draft && 'bg-primary/15 text-primary',
              )}
              onClick={() => {
                setDraft(owner)
                setOpen(false)
                void commit(owner)
              }}
            >
              <span>{owner}</span>
              {owner === draft ? (
                <span className="text-[10px] font-medium">Selected</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
