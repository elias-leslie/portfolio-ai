import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
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

export const metadata: Metadata = {
  applicationName: 'Portfolio AI',
  title: 'Portfolio AI Platform',
  description: 'AI-powered portfolio intelligence and market insights',
  manifest: '/manifest.json',
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
        <link rel="manifest" href="/manifest.json" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <meta name="mobile-web-app-capable" content="yes" />
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
          id="sw-register"
          strategy="afterInteractive"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: registration script is static, no user input
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                var registerPortfolioAiServiceWorker = function() {
                  navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function(registration) {
                    if (registration.waiting) {
                      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                    }
                    registration.addEventListener('updatefound', function() {
                      var worker = registration.installing;
                      if (worker) {
                        worker.addEventListener('statechange', function() {
                          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
                            worker.postMessage({ type: 'SKIP_WAITING' });
                          }
                        });
                      }
                    });
                  }).catch(function(error) {
                    console.warn('portfolio_ai_service_worker_registration_failed', error);
                  });
                };
                if (document.readyState === 'loading') {
                  window.addEventListener('load', registerPortfolioAiServiceWorker);
                } else {
                  registerPortfolioAiServiceWorker();
                }
              }
            `,
          }}
        />
      </body>
    </html>
  )
}
