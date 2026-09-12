'use client'

import { useEffect, useState } from 'react'

/** Wait for source-driven defaults and their debounced updates before starting CPU work. */
export function useRetirementInputsReady(
  requestKey: string,
  waitingForSources: boolean,
) {
  const [readyKey, setReadyKey] = useState<string | null>(null)
  useEffect(() => {
    setReadyKey(null)
    if (waitingForSources) return
    const timer = setTimeout(() => setReadyKey(requestKey), 300)
    return () => clearTimeout(timer)
  }, [requestKey, waitingForSources])
  return !waitingForSources && readyKey === requestKey
}
