'use client'

import { useParams } from 'next/navigation'
import { SymbolWorkspace } from '@/components/symbol/SymbolWorkspace'

export default function SymbolPage() {
  const params = useParams<{ symbol: string }>()
  return <SymbolWorkspace symbol={decodeURIComponent(params.symbol)} />
}
