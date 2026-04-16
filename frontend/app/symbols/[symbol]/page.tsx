'use client'

export const dynamic = 'force-dynamic'

import { useParams } from 'next/navigation'
import { SymbolWorkspace } from '@/components/symbol/SymbolWorkspace'

function SymbolPageContent() {
  const params = useParams<{ symbol: string }>()
  return <SymbolWorkspace symbol={decodeURIComponent(params.symbol)} />
}

export default function SymbolPage() {
  return <SymbolPageContent />
}
