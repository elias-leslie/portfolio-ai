/**
 * Files Tab - Explorer with Inline Details
 *
 * Unified file explorer with:
 * - Tree/table hybrid view (folders expand to show files)
 * - Sortable columns (Name, Files, LOC, Size)
 * - Color indicators for bloat (left border + colored text)
 * - Inline details expansion (click row to show details below)
 * - Chevron click expands children, row click expands details
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Folder,
  FolderOpen,
  File,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  Loader2,
  Home,
  ChevronRightIcon,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
  GitCommit as GitCommitIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// Types
interface FileSummary {
  total_files: number;
  total_directories: number;
  total_loc: number;
  bloat_warnings: number;
  bloat_critical: number;
  stale_files: number;
  orphan_files: number;
  fresh_files: number;
  untracked_files: number;
  last_scan: string | null;
  by_extension: Array<{ extension: string; count: number; loc: number }>;
}

interface FileNode {
  path: string;
  name: string;
  is_directory: boolean;
  extension: string | null;
  size_bytes: number;
  lines_of_code: number;
  file_count: number | null;
  total_loc: number | null;
  bloat_level: "warning" | "critical" | null;
  last_modified: string | null;
  subdir_count: number;
  direct_file_count: number;
  has_children: boolean;
  // Stale detection fields
  last_commit_days: number | null;
  reference_count: number | null;
  stale_status: "fresh" | "stale" | "orphan" | "untracked" | null;
}

type SortField = "name" | "loc" | "size" | "files" | "modified";
type SortDir = "asc" | "desc";

// API functions
async function fetchSummary(): Promise<FileSummary> {
  const res = await fetch("/api/files/summary");
  if (!res.ok) throw new Error("Failed to fetch file summary");
  return res.json();
}

async function fetchChildren(
  path: string,
  sort: SortField,
  dir: SortDir,
  foldersFirst: boolean
): Promise<FileNode[]> {
  const params = new URLSearchParams({
    path,
    sort,
    dir,
    folders_first: String(foldersFirst),
    include_files: "true",
  });
  const res = await fetch(`/api/files/children?${params}`);
  if (!res.ok) throw new Error("Failed to fetch children");
  return res.json();
}

async function triggerScan(): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/files/scan", { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger scan");
  return res.json();
}

interface GitCommit {
  hash: string;
  full_hash: string;
  author: string;
  date: string;
  subject: string;
  lines_added: number;
  lines_deleted: number;
}

interface GitHistory {
  commits: GitCommit[];
  total_commits: number;
  file_path: string;
  error?: string;
}

async function fetchGitHistory(path: string): Promise<GitHistory> {
  const res = await fetch(`/api/files/history?path=${encodeURIComponent(path)}&limit=5`);
  if (!res.ok) return { commits: [], total_commits: 0, file_path: path, error: "Failed to fetch" };
  return res.json();
}

interface FilesListResponse {
  items: FileNode[];
  total: number;
  limit: number;
  offset: number;
}

async function fetchAllFiles(
  sort: SortField,
  dir: SortDir
): Promise<FilesListResponse> {
  const sortMap: Record<SortField, string> = {
    name: "path",
    loc: "lines_of_code",
    size: "size_bytes",
    files: "path",
    modified: "last_modified",
  };
  const params = new URLSearchParams({
    is_directory: "false",
    sort: sortMap[sort],
    dir,
    limit: "500",
    offset: "0",
  });
  const res = await fetch(`/api/files?${params}`);
  if (!res.ok) throw new Error("Failed to fetch files");
  const data = await res.json();
  // Transform to match FileNode interface
  return {
    ...data,
    items: data.items.map((item: Record<string, unknown>) => ({
      ...item,
      name: (item.path as string).split("/").pop() || item.path,
      subdir_count: 0,
      direct_file_count: 0,
      has_children: false,
    })),
  };
}

// Helper functions
const formatNumber = (n: number) => n.toLocaleString();
const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleDateString();
};

// Inline Details Component
function InlineDetails({
  node,
  onClose,
  depth,
}: {
  node: FileNode;
  onClose: () => void;
  depth: number;
}) {
  const isDir = node.is_directory;
  const loc = isDir ? node.total_loc || 0 : node.lines_of_code;
  const bloatStatus = node.bloat_level;
  const staleStatus = node.stale_status;

  // Fetch git history for files only
  const { data: gitHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["files", "history", node.path],
    queryFn: () => fetchGitHistory(node.path),
    enabled: !isDir,
    staleTime: 60000, // Cache for 1 minute
  });

  return (
    <div
      className={cn(
        "mx-2 mb-1 rounded border bg-surface-alt",
        bloatStatus === "critical" && "border-loss/30 bg-loss/5",
        bloatStatus === "warning" && "border-warning/30 bg-warning/5",
        staleStatus === "orphan" && !bloatStatus && "border-loss/30 bg-loss/5",
        staleStatus === "stale" && !bloatStatus && "border-accent/30 bg-accent/5",
        staleStatus === "untracked" && !bloatStatus && "border-neutral/30 bg-neutral/5",
        !bloatStatus && (!staleStatus || staleStatus === "fresh") && "border-border"
      )}
      style={{ marginLeft: depth * 20 + 8 }}
    >
      <div className="p-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            {isDir ? (
              <Folder className="h-4 w-4 text-primary" />
            ) : (
              <File className="h-4 w-4 text-text-secondary" />
            )}
            <span className="font-medium text-sm">{node.name}</span>
            {bloatStatus && (
              <Badge
                variant={bloatStatus === "critical" ? "destructive" : "outline"}
                className={cn(
                  "text-xs",
                  bloatStatus === "warning" && "border-warning text-warning"
                )}
              >
                {bloatStatus}
              </Badge>
            )}
            {staleStatus && staleStatus !== "fresh" && (
              <Badge
                variant={staleStatus === "orphan" ? "destructive" : "outline"}
                className={cn(
                  "text-xs",
                  staleStatus === "stale" && "border-accent text-accent",
                  staleStatus === "untracked" && "border-neutral text-neutral"
                )}
              >
                {staleStatus}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 -mr-1 -mt-1"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>

        {/* Path */}
        <div className="text-xs text-text-secondary font-mono mb-3 break-all">
          {node.path}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div className="bg-background/50 rounded px-2 py-1.5">
            <div className="text-text-secondary">{isDir ? "Total LOC" : "Lines"}</div>
            <div className="font-semibold">{formatNumber(loc)}</div>
          </div>
          <div className="bg-background/50 rounded px-2 py-1.5">
            <div className="text-text-secondary">{isDir ? "Files" : "Size"}</div>
            <div className="font-semibold">
              {isDir ? node.file_count : formatBytes(node.size_bytes)}
            </div>
          </div>
          {isDir ? (
            <>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Subdirs</div>
                <div className="font-semibold">{node.subdir_count}</div>
              </div>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Direct</div>
                <div className="font-semibold">{node.direct_file_count}</div>
              </div>
            </>
          ) : (
            <>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Type</div>
                <div className="font-semibold">{node.extension || "-"}</div>
              </div>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Modified</div>
                <div className="font-semibold">{formatDate(node.last_modified)}</div>
              </div>
            </>
          )}
        </div>

        {/* Stale info row - only show for files with stale data */}
        {!isDir && (node.last_commit_days !== null || node.reference_count !== null) && (
          <div className="grid grid-cols-2 gap-2 text-xs mt-2">
            <div className="bg-background/50 rounded px-2 py-1.5">
              <div className="text-text-secondary">Last Commit</div>
              <div className={cn(
                "font-semibold",
                node.last_commit_days !== null && node.last_commit_days >= 90 && "text-accent"
              )}>
                {node.last_commit_days !== null ? `${node.last_commit_days} days ago` : "-"}
              </div>
            </div>
            <div className="bg-background/50 rounded px-2 py-1.5">
              <div className="text-text-secondary">References</div>
              <div className={cn(
                "font-semibold",
                node.reference_count === 0 && "text-accent"
              )}>
                {node.reference_count ?? "-"}
              </div>
            </div>
          </div>
        )}

        {/* Git History section - for files only */}
        {!isDir && (
          <div className="mt-3 pt-2 border-t border-border/50">
            <div className="flex items-center gap-2 mb-2">
              <GitCommitIcon className="h-3.5 w-3.5 text-text-secondary" />
              <span className="text-xs font-medium text-text-secondary">
                Recent Commits
                {gitHistory?.total_commits ? ` (${gitHistory.total_commits} total)` : ""}
              </span>
            </div>
            {historyLoading ? (
              <div className="flex items-center gap-2 text-xs text-text-secondary">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Loading history...</span>
              </div>
            ) : gitHistory?.error ? (
              <div className="text-xs text-text-secondary italic">{gitHistory.error}</div>
            ) : gitHistory?.commits.length === 0 ? (
              <div className="text-xs text-text-secondary italic">No git history found</div>
            ) : (
              <div className="space-y-1.5">
                {gitHistory?.commits.slice(0, 3).map((commit) => (
                  <div
                    key={commit.full_hash}
                    className="flex items-start gap-2 text-xs bg-background/50 rounded px-2 py-1.5"
                  >
                    <span className="font-mono text-primary/70 flex-shrink-0">{commit.hash}</span>
                    <div className="flex-1 min-w-0">
                      <div className="truncate" title={commit.subject}>{commit.subject}</div>
                      <div className="text-text-secondary">
                        {commit.author} · {new Date(commit.date).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Status message */}
        {bloatStatus && (
          <div className="mt-2 text-xs text-text-secondary">
            {isDir
              ? `Contains ${node.file_count} files (threshold: 50 for warning, 50+ for critical)`
              : `${formatNumber(loc)} lines exceeds ${node.extension === ".py" ? "500/1000" : "300/600"} LOC threshold`}
          </div>
        )}

        {/* Suggestion */}
        {bloatStatus === "critical" && !isDir && (
          <div className="mt-2 pt-2 border-t border-border/50 text-xs">
            <span className="text-text-secondary">Suggestion: </span>
            <span>Consider splitting this file into smaller modules</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Main Component
export function FilesTab() {
  const queryClient = useQueryClient();

  // State
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [foldersFirst, setFoldersFirst] = useState(true);
  const [filesOnly, setFilesOnly] = useState(false);
  const [filesOnlyAutoSet, setFilesOnlyAutoSet] = useState(false); // Track if auto-set by bloat filter
  const [searchFilter, setSearchFilter] = useState("");
  const [bloatFilter, setBloatFilter] = useState<"all" | "warning" | "critical">("all");
  const [staleFilter, setStaleFilter] = useState<"all" | "stale" | "orphan" | "untracked">("all");
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set()); // Children expanded
  const [detailsOpenPaths, setDetailsOpenPaths] = useState<Set<string>>(new Set()); // Details expanded
  const [loadedChildren, setLoadedChildren] = useState<Map<string, FileNode[]>>(
    new Map()
  );
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [currentPath, setCurrentPath] = useState<string[]>([]);

  // Queries
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["files", "summary"],
    queryFn: fetchSummary,
  });

  const rootPath = currentPath.join("/");
  const { data: rootChildren, isLoading: rootLoading } = useQuery({
    queryKey: ["files", "children", rootPath, sortField, sortDir, foldersFirst],
    queryFn: () => fetchChildren(rootPath, sortField, sortDir, foldersFirst),
    enabled: !filesOnly,
  });

  // Files-only mode query
  const { data: allFilesData, isLoading: allFilesLoading } = useQuery({
    queryKey: ["files", "all-files", sortField, sortDir],
    queryFn: () => fetchAllFiles(sortField, sortDir),
    enabled: filesOnly,
  });

  // Mutations
  const scanMutation = useMutation({
    mutationFn: triggerScan,
    onSuccess: () => {
      toast.success("File scan started");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["files"] });
        setLoadedChildren(new Map());
        setExpandedPaths(new Set());
        setDetailsOpenPaths(new Set());
      }, 5000);
    },
    onError: () => toast.error("Failed to start scan"),
  });

  // Handlers
  const loadChildren = useCallback(
    async (path: string) => {
      if (loadedChildren.has(path)) return;
      setLoadingPaths((prev) => new Set(prev).add(path));
      try {
        const children = await fetchChildren(path, sortField, sortDir, foldersFirst);
        setLoadedChildren((prev) => new Map(prev).set(path, children));
      } finally {
        setLoadingPaths((prev) => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
      }
    },
    [sortField, sortDir, foldersFirst, loadedChildren]
  );

  // Toggle children expansion (chevron click)
  const toggleChildren = useCallback(
    async (node: FileNode) => {
      if (!node.has_children) return;

      const isExpanded = expandedPaths.has(node.path);
      if (isExpanded) {
        setExpandedPaths((prev) => {
          const next = new Set(prev);
          next.delete(node.path);
          return next;
        });
      } else {
        if (!loadedChildren.has(node.path)) {
          await loadChildren(node.path);
        }
        setExpandedPaths((prev) => new Set(prev).add(node.path));
      }
    },
    [expandedPaths, loadedChildren, loadChildren]
  );

  // Toggle details expansion (row click)
  const toggleDetails = useCallback((path: string) => {
    setDetailsOpenPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir(field === "name" ? "asc" : "desc");
      }
      setLoadedChildren(new Map());
    },
    [sortField]
  );

  const navigateTo = useCallback((pathParts: string[]) => {
    setCurrentPath(pathParts);
    setExpandedPaths(new Set());
    setLoadedChildren(new Map());
    setDetailsOpenPaths(new Set());
  }, []);

  // Filter nodes
  const filteredChildren = useMemo(() => {
    const sourceData = filesOnly ? allFilesData?.items : rootChildren;
    if (!sourceData) return [];

    return sourceData.filter((node) => {
      // Search filter
      if (searchFilter) {
        const lower = searchFilter.toLowerCase();
        if (!node.name.toLowerCase().includes(lower) &&
            !node.path.toLowerCase().includes(lower)) {
          return false;
        }
      }

      // Bloat filter
      if (bloatFilter !== "all") {
        if (bloatFilter === "warning" && node.bloat_level !== "warning") return false;
        if (bloatFilter === "critical" && node.bloat_level !== "critical") return false;
      }

      // Stale filter
      if (staleFilter !== "all") {
        if (staleFilter === "stale" && node.stale_status !== "stale") return false;
        if (staleFilter === "orphan" && node.stale_status !== "orphan") return false;
        if (staleFilter === "untracked" && node.stale_status !== "untracked") return false;
      }

      return true;
    });
  }, [rootChildren, allFilesData, filesOnly, searchFilter, bloatFilter, staleFilter]);

  const isLoading = filesOnly ? allFilesLoading : rootLoading;

  // Sort icon
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-50" />;
    return sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );
  };

  // Render tree row
  const renderRow = (node: FileNode, depth: number = 0): React.ReactNode => {
    const isChildrenExpanded = expandedPaths.has(node.path);
    const isDetailsOpen = detailsOpenPaths.has(node.path);
    const isLoading = loadingPaths.has(node.path);
    const children = loadedChildren.get(node.path) || [];
    const loc = node.is_directory ? node.total_loc || 0 : node.lines_of_code;

    return (
      <div key={node.path}>
        {/* Main row */}
        <div
          className={cn(
            "flex items-center gap-1 py-1.5 px-2 cursor-pointer transition-colors group",
            "hover:bg-surface-alt",
            isDetailsOpen && "bg-primary/5",
            // Bloat indicator - left border (higher priority)
            node.bloat_level === "critical" && "border-l-2 border-l-loss",
            node.bloat_level === "warning" && "border-l-2 border-l-warning",
            // Stale indicator - left border (when no bloat)
            !node.bloat_level && node.stale_status === "orphan" && "border-l-2 border-l-loss",
            !node.bloat_level && node.stale_status === "stale" && "border-l-2 border-l-accent",
            !node.bloat_level && node.stale_status === "untracked" && "border-l-2 border-l-neutral",
            !node.bloat_level && (!node.stale_status || node.stale_status === "fresh") && "border-l-2 border-l-transparent"
          )}
          onClick={() => toggleDetails(node.path)}
        >
          {/* Indentation */}
          <div style={{ width: depth * 20 }} className="flex-shrink-0" />

          {/* Expand/collapse children (chevron) */}
          <div
            className={cn(
              "w-5 h-5 flex items-center justify-center flex-shrink-0 rounded",
              node.has_children && "hover:bg-surface-alt"
            )}
            onClick={(e) => {
              e.stopPropagation();
              if (node.has_children) toggleChildren(node);
            }}
          >
            {node.has_children ? (
              isLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-text-secondary" />
              ) : isChildrenExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-text-secondary group-hover:text-text-primary" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-text-secondary group-hover:text-text-primary" />
              )
            ) : null}
          </div>

          {/* Icon */}
          <div className="w-5 flex-shrink-0">
            {node.is_directory ? (
              isChildrenExpanded ? (
                <FolderOpen
                  className={cn(
                    "h-4 w-4",
                    node.bloat_level === "critical"
                      ? "text-loss"
                      : node.bloat_level === "warning"
                        ? "text-warning"
                        : "text-primary"
                  )}
                />
              ) : (
                <Folder
                  className={cn(
                    "h-4 w-4",
                    node.bloat_level === "critical"
                      ? "text-loss"
                      : node.bloat_level === "warning"
                        ? "text-warning"
                        : "text-text-secondary"
                  )}
                />
              )
            ) : (
              <File
                className={cn(
                  "h-4 w-4",
                  node.bloat_level === "critical"
                    ? "text-loss"
                    : node.bloat_level === "warning"
                      ? "text-warning"
                      : node.stale_status === "orphan"
                        ? "text-loss"
                        : node.stale_status === "stale"
                          ? "text-accent"
                          : node.stale_status === "untracked"
                            ? "text-neutral"
                            : "text-text-secondary"
                )}
              />
            )}
          </div>

          {/* Name */}
          <span
            className={cn(
              "flex-1 truncate text-sm",
              node.bloat_level === "critical" && "text-loss",
              node.bloat_level === "warning" && "text-warning",
              !node.bloat_level && node.stale_status === "orphan" && "text-loss",
              !node.bloat_level && node.stale_status === "stale" && "text-accent",
              !node.bloat_level && node.stale_status === "untracked" && "text-neutral",
              !node.bloat_level && (!node.stale_status || node.stale_status === "fresh") && node.is_directory && "text-primary"
            )}
            title={node.path}
          >
            {filesOnly ? node.path : node.name}
          </span>

          {/* Files column (folders only, hidden in files-only mode) */}
          {!filesOnly && (
            <span className="w-16 text-right text-xs tabular-nums text-primary/70">
              {node.is_directory ? node.file_count : ""}
            </span>
          )}

          {/* LOC column */}
          <span className="w-20 text-right text-xs tabular-nums font-mono text-accent/80">
            {formatNumber(loc)}
          </span>

          {/* Size column */}
          <span className="w-16 text-right text-xs tabular-nums text-gain/70">
            {node.is_directory
              ? (node.size_bytes ? formatBytes(node.size_bytes) : "")
              : formatBytes(node.size_bytes)}
          </span>

          {/* Modified column */}
          <span className="w-20 text-right text-xs tabular-nums text-neutral">
            {node.last_modified
              ? new Date(node.last_modified).toLocaleDateString("en-US", {
                  month: "numeric",
                  day: "numeric",
                  year: "2-digit",
                })
              : ""}
          </span>
        </div>

        {/* Inline details (if open) */}
        {isDetailsOpen && (
          <InlineDetails
            node={node}
            depth={depth}
            onClose={() => toggleDetails(node.path)}
          />
        )}

        {/* Children (if expanded) */}
        {isChildrenExpanded && children.length > 0 && (
          <div>{children.map((child) => renderRow(child, depth + 1))}</div>
        )}
      </div>
    );
  };

  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-text-secondary" />
      </div>
    );
  }

  // Extension colors for visual distinction
  const extColors: Record<string, string> = {
    ".md": "border-primary/50 text-primary",
    ".sql": "border-accent/50 text-accent",
    ".py": "border-gain/50 text-gain",
    ".ts": "border-primary/50 text-primary",
    ".tsx": "border-primary/50 text-primary",
    ".js": "border-warning/50 text-warning",
    ".json": "border-neutral/50 text-neutral",
    ".css": "border-accent/50 text-accent",
  };

  return (
    <div className="flex flex-col h-full">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mb-4">
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Files</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.total_files || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Directories</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.total_directories || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Total LOC</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.total_loc || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Warnings</div>
          <div className="text-xl font-semibold text-warning">
            {formatNumber(summary?.bloat_warnings || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Critical</div>
          <div className="text-xl font-semibold text-loss">
            {formatNumber(summary?.bloat_critical || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Stale</div>
          <div className="text-xl font-semibold text-accent">
            {formatNumber(summary?.stale_files || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Orphan</div>
          <div className="text-xl font-semibold text-loss">
            {formatNumber(summary?.orphan_files || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Untracked</div>
          <div className="text-xl font-semibold text-neutral">
            {formatNumber(summary?.untracked_files || 0)}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary" />
          <Input
            placeholder="Filter..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="pl-8 h-8"
          />
        </div>

        {/* Folders first toggle */}
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={foldersFirst}
            onCheckedChange={(checked) => {
              setFoldersFirst(!!checked);
              setLoadedChildren(new Map());
            }}
            disabled={filesOnly}
          />
          <span className={cn("text-text-secondary", filesOnly && "opacity-50")}>
            Folders first
          </span>
        </label>

        {/* Files only toggle */}
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={filesOnly}
            onCheckedChange={(checked) => {
              setFilesOnly(!!checked);
              setFilesOnlyAutoSet(false); // Manual toggle clears auto-set
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            }}
          />
          <span className="text-text-secondary">Files only</span>
        </label>

        {/* Bloat filter */}
        <Select
          value={bloatFilter}
          onValueChange={(v) => {
            const val = v as "all" | "warning" | "critical";
            setBloatFilter(val);
            if (val !== "all" && !filesOnly) {
              setFilesOnly(true);
              setFilesOnlyAutoSet(true);
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            } else if (val === "all" && filesOnlyAutoSet) {
              setFilesOnly(false);
              setFilesOnlyAutoSet(false);
            }
          }}
        >
          <SelectTrigger className="w-28 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>

        {/* Stale filter */}
        <Select
          value={staleFilter}
          onValueChange={(v) => {
            const val = v as "all" | "stale" | "orphan" | "untracked";
            setStaleFilter(val);
            if (val !== "all" && !filesOnly) {
              setFilesOnly(true);
              setFilesOnlyAutoSet(true);
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            } else if (val === "all" && filesOnlyAutoSet && bloatFilter === "all") {
              setFilesOnly(false);
              setFilesOnlyAutoSet(false);
            }
          }}
        >
          <SelectTrigger className="w-32 h-8">
            <SelectValue placeholder="Stale" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="stale">Stale</SelectItem>
            <SelectItem value="orphan">Orphan</SelectItem>
            <SelectItem value="untracked">Untracked</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {/* Scan button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
        >
          {scanMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          <span className="ml-1">Scan</span>
        </Button>
      </div>

      {/* Breadcrumb */}
      {currentPath.length > 0 && (
        <div className="flex items-center gap-1 text-sm mb-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2"
            onClick={() => navigateTo([])}
          >
            <Home className="h-3 w-3" />
          </Button>
          {currentPath.map((part, idx) => (
            <div key={idx} className="flex items-center gap-1">
              <ChevronRightIcon className="h-3 w-3 text-text-secondary" />
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={() => navigateTo(currentPath.slice(0, idx + 1))}
              >
                {part}
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Explorer - max height to ensure footer is visible */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col" style={{ maxHeight: "calc(100vh - 460px)" }}>
        {/* Column headers */}
        <div className="flex items-center gap-1 px-2 py-2 border-b border-border bg-surface-alt text-xs font-medium text-text-secondary">
          <div style={{ width: 20 }} className="flex-shrink-0" />
          <div className="w-5 flex-shrink-0" />
          <div className="w-5 flex-shrink-0" />
          <button
            className="flex-1 flex items-center gap-1 hover:text-text-primary text-left"
            onClick={() => handleSort("name")}
          >
            Name <SortIcon field="name" />
          </button>
          {!filesOnly && (
            <button
              className="w-16 flex items-center justify-end gap-1 hover:text-text-primary"
              onClick={() => handleSort("files")}
            >
              Files <SortIcon field="files" />
            </button>
          )}
          <button
            className="w-20 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("loc")}
          >
            LOC <SortIcon field="loc" />
          </button>
          <button
            className="w-16 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("size")}
          >
            Size <SortIcon field="size" />
          </button>
          <button
            className="w-20 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("modified")}
          >
            Modified <SortIcon field="modified" />
          </button>
        </div>

        {/* Tree content */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-text-secondary" />
            </div>
          ) : filteredChildren.length === 0 ? (
            <div className="text-center text-text-secondary py-8">
              {searchFilter
                ? "No matches found"
                : "No files found. Run a scan to populate data."}
            </div>
          ) : (
            <div className="py-1">
              {filteredChildren.map((node) => renderRow(node, 0))}
            </div>
          )}
        </div>

        {/* Footer */}
        {summary?.last_scan && (
          <div className="px-3 py-1.5 border-t border-border text-xs text-text-secondary">
            Last scan: {new Date(summary.last_scan).toLocaleString()}
          </div>
        )}
      </div>

      {/* Extension breakdown */}
      {summary?.by_extension && summary.by_extension.length > 0 && (
        <div className="mt-3 bg-surface border border-border rounded-lg p-3 flex-shrink-0">
          <h3 className="text-xs font-medium text-text-secondary mb-2">
            Lines of Code by Type
          </h3>
          <div className="flex flex-wrap gap-2">
            {summary.by_extension.slice(0, 8).map((ext) => (
              <Badge
                key={ext.extension}
                variant="outline"
                className={cn("text-xs", extColors[ext.extension] || "border-border")}
              >
                {ext.extension}: {formatNumber(ext.loc)} ({ext.count})
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
