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
    if (typeof window === 'undefined') {
      return
    }

    const syncFromLocation = () => {
      const requestedValue = readRequestedValue()
      const nextValue = resolveValue(requestedValue)
      if (requestedValue !== nextValue) {
        syncLocationToValue(nextValue)
      }
      setValue((currentValue) =>
        currentValue === nextValue ? currentValue : nextValue,
      )
    }

    const { history } = window
    const originalPushState = history.pushState.bind(history)
    const originalReplaceState = history.replaceState.bind(history)
    const emitLocationChange = () => {
      window.dispatchEvent(new Event('locationchange'))
    }

    history.pushState = function pushState(...args) {
      const result = originalPushState(...args)
      emitLocationChange()
      return result
    }
    history.replaceState = function replaceState(...args) {
      const result = originalReplaceState(...args)
      emitLocationChange()
      return result
    }

    window.addEventListener('locationchange', syncFromLocation)
    window.addEventListener('popstate', emitLocationChange)
    syncFromLocation()

    return () => {
      history.pushState = originalPushState
      history.replaceState = originalReplaceState
      window.removeEventListener('locationchange', syncFromLocation)
      window.removeEventListener('popstate', emitLocationChange)
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
      <div className="sticky top-0 z-20 -mx-px rounded-2xl border border-border/50 bg-bg/95 p-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-bg/85">
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
