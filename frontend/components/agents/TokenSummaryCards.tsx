'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface TokenSummary {
  totalTokens: number;
  byProvider: Record<string, number>;
  byAgent: Record<string, number>;
  periodDays: number;
  periodStart: string;
  periodEnd: string;
}

function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`;
  }
  return tokens.toString();
}

interface TokenCardProps {
  days: number;
  data: TokenSummary | null;
  isLoading: boolean;
}

function TokenCard({ days, data, isLoading }: TokenCardProps) {
  return (
    <div className="bg-surface/50 rounded-lg p-3 border border-border flex-1">
      <div className="text-xs text-text-muted mb-1">{days} Days</div>
      {isLoading ? (
        <div className="animate-pulse">
          <div className="h-6 bg-surface-muted rounded w-16 mb-2" />
          <div className="h-3 bg-surface-muted rounded w-24" />
        </div>
      ) : data ? (
        <>
          <div className="text-xl font-bold text-text">
            {formatTokenCount(data.totalTokens)}
          </div>
          <div className="text-[10px] text-text-muted">tokens</div>
          <div className="mt-2 space-y-1">
            {Object.entries(data.byProvider).map(([provider, tokens]) => (
              <div key={provider} className="flex justify-between text-xs">
                <span className={cn(
                  "capitalize",
                  provider === 'gemini' ? "text-green-400" : "text-blue-400"
                )}>
                  {provider}
                </span>
                <span className="text-text-muted">{formatTokenCount(tokens)}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="text-text-muted text-sm">No data</div>
      )}
    </div>
  );
}

interface TokenSummaryCardsProps {
  serverUrl?: string;
}

export function TokenSummaryCards({ serverUrl = '' }: TokenSummaryCardsProps) {
  const [data7d, setData7d] = useState<TokenSummary | null>(null);
  const [data14d, setData14d] = useState<TokenSummary | null>(null);
  const [data30d, setData30d] = useState<TokenSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [res7, res14, res30] = await Promise.all([
          fetch(`${serverUrl}/api/agents/token-summary?days=7`),
          fetch(`${serverUrl}/api/agents/token-summary?days=14`),
          fetch(`${serverUrl}/api/agents/token-summary?days=30`),
        ]);

        if (res7.ok) setData7d(await res7.json());
        if (res14.ok) setData14d(await res14.json());
        if (res30.ok) setData30d(await res30.json());
      } catch (err) {
        console.error('Failed to fetch token summary:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [serverUrl]);

  return (
    <div className="flex gap-2 p-2 border-b border-border">
      <TokenCard days={7} data={data7d} isLoading={isLoading} />
      <TokenCard days={14} data={data14d} isLoading={isLoading} />
      <TokenCard days={30} data={data30d} isLoading={isLoading} />
    </div>
  );
}
