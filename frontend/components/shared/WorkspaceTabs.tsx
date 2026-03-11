'use client'

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

export interface WorkspaceTab {
  value: string
  label: string
  description?: string
  badge?: string
  content: ReactNode
}

export function WorkspaceTabs({
  tabs,
  defaultValue,
  className,
}: {
  tabs: WorkspaceTab[]
  defaultValue?: string
  className?: string
}) {
  const fallbackValue = defaultValue ?? tabs[0]?.value ?? ''
  const resolveValue = (requestedValue: string | null) =>
    tabs.some((tab) => tab.value === requestedValue) && requestedValue
      ? requestedValue
      : fallbackValue
  const readRequestedValue = () => {
    if (typeof window === 'undefined') {
      return null
    }

    return new URLSearchParams(window.location.search).get('tab')
  }
  const syncLocationToValue = (nextValue: string) => {
    if (typeof window === 'undefined') {
      return
    }

    const nextUrl = new URL(window.location.href)
    const nextParams = new URLSearchParams(nextUrl.search)
    const currentTab = nextParams.get('tab')

    if (nextValue === fallbackValue) {
      if (!currentTab) {
        return
      }
      nextParams.delete('tab')
    } else {
      if (currentTab === nextValue) {
        return
      }
      nextParams.set('tab', nextValue)
    }

    nextUrl.search = nextParams.toString()
    window.history.replaceState(window.history.state, '', nextUrl)
  }
  const initialValue = resolveValue(readRequestedValue())
  const [value, setValue] = useState(initialValue)
  const activeTab = tabs.find((tab) => tab.value === value) ?? tabs[0]

  useEffect(() => {
    const syncFromLocation = () => {
      const requestedValue = readRequestedValue()
      const nextValue = resolveValue(readRequestedValue())
      if (requestedValue !== nextValue) {
        syncLocationToValue(nextValue)
      }
      setValue((currentValue) =>
        currentValue === nextValue ? currentValue : nextValue,
      )
    }

    syncFromLocation()
    window.addEventListener('popstate', syncFromLocation)
    return () => {
      window.removeEventListener('popstate', syncFromLocation)
    }
  }, [fallbackValue, tabs])

  useEffect(() => {
    const nextValue = resolveValue(value)
    if (nextValue !== value) {
      setValue(nextValue)
      syncLocationToValue(nextValue)
    }
  }, [fallbackValue, tabs, value])

  const handleValueChange = (nextValue: string) => {
    if (nextValue === value) {
      return
    }

    setValue(nextValue)

    if (typeof window === 'undefined') {
      return
    }

    syncLocationToValue(nextValue)
  }

  return (
    <Tabs value={value} onValueChange={handleValueChange} className={className}>
      <div className="sticky top-20 z-10 rounded-2xl border border-border/50 bg-bg/90 p-3 backdrop-blur">
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-2 bg-transparent p-0">
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              aria-current={tab.value === value ? 'page' : undefined}
              className={cn(
                'rounded-xl border border-border/40 bg-surface/70 px-4 py-2 text-left',
                'data-[state=active]:border-primary/40 data-[state=active]:bg-primary/10',
              )}
            >
              <span className="flex items-center gap-2">
                <span>{tab.label}</span>
                {tab.badge ? (
                  <span
                    aria-hidden="true"
                    className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] uppercase tracking-wide text-text-muted"
                  >
                    {tab.badge}
                  </span>
                ) : null}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
        {activeTab?.description ? (
          <p className="mt-3 text-sm text-text-muted">{activeTab.description}</p>
        ) : null}
      </div>

      {tabs.map((tab) => (
        <TabsContent key={tab.value} value={tab.value} className="mt-6">
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  )
}
