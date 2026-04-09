'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { HouseholdPlanningSnapshot } from '@/lib/api/household-planning'

export type EditableValue = boolean | number | string | null | undefined

export type EditableItem = {
  id?: string | null
} & Record<string, EditableValue>

export type EditableField = {
  key: string
  label: string
  placeholder?: string
  inputMode?: 'decimal' | 'numeric' | 'text'
  type?: 'date' | 'text'
}

export function emptyPlanning(): HouseholdPlanningSnapshot {
  return {
    summary: {
      completionScore: 0,
      readySections: 0,
      totalSections: 0,
      missingDocumentCount: 0,
      highPriorityDocumentCount: 0,
      sections: [],
    },
    members: [],
    incomeSources: [],
    debtObligations: [],
    housingCosts: [],
    insurancePolicies: [],
    retirementIncomeSources: [],
    plannedExpenses: [],
    documentRequirements: [],
  }
}

export function stripPlanningMeta<
  T extends { createdAt: string; updatedAt: string },
>(item: T): Omit<T, 'createdAt' | 'updatedAt'> {
  const { createdAt: _createdAt, updatedAt: _updatedAt, ...rest } = item
  return rest
}

export function normalizeEditableItems(
  items: EditableItem[],
  numericKeys: string[],
): EditableItem[] {
  return items
    .map((item) => {
      const next: EditableItem = { ...item }
      for (const key of numericKeys) {
        const value = next[key]
        if (typeof value !== 'string') {
          continue
        }
        const trimmed = value.trim()
        if (trimmed === '') {
          next[key] = null
          continue
        }
        const parsed = Number(trimmed)
        next[key] = Number.isFinite(parsed) ? parsed : null
      }
      return next
    })
    .filter((item) =>
      Object.entries(item).some(
        ([key, value]) => key !== 'id' && value !== '' && value != null,
      ),
    )
}

export function EditableListSection({
  title,
  description,
  fields,
  items,
  onChange,
  onSave,
  onAdd,
  isSaving,
}: {
  title: string
  description: string
  fields: EditableField[]
  items: EditableItem[]
  onChange: (next: EditableItem[]) => void
  onSave: () => void
  onAdd: () => void
  isSaving: boolean
}) {
  const updateField = (index: number, key: string, value: string) => {
    onChange(
      items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    )
  }

  const removeItem = (index: number) => {
    onChange(items.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">{title}</p>
          <p className="mt-1 text-sm text-text-muted">{description}</p>
        </div>
        <Badge variant="outline">{items.length}</Badge>
      </div>
      <div className="mt-4 space-y-4">
        {items.length === 0 ? (
          <p className="text-sm text-text-muted">No items yet.</p>
        ) : (
          items.map((item, index) => (
            <div
              key={item.id ?? `${title}-${index}`}
              className="rounded-xl border border-border/40 bg-surface/70 p-3"
            >
              <div className="grid gap-3 md:grid-cols-2">
                {fields.map((field) => (
                  <div key={`${field.key}-${index}`}>
                    <Label htmlFor={`${title}-${field.key}-${index}`}>
                      {field.label}
                    </Label>
                    <Input
                      id={`${title}-${field.key}-${index}`}
                      type={field.type ?? 'text'}
                      inputMode={field.inputMode ?? 'text'}
                      value={String(item[field.key] ?? '')}
                      onChange={(event) =>
                        updateField(index, field.key, event.target.value)
                      }
                      placeholder={field.placeholder}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => removeItem(index)}
                  disabled={isSaving}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onAdd}
            disabled={isSaving}
          >
            Add item
          </Button>
          <Button type="button" onClick={onSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save section'}
          </Button>
        </div>
      </div>
    </div>
  )
}
