'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { AgentPanel, AgentPanelTrigger } from '@/components/agents/AgentPanel';

interface PageContext {
  path: string;
  data?: Record<string, unknown>;
}

interface AgentContextValue {
  isOpen: boolean;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
  setPageData: (data: Record<string, unknown>) => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

export function useAgent() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgent must be used within AgentProvider');
  }
  return context;
}

export function AgentProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [pageData, setPageData] = useState<Record<string, unknown>>({});
  const pathname = usePathname();

  const openPanel = useCallback(() => setIsOpen(true), []);
  const closePanel = useCallback(() => setIsOpen(false), []);
  const togglePanel = useCallback(() => setIsOpen(prev => !prev), []);

  const pageContext: PageContext = {
    path: pathname,
    data: pageData,
  };

  return (
    <AgentContext.Provider value={{ isOpen, openPanel, closePanel, togglePanel, setPageData }}>
      {children}
      <AgentPanel
        open={isOpen}
        onOpenChange={setIsOpen}
        pageContext={pageContext}
      />
      {!isOpen && <AgentPanelTrigger onClick={openPanel} />}
    </AgentContext.Provider>
  );
}
