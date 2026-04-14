'use client'

import type { ComponentProps, ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

export function InfoBadge({
  label,
  detail,
  variant = 'outline',
  className,
}: {
  label: ReactNode
  detail?: ReactNode
  variant?: ComponentProps<typeof Badge>['variant']
  className?: string
}) {
  if (!detail) {
    return (
      <Badge variant={variant} className={className}>
        {label}
      </Badge>
    )
  }

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex cursor-help appearance-none border-0 bg-transparent p-0 text-left outline-none"
            aria-label={
              typeof label === 'string'
                ? `${label}: more detail`
                : 'Show more detail'
            }
          >
            <Badge variant={variant} className={className}>
              {label}
            </Badge>
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-xs leading-relaxed">
          {detail}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
