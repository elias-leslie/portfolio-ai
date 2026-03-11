'use client'

import { useEffect, useId, useState } from 'react'
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
  queryKey = 'tab',
  ariaLabel = 'Workspace sections',
}: {
  tabs: WorkspaceTab[]
  defaultValue?: string
  className?: string
  queryKey?: string
  ariaLabel?: string
}) {
  const idBase = useId().replace(/:/g, '')
  const fallbackValue = defaultValue ?? tabs[0]?.value ?? ''
  const resolveValue = (requestedValue: string | null) =>
    tabs.some((tab) => tab.value === requestedValue) && requestedValue
      ? requestedValue
      : fallbackValue
  const readRequestedValue = () => {
    if (typeof window === 'undefined') {
      return null
    }

    return new URLSearchParams(window.location.search).get(queryKey)
  }
  const syncLocationToValue = (nextValue: string) => {
    if (typeof window === 'undefined') {
      return
    }

    const nextUrl = new URL(window.location.href)
    const nextParams = new URLSearchParams(nextUrl.search)
    const currentTab = nextParams.get(queryKey)

    if (nextValue === fallbackValue) {
      if (!currentTab) {
        return
      }
      nextParams.delete(queryKey)
    } else {
      if (currentTab === nextValue) {
        return
      }
      nextParams.set(queryKey, nextValue)
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
  }, [fallbackValue, queryKey, tabs])

  useEffect(() => {
    const nextValue = resolveValue(value)
    if (nextValue !== value) {
      setValue(nextValue)
      syncLocationToValue(nextValue)
    }
  }, [fallbackValue, queryKey, tabs, value])

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
        <TabsList
          aria-label={ariaLabel}
          className="flex h-auto w-full flex-wrap justify-start gap-2 bg-transparent p-0"
        >
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              id={`${idBase}-${tab.value}-tab`}
              aria-controls={`${idBase}-${tab.value}-panel`}
              aria-describedby={
                tab.value === activeTab?.value && activeTab.description
                  ? `${idBase}-active-description`
                  : undefined
              }
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
          <p
            id={`${idBase}-active-description`}
            className="mt-3 text-sm text-text-muted"
          >
            {activeTab.description}
          </p>
        ) : null}
      </div>

      {tabs.map((tab) => (
        <TabsContent
          key={tab.value}
          value={tab.value}
          id={`${idBase}-${tab.value}-panel`}
          aria-labelledby={`${idBase}-${tab.value}-tab`}
          className="mt-6"
        >
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  )
}
