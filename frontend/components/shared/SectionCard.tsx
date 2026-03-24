'use client'

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type SectionPadding = 'none' | 'sm' | 'md' | 'lg'
type SectionVariant = 'surface' | 'ghost'

const paddingStyles: Record<SectionPadding, string> = {
  none: '',
  sm: 'px-4 py-4',
  md: 'px-6 py-6',
  lg: 'px-8 py-8',
}

export interface SectionCardProps {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
  headerClassName?: string
  padding?: SectionPadding
  variant?: SectionVariant
}

/**
 * Layout helper that wraps feature blocks in a consistent surface with shared spacing.
 */
export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
  headerClassName,
  padding = 'md',
  variant = 'ghost',
}: SectionCardProps) {
  const baseClass =
    variant === 'surface'
      ? 'rounded-2xl border border-border/40 bg-surface/50 shadow-sm backdrop-blur-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-border/60 hover:shadow-md'
      : 'rounded-2xl'

  return (
    <section className={cn(baseClass, className)}>
      {(title || description || actions) && (
        <div
          className={cn(
            'flex flex-col gap-3 px-6 py-5 md:flex-row md:items-center md:justify-between',
            variant === 'surface' && 'border-b border-border/40',
            headerClassName,
          )}
        >
          <div className="space-y-1">
            {title && (
              <h2 className="font-display text-lg tracking-tight text-text">
                {title}
              </h2>
            )}
            {description && (
              <p className="text-sm text-text-muted">{description}</p>
            )}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn(paddingStyles[padding], contentClassName)}>
        {children}
      </div>
    </section>
  )
}
