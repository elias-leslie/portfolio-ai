'use client'

import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

export const PREFERS_REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

const ThemeContext = createContext<{
  theme: 'dark'
  resolvedTheme: 'dark'
  prefersReducedMotion: boolean
  setTheme: (value: 'dark') => void
} | null>(null)

function applyMotionPreference(reduced: boolean) {
  const root = document.documentElement
  root.dataset.reducedMotion = reduced ? 'true' : 'false'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    // Handle reduced motion preference
    const motionMedia = window.matchMedia(PREFERS_REDUCED_MOTION_QUERY)
    const handleMotion = (event?: MediaQueryListEvent) => {
      const prefersReduced = event ? event.matches : motionMedia.matches
      startTransition(() => {
        setPrefersReducedMotion(prefersReduced)
      })
      applyMotionPreference(prefersReduced)
    }

    handleMotion()
    motionMedia.addEventListener('change', handleMotion)

    return () => {
      motionMedia.removeEventListener('change', handleMotion)
    }
  }, [])

  useEffect(() => {
    applyMotionPreference(prefersReducedMotion)
  }, [prefersReducedMotion])

  const contextValue = useMemo(
    () => ({
      theme: 'dark' as const,
      resolvedTheme: 'dark' as const,
      prefersReducedMotion,
      setTheme: () => {}, // no-op since we're dark-only
    }),
    [prefersReducedMotion],
  )

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)

  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }

  return context
}
