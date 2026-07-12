/**
 * Tabs component for tabbed interfaces
 */

import * as React from 'react'
import { cn } from '@/lib/utils'

interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | undefined>(undefined)

function useTabsContext() {
  const context = React.useContext(TabsContext)
  if (!context) {
    throw new Error('Tabs components must be used within Tabs')
  }
  return context
}

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
}

export function Tabs({
  value,
  onValueChange,
  children,
  className,
  ...props
}: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={cn('w-full', className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  )
}

interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export function TabsList({ children, className, ...props }: TabsListProps) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex h-10 items-center justify-center rounded-md bg-surface-muted p-1 text-text-muted',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

interface TabsTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  children: React.ReactNode
}

export function TabsTrigger({
  value,
  children,
  className,
  onClick,
  onKeyDown,
  ...props
}: TabsTriggerProps) {
  const { value: selectedValue, onValueChange } = useTabsContext()
  const isActive = selectedValue === value

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      tabIndex={isActive ? 0 : -1}
      data-state={isActive ? 'active' : 'inactive'}
      onClick={(event) => {
        onClick?.(event)
        if (!event.defaultPrevented) {
          onValueChange(value)
        }
      }}
      onKeyDown={(event) => {
        onKeyDown?.(event)
        if (event.defaultPrevented) {
          return
        }
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          return
        }
        const tabList = event.currentTarget.closest('[role="tablist"]')
        const tabs = Array.from(
          tabList?.querySelectorAll<HTMLButtonElement>(
            '[role="tab"]:not(:disabled)',
          ) ?? [],
        )
        if (tabs.length === 0) {
          return
        }
        const currentIndex = tabs.indexOf(event.currentTarget)
        const nextIndex =
          event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? tabs.length - 1
              : event.key === 'ArrowRight'
                ? (currentIndex + 1) % tabs.length
                : (currentIndex - 1 + tabs.length) % tabs.length
        event.preventDefault()
        tabs[nextIndex]?.focus()
        tabs[nextIndex]?.click()
      }}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-bg transition-all duration-200 ease-in-out cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40',
        isActive
          ? 'bg-bg text-text shadow-sm'
          : 'text-text-muted hover:bg-surface hover:text-text',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  children: React.ReactNode
}

export function TabsContent({
  value,
  children,
  className,
  ...props
}: TabsContentProps) {
  const { value: selectedValue } = useTabsContext()

  if (selectedValue !== value) {
    return null
  }

  return (
    <div
      role="tabpanel"
      className={cn(
        'mt-2 ring-offset-bg animate-tab-enter focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
