import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import './globals-watchlist.css'
import { VoiceOverlay } from '@agent-hub/passport-client'
import { Toaster } from 'sonner'
import { Navigation } from '@/components/Navigation'
import { cn } from '@/lib/utils'
import { Providers } from './providers'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Portfolio AI Platform',
  description: 'AI-powered portfolio intelligence and market insights',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={cn(
          geistSans.variable,
          geistMono.variable,
          'bg-bg text-text antialiased h-screen overflow-hidden flex flex-col',
        )}
      >
        <Providers>
          <Navigation />
          <main className="flex-1 overflow-auto">{children}</main>
          <Toaster position="top-right" richColors />
          <VoiceOverlay wsUrl="wss://agentapi.summitflow.dev/api/voice/ws?user_id=portfolio_user&app=portfolio" />
        </Providers>
      </body>
    </html>
  )
}
