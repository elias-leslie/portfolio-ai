import { useState, useCallback } from 'react';

export interface UseAgentPanelUIReturn {
  // Panel visibility states
  showSessions: boolean;
  showSettings: boolean;
  showStatus: boolean;
  showTokenSummary: boolean;
  showEvidenceCapture: boolean;

  // Setters
  setShowSessions: (show: boolean) => void;
  setShowSettings: (show: boolean) => void;
  setShowStatus: (show: boolean) => void;
  setShowTokenSummary: (show: boolean) => void;
  setShowEvidenceCapture: (show: boolean) => void;

  // Convenience toggles
  toggleSessions: () => void;
  toggleTokenSummary: () => void;
  closeAllPanels: () => void;
}

/**
 * Hook to manage AgentPanel UI visibility states.
 * Centralizes panel toggle logic and provides convenience methods.
 */
export function useAgentPanelUI(): UseAgentPanelUIReturn {
  const [showSessions, setShowSessions] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showStatus, setShowStatus] = useState(false);
  const [showTokenSummary, setShowTokenSummary] = useState(false);
  const [showEvidenceCapture, setShowEvidenceCapture] = useState(false);

  // Toggle sessions panel and close token summary (mutual exclusion)
  const toggleSessions = useCallback(() => {
    setShowSessions(prev => !prev);
    setShowTokenSummary(false);
  }, []);

  // Toggle token summary
  const toggleTokenSummary = useCallback(() => {
    setShowTokenSummary(prev => !prev);
  }, []);

  // Close all panels at once
  const closeAllPanels = useCallback(() => {
    setShowSessions(false);
    setShowSettings(false);
    setShowStatus(false);
    setShowTokenSummary(false);
    setShowEvidenceCapture(false);
  }, []);

  return {
    showSessions,
    showSettings,
    showStatus,
    showTokenSummary,
    showEvidenceCapture,
    setShowSessions,
    setShowSettings,
    setShowStatus,
    setShowTokenSummary,
    setShowEvidenceCapture,
    toggleSessions,
    toggleTokenSummary,
    closeAllPanels,
  };
}
