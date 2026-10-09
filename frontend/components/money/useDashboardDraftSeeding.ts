import { useCallback, useEffect, useRef } from 'react'

type DashboardWithProfile = { profile: { id: string } }

/**
 * Seed editable drafts from the dashboard without wiping unsaved edits.
 *
 * Background refetches hand the panel a new `dashboard` object often (every
 * household invalidation). Drafts re-seed wholesale only when the profile
 * identity changes; a section re-seeds from server data only after that
 * section was saved through `trackSave`.
 */
export function useDashboardDraftSeeding<
  D extends DashboardWithProfile,
  S extends string,
>({
  dashboard,
  seedAll,
  seedSection,
}: {
  dashboard: D
  seedAll: (dashboard: D) => void
  seedSection: (section: S, dashboard: D) => void
}) {
  const latestDashboard = useRef(dashboard)
  // Null so the first effect seeds once, matching the mount-time request.
  const seededProfileId = useRef<string | null>(null)
  const pendingSections = useRef(new Set<S>())
  const seeders = useRef({ seedAll, seedSection })
  seeders.current = { seedAll, seedSection }

  useEffect(() => {
    latestDashboard.current = dashboard
    if (dashboard.profile.id !== seededProfileId.current) {
      seededProfileId.current = dashboard.profile.id
      pendingSections.current.clear()
      seeders.current.seedAll(dashboard)
      return
    }
    if (pendingSections.current.size === 0) return
    for (const section of pendingSections.current) {
      seeders.current.seedSection(section, dashboard)
    }
    pendingSections.current.clear()
  }, [dashboard])

  /**
   * Run a save; on success re-seed `sections` from the post-save dashboard.
   * Mutations await their household invalidation, so a dashboard that changed
   * while the save ran already reflects it; otherwise wait for the next one.
   */
  const trackSave = useCallback(
    async <T>(sections: S[], save: () => Promise<T>): Promise<T> => {
      const before = latestDashboard.current
      const result = await save()
      const current = latestDashboard.current
      // A profile switch already re-seeded everything.
      if (current.profile.id !== before.profile.id) return result
      if (current !== before) {
        for (const section of sections) {
          seeders.current.seedSection(section, current)
        }
      } else {
        for (const section of sections) pendingSections.current.add(section)
      }
      return result
    },
    [],
  )

  return { trackSave }
}
