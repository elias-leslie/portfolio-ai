'use client';

import { Diamond, Star, ChevronDown } from 'lucide-react';
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

export function AgentSelector({
  value,
  onChange,
  disabled = false,
  roundtableOrder = 'claude-first',
  onRoundtableOrderChange,
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
    <div className="relative" ref={menuRef}>
      <div className="flex items-center gap-1">
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

        {/* Order selector dropdown trigger - only shown when "both" is selected */}
        {value === 'both' && onRoundtableOrderChange && (
          <button
            onClick={() => setShowOrderMenu(!showOrderMenu)}
            className="h-6 w-6 flex items-center justify-center rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 transition-colors"
            title="Change response order"
          >
            <ChevronDown className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Order selection dropdown */}
      {showOrderMenu && value === 'both' && onRoundtableOrderChange && (
        <div className="absolute top-full left-0 mt-1 w-48 bg-gray-800 border border-gray-700 rounded-md shadow-lg z-50">
          <div className="py-1">
            <button
              onClick={() => {
                onRoundtableOrderChange('claude-first');
                setShowOrderMenu(false);
              }}
              className={cn(
                "w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-gray-700 transition-colors",
                roundtableOrder === 'claude-first' ? "text-blue-400" : "text-gray-300"
              )}
            >
              <Diamond className="h-3 w-3 text-blue-400" />
              Claude first
              {roundtableOrder === 'claude-first' && <span className="ml-auto text-xs">✓</span>}
            </button>
            <button
              onClick={() => {
                onRoundtableOrderChange('gemini-first');
                setShowOrderMenu(false);
              }}
              className={cn(
                "w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-gray-700 transition-colors",
                roundtableOrder === 'gemini-first' ? "text-green-400" : "text-gray-300"
              )}
            >
              <Star className="h-3 w-3 text-green-400" />
              Gemini first
              {roundtableOrder === 'gemini-first' && <span className="ml-auto text-xs">✓</span>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
