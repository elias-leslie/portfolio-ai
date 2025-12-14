'use client';

import { useEffect, useState, useRef } from 'react';
import { AgentHubContent } from '@/components/agents/AgentHubContent';

// Must match the channel name in AgentProvider
const AGENT_CHANNEL = 'portfolio-ai-agent-hub';

interface PageContext {
  path: string;
  data?: Record<string, unknown>;
}

export default function AgentHubPage() {
  // Default to /watchlist for standalone testing, will be overridden by BroadcastChannel
  const [pageContext, setPageContext] = useState<PageContext>({ path: '/watchlist' });
  const channelRef = useRef<BroadcastChannel | null>(null);

  useEffect(() => {
    // Initialize BroadcastChannel
    channelRef.current = new BroadcastChannel(AGENT_CHANNEL);

    // Listen for context updates from main window
    channelRef.current.onmessage = (event) => {
      if (event.data.type === 'PAGE_CONTEXT') {
        setPageContext(event.data.payload);
      }
    };

    // Notify main window that popup is ready
    channelRef.current.postMessage({ type: 'POPUP_READY' });

    // Notify main window when popup closes
    const handleBeforeUnload = () => {
      channelRef.current?.postMessage({ type: 'POPUP_CLOSED' });
    };
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      channelRef.current?.close();
    };
  }, []);

  return (
    <div className="h-screen w-full bg-gray-900 text-gray-100">
      <AgentHubContent pageContext={pageContext} />
    </div>
  );
}
