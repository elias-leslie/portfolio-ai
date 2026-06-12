'use client'

import { ChevronDown } from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { RecategorizeDraft } from './category-options'

export interface CategoryEditorFormProps {
  transactionId: string
  draft: RecategorizeDraft
  setDraft: Dispatch<SetStateAction<RecategorizeDraft | null>>
  pickerOpen: boolean
  onPickerOpenChange: (open: boolean) => void
  categoryOptions: string[]
  /** Matching-purchase count behind the apply-to-merchant note; omit to hide it. */
  similarMerchantCount?: number
  pending: boolean
  onSave: () => void
  onCancel: () => void
}

/**
 * The canonical category/essentiality editor. Every surface that recategorizes
 * a transaction (Budget drill-downs, Ledger rows) renders this form and saves
 * through useCategorizeHouseholdTransaction.
 */
export function CategoryEditorForm({
  transactionId,
  draft,
  setDraft,
  pickerOpen,
  onPickerOpenChange,
  categoryOptions,
  similarMerchantCount,
  pending,
  onSave,
  onCancel,
}: CategoryEditorFormProps) {
  const categoryListId = `category-options-${transactionId}`

  return (
    <div className="w-full space-y-3 rounded-xl border border-border/35 bg-surface-muted/15 p-3 lg:w-[420px]">
      <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
        <div
          className="relative space-y-1.5"
          onBlur={(event) => {
            const nextFocus = event.relatedTarget
            if (
              nextFocus instanceof Node &&
              event.currentTarget.contains(nextFocus)
            ) {
              return
            }
            onPickerOpenChange(false)
          }}
        >
          <Label htmlFor={`category-${transactionId}`}>Category</Label>
          <div className="relative">
            <Input
              id={`category-${transactionId}`}
              value={draft.category}
              role="combobox"
              aria-expanded={pickerOpen}
              aria-controls={categoryListId}
              aria-autocomplete="list"
              className="pr-10"
              onFocus={() => onPickerOpenChange(true)}
              onClick={() => onPickerOpenChange(true)}
              onChange={(event) => {
                setDraft((current) =>
                  current
                    ? { ...current, category: event.target.value }
                    : current,
                )
                onPickerOpenChange(true)
              }}
            />
            <button
              type="button"
              aria-label="Show category options"
              aria-expanded={pickerOpen}
              aria-controls={categoryListId}
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text"
              onClick={() => onPickerOpenChange(!pickerOpen)}
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
          {pickerOpen ? (
            <div
              id={categoryListId}
              role="listbox"
              aria-label="Existing categories"
              className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
            >
              {categoryOptions.map((category) => (
                <button
                  key={category}
                  type="button"
                  role="option"
                  aria-selected={category === draft.category}
                  className={cn(
                    'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-text transition-colors hover:bg-surface-muted/70',
                    category === draft.category && 'bg-primary/15 text-primary',
                  )}
                  onClick={() => {
                    setDraft((current) =>
                      current ? { ...current, category } : current,
                    )
                    onPickerOpenChange(false)
                  }}
                >
                  <span>{category}</span>
                  {category === draft.category ? (
                    <span className="text-xs font-medium">Selected</span>
                  ) : null}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <div className="space-y-1.5">
          <Label>Type</Label>
          <Select
            value={draft.essentiality}
            onValueChange={(value) =>
              setDraft((current) =>
                current ? { ...current, essentiality: value } : current,
              )
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="essential">Essential</SelectItem>
              <SelectItem value="mixed">Mixed</SelectItem>
              <SelectItem value="discretionary">Discretionary</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <label className="flex items-start gap-2 text-sm text-text-muted">
        <Checkbox
          checked={draft.applyToMerchant}
          onCheckedChange={(checked) =>
            setDraft((current) =>
              current
                ? {
                    ...current,
                    applyToMerchant: checked === true,
                  }
                : current,
            )
          }
        />
        <span>
          Apply to this merchant going forward
          {similarMerchantCount != null && similarMerchantCount > 1
            ? ` and update ${similarMerchantCount} matching purchases`
            : ''}
          .
        </span>
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={onSave}
          disabled={pending || !draft.category.trim()}
        >
          {pending ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  )
}
