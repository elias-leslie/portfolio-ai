/**
 * Sitemap Tree View - Hierarchical view by port -> path
 *
 * Structure:
 * ├── :3000 (Frontend)
 * │   ├── / (Dashboard) ✓
 * │   ├── /watchlist ⚠️ 2 warnings
 * │   └── /capabilities
 * │       └── ?tab=api ❌ 1 error
 * ├── :8000 (Backend)
 * │   ├── /api/watchlist/* ✓
 * │   └── /health ✓
 */

"use client";

import { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Globe,
  Server,
  FileCode,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  RefreshCw,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { checkEntryHealth, type SitemapEntry } from "@/lib/api/sitemap";

interface TreeNode {
  name: string;
  fullPath: string;
  port: number;
  entry: SitemapEntry | null;
  children: Map<string, TreeNode>;
}

interface SitemapTreeViewProps {
  entries: SitemapEntry[];
}

export function SitemapTreeView({ entries }: SitemapTreeViewProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["3000", "8000"]));
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

  // Build tree structure from flat entries
  const tree = useMemo(() => {
    const root = new Map<string, TreeNode>();

    // Group by port first
    const byPort = new Map<number, SitemapEntry[]>();
    for (const entry of entries) {
      const portEntries = byPort.get(entry.port) || [];
      portEntries.push(entry);
      byPort.set(entry.port, portEntries);
    }

    // Build tree for each port
    for (const [port, portEntries] of byPort) {
      const portLabel = port === 3000 ? "Frontend" : port === 8000 ? "Backend" : `Port ${port}`;
      const portNode: TreeNode = {
        name: `:${port} (${portLabel})`,
        fullPath: String(port),
        port,
        entry: null,
        children: new Map(),
      };

      for (const entry of portEntries) {
        // Split path into segments
        const segments = entry.path.split("/").filter(Boolean);

        if (segments.length === 0) {
          // Root path "/"
          portNode.children.set("/", {
            name: "/ (root)",
            fullPath: `${port}/`,
            port,
            entry,
            children: new Map(),
          });
          continue;
        }

        let current = portNode;

        for (let i = 0; i < segments.length; i++) {
          const segment = segments[i];
          const fullPath = `${port}/${segments.slice(0, i + 1).join("/")}`;

          if (!current.children.has(segment)) {
            current.children.set(segment, {
              name: segment,
              fullPath,
              port,
              entry: i === segments.length - 1 ? entry : null,
              children: new Map(),
            });
          } else if (i === segments.length - 1) {
            // Update entry for leaf node
            const existing = current.children.get(segment)!;
            existing.entry = entry;
          }

          current = current.children.get(segment)!;
        }
      }

      root.set(String(port), portNode);
    }

    return root;
  }, [entries]);

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  // Health icon component
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

  const renderNode = (node: TreeNode, depth: number = 0): React.ReactNode => {
    const hasChildren = node.children.size > 0;
    const isExpanded = expanded.has(node.fullPath);
    const entry = node.entry;
    const isPort = depth === 0;

    // Health status styling
    const healthColor = entry
      ? entry.health_status === "healthy"
        ? "text-gain"
        : entry.health_status === "warning"
          ? "text-warning"
          : entry.health_status === "error"
            ? "text-loss"
            : "text-neutral"
      : "";

    const borderColor = entry
      ? entry.health_status === "error"
        ? "border-l-2 border-l-loss"
        : entry.health_status === "warning"
          ? "border-l-2 border-l-warning"
          : ""
      : "";

    return (
      <div key={node.fullPath}>
        <div
          className={cn(
            "flex items-center gap-2 py-1.5 px-2 rounded",
            "hover:bg-surface-alt transition-colors group",
            borderColor
          )}
          style={{ paddingLeft: depth * 16 + 8 }}
        >
          {/* Expand/collapse icon */}
          <button
            className="w-4 h-4 flex items-center justify-center shrink-0"
            onClick={() => hasChildren && toggleExpand(node.fullPath)}
          >
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-text-secondary" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-text-secondary" />
              )
            ) : null}
          </button>

          {/* Icon based on type */}
          {isPort ? (
            node.port === 3000 ? (
              <Globe className="h-4 w-4 text-primary shrink-0" />
            ) : (
              <Server className="h-4 w-4 text-primary shrink-0" />
            )
          ) : entry?.entry_type === "frontend_page" ? (
            <Globe className="h-4 w-4 text-text-secondary shrink-0" />
          ) : (
            <FileCode className="h-4 w-4 text-text-secondary shrink-0" />
          )}

          {/* Name */}
          <span className={cn("flex-1 text-sm truncate", healthColor)}>
            {node.name}
            {entry?.title && entry.title !== node.name && (
              <span className="text-text-secondary text-xs ml-2">({entry.title})</span>
            )}
          </span>

          {/* Health indicator & counts */}
          {entry && (
            <>
              {entry.console_errors > 0 && (
                <span className="text-xs tabular-nums text-loss">
                  {entry.console_errors} {entry.console_errors === 1 ? "error" : "errors"}
                </span>
              )}
              {entry.console_warnings > 0 && entry.console_errors === 0 && (
                <span className="text-xs tabular-nums text-warning">
                  {entry.console_warnings} {entry.console_warnings === 1 ? "warning" : "warnings"}
                </span>
              )}
              <HealthIcon status={entry.health_status} />
            </>
          )}

          {/* Actions (visible on hover) */}
          {entry && (
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={(e) => {
                  e.stopPropagation();
                  checkMutation.mutate(entry.id);
                }}
                disabled={checkingId === entry.id}
                title="Check health"
              >
                {checkingId === entry.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <RefreshCw className="h-3 w-3" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={(e) => {
                  e.stopPropagation();
                  const host = entry.port === 3000 ? "192.168.8.233" : "localhost";
                  window.open(`http://${host}:${entry.port}${entry.path}`, "_blank");
                }}
                title="Open in new tab"
              >
                <ExternalLink className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>

        {/* Children */}
        {isExpanded && hasChildren && (
          <div>
            {Array.from(node.children.values())
              .sort((a, b) => {
                // Sort directories first, then alphabetically
                const aIsDir = a.children.size > 0;
                const bIsDir = b.children.size > 0;
                if (aIsDir && !bIsDir) return -1;
                if (!aIsDir && bIsDir) return 1;
                return a.name.localeCompare(b.name);
              })
              .map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="p-2 max-h-[600px] overflow-y-auto">
        {Array.from(tree.values())
          .sort((a, b) => a.port - b.port)
          .map((node) => renderNode(node, 0))}
      </div>
    </div>
  );
}
