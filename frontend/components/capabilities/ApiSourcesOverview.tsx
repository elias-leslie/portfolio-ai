/**
 * API Sources Overview Component
 *
 * Displays all data source providers with:
 * - Provider cards with tier, rate limits, capabilities
 * - GAP coverage badges
 * - Expandable endpoint details
 */

'use client'

import { useQuery } from '@tanstack/react-query'
import { Loader2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { fetchSourceDetail, fetchSources } from '@/lib/api/sources'
import { DataRoutingSection } from './DataRoutingSection'
import { ProviderCard } from './ProviderCard'
import { SourcesSummaryCards } from './SourcesSummaryCards'

interface ExpandedProviders {
  [key: string]: boolean
}

export function ApiSourcesOverview() {
  const [expandedProviders, setExpandedProviders] = useState<ExpandedProviders>(
    {},
  )
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

  const {
    data: sourcesData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['api-sources'],
    queryFn: fetchSources,
  })

  const { data: providerDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['api-source-detail', selectedProvider],
    queryFn: () =>
      selectedProvider ? fetchSourceDetail(selectedProvider) : null,
    enabled: !!selectedProvider,
  })

  const toggleProvider = (name: string) => {
    setExpandedProviders((prev) => ({
      ...prev,
      [name]: !prev[name],
    }))
    if (!expandedProviders[name]) {
      setSelectedProvider(name)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <XCircle className="mx-auto h-10 w-10 text-destructive" />
        <p className="mt-2 text-sm text-destructive">
          Failed to load API sources
        </p>
      </div>
    )
  }

  if (!sourcesData) return null

  return (
    <div className="space-y-6">
      <SourcesSummaryCards providers={sourcesData.providers} />

      <div className="space-y-3">
        {sourcesData.providers.map((provider) => (
          <ProviderCard
            key={provider.name}
            provider={provider}
            isExpanded={!!expandedProviders[provider.name]}
            detail={
              selectedProvider === provider.name ? providerDetail : null
            }
            detailLoading={detailLoading}
            onToggle={toggleProvider}
          />
        ))}
      </div>

      {sourcesData.dataRouting && (
        <DataRoutingSection dataRouting={sourcesData.dataRouting} />
      )}
    </div>
  )
}
