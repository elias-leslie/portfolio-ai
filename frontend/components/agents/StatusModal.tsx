'use client';

import { useState } from 'react';
import { Activity, Cpu, Clock, CheckCircle2, XCircle, ExternalLink } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useTelemetrySummary, useRunHistory } from '@/lib/hooks/useAgentTelemetry';
import { cn } from '@/lib/utils';
import Link from 'next/link';

interface StatusModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StatusModal({ open, onOpenChange }: StatusModalProps) {
  const [days, setDays] = useState(7);
  const { data: summary, isLoading: summaryLoading } = useTelemetrySummary(days);
  const { data: historyData, isLoading: historyLoading } = useRunHistory({ limit: 5 });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col bg-gray-900 text-gray-100 border-gray-700">
        <DialogHeader className="border-b border-gray-700 pb-4">
          <DialogTitle className="flex items-center justify-between">
            <span>Agent Status</span>
            <Link href="/agents" onClick={() => onOpenChange(false)}>
              <Button variant="ghost" size="sm" className="text-gray-400 text-xs">
                Full Dashboard <ExternalLink className="h-3 w-3 ml-1" />
              </Button>
            </Link>
          </DialogTitle>
        </DialogHeader>

        {/* Period selector */}
        <div className="flex gap-1 py-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 py-1 rounded-md text-xs transition-colors",
                days === d
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              )}
            >
              {d}d
            </button>
          ))}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3 py-2">
          <MetricCard
            title="Total Runs"
            value={summary?.total_runs ?? 0}
            icon={<Activity className="h-4 w-4 text-blue-400" />}
            loading={summaryLoading}
          />
          <MetricCard
            title="Success Rate"
            value={`${summary?.success_rate?.toFixed(1) ?? 0}%`}
            icon={<CheckCircle2 className="h-4 w-4 text-green-400" />}
            loading={summaryLoading}
            valueColor={
              (summary?.success_rate ?? 0) >= 90
                ? "text-green-400"
                : (summary?.success_rate ?? 0) >= 70
                ? "text-yellow-400"
                : "text-red-400"
            }
          />
          <MetricCard
            title="Total Tokens"
            value={formatNumber(summary?.total_tokens ?? 0)}
            icon={<Cpu className="h-4 w-4 text-purple-400" />}
            loading={summaryLoading}
          />
          <MetricCard
            title="Avg Duration"
            value={formatDuration(summary?.avg_duration_ms ?? 0)}
            icon={<Clock className="h-4 w-4 text-orange-400" />}
            loading={summaryLoading}
          />
        </div>

        {/* Provider breakdown */}
        {!summaryLoading && summary?.by_provider && summary.by_provider.length > 0 && (
          <div className="border-t border-gray-700 pt-3">
            <h4 className="text-xs text-gray-400 mb-2">By Provider</h4>
            <div className="space-y-2">
              {summary.by_provider.map((provider) => (
                <div
                  key={provider.provider}
                  className="flex items-center justify-between p-2 bg-gray-800/50 rounded text-xs"
                >
                  <Badge variant="outline" className="capitalize text-xs">
                    {provider.provider}
                  </Badge>
                  <div className="flex gap-4 text-gray-400">
                    <span>{provider.total_runs} runs</span>
                    <span className={
                      provider.success_rate >= 90
                        ? "text-green-400"
                        : provider.success_rate >= 70
                        ? "text-yellow-400"
                        : "text-red-400"
                    }>
                      {provider.success_rate.toFixed(0)}%
                    </span>
                    <span>{formatNumber(provider.total_tokens)} tok</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Runs */}
        <div className="flex-1 overflow-y-auto border-t border-gray-700 pt-3 mt-2">
          <h4 className="text-xs text-gray-400 mb-2">Recent Runs</h4>
          {historyLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 w-full animate-pulse bg-gray-800 rounded" />
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {historyData?.runs.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between p-2 bg-gray-800/30 rounded text-xs"
                >
                  <div className="flex items-center gap-2">
                    {run.status === 'completed' ? (
                      <CheckCircle2 className="h-3 w-3 text-green-400" />
                    ) : (
                      <XCircle className="h-3 w-3 text-red-400" />
                    )}
                    <span className="text-gray-300">{run.agent_type}</span>
                    <Badge variant="secondary" className="text-[10px] px-1 py-0">
                      {run.provider ?? 'unknown'}
                    </Badge>
                  </div>
                  <div className="flex gap-3 text-gray-500">
                    <span>{run.duration_ms ? formatDuration(run.duration_ms) : '-'}</span>
                    <span>{formatDate(run.started_at)}</span>
                  </div>
                </div>
              ))}
              {historyData?.runs.length === 0 && (
                <p className="text-gray-500 text-center py-4 text-xs">No runs yet</p>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Helper Components
function MetricCard({
  title,
  value,
  icon,
  loading,
  valueColor,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  loading?: boolean;
  valueColor?: string;
}) {
  if (loading) {
    return (
      <div className="p-3 bg-gray-800 rounded-lg">
        <div className="h-4 w-20 animate-pulse bg-gray-700 rounded mb-2" />
        <div className="h-6 w-16 animate-pulse bg-gray-700 rounded" />
      </div>
    );
  }

  return (
    <div className="p-3 bg-gray-800 rounded-lg">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-gray-400">{title}</span>
      </div>
      <div className={cn("text-lg font-semibold", valueColor || "text-gray-100")}>
        {value}
      </div>
    </div>
  );
}

// Helper functions
function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

function formatDuration(ms: number): string {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoString;
  }
}
