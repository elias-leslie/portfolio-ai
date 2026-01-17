'use client'

import { Diamond, Star } from 'lucide-react'

interface ProviderBadgeProps {
  provider: string | null | undefined
  size?: 'sm' | 'xs'
}

/**
 * Provider badge component for session attribution.
 * Displays Claude (diamond) and/or Gemini (star) icons based on provider.
 */
export function ProviderBadge({ provider, size = 'sm' }: ProviderBadgeProps) {
  if (!provider) return null

  const iconClass = size === 'xs' ? 'h-3 w-3' : 'h-4 w-4'

  if (provider === 'claude') {
    return (
      <span title="Claude">
        <Diamond className={`${iconClass} text-status-info`} />
      </span>
    )
  }
  if (provider === 'gemini') {
    return (
      <span title="Gemini">
        <Star className={`${iconClass} text-status-success`} />
      </span>
    )
  }
  if (provider === 'both') {
    return (
      <span className="flex -space-x-1" title="Claude + Gemini">
        <Diamond className={`${iconClass} text-status-info`} />
        <Star className={`${iconClass} text-status-success`} />
      </span>
    )
  }
  return null
}
