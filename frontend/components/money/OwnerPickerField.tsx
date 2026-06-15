'use client'

import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface OwnerPickerFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  placeholder?: string
  description?: string
  className?: string
}

export function OwnerPickerField({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  description,
  className,
}: OwnerPickerFieldProps) {
  const [open, setOpen] = useState(false)
  const listId = `${id}-options`

  return (
    <div
      className={cn('relative space-y-1.5', className)}
      onBlur={(event) => {
        const nextFocus = event.relatedTarget
        if (
          nextFocus instanceof Node &&
          event.currentTarget.contains(nextFocus)
        ) {
          return
        }
        setOpen(false)
      }}
    >
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          value={value}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          className="pr-10"
          placeholder={placeholder}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onChange={(event) => {
            onChange(event.target.value)
            setOpen(true)
          }}
        />
        <button
          type="button"
          aria-label={`Show ${label.toLowerCase()} options`}
          aria-expanded={open}
          aria-controls={listId}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text"
          onClick={() => setOpen(!open)}
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>
      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label={`${label} options`}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
        >
          {options.map((owner) => (
            <button
              key={owner}
              type="button"
              role="option"
              aria-selected={owner === value}
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-text transition-colors hover:bg-surface-muted/70',
                owner === value && 'bg-primary/15 text-primary',
              )}
              onClick={() => {
                onChange(owner)
                setOpen(false)
              }}
            >
              <span>{owner}</span>
              {owner === value ? (
                <span className="text-xs font-medium">Selected</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
      {description ? (
        <p className="text-xs text-text-muted">{description}</p>
      ) : null}
    </div>
  )
}
