'use client';

import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import { usePathname } from 'next/navigation';

// Channel name for cross-window communication
const AGENT_CHANNEL = 'portfolio-ai-agent-hub';

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
  const popupRef = useRef<Window | null>(null);
  const channelRef = useRef<BroadcastChannel | null>(null);

  // Initialize BroadcastChannel for cross-window communication
  useEffect(() => {
    channelRef.current = new BroadcastChannel(AGENT_CHANNEL);

    // Listen for messages from popup
    channelRef.current.onmessage = (event) => {
      if (event.data.type === 'POPUP_CLOSED') {
        setIsOpen(false);
        popupRef.current = null;
      } else if (event.data.type === 'POPUP_READY') {
        // Send initial context when popup is ready
        sendContext();
      }
    };

    return () => {
      channelRef.current?.close();
    };
  }, []);

  // Send page context to popup whenever it changes
  const sendContext = useCallback(() => {
    if (channelRef.current && isOpen) {
      channelRef.current.postMessage({
        type: 'PAGE_CONTEXT',
        payload: {
          path: pathname,
          data: pageData,
        },
      });
    }
  }, [pathname, pageData, isOpen]);

  // Send context updates when path or data changes
  useEffect(() => {
    sendContext();
  }, [sendContext]);

  const openPanel = useCallback(() => {
    // Check if popup already exists and is open
    if (popupRef.current && !popupRef.current.closed) {
      popupRef.current.focus();
      setIsOpen(true);
      return;
    }

    // Calculate popup position (right side of screen)
    const width = 520;
    const height = window.screen.availHeight;
    const left = window.screen.availWidth - width;
    const top = 0;

    // Open popup window
    popupRef.current = window.open(
      '/agent-hub',
      'AgentHub',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );

    if (popupRef.current) {
      setIsOpen(true);

      // Monitor popup close
      const checkClosed = setInterval(() => {
        if (popupRef.current?.closed) {
          setIsOpen(false);
          popupRef.current = null;
          clearInterval(checkClosed);
        }
      }, 500);
    }
  }, []);

  const closePanel = useCallback(() => {
    if (popupRef.current && !popupRef.current.closed) {
      popupRef.current.close();
    }
    popupRef.current = null;
    setIsOpen(false);
  }, []);

  const togglePanel = useCallback(() => {
    if (isOpen) {
      closePanel();
    } else {
      openPanel();
    }
  }, [isOpen, openPanel, closePanel]);

  return (
    <AgentContext.Provider value={{ isOpen, openPanel, closePanel, togglePanel, setPageData }}>
      {children}
    </AgentContext.Provider>
  );
}
