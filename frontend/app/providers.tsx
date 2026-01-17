'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { AgentProvider } from '@/components/providers/AgentProvider'
import { ThemeProvider } from '@/components/providers/ThemeProvider'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60, // 1 minute
            refetchOnWindowFocus: false,
            // Enable interval refetching globally (can be overridden per-query)
            refetchIntervalInBackground: true,
          },
        },
      }),
  )

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AgentProvider>{children}</AgentProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
