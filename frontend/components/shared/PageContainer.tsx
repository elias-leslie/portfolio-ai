import { cn } from '@/lib/utils'

export const DEFAULT_PAGE_WIDTH_CLASS = 'max-w-[1680px]'

interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  fullWidth?: boolean
}

export function PageContainer({
  children,
  className,
  fullWidth = false,
  ...props
}: PageContainerProps) {
  return (
    <div
      className={cn(
        'mx-auto w-full space-y-8 px-4 py-6 sm:px-6 lg:px-8 animate-fade-in',
        !fullWidth && DEFAULT_PAGE_WIDTH_CLASS,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
