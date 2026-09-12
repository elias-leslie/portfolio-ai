'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { ChatWidgetProvider } from '@/components/providers/ChatWidgetProvider'
import { HomeActionQueueProvider } from '@/components/providers/HomeActionQueueProvider'
import {
  HouseholdIdentityProvider,
  useHouseholdIdentity,
} from '@/components/providers/HouseholdIdentityProvider'
import { ThemeProvider } from '@/components/providers/ThemeProvider'

function MemberProviders({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const identity = useHouseholdIdentity()
  return (
    <HomeActionQueueProvider
      enabled={
        !pathname.startsWith('/capture') && identity.access !== 'capture_only'
      }
    >
      <ChatWidgetProvider>{children}</ChatWidgetProvider>
    </HomeActionQueueProvider>
  )
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60, // 1 minute
            // apiRequest already retries safe reads with bounded backoff. A
            // second React Query retry layer multiplies outage traffic and
            // can keep error states loading for tens of seconds.
            retry: false,
            refetchOnWindowFocus: false,
            refetchIntervalInBackground: false,
          },
        },
      }),
  )

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <HouseholdIdentityProvider>
          <MemberProviders>{children}</MemberProviders>
        </HouseholdIdentityProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
