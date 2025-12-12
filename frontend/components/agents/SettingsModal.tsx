'use client';

import { useState, useEffect } from 'react';
import { X, Save, RotateCcw } from 'lucide-react';
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

type SettingsTab = 'prompts' | 'cross-validation' | 'llm';

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  const [settings, setSettings] = useState<AgentSettings>(DEFAULT_SETTINGS);
  const [activeTab, setActiveTab] = useState<SettingsTab>('prompts');
  const [isDirty, setIsDirty] = useState(false);

  // Load settings on mount
  useEffect(() => {
    setSettings(loadSettings());
  }, []);

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
    { id: 'llm', label: 'LLM Settings' },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col bg-gray-900 text-gray-100 border-gray-700">
        <DialogHeader className="border-b border-gray-700 pb-4">
          <DialogTitle className="flex items-center justify-between">
            Agent Settings
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="h-8 w-8 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-700 -mx-6 px-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.id
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
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
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Dev Mode System Prompt
                </label>
                <textarea
                  value={settings.devSystemPrompt}
                  onChange={(e) => handleChange('devSystemPrompt', e.target.value)}
                  className="w-full h-40 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
                  placeholder="Instructions for code assistance..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Financial Advisor System Prompt
                </label>
                <textarea
                  value={settings.financialSystemPrompt}
                  onChange={(e) => handleChange('financialSystemPrompt', e.target.value)}
                  className="w-full h-40 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
                  placeholder="Instructions for financial analysis..."
                />
              </div>
            </>
          )}

          {activeTab === 'cross-validation' && (
            <>
              <p className="text-sm text-gray-400 mb-4">
                Cross-validation uses multiple LLMs to verify outputs before applying changes.
              </p>
              <div className="space-y-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.crossValidationEnabled}
                    onChange={(e) => handleChange('crossValidationEnabled', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm">Enable cross-validation</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.requireHumanReview}
                    onChange={(e) => handleChange('requireHumanReview', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm">Require human review before applying</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.fullAutoMode}
                    onChange={(e) => handleChange('fullAutoMode', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm">Full auto mode (apply validated changes automatically)</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifyOnDisagreement}
                    onChange={(e) => handleChange('notifyOnDisagreement', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm">Notify when agents disagree</span>
                </label>

                <div>
                  <label className="block text-sm text-gray-300 mb-2">
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
                  <p className="text-xs text-gray-500 mt-1">
                    Confidence threshold for auto-applying changes in full auto mode
                  </p>
                </div>
              </div>
            </>
          )}

          {activeTab === 'llm' && (
            <>
              <p className="text-sm text-gray-400 mb-4">
                Select your preferred LLM provider for Agent Hub conversations.
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => handleChange('llmProvider', 'claude')}
                  className={cn(
                    "w-full p-4 rounded border text-left transition-colors",
                    settings.llmProvider === 'claude'
                      ? "bg-blue-900/30 border-blue-600"
                      : "bg-gray-800 border-gray-700 hover:border-gray-600"
                  )}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={cn(
                      "w-2 h-2 rounded-full",
                      settings.llmProvider === 'claude' ? "bg-green-500" : "bg-gray-500"
                    )} />
                    <span className="text-sm font-medium">Claude</span>
                    {settings.llmProvider === 'claude' && (
                      <span className="text-xs bg-blue-600 px-2 py-0.5 rounded">Active</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">
                    Claude Agent SDK via Dev Companion service (port 9999)
                  </p>
                </button>
                <button
                  onClick={() => handleChange('llmProvider', 'gemini')}
                  className={cn(
                    "w-full p-4 rounded border text-left transition-colors",
                    settings.llmProvider === 'gemini'
                      ? "bg-green-900/30 border-green-600"
                      : "bg-gray-800 border-gray-700 hover:border-gray-600"
                  )}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={cn(
                      "w-2 h-2 rounded-full",
                      settings.llmProvider === 'gemini' ? "bg-green-500" : "bg-gray-500"
                    )} />
                    <span className="text-sm font-medium">Gemini</span>
                    {settings.llmProvider === 'gemini' && (
                      <span className="text-xs bg-green-600 px-2 py-0.5 rounded">Active</span>
                    )}
                    <span className="text-xs bg-green-600/50 px-2 py-0.5 rounded text-green-200">Free</span>
                  </div>
                  <p className="text-xs text-gray-500">
                    Free via local Gemini CLI with cached OAuth credentials
                  </p>
                </button>
              </div>
              {settings.llmProvider === 'gemini' && (
                <div className="mt-4 p-3 bg-blue-900/30 border border-blue-700 rounded text-sm text-blue-200">
                  <strong>Note:</strong> Gemini uses local CLI with cached OAuth credentials.
                  Free tier, no API costs.
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center border-t border-gray-700 pt-4 -mx-6 px-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-gray-400"
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
  const [settings, setSettings] = useState<AgentSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    setSettings(loadSettings());

    // Listen for storage changes
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
