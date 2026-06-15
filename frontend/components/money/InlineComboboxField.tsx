'use client'

import { ChevronDown } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export interface InlineComboboxCommitOptions {
  applyRule?: boolean
}

interface InlineComboboxFieldProps {
  id: string
  label: string
  value?: string | null
  options: string[]
  onCommit: (
    value: string,
    options?: InlineComboboxCommitOptions,
  ) => void | Promise<void>
  placeholder?: string
  disabled?: boolean
  ruleLabel?: string
  ruleChecked?: boolean
  onRuleCheckedChange?: (checked: boolean) => void
  className?: string
  inputClassName?: string
}

export function InlineComboboxField({
  id,
  label,
  value,
  options,
  onCommit,
  placeholder,
  disabled = false,
  ruleLabel,
  ruleChecked = false,
  onRuleCheckedChange,
  className,
  inputClassName,
}: InlineComboboxFieldProps) {
  const currentValue = value?.trim() ?? ''
  const [draft, setDraft] = useState(currentValue)
  const [open, setOpen] = useState(false)
  const lastCommittedRef = useRef(currentValue)
  const listId = `${id}-options`
  const ruleId = `${id}-rule`
  const choices = useMemo(() => {
    const unique = new Set<string>()
    for (const option of [draft, currentValue, ...options]) {
      const trimmed = option.trim()
      if (trimmed) {
        unique.add(trimmed)
      }
    }
    return Array.from(unique)
  }, [currentValue, draft, options])

  useEffect(() => {
    setDraft(currentValue)
    lastCommittedRef.current = currentValue
  }, [currentValue])

  function commit(
    nextValue = draft,
    options: InlineComboboxCommitOptions & { force?: boolean } = {},
  ) {
    const trimmed = nextValue.trim()
    if (!options.force && trimmed === lastCommittedRef.current) {
      return
    }
    lastCommittedRef.current = trimmed
    void onCommit(trimmed, { applyRule: options.applyRule ?? ruleChecked })
  }

  return (
    <div
      className={cn('relative', className)}
      onBlur={(event) => {
        const nextFocus = event.relatedTarget
        if (
          nextFocus instanceof Node &&
          event.currentTarget.contains(nextFocus)
        ) {
          return
        }
        setOpen(false)
        commit()
      }}
    >
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          value={draft}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          className={cn('h-8 pr-8 text-xs', inputClassName)}
          placeholder={placeholder}
          disabled={disabled}
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
              commit()
            }
          }}
        />
        <button
          type="button"
          aria-label={`Show ${label.toLowerCase()} options`}
          aria-expanded={open}
          aria-controls={listId}
          disabled={disabled}
          className="absolute inset-y-0 right-0 flex w-8 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text disabled:opacity-50"
          onClick={() => setOpen(!open)}
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label={`${label} options`}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
        >
          {choices.map((choice) => (
            <button
              key={choice}
              type="button"
              role="option"
              aria-selected={choice === draft}
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs text-text transition-colors hover:bg-surface-muted/70',
                choice === draft && 'bg-primary/15 text-primary',
              )}
              onClick={() => {
                setDraft(choice)
                setOpen(false)
                commit(choice)
              }}
            >
              <span>{choice}</span>
              {choice === draft ? (
                <span className="text-[10px] font-medium">Selected</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
      {ruleLabel ? (
        <div className="mt-1 flex items-center gap-1 text-[10px] leading-none text-text-muted">
          <Checkbox
            id={ruleId}
            checked={ruleChecked}
            disabled={disabled}
            aria-label={`${ruleLabel} for ${label}`}
            className="h-3 w-3"
            onCheckedChange={(checked) => {
              const nextChecked = checked === true
              onRuleCheckedChange?.(nextChecked)
              if (nextChecked && draft.trim()) {
                commit(draft, { applyRule: true, force: true })
              }
            }}
          />
          <Label
            htmlFor={ruleId}
            className="cursor-pointer text-[10px] font-normal leading-none text-text-muted"
          >
            {ruleLabel}
          </Label>
        </div>
      ) : null}
    </div>
  )
}
