'use client'

import { BookOpen, Cloud, Loader2 } from 'lucide-react'
import { Suspense, useState } from 'react'
import { ApiSourcesOverview } from '@/components/capabilities/ApiSourcesOverview'
import { RulesViewer } from '@/components/rules/RulesViewer'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type TabValue = 'sources' | 'rules'

function CapabilitiesPageContent() {
  const [activeTab, setActiveTab] = useState<TabValue>('sources')

  return (
    <PageContainer className="space-y-6 py-4">
      <PageHeader
        title="Data Sources & Rules"
        description="Review vendor coverage, routing, and the portfolio guardrails that shape signals."
        size="md"
      />

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as TabValue)}
      >
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="sources">
            <Cloud className="mr-2 h-4 w-4" />
            Sources
          </TabsTrigger>
          <TabsTrigger value="rules">
            <BookOpen className="mr-2 h-4 w-4" />
            Rules
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sources">
          <ApiSourcesOverview />
        </TabsContent>

        <TabsContent value="rules">
          <RulesViewer />
        </TabsContent>
      </Tabs>
    </PageContainer>
  )
}

export function CapabilitiesPageClient() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-bg">
          <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
            <PageHeader
              title="Data Sources & Rules"
              description="Loading source coverage and portfolio rules..."
              size="md"
            />
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          </div>
        </div>
      }
    >
      <CapabilitiesPageContent />
    </Suspense>
  )
}
