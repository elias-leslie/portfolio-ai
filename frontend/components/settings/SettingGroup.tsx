'use client'

import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface SettingGroupProps {
  title: string
  description?: string
  icon?: ReactNode
  children: ReactNode
  className?: string
  helpText?: string
  helpLink?: string
}

export function SettingGroup({
  title,
  description,
  icon,
  children,
  className,
  helpText,
  helpLink,
}: SettingGroupProps) {
  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-start gap-3">
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {icon}
          </div>
        )}
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text">{title}</h3>
            {helpText && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="text-text-muted hover:text-text"
                    >
                      <Info className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>{helpText}</p>
                    {helpLink && (
                      <a
                        href={helpLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-block text-xs text-primary hover:underline"
                      >
                        Learn more →
                      </a>
                    )}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          {description && (
            <p className="mt-1 text-sm text-text-muted">{description}</p>
          )}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  )
}
