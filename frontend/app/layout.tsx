import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono, Newsreader } from 'next/font/google'
import Script from 'next/script'
import './globals.css'
import './globals-watchlist.css'
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

const newsreader = Newsreader({
  variable: '--font-display',
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  style: ['normal', 'italic'],
})

export const metadata: Metadata = {
  title: 'Portfolio AI Platform',
  description: 'AI-powered portfolio intelligence and market insights',
}

export const viewport: Viewport = {
  themeColor: '#0f172a',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className="dark"
      data-theme="dark"
      style={{ colorScheme: 'dark' }}
      suppressHydrationWarning
    >
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta
          name="apple-mobile-web-app-status-bar-style"
          content="black-translucent"
        />
        <meta name="apple-mobile-web-app-title" content="Portfolio AI" />
      </head>
      <body
        className={cn(
          geistSans.variable,
          geistMono.variable,
          newsreader.variable,
          'bg-bg text-text antialiased h-screen overflow-hidden flex flex-col',
        )}
      >
        <Providers>
          <Navigation />
          <main className="flex-1 overflow-auto">{children}</main>
          <Toaster
            position="top-right"
            richColors
            theme="dark"
            toastOptions={{ className: 'border-border/50' }}
          />
        </Providers>
        <Script
          id="sw-cleanup"
          strategy="afterInteractive"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: cleanup script is static, no user input
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.getRegistrations().then(function(registrations) {
                    registrations.forEach(function(registration) {
                      registration.unregister();
                    });
                  });
                  if ('caches' in window) {
                    caches.keys().then(function(keys) {
                      keys
                        .filter(function(key) {
                          return key.startsWith('portfolio-ai-');
                        })
                        .forEach(function(key) {
                          caches.delete(key);
                        });
                    });
                  }
                });
              }
            `,
          }}
        />
      </body>
    </html>
  )
}
