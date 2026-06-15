import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export type SortDirection = 'asc' | 'desc'

interface SortableTableHeaderProps<T extends string> {
  field: T
  label: string
  activeField: T | null
  direction: SortDirection
  onSort: (field: T) => void
  align?: 'left' | 'right'
}

export function nextSortDirection<T extends string>(
  currentField: T | null,
  field: T,
  currentDirection: SortDirection,
  defaultDirection: SortDirection = 'desc',
): SortDirection {
  if (currentField !== field) {
    return defaultDirection
  }
  return currentDirection === 'asc' ? 'desc' : 'asc'
}

export function SortableTableHeader<T extends string>({
  field,
  label,
  activeField,
  direction,
  onSort,
  align = 'left',
}: SortableTableHeaderProps<T>) {
  const active = activeField === field
  const Icon = active
    ? direction === 'asc'
      ? ArrowUp
      : ArrowDown
    : ArrowUpDown

  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      aria-label={`Sort by ${label}`}
      className={cn(
        'flex w-full items-center gap-1 font-semibold uppercase tracking-[0.16em] text-text-muted/80 transition-colors hover:text-text',
        align === 'right' ? 'justify-end' : 'justify-start',
      )}
    >
      <span>{label}</span>
      <Icon
        className={cn('h-3.5 w-3.5', active ? 'text-text' : 'text-text-muted')}
      />
    </button>
  )
}
