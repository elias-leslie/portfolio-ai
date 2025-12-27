'use client';

import { Diamond, Star, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState, useRef, useEffect } from 'react';

export type AgentProvider = 'claude' | 'gemini' | 'both';
export type RoundtableOrder = 'claude-first' | 'gemini-first';

interface AgentSelectorProps {
  value: AgentProvider;
  onChange: (value: AgentProvider) => void;
  disabled?: boolean;
  roundtableOrder?: RoundtableOrder;
  onRoundtableOrderChange?: (order: RoundtableOrder) => void;
  maxTurns?: number;
  onMaxTurnsChange?: (turns: number) => void;
}

const providers: AgentProvider[] = ['claude', 'gemini', 'both'];

const providerConfig = {
  claude: {
    tooltip: 'Claude - Click to switch',
    color: 'text-accent hover:text-accent',
    bgColor: 'hover:bg-accent/20',
  },
  gemini: {
    tooltip: 'Gemini - Click to switch',
    color: 'text-gain hover:text-gain',
    bgColor: 'hover:bg-gain/20',
  },
  both: {
    tooltip: 'Roundtable - Click to switch',
    color: 'text-primary hover:text-primary',
    bgColor: 'hover:bg-primary/20',
  },
};

export function AgentSelector({
  value,
  onChange,
  disabled = false,
  roundtableOrder = 'claude-first',
  onRoundtableOrderChange,
  maxTurns = 10,
  onMaxTurnsChange,
}: AgentSelectorProps) {
  const [showOrderMenu, setShowOrderMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowOrderMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const cycleProvider = () => {
    if (disabled) return;
    const currentIndex = providers.indexOf(value);
    const nextIndex = (currentIndex + 1) % providers.length;
    onChange(providers[nextIndex]);
  };

  const config = providerConfig[value];

  return (
    // suppressHydrationWarning to handle browser extensions (Dashlane) adding attributes
    <div className="relative" ref={menuRef} suppressHydrationWarning>
      <div className="flex items-center gap-1">
        <button
          onClick={cycleProvider}
          disabled={disabled}
          suppressHydrationWarning
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
              <Diamond className="h-3 w-3 text-accent" />
              <Star className="h-3 w-3 text-gain" />
            </span>
          ) : value === 'claude' ? (
            <Diamond className="h-4 w-4" />
          ) : (
            <Star className="h-4 w-4" />
          )}
        </button>

        {/* Order selector dropdown trigger - only shown when "both" is selected */}
        {value === 'both' && onRoundtableOrderChange && (
          <button
            onClick={() => setShowOrderMenu(!showOrderMenu)}
            className="h-6 w-6 flex items-center justify-center rounded text-text-muted hover:text-text hover:bg-surface/50 transition-colors"
            title="Change response order"
          >
            <ChevronUp className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Order selection dropdown - drops UP to avoid expanding window */}
      {showOrderMenu && value === 'both' && onRoundtableOrderChange && (
        <div className="absolute bottom-full left-0 mb-1 w-48 bg-surface border border-border rounded-md shadow-lg z-50">
          <div className="py-1">
            <button
              onClick={() => {
                onRoundtableOrderChange('claude-first');
                setShowOrderMenu(false);
              }}
              className={cn(
                "w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-surface-muted transition-colors",
                roundtableOrder === 'claude-first' ? "text-accent" : "text-text"
              )}
            >
              <Diamond className="h-3 w-3 text-accent" />
              Claude first
              {roundtableOrder === 'claude-first' && <span className="ml-auto text-xs">✓</span>}
            </button>
            <button
              onClick={() => {
                onRoundtableOrderChange('gemini-first');
                setShowOrderMenu(false);
              }}
              className={cn(
                "w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-surface-muted transition-colors",
                roundtableOrder === 'gemini-first' ? "text-gain" : "text-text"
              )}
            >
              <Star className="h-3 w-3 text-gain" />
              Gemini first
              {roundtableOrder === 'gemini-first' && <span className="ml-auto text-xs">✓</span>}
            </button>
          </div>
          {/* Max turns selector */}
          {onMaxTurnsChange && (
            <div className="border-t border-border px-3 py-2">
              <label className="text-xs text-text-muted block mb-1">Max turns</label>
              <div className="flex items-center gap-2">
                {[3, 5, 10, 20, 50].map((turns) => (
                  <button
                    key={turns}
                    onClick={() => onMaxTurnsChange(turns)}
                    className={cn(
                      "px-2 py-1 text-xs rounded transition-colors",
                      maxTurns === turns
                        ? "bg-primary text-primary-foreground"
                        : "bg-surface-muted text-text hover:bg-surface-elev"
                    )}
                  >
                    {turns}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
