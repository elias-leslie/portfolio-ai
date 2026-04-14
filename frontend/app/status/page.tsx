'use client'

export const dynamic = 'force-dynamic'

import { StatusWorkspace } from '@/components/status/StatusWorkspace'
import { useClientReady } from '@/lib/hooks/useClientReady'

function StatusPageContent() {
  return <StatusWorkspace />
}

export default function StatusPage() {
  const ready = useClientReady()

  if (!ready) {
    return <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8" />
  }

  return <StatusPageContent />
}
