'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function WorkflowsRedirect() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to capabilities page with workflows tab
    router.replace('/capabilities?tab=workflows')
  }, [router])

  return null
}
