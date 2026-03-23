import { cva, type VariantProps } from 'class-variance-authority'
import type * as React from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-surface-muted text-text',
        outline: 'border-border text-text',
        destructive: 'border-transparent bg-destructive/20 text-destructive',
        gain: 'border-transparent bg-gain/20 text-gain',
        loss: 'border-transparent bg-loss/20 text-loss',
        neutral: 'border-transparent bg-neutral/20 text-neutral',
        success: 'border-transparent bg-gain/20 text-gain',
        warning: 'border-transparent bg-warning/20 text-warning',
        error: 'border-transparent bg-loss/20 text-loss',
        // Score-based variants using viz tokens
        'viz-0': 'border-transparent bg-viz-0/30 text-viz-0',
        'viz-1': 'border-transparent bg-viz-1/30 text-viz-1',
        'viz-2': 'border-transparent bg-viz-2/30 text-viz-2',
        'viz-3': 'border-transparent bg-viz-3/30 text-viz-3',
        'viz-4': 'border-transparent bg-viz-4/30 text-viz-4',
        'viz-5': 'border-transparent bg-viz-5/30 text-viz-5',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
