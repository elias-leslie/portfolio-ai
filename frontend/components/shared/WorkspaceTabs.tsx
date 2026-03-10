'use client'

import { useState } from 'react'
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
  const initialValue = defaultValue ?? tabs[0]?.value ?? ''
  const [value, setValue] = useState(initialValue)
  const activeTab = tabs.find((tab) => tab.value === value) ?? tabs[0]

  return (
    <Tabs value={value} onValueChange={setValue} className={className}>
      <div className="sticky top-20 z-10 rounded-2xl border border-border/50 bg-bg/90 p-3 backdrop-blur">
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-2 bg-transparent p-0">
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className={cn(
                'rounded-xl border border-border/40 bg-surface/70 px-4 py-2 text-left',
                'data-[state=active]:border-primary/40 data-[state=active]:bg-primary/10',
              )}
            >
              <span className="flex items-center gap-2">
                <span>{tab.label}</span>
                {tab.badge ? (
                  <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] uppercase tracking-wide text-text-muted">
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
