'use client'

import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface ExpandableCardProps {
  title: ReactNode
  description?: ReactNode
  summary?: ReactNode
  actions?: ReactNode
  defaultCollapsed?: boolean
  className?: string
  contentClassName?: string
  children: ReactNode | ((props: { isExpanded: boolean }) => ReactNode)
}

export function ExpandableCard({
  title,
  description,
  summary,
  actions,
  defaultCollapsed = true,
  className,
  contentClassName,
  children,
}: ExpandableCardProps) {
  const [isExpanded, setIsExpanded] = useState(!defaultCollapsed)
  const contentId = useId()

  const renderChildren =
    typeof children === 'function' ? children({ isExpanded }) : children

  return (
    <Card className={cn('border-border', className)}>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              {title}
            </CardTitle>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
            {summary && (
              <p className="text-xs text-muted-foreground mt-1">{summary}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <Button
              data-testid="expandable-card"
              variant="ghost"
              size="sm"
              className="flex items-center gap-1"
              onClick={() => setIsExpanded((prev) => !prev)}
              aria-expanded={isExpanded}
              aria-controls={contentId}
            >
              {isExpanded ? 'Collapse' : 'Expand'}
              <ChevronDown
                className={cn(
                  'h-4 w-4 transition-transform',
                  isExpanded && 'rotate-180',
                )}
              />
            </Button>
          </div>
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent id={contentId} className={contentClassName}>
          {renderChildren}
        </CardContent>
      )}
    </Card>
  )
}
