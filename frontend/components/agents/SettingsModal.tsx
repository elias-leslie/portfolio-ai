'use client';

import { useState, useEffect } from 'react';
import { Save, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export type LLMProvider = 'claude' | 'gemini';

interface AgentSettings {
  devSystemPrompt: string;
  financialSystemPrompt: string;
  crossValidationEnabled: boolean;
  requireHumanReview: boolean;
  fullAutoMode: boolean;
  notifyOnDisagreement: boolean;
  autoApplyThreshold: number;
  llmProvider: LLMProvider;
}

const DEFAULT_SETTINGS: AgentSettings = {
  devSystemPrompt: `You are a senior developer helping with the Portfolio AI codebase.
You have access to the full codebase and can help with:
- Debugging issues
- Writing new features
- Code reviews
- Architecture decisions
- Performance optimization

Always provide clear, actionable advice with code examples when relevant.`,
  financialSystemPrompt: `You are a financial advisor helping analyze market data and investment strategies.
You have access to:
- Watchlist data with signals and scores
- Portfolio positions and allocations
- Trading recommendations
- Market analysis tools

Provide data-driven insights based on the visible information. Be specific about symbols, prices, and metrics when answering questions.`,
  crossValidationEnabled: true,
  requireHumanReview: true,
  fullAutoMode: false,
  notifyOnDisagreement: true,
  autoApplyThreshold: 0.9,
  llmProvider: 'claude',
};

const STORAGE_KEY = 'agent-hub-settings';

function loadSettings(): AgentSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch {
    // Ignore
  }
  return DEFAULT_SETTINGS;
}

function saveSettings(settings: AgentSettings) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type SettingsTab = 'prompts' | 'cross-validation';

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  // Lazy initialization avoids setState-in-effect anti-pattern
  const [settings, setSettings] = useState<AgentSettings>(() => loadSettings());
  const [activeTab, setActiveTab] = useState<SettingsTab>('prompts');
  const [isDirty, setIsDirty] = useState(false);

  const handleChange = <K extends keyof AgentSettings>(key: K, value: AgentSettings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setIsDirty(true);
  };

  const handleSave = () => {
    saveSettings(settings);
    setIsDirty(false);
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    setIsDirty(true);
  };

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'prompts', label: 'Role Prompts' },
    { id: 'cross-validation', label: 'Cross-Validation' },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col bg-bg text-text border-border">
        <DialogHeader className="border-b border-border pb-4">
          <DialogTitle>Agent Settings</DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border -mx-6 px-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.id
                  ? "border-accent text-accent"
                  : "border-transparent text-text-muted hover:text-text"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {activeTab === 'prompts' && (
            <>
              <div>
                <label className="block text-sm font-medium text-text-muted mb-2">
                  Dev Mode System Prompt
                </label>
                <textarea
                  value={settings.devSystemPrompt}
                  onChange={(e) => handleChange('devSystemPrompt', e.target.value)}
                  className="w-full h-40 bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                  placeholder="Instructions for code assistance..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-muted mb-2">
                  Financial Advisor System Prompt
                </label>
                <textarea
                  value={settings.financialSystemPrompt}
                  onChange={(e) => handleChange('financialSystemPrompt', e.target.value)}
                  className="w-full h-40 bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                  placeholder="Instructions for financial analysis..."
                />
              </div>
            </>
          )}

          {activeTab === 'cross-validation' && (
            <>
              <p className="text-sm text-text-muted mb-4">
                Cross-validation uses multiple LLMs to verify outputs before applying changes.
              </p>
              <div className="space-y-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.crossValidationEnabled}
                    onChange={(e) => handleChange('crossValidationEnabled', e.target.checked)}
                    className="w-4 h-4 rounded border-border bg-surface text-accent focus:ring-accent"
                  />
                  <span className="text-sm">Enable cross-validation</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.requireHumanReview}
                    onChange={(e) => handleChange('requireHumanReview', e.target.checked)}
                    className="w-4 h-4 rounded border-border bg-surface text-accent focus:ring-accent"
                  />
                  <span className="text-sm">Require human review before applying</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.fullAutoMode}
                    onChange={(e) => handleChange('fullAutoMode', e.target.checked)}
                    className="w-4 h-4 rounded border-border bg-surface text-accent focus:ring-accent"
                  />
                  <span className="text-sm">Full auto mode (apply validated changes automatically)</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifyOnDisagreement}
                    onChange={(e) => handleChange('notifyOnDisagreement', e.target.checked)}
                    className="w-4 h-4 rounded border-border bg-surface text-accent focus:ring-accent"
                  />
                  <span className="text-sm">Notify when agents disagree</span>
                </label>

                <div>
                  <label className="block text-sm text-text-muted mb-2">
                    Auto-apply threshold: {settings.autoApplyThreshold}
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="1.0"
                    step="0.05"
                    value={settings.autoApplyThreshold}
                    onChange={(e) => handleChange('autoApplyThreshold', parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <p className="text-xs text-text-muted mt-1">
                    Confidence threshold for auto-applying changes in full auto mode
                  </p>
                </div>
              </div>
            </>
          )}

        </div>

        {/* Footer */}
        <div className="flex justify-between items-center border-t border-border pt-4 -mx-6 px-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-text-muted"
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to Defaults
          </Button>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!isDirty}
            >
              <Save className="h-4 w-4 mr-2" />
              Save
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Hook to access settings
export function useAgentSettings() {
  // Lazy initialization avoids setState-in-effect anti-pattern
  const [settings, setSettings] = useState<AgentSettings>(() => loadSettings());

  // Listen for cross-tab storage changes only
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        try {
          setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(e.newValue) });
        } catch {
          // Ignore
        }
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return settings;
}
