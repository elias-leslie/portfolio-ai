'use client';

import { Diamond, Star } from 'lucide-react';
import { cn } from '@/lib/utils';

export type AgentProvider = 'claude' | 'gemini' | 'both';

interface AgentSelectorProps {
  value: AgentProvider;
  onChange: (value: AgentProvider) => void;
  disabled?: boolean;
}

const providers: AgentProvider[] = ['claude', 'gemini', 'both'];

const providerConfig = {
  claude: {
    tooltip: 'Claude - Click to switch',
    color: 'text-blue-400 hover:text-blue-300',
    bgColor: 'hover:bg-blue-900/30',
  },
  gemini: {
    tooltip: 'Gemini - Click to switch',
    color: 'text-green-400 hover:text-green-300',
    bgColor: 'hover:bg-green-900/30',
  },
  both: {
    tooltip: 'Roundtable - Click to switch',
    color: 'text-purple-400 hover:text-purple-300',
    bgColor: 'hover:bg-purple-900/30',
  },
};

export function AgentSelector({ value, onChange, disabled = false }: AgentSelectorProps) {
  const cycleProvider = () => {
    if (disabled) return;
    const currentIndex = providers.indexOf(value);
    const nextIndex = (currentIndex + 1) % providers.length;
    onChange(providers[nextIndex]);
  };

  const config = providerConfig[value];

  return (
    <button
      onClick={cycleProvider}
      disabled={disabled}
      className={cn(
        "h-8 w-8 flex items-center justify-center rounded transition-colors",
        config.color,
        config.bgColor,
        disabled && "opacity-50 cursor-not-allowed"
      )}
      title={config.tooltip}
    >
      {value === 'both' ? (
        <span className="flex items-center -space-x-1">
          <Diamond className="h-3 w-3 text-blue-400" />
          <Star className="h-3 w-3 text-green-400" />
        </span>
      ) : value === 'claude' ? (
        <Diamond className="h-4 w-4" />
      ) : (
        <Star className="h-4 w-4" />
      )}
    </button>
  );
}
