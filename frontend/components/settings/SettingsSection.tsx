'use client'

import type { ReactNode } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { cn } from '@/lib/utils'

interface SettingsSectionProps {
  title: ReactNode
  description?: ReactNode
  summary: ReactNode
  actions?: ReactNode
  defaultCollapsed?: boolean
  children: ReactNode
  className?: string
  contentClassName?: string
}

export function SettingsSection({
  title,
  description,
  summary,
  actions,
  defaultCollapsed = true,
  children,
  className,
  contentClassName,
}: SettingsSectionProps) {
  return (
    <ExpandableCard
      title={title}
      description={description}
      summary={summary}
      actions={actions}
      defaultCollapsed={defaultCollapsed}
      className={cn(
        'border-border/70 bg-surface/80 shadow-sm backdrop-blur',
        className,
      )}
      contentClassName={cn('space-y-6', contentClassName)}
    >
      {children}
    </ExpandableCard>
  )
}
