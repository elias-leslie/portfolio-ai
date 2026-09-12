'use client'

import { useEffect, useRef } from 'react'

type FinancialView =
  | 'today'
  | 'money-review'
  | 'retirement'
  | 'symbol-decision'
  | 'investment-analysis'

/** Local browser timings only: no figures, account IDs or input values are emitted. */
export function useUsableContentTiming(
  view: FinancialView,
  ready: boolean,
  contextKey = '',
) {
  const timing = useRef({
    key: contextKey,
    start: performance.now(),
    recorded: false,
  })
  useEffect(() => {
    if (timing.current.key !== contextKey)
      timing.current = {
        key: contextKey,
        start: performance.now(),
        recorded: false,
      }
    if (
      !ready ||
      timing.current.recorded ||
      typeof performance.measure !== 'function'
    )
      return
    let paint = 0
    const frame = requestAnimationFrame(() => {
      paint = requestAnimationFrame(() => {
        const name = `portfolio-ai:usable:${view}`
        if (performance.getEntriesByName(name).length >= 20)
          performance.clearMeasures(name)
        performance.measure(name, {
          start: timing.current.start,
          end: performance.now(),
        })
        timing.current.recorded = true
      })
    })
    return () => {
      cancelAnimationFrame(frame)
      cancelAnimationFrame(paint)
    }
  }, [view, ready, contextKey])
}
