'use client';

import { Diamond, Star } from 'lucide-react';

interface ProviderBadgeProps {
  provider: string | null | undefined;
  size?: 'sm' | 'xs';
}

/**
 * Provider badge component for session attribution.
 * Displays Claude (diamond) and/or Gemini (star) icons based on provider.
 */
export function ProviderBadge({ provider, size = 'sm' }: ProviderBadgeProps) {
  if (!provider) return null;

  const iconClass = size === 'xs' ? 'h-3 w-3' : 'h-4 w-4';

  if (provider === 'claude') {
    return <span title="Claude"><Diamond className={`${iconClass} text-blue-400`} /></span>;
  }
  if (provider === 'gemini') {
    return <span title="Gemini"><Star className={`${iconClass} text-green-400`} /></span>;
  }
  if (provider === 'both') {
    return (
      <span className="flex -space-x-1" title="Claude + Gemini">
        <Diamond className={`${iconClass} text-blue-400`} />
        <Star className={`${iconClass} text-green-400`} />
      </span>
    );
  }
  return null;
}
