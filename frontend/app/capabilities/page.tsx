'use client'

import { BookOpen, Cloud, ExternalLink, Loader2 } from 'lucide-react'
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
      {/* Header */}
      <PageHeader title="System Registry" size="md" />

      {/* SummitFlow link for dev tooling */}
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-phosphor/30 bg-phosphor/5 px-4 py-2 text-sm">
        <ExternalLink className="h-4 w-4 text-phosphor" />
        <span className="text-muted-foreground">
          Dev tooling (Features, Vision, Explorer, DB, Tasks, Evidence) moved to
        </span>
        <a
          href="https://dev.summitflow.dev/projects/portfolio-ai"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-phosphor hover:underline"
        >
          SummitFlow
        </a>
      </div>

      {/* Tabs - domain-specific only: Sources, Rules */}
      <Tabs
        value={activeTab}
        onValueChange={(val) => setActiveTab(val as TabValue)}
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

        {/* Data Sources Tab */}
        <TabsContent value="sources">
          <ApiSourcesOverview />
        </TabsContent>

        {/* Trading Rules Tab */}
        <TabsContent value="rules">
          <RulesViewer />
        </TabsContent>
      </Tabs>
    </PageContainer>
  )
}

export default function CapabilitiesPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-bg">
          <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
            <PageHeader
              title="System Capabilities"
              description="Loading..."
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
