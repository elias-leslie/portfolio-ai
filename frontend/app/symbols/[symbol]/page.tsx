'use client'

export const dynamic = 'force-dynamic'

import { useParams } from 'next/navigation'
import { SymbolWorkspace } from '@/components/symbol/SymbolWorkspace'
import { useClientReady } from '@/lib/hooks/useClientReady'

function SymbolPageContent() {
  const params = useParams<{ symbol: string }>()
  return <SymbolWorkspace symbol={decodeURIComponent(params.symbol)} />
}

export default function SymbolPage() {
  const ready = useClientReady()

  if (!ready) {
    return <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8" />
  }

  return <SymbolPageContent />
}
