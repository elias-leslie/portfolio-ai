/**
 * Sitemap Table View - Flat, filterable, sortable table
 *
 * Columns: Health | Port | Path | Method | Errors | Warnings | Last Check | Actions
 */

"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  RefreshCw,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { checkEntryHealth, type SitemapEntry } from "@/lib/api/sitemap";

interface SitemapTableViewProps {
  entries: SitemapEntry[];
}

export function SitemapTableView({ entries }: SitemapTableViewProps) {
  const queryClient = useQueryClient();
  const [checkingId, setCheckingId] = useState<number | null>(null);

  const checkMutation = useMutation({
    mutationFn: (id: number) => {
      setCheckingId(id);
      return checkEntryHealth(id);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["sitemap"] });
      if (result.success) {
        toast.success(`Health: ${result.health_status}`);
      }
    },
    onSettled: () => setCheckingId(null),
  });

  const HealthIcon = ({ status }: { status: string }) => {
    switch (status) {
      case "healthy":
        return <CheckCircle2 className="h-4 w-4 text-gain" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-loss" />;
      default:
        return <HelpCircle className="h-4 w-4 text-neutral" />;
    }
  };

  const formatLastChecked = (dateStr: string | null): string => {
    if (!dateStr) return "Never";
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="max-h-[600px] overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-surface z-10">
            <TableRow>
              <TableHead className="w-12">Health</TableHead>
              <TableHead className="w-20">Port</TableHead>
              <TableHead>Path</TableHead>
              <TableHead className="w-20">Method</TableHead>
              <TableHead className="w-20 text-right">Errors</TableHead>
              <TableHead className="w-24 text-right">Warnings</TableHead>
              <TableHead className="w-28">Last Check</TableHead>
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => (
              <TableRow
                key={entry.id}
                className={cn(
                  entry.health_status === "error" && "bg-loss/5",
                  entry.health_status === "warning" && "bg-warning/5"
                )}
              >
                <TableCell>
                  <HealthIcon status={entry.health_status} />
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-xs font-mono">
                    :{entry.port}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <code className="text-sm truncate max-w-[300px]">{entry.path}</code>
                    {entry.title && (
                      <span className="text-xs text-text-secondary truncate max-w-[300px]">
                        {entry.title}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-xs font-mono",
                      entry.method === "GET" && "bg-green-500/10 text-green-600",
                      entry.method === "POST" && "bg-blue-500/10 text-blue-600",
                      entry.method === "PUT" && "bg-yellow-500/10 text-yellow-600",
                      entry.method === "DELETE" && "bg-red-500/10 text-red-600"
                    )}
                  >
                    {entry.method}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <span
                    className={cn(
                      "tabular-nums",
                      entry.console_errors > 0 && "text-loss font-semibold"
                    )}
                  >
                    {entry.console_errors}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <span
                    className={cn(
                      "tabular-nums",
                      entry.console_warnings > 0 && "text-warning"
                    )}
                  >
                    {entry.console_warnings}
                  </span>
                </TableCell>
                <TableCell className="text-xs text-text-secondary">
                  {formatLastChecked(entry.last_checked_at)}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => checkMutation.mutate(entry.id)}
                      disabled={checkingId === entry.id}
                      title="Check health"
                    >
                      {checkingId === entry.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title="Open in new tab"
                      onClick={() => {
                        const host = entry.port === 3000 ? "192.168.8.233" : "localhost";
                        window.open(`http://${host}:${entry.port}${entry.path}`, "_blank");
                      }}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
