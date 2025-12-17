'use client';

import { cn } from '@/lib/utils';
import { BarChart3, Laptop } from 'lucide-react';

export type AgentMode = 'financial' | 'dev';

interface ModeSelectorProps {
  value: AgentMode;
  onChange: (value: AgentMode) => void;
  disabled?: boolean;
}

const modes: AgentMode[] = ['financial', 'dev'];

const modeConfig = {
  financial: {
    icon: BarChart3,
    tooltip: 'Financial Mode - Click to switch',
    color: 'text-emerald-400 hover:text-emerald-300',
    bgColor: 'hover:bg-emerald-900/30',
  },
  dev: {
    icon: Laptop,
    tooltip: 'Dev Mode - Click to switch',
    color: 'text-sky-400 hover:text-sky-300',
    bgColor: 'hover:bg-sky-900/30',
  },
};

export function ModeSelector({ value, onChange, disabled = false }: ModeSelectorProps) {
  const cycleMode = () => {
    if (disabled) return;
    const currentIndex = modes.indexOf(value);
    const nextIndex = (currentIndex + 1) % modes.length;
    onChange(modes[nextIndex]);
  };

  const config = modeConfig[value];
  const Icon = config.icon;

  return (
    <button
      onClick={cycleMode}
      disabled={disabled}
      // suppressHydrationWarning to handle browser extensions (Dashlane)
      suppressHydrationWarning
      className={cn(
        "h-8 w-8 flex items-center justify-center rounded transition-colors",
        config.color,
        config.bgColor,
        disabled && "opacity-50 cursor-not-allowed"
      )}
      title={config.tooltip}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
