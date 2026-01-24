import type { Metadata, Viewport } from 'next'
import Script from 'next/script'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import './globals-watchlist.css'
import { Toaster } from 'sonner'
import { Navigation } from '@/components/Navigation'
import { VoiceOverlayWrapper } from '@/components/VoiceOverlayWrapper'
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

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
  ],
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Portfolio AI" />
      </head>
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
          <VoiceOverlayWrapper />
        </Providers>
        <Script
          id="sw-register"
          strategy="afterInteractive"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: SW registration is hardcoded, no user input
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js').then(
                    function(registration) {
                      console.log('SW registered:', registration.scope);
                    },
                    function(err) {
                      console.log('SW registration failed:', err);
                    }
                  );
                });
              }
            `,
          }}
        />
      </body>
    </html>
  )
}
