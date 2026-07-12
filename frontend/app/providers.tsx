'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { ChatWidgetProvider } from '@/components/providers/ChatWidgetProvider'
import { HomeActionQueueProvider } from '@/components/providers/HomeActionQueueProvider'
import { ThemeProvider } from '@/components/providers/ThemeProvider'

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
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
        <HomeActionQueueProvider enabled={pathname === '/'}>
          <ChatWidgetProvider>{children}</ChatWidgetProvider>
        </HomeActionQueueProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
