'use client'

export const dynamic = 'force-dynamic'

import { useSearchParams } from 'next/navigation'
import { StrategyLabWorkspace } from '@/components/strategy-lab/StrategyLabWorkspace'

export default function StrategyLabPage() {
  const searchParams = useSearchParams()
  return <StrategyLabWorkspace initialSymbol={searchParams.get('symbol')} />
}
