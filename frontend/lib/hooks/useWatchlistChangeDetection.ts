import { useEffect, useRef, useState } from 'react'
import type { WatchlistItem } from '@/lib/api/watchlist'

type WatchlistSnapshot = {
  price: number | null
  score: number | null
  risk: WatchlistItem['riskLevel']
  updatedAt: string | null
}

interface ChangeDetectionResult {
  changedCells: Record<string, Record<string, boolean>>
  recentlyUpdatedRows: Set<string>
}

function buildSnapshot(item: WatchlistItem): WatchlistSnapshot {
  return {
    price:
      typeof item.currentScore?.price.metadata?.price === 'number'
        ? item.currentScore.price.metadata.price
        : null,
    score: item.currentScore?.overall ?? null,
    risk: item.riskLevel ?? null,
    updatedAt: item.currentScore?.price?.updatedAt ?? item.updatedAt,
  }
}

/**
 * Hook to detect changes in watchlist items for cell flash animations.
 * Tracks previous snapshots and computes which cells have changed.
 */
export function useWatchlistChangeDetection(
  items: WatchlistItem[],
): ChangeDetectionResult {
  const previousSnapshots = useRef<Map<string, WatchlistSnapshot>>(new Map())
  const [changedCells, setChangedCells] = useState<
    Record<string, Record<string, boolean>>
  >({})
  const [recentlyUpdatedRows, setRecentlyUpdatedRows] = useState<Set<string>>(
    new Set(),
  )

  useEffect(() => {
    // Handle empty items - clear refs only, no setState needed
    if (!items.length) {
      previousSnapshots.current = new Map()
      return
    }

    const nextSnapshots = new Map<string, WatchlistSnapshot>()
    const nextChanged: Record<string, Record<string, boolean>> = {}
    const updatedRows: string[] = []

    items.forEach((item) => {
      const snapshot = buildSnapshot(item)
      nextSnapshots.set(item.id, snapshot)
      const previous = previousSnapshots.current.get(item.id)
      if (!previous) {
        updatedRows.push(item.id)
        return
      }

      const fieldChanges: Record<string, boolean> = {}
      if (snapshot.price !== previous.price) fieldChanges.price = true
      if (snapshot.score !== previous.score) fieldChanges.score = true
      if (snapshot.risk !== previous.risk) fieldChanges.risk = true
      if (snapshot.updatedAt !== previous.updatedAt)
        fieldChanges.updatedAt = true

      if (Object.keys(fieldChanges).length > 0) {
        nextChanged[item.id] = fieldChanges
        updatedRows.push(item.id)
      }
    })

    previousSnapshots.current = nextSnapshots

    // Use setTimeout(0) to defer state updates outside the synchronous effect body
    const immediateTimeout = window.setTimeout(() => {
      if (Object.keys(nextChanged).length > 0) {
        setChangedCells(nextChanged)
      }
      if (updatedRows.length > 0) {
        setRecentlyUpdatedRows(new Set(updatedRows))
      }
    }, 0)

    // Clear animation state after delay
    const cellTimeout = window.setTimeout(() => setChangedCells({}), 2200)
    const rowTimeout = window.setTimeout(
      () => setRecentlyUpdatedRows(new Set()),
      1500,
    )

    return () => {
      window.clearTimeout(immediateTimeout)
      window.clearTimeout(cellTimeout)
      window.clearTimeout(rowTimeout)
    }
  }, [items])

  return { changedCells, recentlyUpdatedRows }
}
