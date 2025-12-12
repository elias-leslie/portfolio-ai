'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { AgentPanel } from '@/components/agents/AgentPanel';
import { cn } from '@/lib/utils';

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
      {/* Main content wrapper - shrinks when Agent Hub is open (FEAT-220) */}
      <div
        className={cn(
          "transition-[margin] duration-300 ease-in-out",
          isOpen && "mr-[500px]"
        )}
      >
        {children}
      </div>
      <AgentPanel
        open={isOpen}
        onOpenChange={setIsOpen}
        pageContext={pageContext}
      />
    </AgentContext.Provider>
  );
}
