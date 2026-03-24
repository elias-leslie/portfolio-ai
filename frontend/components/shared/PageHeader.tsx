'use client'

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type PageHeaderVariant = 'gradient' | 'plain'
type PageHeaderSize = 'sm' | 'md' | 'lg'

const sizeStyles: Record<PageHeaderSize, string> = {
  sm: 'text-3xl',
  md: 'text-4xl',
  lg: 'text-5xl',
}

export interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
  className?: string
  variant?: PageHeaderVariant
  size?: PageHeaderSize
  align?: 'start' | 'center'
}

/**
 * Shared hero/header for primary app pages so we keep typography + spacing consistent.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  className,
  variant = 'gradient',
  size = 'lg',
  align = 'start',
}: PageHeaderProps) {
  const titleClass =
    variant === 'gradient'
      ? 'bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent animate-gradient-text'
      : 'text-text'

  return (
    <header
      className={cn(
        'flex flex-col gap-4 md:flex-row md:items-end md:justify-between',
        className,
      )}
    >
      <div
        className={cn(
          'space-y-3',
          align === 'center' && 'text-center md:text-left',
        )}
      >
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            {eyebrow}
          </p>
        )}
        <h1
          className={cn(
            'font-display italic tracking-tight',
            sizeStyles[size],
            titleClass,
          )}
        >
          {title}
        </h1>
        {description && (
          <p className="text-base text-text-muted">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap gap-2 md:justify-end">{actions}</div>
      )}
    </header>
  )
}
