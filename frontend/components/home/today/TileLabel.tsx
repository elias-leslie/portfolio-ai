'use client'

import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

/**
 * Compact uppercase tile label. When `detail` is provided, the label becomes a
 * tooltip trigger with an info glyph so the affordance is discoverable.
 *
 * Note: the trigger's `aria-label` follows the `${label}: more detail` pattern
 * which is asserted by tests — keep this format stable.
 */
export function TileLabel({
  label,
  detail,
}: {
  label: string
  detail?: ReactNode
}) {
  if (!detail) {
    return (
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {label}
      </p>
    )
  }

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="group inline-flex cursor-help items-center gap-1 appearance-none border-0 bg-transparent p-0 text-left outline-none focus-visible:text-text"
            aria-label={`${label}: more detail`}
          >
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted group-hover:text-text">
              {label}
            </span>
            <Info
              className="h-3 w-3 text-text-muted/60 group-hover:text-text-muted"
              aria-hidden="true"
            />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-xs leading-relaxed">
          {detail}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
