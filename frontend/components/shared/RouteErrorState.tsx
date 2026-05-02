'use client'

import { AlertTriangle, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'

interface RouteErrorStateProps {
  error: Error & { digest?: string }
  reset: () => void
  logLabel: string
  title: string
  description: string
  retryLabel?: string
}

export function RouteErrorState({
  error,
  reset,
  logLabel,
  title,
  description,
  retryLabel = 'Retry',
}: RouteErrorStateProps) {
  useEffect(() => {
    console.error(logLabel, error)
  }, [error, logLabel])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 p-8">
      <div className="relative">
        <div className="absolute -inset-6 rounded-full bg-loss/8 blur-2xl" />
        <div className="relative rounded-full border border-loss/20 bg-loss/10 p-5 shadow-lg">
          <AlertTriangle className="h-10 w-10 text-loss" />
        </div>
      </div>
      <div className="space-y-3 text-center">
        <h2 className="font-display text-2xl italic text-text">{title}</h2>
        <p className="max-w-md text-sm leading-relaxed text-text-muted">
          {description}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" asChild>
          <Link href="/">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Dashboard
          </Link>
        </Button>
        <Button type="button" onClick={reset}>
          {retryLabel}
        </Button>
      </div>
    </div>
  )
}
